# sdd — Spec-Driven Development para Claude Code

Plugin que implementa el ciclo **constitution → specify → clarify → plan → tasks
→ implement**, con una compuerta que impide escribir código sin una
especificación completa y aprobada por el usuario.

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
/sdd:specify B03               # o desde una candidata del backlog de discovery
/sdd:clarify                   # cierra las preguntas abiertas
/sdd:approve                   # tú apruebas la siguiente fase pendiente (aquí, spec)
/sdd:plan                      # decisiones de arquitectura y diagramas de la feature
/sdd:approve                   # plan
/sdd:tasks                     # descomposición en tareas atómicas
/sdd:analyze                   # coherencia entre artefactos, solo lectura
/sdd:approve                   # tasks; a partir de aquí la compuerta deja escribir código
/sdd:implement [T003]          # ejecuta una tarea y se detiene
/sdd:amend <cambio>            # cambia requisitos ya aprobados sin romper IDs
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

La cabecera de `spec.md` lleva la fila `| Tipo | funcionalidad |`. Si la
feature solo corrige comportamiento existente, el usuario la cambia a
`corrección` (`/sdd:specify` lo pregunta si no está claro). `sdd` no comprueba
el valor: lo lee el plugin `release` para proponer el número de versión, y da
error si no es ninguno de los dos.

## Desde discovery

Si el proyecto pasó por el plugin `discovery`, cada candidata del backlog
aprobado se convierte en una feature con `/sdd:specify B03`. El script
(`sdd.py new B03`) crea la spec con lo que la candidata ya dice:

- **Problema:** el de la candidata.
- **Contexto:** los objetivos del brief que persigue y sus secciones de origen.
- **Alcance:** en Dentro, el resultado observable y el alcance; en Fuera, lo
  que la candidata excluye.
- **Cabecera:** `| Origen | B03 · G2 · D2§4.2 |`, con la candidata, los
  objetivos y las secciones, en ese orden. Un grupo vacío se escribe `—`.

Requisitos y criterios los sigue redactando `/sdd:specify`, que recibe del
script el contexto que debe leer: el brief, los objetivos y el archivo de cada
sección de origen.

No se crea nada, con salida 1 y el motivo, si:

- `product/brief.md` o `product/backlog.md` faltan (los crea
  `/discovery:decompose`), no están aprobados o cambiaron después de
  aprobarse (los aprueba el usuario con `/discovery:approve`);
- la candidata no existe o está descartada;
- la candidata ya tiene feature, es decir, alguna spec la lleva como primer
  elemento de su fila `Origen`.

Se crea, pero con un aviso, si la candidata depende de otra que aún no tiene
feature (las descartadas no cuentan), o si una sección de origen está en un documento que ya no existe en
`product/sources/`.

Sin `product/backlog.md`, o con una descripción que no es solo un ID de
candidata, `/sdd:specify` funciona exactamente igual que siempre. El backlog
aprobado no se modifica nunca: qué candidatas tienen feature se lee de las
filas `Origen`.

**Contrato con `discovery`.** `sdd` no importa código de `discovery`: lee sus
archivos con `scripts/sdd_product.py`, que copia de `discovery.py` el formato
de candidatas y objetivos y el algoritmo de huella de la aprobación. Si
`discovery` cambia ese formato o esa huella, la prueba de contrato del selftest
de `sdd`, que aprueba un producto con el `discovery.py` real, falla en CI.

## Diagramas del plan

`plan.md` tiene una sección `## Diagramas` en Mermaid, que GitHub y los editores
muestran dibujada, con tres apartados: **Secuencia** (`sequenceDiagram`, el flujo
principal), **Modelo de datos** (`erDiagram`) y **Clases** (`classDiagram`).
Cada uno se rellena o dice «No aplica.»; mientras quede el hueco de la
plantilla, el plan no se aprueba. Un plan sin la sección (de antes de que
existiera) solo da el aviso `W-PLAN-NO-DIAGRAMS`.

