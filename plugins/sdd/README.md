# sdd — Spec-Driven Development para Claude Code

Plugin que implementa el ciclo **constitution → specify → clarify → plan → tasks
→ implement**, con una compuerta que impide escribir código sin especificación.

## Instalación

Durante el desarrollo, cárgalo sin instalar:

```bash
claude --plugin-dir /ruta/a/sdd
```

Tras editar cualquier cosa que no sea un `SKILL.md`, ejecuta `/reload-plugins`.
Los cambios en `SKILL.md` se recogen al instante; los de `hooks/`, `.mcp.json` y
`agents/` no.

Cuando estés conforme, para tenerlo siempre disponible sin la bandera:

```bash
cp -r sdd ~/.claude/skills/sdd
```

Se cargará en la siguiente sesión como `sdd@skills-dir`, sin marketplace ni paso
de instalación.

**Requisitos:** Python 3.8+ en el `PATH` como `python3`. Git es opcional. Sin
dependencias externas: el plugin no instala nada.

## Uso

```
/sdd:constitution              # una vez por repositorio
/sdd:specify <qué construir>   # crea specs/NNN-slug/spec.md
/sdd:clarify                   # cierra las preguntas abiertas
/sdd:plan                      # decisiones de arquitectura
/sdd:tasks                     # descomposición en tareas atómicas
/sdd:implement [T003]          # ejecuta una tarea y se detiene
/sdd:trace                     # ¿cubre la implementación lo que dice la spec?
/sdd:status                    # dónde estás y qué falta
```

Artefactos generados:

```
specs/
├── constitution.md
└── 001-autenticacion-oauth-google/
    ├── spec.md      qué y por qué
    ├── plan.md      cómo
    └── tasks.md     en qué unidades
.sdd/
├── current          slug de la feature activa
└── config.json      opcional
```

## La compuerta

Un hook `PreToolUse` sobre `Write|Edit|NotebookEdit` bloquea la escritura de
código mientras falten artefactos. Se comporta así:

| Situación                            | Resultado                          |
| ------------------------------------ | ---------------------------------- |
| El repo no tiene `specs/`            | No opina. El plugin es inerte      |
| La ruta está en la lista de exentos  | Permite                            |
| No hay feature activa                | Bloquea → `/sdd:specify`           |
| Falta `spec.md` / `plan.md` / `tasks.md` | Bloquea → la skill que lo produce |
| Todos los artefactos presentes       | Permite                            |

**Escapes**, en orden de contundencia:

```bash
SDD_BYPASS=1 claude              # desactiva la compuerta en esa sesión
echo '{"gate":"off"}' > .sdd/config.json   # la desactiva en el repo
claude plugin disable sdd@skills-dir       # desactiva el plugin entero
```

`"disableAllHooks": true` en tu `settings.json` desactiva todos los hooks de
Claude Code, no solo los de este plugin. Es el martillo grande.

Un guardrail sin escape se desinstala a la semana. Estos son deliberados.

## Trazabilidad

`sdd.py trace` construye la matriz requisito → tarea → prueba y señala lo que
falta. Es lo que convierte los `R001` en algo con consecuencias.

```bash
sdd.py trace           # reporte legible, siempre sale con 0
sdd.py trace --json    # contrato estable para CI (schema sdd.trace/v1)
sdd.py trace --check   # sale con 1 si hay algún error
```

La evidencia de prueba se detecta por el ID del requisito dentro del archivo de
test, en el nombre de la función o en un comentario:

```python
def test_R001_rechaza_token_expirado():
    ...
```

Un requisito que no aparezca en ningún test cuenta como no probado, aunque
tenga cobertura de código. Es deliberado: la cobertura mide líneas ejecutadas,
no requisitos satisfechos.

### Hallazgos

Los `E-` bloquean `--check`; los `W-` solo informan.

