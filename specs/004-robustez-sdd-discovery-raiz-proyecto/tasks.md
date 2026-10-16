# Tasks: robustez de sdd y discovery: raíz del proyecto y falso positivo de la compuerta

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-15  |
| Estado | Approved · 175bc860dba3       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F004_R001_raiz_desde_subdirectorio`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Las pruebas viven en `plugins/sdd/tests/selftest.py` y en
`plugins/discovery/tests/selftest.py`, como funciones `test_F004_Rxxx_*`
registradas en su ejecución. Las pruebas de la raíz quitan
`CLAUDE_PROJECT_DIR` del entorno del proceso.

## Tareas

### T001 — Raíz del proyecto en `sdd` · P

- **Estado:** `[x]`
- **Requisitos:** R001, R003, R004
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `project_root` sigue D1: `CLAUDE_PROJECT_DIR` tal cual; si no, primero sube buscando `.sdd/` y luego `specs/`, con tope en el primer `.git`; si no encuentra nada, el directorio de partida. Un `OSError` no se propaga.
  - Pasan estas pruebas:
    - `test_F004_R001_raiz_desde_subdirectorio`: `status` lanzado desde `specs/<feature>/` muestra la feature activa, la aprobación lanzada desde ahí aprueba el artefacto de esa feature, y un `src/specs/` más cercano no gana a `.sdd/`;
    - `test_F004_R003_sin_datos_usa_el_directorio_actual`: un directorio sin datos dentro de un repo git, con un `specs/` fuera del repo, da el mismo resultado que hoy, sin salir del `.git`;
    - `test_F004_R004_variable_de_entorno_manda`: con `CLAUDE_PROJECT_DIR` apuntando a un proyecto y el `cwd` en otro, actúa sobre el de la variable.
  - El selftest de `sdd` pasa.

### T002 — Raíz del proyecto en `discovery` · P

- **Estado:** `[x]`
- **Requisitos:** R002, R003, R004
- **Depende de:** —
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:**
  - `project_root` sigue D1 con `product/` como dato, con el mismo tope en `.git` y la misma tolerancia a `OSError`.
  - Pasan estas pruebas:
    - `test_F004_R002_raiz_desde_subdirectorio`: `check --json` lanzado desde `product/sources/` analiza el brief y el backlog del proyecto;
    - `test_F004_R003_sin_product_usa_el_directorio_actual`;
    - `test_F004_R004_variable_de_entorno_manda`.
  - El selftest de `discovery` pasa.

### T003 — La compuerta de `discovery` distingue ejecutar de mencionar

- **Estado:** `[x]`
- **Requisitos:** R005, R006, R007
- **Depende de:** T002
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:**
  - `discovery.py` incorpora la copia del analizador de D2, con un comentario de cabecera que nombra `plugins/sdd/scripts/sdd_bash.py`, y `cmd_guard` la usa en lugar de la expresión, salvo para los comandos que no se pueden analizar.
  - Pasan estas pruebas:
    - `test_F004_R005_mencion_no_bloquea`: commit con `-m`, `gh pr create --body`, heredoc con la orden, `grep` con la orden entre comillas simples y `echo "…"`;
    - `test_F004_R006_ejecucion_bloquea`: directa, con ruta absoluta y entre comillas, tras `&&` y `;`, con `VAR=1` delante, dentro de `$(…)` y de comillas invertidas, y un comando no analizable que la contiene;
    - `test_F004_R007_auditoria_revierte`: un `bash -c` con la orden, que la compuerta deja pasar, cambia el backlog a aprobado y la auditoría lo devuelve a Draft con exit 2.
  - Sigue pasando `test_F001_R015_guard_bash`, y el selftest de `discovery` pasa.

### T004 — El selftest de `discovery` deja de citar un requisito sin prefijo · P

- **Estado:** `[x]`
- **Requisitos:** R008
- **Depende de:** —
- **Archivos:** `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** el comentario de `test_huella_de_texto` describe el criterio sin citar un ID de requisito (D3). `sdd.py trace` de la feature activa no tiene ningún `W-TEST-UNSCOPED` que señale `plugins/discovery/tests/selftest.py`, y el selftest de `discovery` pasa.

### T005 — READMEs y cierre

- **Estado:** `[x]`
- **Requisitos:** R001, R002, R005
- **Depende de:** T001, T002, T003, T004
- **Archivos:** `plugins/sdd/README.md`, `plugins/discovery/README.md`
- **Hecho cuando:**
  - El README de `sdd` explica cómo se resuelve la raíz sin `CLAUDE_PROJECT_DIR`.
  - El de `discovery` explica lo mismo y qué bloquea su compuerta: la ejecución, no la mención, con sus límites y `DISCOVERY_BYPASS=1`.
  - `python3 scripts/validate.py --strict` y los dos selftests pasan, y `sdd.py trace` de la feature 004 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T001, T005 |
| R002 | T002, T005 |
| R003 | T001, T002 |
| R004 | T001, T002 |
| R005 | T003, T005 |
| R006 | T003 |
| R007 | T003 |
| R008 | T004 |

> Todo requisito MUST debe tener al menos una tarea.