- **Esqueleto.** Con `architecture/`, `sdd.py diagram` escribe en el apartado de
  secuencia un `participant` por componente que aloja la candidata
  (`participant C1 as Ventas`) y una línea `%%` que pide completar el flujo y
  citar la decisión de cada llamada. Sin candidata no pone participantes y
  lista los componentes entre los que elegir. No toca un apartado que ya tiene
  contenido; a un plan sin la sección se la añade al final; si el plan estaba
  aprobado, lo dice, porque hay que volver a aprobarlo. Sale con 0 sin
  `architecture/` (sin escribir nada) y con 1 sin `plan.md`, con la
  arquitectura sin aprobar o con la candidata sin componente.
- **Convenciones.** Un componente es un participante con su ID de
  `components.md`. Una llamada es una flecha continua (`->>`, `->`, `-x`, `-)`)
  y hace al que llama depender del llamado; una respuesta es discontinua
  (`-->>`, `-->`, `--x`, `--)`) y no cuenta, y `A<<->>B` cuenta en los dos
  sentidos. Cada llamada entre componentes cita su decisión:
  `C2->>C1: totales (ADR-0001)` o `(D2)`.
- **Comprobación.** Con `architecture/`, `trace` lee los participantes y los
  mensajes de los `sequenceDiagram` (`Note`, `loop`, `alt`, `activate` y los
  comentarios `%%` se ignoran) y da error si nombran un componente que no
  existe (`E-PLAN-DIAGRAM-UNKNOWN`) o si una llamada va al revés de un estándar
  `dependencia` o coincide con un par `prohibida`
  (`E-PLAN-DIAGRAM-VIOLATION`). El modelo de datos, las clases y cualquier otro
  tipo de diagrama no se comprueban. Sin `architecture/`, solo el aviso.

## Con architecture

Si el proyecto tiene `architecture/` (la deja el plugin `architecture`: atributos
de calidad, componentes, decisiones ADR y estándares), `sdd` planifica sobre
ella en lugar de volver a decidir el stack en cada feature. Sin
`architecture/`, nada de esto se activa y todo funciona como siempre.

- **Contexto para el plan.** `sdd.py arch-context [--json]` da los componentes
  que alojan la candidata de la feature activa (o todos, si no viene de una
  candidata), las decisiones vigentes, las propuestas pendientes y los
  estándares. `/sdd:plan` parte de ahí: cita los ADR que respeta y añade la
  sección «Comprobación de arquitectura». El JSON trae `architecture`,
  `approved`, `problems`, `feature`, `candidate`, `components_scope`
  (`candidate` o `all`), `components`, `adrs`, `proposed` y `standards`; sin
  `architecture/`, solo `{"architecture": false}`.
- **Comprobación.** `trace` da error si el plan cita un ADR que no existe o que
  no está aprobado (uno propuesto se decide antes con `/architecture:review`),
  avisa si falta la sección de arquitectura, y avisa (sin error) si un plan ya
  aprobado cita un ADR que se sustituyó después.
- **Decisiones nuevas.** Si el plan necesita una decisión que afecta a más de
  una feature o es cara de revertir y ningún ADR la cubre, no la toma: la
  propone con `sdd.py propose-adr "<título>"`, que escribe el siguiente ADR en
  `Proposed` con `| Propuesto por | specs/<feature>/plan.md |`. La decide el
  usuario con `/architecture:review`; hasta entonces el plan no se aprueba.
  Sale con 1 sin `architecture/` o sin feature activa, y con 2 sin título.
- **Traspaso.** `/sdd:specify B03` con arquitectura exige que esté aprobada y
  que la candidata viva en algún componente; si no, no crea nada y dice qué
  corregir en `architecture`. La fila `Origen` gana un cuarto grupo con los
  componentes (`B02 · G2 · D1§4 · C2`), y el JSON de `new` los trae en
  `origin.components` y `context.components`.

`sdd` lee `architecture/` con `scripts/sdd_architecture.py`, copia documentada
del formato de `architecture.py`, incluida la lectura de los pares de los
estándares que contrasta los diagramas (`standard_pairs`); los plugins no
comparten código. La plantilla `templates/adr.md` es copia de la de
`architecture` con Estado `Proposed`. Una prueba de contrato del selftest
aprueba una arquitectura con el `architecture.py` real y comprueba que `sdd` la
lee igual, también sus pares.

## La compuerta