| Código | Significado |
| ------ | ----------- |
| `E-REQ-NO-TASK` | Requisito MUST sin tarea |
| `E-REQ-NO-TEST` | Requisito MUST sin prueba que lo referencie |
| `E-REQ-NO-CRITERIA` | Requisito MUST sin criterios de aceptación |
| `E-REQ-DUPLICATE` | ID de requisito duplicado |
| `E-TASK-UNKNOWN-REQ` | Tarea que referencia un requisito inexistente |
| `E-TASK-UNKNOWN-DEP` | Tarea que depende de una tarea inexistente |
| `E-TASK-DEP-CYCLE` | Ciclo de dependencias |
| `E-DONE-NO-TEST` | Tarea cerrada cuyos requisitos no tienen prueba |
| `W-REQ-NO-TASK` | Requisito SHOULD/COULD sin tarea |
| `W-REQ-NO-EARS` | Requisito que no usa la forma EARS |
| `W-REQ-VAGUE` | Adjetivo sin umbral verificable |
| `W-TASK-NO-REQ` | Tarea que no sirve a ningún requisito |
| `W-DONE-OPEN-DEPS` | Tarea cerrada con dependencias abiertas |
| `W-SPEC-OPEN-QUESTIONS` | Preguntas abiertas sin resolver |
| `W-SPEC-NO-UNWANTED` | Ningún requisito `SI... ENTONCES` |

Los códigos son contrato público: si construyes algo encima, no cambiarán de
nombre sin subir la versión del schema.

### En CI (del repo de producto)

`examples/github-actions-sdd.yml` es un workflow listo para copiar a
`.github/workflows/`. Corre exactamente la misma lógica que en local, así que
no hay dos definiciones de «esto está completo» que puedan divergir.

Para adoptarlo en un repo con specs existentes, empieza con
`continue-on-error: true` unas semanas y mira el resumen antes de hacerlo
bloqueante.

## Control de calidad

Un hook `PostToolUse` corre formateador y linter sobre **el archivo editado**,
no sobre el repo entero. Detecta la herramienta disponible y no hace nada si no
encuentra ninguna, así que funciona sin configurar:

| Extensión | Herramientas |
| --------- | ------------ |
| `.py` | ruff, o black + flake8 |
| `.ts` `.tsx` `.js` `.jsx` | prettier, eslint |
| `.tf` `.tfvars` | terraform fmt |
| `.go` | gofmt |
| `.rs` | rustfmt |
| `.rb` | rubocop |
| `.sh` | shellcheck |

Prefiere el binario local (`node_modules/.bin`) al global. Los formateadores
que reescriben el archivo no cuentan como fallo; solo los errores de linter
llegan a Claude, vía exit 2, con instrucción explícita de corregirlos sin
preguntar.

Para desactivarlo: `SDD_NO_QUALITY=1`, o `{"quality": {"enabled": false}}`.

## Configuración (`.sdd/config.json`)

```json
{
  "enabled": true,
  "gate": "tasks",
  "exempt": ["specs/**", ".sdd/**", ".claude/**", ".git/**", "*.md", ".gitignore"],
  "quality": {
    "enabled": true,
    "timeout": 30,
    "commands": {
      ".py": ["ruff check --fix {file}", "mypy {file}"]
    }
  },
  "tests": {
    "globs": ["e2e/**/*.py"]
  }
}
```

- **`quality.commands`**: si defines comandos para una extensión, reemplazan la
  detección automática. `{file}` se sustituye por la ruta.
- **`tests.globs`**: archivos adicionales que cuentan como pruebas, más allá de
  las convenciones habituales (`test_*.py`, `*.spec.ts`, directorios `tests/`…).

- **`gate`**: hasta qué fase exige antes de permitir código.
  `"spec"` es permisivo, `"tasks"` es el ciclo completo, `"off"` desactiva.
  Empieza en `"spec"` si el flujo te resulta pesado y endurécelo después.
- **`exempt`**: rutas que la compuerta nunca bloquea. Los patrones que terminan
  en `/**` son prefijos; el resto son globs contra la ruta relativa y contra el
  nombre del archivo.

## Cómo se resuelve la feature activa

Por orden de prioridad:

1. El contenido de `.sdd/current` (lo escribe `/sdd:specify`).
2. El nombre de la rama git, si coincide con un directorio bajo `specs/`.
3. Si solo existe una feature, esa.

Para trabajar en varias features en paralelo, usa una rama por feature con el
mismo nombre que su directorio.

## Decisiones de diseño

**Todo lo determinista está en `scripts/sdd.py`, no en los prompts.** La
numeración de features, la resolución de la feature activa y la evaluación de la
compuerta son código. Pedirle al modelo que «recuerde» numerar correctamente es
donde estos flujos se degradan.

