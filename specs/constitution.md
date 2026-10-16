# Constitución del proyecto

| Campo | Valor      |
| ----- | ---------- |
| Fecha | 2026-10-16 |

> Reglas que ninguna spec, plan o tarea puede violar. Si una regla aquí impide
> algo que hace falta, se cambia la regla explícitamente, no se ignora.

## Principios

1. **Lo determinista vive en un script, no en un prompt.** Numeración, resolución
   de estado, compuertas y comprobaciones de cobertura son código Python. Las
   skills solo describen lo que requiere criterio.
2. **Cada plugin es una etapa del ciclo de vida, unida a las demás por archivos.**
   Un plugin no importa código de otro; lee los artefactos que el otro deja. Cada
   plugin funciona aunque los demás no estén instalados.
3. **Un guardrail falla abierto y siempre tiene escape.** Un error inesperado de
   un hook deja pasar en vez de bloquear, y todo bloqueo documenta cómo
   desactivarlo.
4. **Un guardrail nunca concede permisos.** Ningún hook devuelve
   `permissionDecision: "allow"`; si no objeta, no dice nada.
5. **Lo que bloquea lo decide una persona.** Las fases que abren una compuerta
   (aprobar un artefacto) solo las lanza el usuario
   (`disable-model-invocation: true`), y el modelo no puede escribir esa
   aprobación por ninguna vía.

## Estándares de código

- **Lenguajes y versiones:** Python 3.8 como mínimo, solo biblioteca estándar.
  Sin dependencias externas en los scripts de los plugins.
- **Formato y linting:** ninguna herramienta configurada hoy. Se sigue el estilo
  del código existente (PEP 8, 4 espacios, líneas de ~90 caracteres).
- **Estructura de directorios:**
  - `.claude-plugin/marketplace.json` en la raíz; un directorio por plugin en
    `plugins/<nombre>/`.
  - Dentro de cada plugin: `.claude-plugin/plugin.json` (solo ese archivo),
    `skills/<skill>/SKILL.md`, `agents/`, `hooks/hooks.json`, `scripts/`,
    `templates/`, `tests/selftest.py`, `docs/` y `README.md`.
- **Hooks:** forma exec (`command` + `args`), con `timeout` explícito y rutas
  vía `${CLAUDE_PLUGIN_ROOT}`. Un `PreToolUse` que bloquea responde JSON con
  exit 0; un `PostToolUse` que informa al modelo usa exit 2 con stderr.
- **Idioma:** documentación, skills, mensajes al usuario y mensajes de commit,
  en español. Commits con el prefijo del plugin afectado (`sdd: …`).

## Pruebas

- Cada plugin tiene `tests/selftest.py`, solo con biblioteca estándar, y CI lo
  ejecuta. Una tarea que cambia comportamiento de un script no está hecha si el
  selftest no cubre el cambio.
- Todo código de hallazgo declarado (`E-…`, `W-…`) es alcanzable en el selftest:
  el selftest falla si un código declarado no se prueba.
- No hay umbral de cobertura: no se mide hoy.

## Seguridad y datos

- Los plugins no hacen peticiones de red ni envían datos fuera de la máquina.
- Ningún secreto en el repositorio.

## Límites

- Añadir una dependencia externa a un script de plugin requiere aprobación
  explícita del usuario.
- Los códigos de hallazgo y los schemas JSON (`sdd.trace/v1`) son contrato
  público: renombrar o eliminar un código, o cambiar la forma de un campo,
  exige subir la versión del schema. Añadir códigos es aditivo.
- Cada plugin reserva sus prefijos de hallazgo en un registro común antes de
  usarlos (hoy, `docs/standards-roadmap.md` de `sdd`, sección 7).
- Cambiar el formato de un artefacto que lee otro plugin es un cambio de
  contrato entre plugins y requiere aprobación explícita del usuario.
- Código copiado entre plugins: como los plugins no comparten código, una copia
  de lógica de otro plugin lleva un comentario que nombra el original y las
  demás copias. Si lee el formato de un artefacto de otro plugin, una prueba de
  contrato de su selftest la contrasta con el plugin real cuando está en el
  repositorio.

## Comprobación

Cómo se hace cumplir cada regla de arriba. Una regla sin fila aquí depende de
que alguien se acuerde, y eso hay que saberlo.

| Regla | Nivel | Mecanismo | Suelo actual |
| ----- | ----- | --------- | ------------ |
| Sintaxis compatible con Python 3.8 | mecánica | `scripts/validate.py --strict` compila todo `.py` en CI con 3.8 | cumple |
| Estructura de marketplace, plugins, skills, agentes y hooks | mecánica | `scripts/validate.py --strict` en CI | cumple |
| Hooks con `timeout` | mecánica | `validate.py --strict` (el aviso falla en modo estricto) | cumple |
| Selftest de cada plugin en CI | mecánica | `.github/workflows/validate.yml` recorre `plugins/*/tests/selftest.py`. Pendiente de automatizar: que `validate.py` exija `tests/selftest.py` en cada plugin | 3 de 3 plugins |
| Todo código de hallazgo alcanzable | mecánica | el selftest compara los declarados con los probados | cumple en los 3 plugins |
| Solo biblioteca estándar | mecánica | pendiente de automatizar: comprobar los `import` en `validate.py` | cumple |
| Hooks en forma exec | mecánica | pendiente de automatizar en `validate.py` | cumple |
| Ningún hook devuelve `allow` | mecánica (parcial) | el selftest de cada plugin lo comprueba para su compuerta; el resto, revisión del diff | cumple |
| Lo determinista en scripts | revisable | revisión del diff | — |
| Guardrail con escape documentado | revisable | revisión del diff y README | — |
| Aprobaciones solo por el usuario | revisable | revisión del diff; `disable-model-invocation` en las skills que aprueban | — |
| Códigos y schemas como contrato | revisable | revisión del diff | — |
| Plugins unidos solo por archivos | revisable | revisión del diff | — |
| Código copiado entre plugins, referenciado y contrastado | revisable (parcial) | revisión del diff; pruebas de contrato contra `discovery` en los selftests de `sdd` y `architecture` | cumple |
| Idioma y formato de commits | juicio | criterio humano | — |
| Estilo del código | juicio | criterio humano; sin herramienta | — |

Niveles: **mecánica** (un script la comprueba), **revisable** (requiere leer el
diff y juzgar), **juicio** (la decide una persona caso por caso).

La columna de suelo existe para el ratchet: si el repositorio hoy no cumple un
umbral, se registra lo que hay y solo se permite que suba. Un umbral inalcanzable
termina desactivado, y eso desacredita a todas las demás comprobaciones.

## Decisiones aplazadas

- **Formateador y linter:** no se adopta por ahora (2026-10-15). El hook de
  calidad de `sdd` no hace nada en este repo mientras no haya ninguno.
- **Cobertura:** no se mide por ahora (2026-10-15). Si se adopta, el primer
  valor medido será el suelo.