Un hook `PreToolUse` sobre `Write|Edit|NotebookEdit|Bash` bloquea la escritura
de código mientras algún artefacto no esté **listo**. Que el archivo exista no
basta: una plantilla recién copiada no cuenta. Se comporta así:

| Situación                                  | Resultado                          |
| ------------------------------------------ | ---------------------------------- |
| El repo no tiene `specs/`                  | No opina. El plugin es inerte      |
| La escritura pone `Estado: Approved`       | Bloquea: solo aprueba el usuario   |
| La ruta está en la lista de exentos        | Permite                            |
| No hay feature activa                      | Bloquea → `/sdd:specify`           |
| Falta `spec.md` / `plan.md` / `tasks.md`   | Bloquea → la skill que lo produce  |
| El artefacto existe pero está incompleto   | Bloquea y lista los problemas      |
| Cambió después de aprobarse               | Bloquea → revisar y `/sdd:approve` |
| Completo pero sin aprobar                  | Bloquea → `/sdd:approve`           |
| Los tres listos y aprobados                | Permite                            |

Qué significa «completo» en cada fase:

| Fase  | Condiciones |
| ----- | ----------- |
| spec  | sin huecos de plantilla · al menos un MUST · todo MUST con criterios · sin IDs duplicados · sin preguntas abiertas sobre un MUST |
| plan  | sin huecos de plantilla · menciona todos los MUST de la spec |
| tasks | sin huecos de plantilla · al menos una tarea · ningún MUST sin tarea · sin requisitos ni dependencias inexistentes · sin ciclos |

Un **hueco de plantilla** es cualquier texto en cursiva de la plantilla que
siga sin sustituir, un `{{VARIABLE}}`, o una cursiva con `...` o `\<…\>`. Las
notas que se pueden conservar van en blockquote, no en cursiva.

### Aprobación

Cada artefacto lleva `| Estado | Draft |` en la cabecera. Solo
`/sdd:approve` lo pasa a `Approved`:

- La skill solo la puede lanzar el usuario (`disable-model-invocation`).
- La aprobación la ejecuta Claude Code al cargar la skill, con la inyección
  `` !`…` ``, así que no pasa por la herramienta Bash. Por eso el hook puede
  denegar la **ejecución** de `sdd.py approve` por parte del modelo sin
  bloquear al usuario. Mencionar la orden entre comillas (en un mensaje de
  commit, la descripción de un PR) o en un texto que se escribe a un archivo no
  se bloquea.
- Aprueba siempre la siguiente fase pendiente. El orden spec → plan → tasks
  hace que no haya otra aprobable, así que no necesita argumento.
- Se niega si el artefacto no está completo.

Al aprobar se guarda una **huella del contenido**: `| Estado | Approved ·
3f9a2c1b0d4e |`. Si el artefacto cambia después, la fase pasa a «cambió tras
aprobar» (`[!]` en `/sdd:status`) y la compuerta se cierra hasta que vuelvas a
aprobarla. Así se detecta la deriva sin vigilar archivos:

- La huella ignora espacios y líneas en blanco. En `tasks.md` ignora también
  el estado de cada tarea, que `/sdd:implement` cambia sin alterar el plan de
  trabajo.
- Reaprobar una fase devuelve a borrador las posteriores que estuvieran
  aprobadas, porque se aprobaron sobre la versión anterior.
- Las aprobaciones sin huella (versiones anteriores del plugin) se aceptan tal
  cual.

El hook rechaza cualquier Write, Edit o comando Bash del modelo que pase un
artefacto a aprobado o reescriba su huella. Las demás ediciones de un artefacto aprobado pasan (por
ejemplo, marcar tareas `[x]` en `tasks.md`). Para desactivar el requisito de
aprobación: `{"approval": false}` en `.sdd/config.json`.

### Bash

Write y Edit declaran el archivo que tocan; Bash no. Para que `sed -i` o
`cat > src/app.py` no sean una puerta trasera hay dos capas:

1. **Prevención** (`PreToolUse`). Un analizador conservador extrae del comando
   los archivos que va a escribir —redirecciones, `tee`, `sed -i`, `perl -i`,
   `cp`, `mv`, `install`, `ln`, `rm`, `touch`, `truncate`, `dd of=`— y los
   evalúa contra la compuerta igual que un Write. Las rutas relativas se
   resuelven contra el `cwd` del comando. La aprobación se reconoce por las
   palabras del comando: el script `sdd.py` seguido de `approve`, también
   encadenado (`&&`, `;`) o dentro de una sustitución `$(…)` o con comillas
   invertidas que se ejecute. Lo que va entre comillas simples o en un heredoc
   es texto. Si el comando no se puede analizar, se busca la orden en su texto.
2. **Auditoría** (`PostToolUse`). Lo que el analizador no puede ver
   (`python -c`, un script, una variable) se detecta comparando `git status`
   antes y después del comando:
   - Archivos de código cambiados con la compuerta cerrada: se informa al
     modelo, con instrucción de deshacerlos y detenerse. `PostToolUse` no
     puede deshacer el comando, y borrar trabajo por su cuenta no es asunto
     de un hook.
   - Un artefacto que pasó a aprobado: se devuelve a su Estado anterior. Ahí
     revertir sí es seguro: solo restaura un campo. Se vigilan los artefactos
     de **todas** las features, no solo de la activa, así que tampoco se
     escapa un comando que cambie `.sdd/current`, apruebe otra feature y deje
     el puntero como estaba.

Límites:
- Sin git, la auditoría no corre y solo queda la prevención.
- Con la compuerta cerrada, cualquier cambio fuera de las rutas exentas
  cuenta como código, también un `package-lock.json` tras `npm install`.
  Añade a `exempt` lo que deba poder cambiar durante la especificación.
- Las instantáneas se guardan en el directorio temporal del sistema, una por
  llamada (`tool_use_id`), y se barren al cabo de un día.
- La prevención no ve una aprobación lanzada por un script, `bash -c "…"`, una
  tubería a `sh`, un heredoc que se pasa a un intérprete, o uno sin comillas
  cuya sustitución la ejecute: eso lo revierte la auditoría.
- La auditoría no distingue de dónde viene una aprobación. Si el modelo lanza
  un `git checkout`, `pull` o `rebase` que trae la versión aprobada de un
  artefacto que en tu copia estaba en Draft, también se revierte, y el modelo
  recibe la instrucción de avisarte. Lanza tú esos comandos con `!`, que no
  pasa por los hooks, o usa `SDD_BYPASS=1`.
- Un artefacto que no existía antes del comando no se vigila: un script que
  cree una feature con artefactos ya aprobados no se revierte. Vigilarlo
  revertiría también las features que llegan aprobadas con un `git pull`.
- Un artefacto que no se puede leer (por ejemplo, sin permiso) se salta: la
  compuerta falla abierta para ese comando y los demás siguen vigilados. Uno
  con bytes que no son UTF-8 sí se lee y se vigila.
- Un `\$(…)` escapado fuera de comillas dobles que contenga la orden se
  bloquea aunque no se ejecute, igual que una mención sin comillas
  (`echo python3 sdd.py approve`): peca de prudente.

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
sdd.py trace --feature 008 --json   # otra feature, sin cambiar la activa
```

`--feature` acepta el número (`008`) o el directorio (`008-slug`) y se combina
con `--json` y `--check`: el resultado es el mismo que con esa feature activa,
y `.sdd/current` no cambia. Si no existe, o si dos features comparten el
número, sale con 1 y la nombra. Lo usa el plugin `release` para trazar cada
feature de una versión.

La evidencia de prueba se detecta por el ID del requisito **con el prefijo de
la feature** dentro del archivo de test, en el nombre de la función o en un
comentario:

```python
def test_F001_R001_rechaza_token_expirado():   # R001 de specs/001-…
    ...

def test_otro_caso():
    # F001-R002
    ...