**La compuerta nunca devuelve `permissionDecision: "allow"`.** Devolver `allow`
saltaría la petición de permiso normal de Claude Code, convirtiendo un guardrail
en una escalada de privilegios silenciosa. Cuando la compuerta está conforme,
el hook no dice nada y el flujo de permisos habitual sigue su curso.

**Exit 0 con JSON, nunca exit 2.** Claude Code solo procesa el JSON del hook si
el proceso sale con código 0; con exit 2 ignora el JSON y usa stderr. Combinar
ambos es la causa habitual de que un bloqueo se ignore. El hook de calidad hace
lo contrario a propósito: `PostToolUse` no puede bloquear nada, así que usa
exit 2 justamente porque su único efecto ahí es enseñarle stderr a Claude.

**Los hooks usan forma exec, no forma shell.** `command` es el ejecutable y
`args` el vector de argumentos, sin shell de por medio. Es lo recomendado
cuando un hook referencia `${CLAUDE_PLUGIN_ROOT}`: cada ruta llega como un solo
argumento sin necesidad de comillas, y funciona igual en Windows.

**El texto de `SessionStart` es declarativo.** Un hook que inyecta contexto
redactado como órdenes al sistema activa las defensas anti prompt-injection de
Claude, que entonces te muestra el texto en vez de usarlo. Por eso dice «la
compuerta exige tasks.md» y no «ejecuta /sdd:tasks».

**Cualquier fallo del script permite en vez de bloquear.** Config corrupta,
stdin malformado, ruta rara o excepción no prevista: el hook deja pasar. Un
guardrail que revienta no debe dejarte sin poder trabajar.

**Las skills de fase llevan `disable-model-invocation: true`.** Solo se disparan
cuando tú escribes el comando; el modelo no decide entrar en la fase de plan por
su cuenta. La excepción es `spec-authoring`, que sí es invocable por el modelo
para que las reglas de redacción EARS se apliquen solas al editar cualquier
archivo bajo `specs/`.

## Verificación

```bash
claude plugin validate /ruta/a/sdd --strict
claude plugin details sdd
```

El segundo comando muestra el coste en tokens: *always-on* (lo que el plugin
añade a cada sesión solo por existir, unos 8 descripciones de skill) frente a
*on-invoke*. Si el coste always-on te molesta, la vía es fusionar skills, no
acortar sus descripciones: la descripción es el mecanismo de activación.

## Estándares y hoja de ruta

`docs/standards-roadmap.md` documenta qué estándares puede llegar a hacer
cumplir el plugin —Clean Architecture, TDD, contratos de API, gestión de
dependencias, secretos, cumplimiento— con el criterio de entrada y el coste de
cada escalón. Está pensado como documento vivo: la tabla de fases es el estado
real, y se sube un escalón cuando el producto lo justifica.

Dos ideas de ahí que ya condicionan el diseño actual:

- **Tres niveles de estándar.** Mecánico (lo comprueba un script), revisable
  (requiere leer el diff), de juicio (lo decide una persona). Un estándar
  mecánico escrito solo en prosa se cumple más o menos. `/sdd:constitution`
  clasifica cada regla por nivel, y la plantilla tiene una sección
  «Comprobación» donde queda anotado.
- **Ratchet.** No se codifica un estándar que el repositorio hoy no cumple. Se
  registra el valor actual como suelo y solo se permite que suba. Un umbral
  inalcanzable acaba desactivado, y eso desacredita a todas las demás
  comprobaciones.

## Qué falta a propósito

El detalle y el orden están en `docs/standards-roadmap.md`. En resumen:

- **Agentes** (`agents/`): `spec-reviewer` de solo lectura, e
  `implementation-reviewer` que audite el diff contra la spec.
- **`.lsp.json`**: diagnósticos en tiempo real del servidor de lenguaje, sin
  coste en tokens de contexto.
- **Detección de deriva**: un hook de tipo `agent` sobre el evento `FileChanged`
  vigilando `spec.md`, más `/sdd:amend` para cambios de requisito
  post-implementación. Ojo al montarlo: `FileChanged` solo se dispara sobre
  rutas registradas, y quien las registra es un hook `SessionStart` que
  devuelve `watchPaths`. Un `FileChanged` suelto no vigila nada.
- **Workflow** (`workflows/`) para la fase de implementación, con fan-out de un
  agente por tarea y revisión adversarial. Nota: los workflows no admiten
  entrada del usuario a mitad de ejecución, así que cada fase que requiera tu
  aprobación debe seguir siendo su propia skill.