```

En **archivos de prueba Python**, una cita dentro de un texto no cuenta, tampoco
en un docstring: un `"def test_F001_R001_x(): …"` escrito como dato en un test
no es una prueba. Si el archivo no se puede tokenizar, se lee tal cual.

Además, en Python solo cuentan **el nombre y el cuerpo de una prueba**: una
función o un método cuyo nombre empieza por `test`. Una cita en un comentario de
módulo, encima del `def`, en un decorador, en un ayudante o en la llamada que
hace un `main()` no es evidencia de ninguna prueba. Dentro de una prueba
anidada, la cita es de la más interior. Si el archivo no se puede analizar (por
ejemplo, sintaxis de una versión de Python más nueva), se atribuye como en los
demás lenguajes: a la última prueba declarada encima, hasta 25 líneas; si no
hay ninguna, al archivo, sin nombre de prueba.

En los demás lenguajes las citas cuentan dondequiera que estén, también dentro
de un texto. Distinguir allí un dato de un título de prueba
(`it.only("…")`, `t.Run("…")`, ``fun `…`()``, `DisplayName = "…"`, RSpec, Bats,
tablas de Go…) exigiría un analizador por lenguaje; un fixture de código de
prueba escrito como dato en esos lenguajes cuenta como evidencia.

El prefijo es obligatorio porque cada feature numera sus requisitos desde
`R001`. Sin él, la prueba de una feature cubriría en silencio el requisito
homónimo de otra. Un `test_R001_…` sin prefijo no cuenta y genera
`W-TEST-UNSCOPED`.

Una prueba cuyo cuerpo es solo `pass`, `...`, comentarios o un docstring no
cuenta como evidencia (`W-TEST-EMPTY`). Una que tiene código pero ninguna
aserción reconocible sí cuenta, porque la aserción puede vivir en un helper,
pero genera `W-TEST-NO-ASSERT`. El análisis del cuerpo cubre Python y los
lenguajes de llaves (JS/TS, Go, Java, Rust, C#…); en el resto, toda prueba
cuenta.

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
| `E-PLAN-REQ-MISSING` | Requisito MUST que `plan.md` no menciona |
| `E-PLAN-UNKNOWN-REQ` | `plan.md` cita un requisito que no está en la spec |
| `E-PLAN-TEMPLATE` | `plan.md` conserva huecos de plantilla |
| `E-SPEC-OPEN-MUST-QUESTION` | Pregunta abierta que cita un requisito MUST |
| `E-SPEC-TEMPLATE` | `spec.md` conserva huecos de plantilla |
| `E-TASK-TEMPLATE` | `tasks.md` conserva huecos de plantilla |
| `W-REQ-NO-TASK` | Requisito SHOULD/COULD sin tarea |
| `W-REQ-NO-EARS` | Requisito que no usa la forma EARS |
| `W-REQ-VAGUE` | Adjetivo sin umbral verificable |
| `W-TASK-NO-REQ` | Tarea que no sirve a ningún requisito |
| `W-DONE-OPEN-DEPS` | Tarea cerrada con dependencias abiertas |
| `W-SPEC-OPEN-QUESTIONS` | Preguntas abiertas que no citan ningún MUST |
| `W-SPEC-NO-UNWANTED` | Ningún requisito `SI... ENTONCES` |
| `W-PLAN-NO-CONSTITUTION-CHECK` | Hay constitución y el plan no la contrasta |
| `E-PLAN-ADR-UNKNOWN` | Con `architecture/`: el plan cita un ADR que no existe |
| `E-PLAN-ADR-NOT-APPROVED` | Con `architecture/`: el plan cita un ADR en borrador, propuesto, rechazado, cambiado tras aprobarse o sustituido (si el plan no está aprobado) |
| `W-PLAN-NO-ARCHITECTURE-CHECK` | Con `architecture/`: el plan no tiene la sección «Comprobación de arquitectura» |
| `W-PLAN-ADR-SUPERSEDED` | Con `architecture/`: un plan aprobado cita un ADR sustituido después |
| `E-PLAN-DIAGRAM-UNKNOWN` | Con `architecture/`: un diagrama de secuencia del plan nombra un componente que no existe |
| `E-PLAN-DIAGRAM-VIOLATION` | Con `architecture/`: una llamada del diagrama de secuencia va al revés de un estándar o está prohibida |
| `W-PLAN-NO-DIAGRAMS` | El plan no tiene la sección «Diagramas» (ni «No aplica.» en ella) |
| `W-TASK-NO-DONE-WHEN` | Tarea sin «hecho cuando» |
| `W-TEST-EMPTY` | Prueba vacía (solo `pass`, `...`, comentarios): no cuenta |
| `W-TEST-NO-ASSERT` | Prueba sin aserción reconocible: cuenta, pero revísala |
| `W-TASK-OBSOLETE-REQ` | Tarea abierta que sirve a un requisito obsoleto |
| `W-TEST-UNSCOPED` | Prueba que cita el requisito sin prefijo de feature |

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
  "approval": true,
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
- **`approval`**: si exige `Estado: Approved` en cada fase. `true` por defecto.
- **`exempt`**: rutas que la compuerta nunca bloquea. Los patrones que terminan
  en `/**` son prefijos; el resto son globs contra la ruta relativa y contra el
  nombre del archivo.

## Cómo se resuelve la raíz del proyecto

`CLAUDE_PROJECT_DIR`, si está, se usa tal cual. Si no (la inyección de una
skill como `/sdd:approve` no la recibe), se sube desde el directorio de trabajo
hasta el primero que contiene `.sdd/` y, si ninguno lo tiene, hasta el primero
que contiene `specs/`. `.sdd/` va primero porque es exclusivo del plugin: una
carpeta `specs/` de pruebas en `src/` no se confunde con la raíz. La búsqueda no
sale del repositorio git (se detiene en el primer `.git`), y si no encuentra
nada se usa el directorio de trabajo.

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
su cuenta. En `/sdd:approve` es además la garantía de la aprobación. La excepción es `spec-authoring`, que sí es invocable por el modelo
para que las reglas de redacción EARS se apliquen solas al editar cualquier
archivo bajo `specs/`.

## Verificación

```bash
claude plugin validate /ruta/a/sdd --strict
claude plugin details sdd
```

El segundo comando muestra el coste en tokens: *always-on* (lo que el plugin
añade a cada sesión solo por existir, unas 10 descripciones de skill) frente a
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

## Cambios de requisitos

`/sdd:amend <cambio>` modifica una spec ya aprobada sin romper la
trazabilidad:

| Tipo de cambio | En `spec.md` |
| -------------- | ------------ |
| Requisito nuevo | Fila con el siguiente ID libre (`sdd.py next-req`) |
| Cambio de comportamiento | El viejo pasa a `OBSOLETO`; nace uno con ID nuevo |
| Requisito retirado | Pasa a `OBSOLETO` |
| Aclaración | Se edita en su sitio, mismo ID |

Un requisito `OBSOLETO` no exige tarea ni prueba, y su ID no se recicla. Las
tareas abiertas que aún le sirven generan `W-TASK-OBSOLETE-REQ`. Cada
enmienda deja una entrada en `## Historial de cambios`. Como la spec cambió,
la huella deja de coincidir y la compuerta se cierra hasta reaprobar spec,
plan y tasks.

## Revisión de la implementación

`agents/implementation-reviewer.md` es un subagente de solo lectura (`Read`,
`Grep`, `Glob` y Bash para `git diff`). `/sdd:implement` lo lanza al terminar
cada tarea, antes de marcarla `[x]`. Contrasta el diff con:

- los criterios de aceptación de los requisitos que la tarea cita, exigiendo
  archivo y línea como evidencia;
- las pruebas, que deben verificar el criterio y no solo nombrarlo;
- el alcance de la tarea;
- las decisiones del plan y la constitución.

Devuelve `CUMPLE`, `NO CUMPLE` o `CUMPLE CON RESERVAS`. Es independiente de
quien implementó: no hereda su contexto ni sus suposiciones.

## Qué falta a propósito

El detalle y el orden están en `docs/standards-roadmap.md`. En resumen:

- **Agente `spec-reviewer`**: revisión de solo lectura de la spec antes de
  aprobarla. Hoy la cubren a medias `/sdd:analyze` y la readiness.
- **`.lsp.json`**: diagnósticos en tiempo real del servidor de lenguaje, sin
  coste en tokens de contexto.
- **Workflow** (`workflows/`) para la fase de implementación, con fan-out de un
  agente por tarea y revisión adversarial. Nota: los workflows no admiten
  entrada del usuario a mitad de ejecución, así que cada fase que requiera tu
  aprobación debe seguir siendo su propia skill.
