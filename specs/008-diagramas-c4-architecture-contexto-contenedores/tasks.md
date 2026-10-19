# Tasks: diagramas C4 en architecture: contexto, contenedores y componentes desde la arquitectura aprobada

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-19  |
| Estado | Approved · e87d18a2b203       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F008_R003_dependencia_con_su_decision`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

El código vive en `plugins/architecture/scripts/architecture.py` y las pruebas
en `plugins/architecture/tests/selftest.py`, como funciones `test_F008_Rxxx_*`,
sobre la arquitectura de prueba de la feature 006.

## Tareas

### T001 — `architecture.py diagram`: el esqueleto

- **Estado:** `[ ]`
- **Requisitos:** R001, R002, R003, R004
- **Depende de:** —
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `diagram` sigue D2 y D3:
    - escribe `architecture/diagrams.md` en `Draft`, con las tres secciones y un bloque Mermaid `flowchart` en cada una;
    - no toca un archivo que ya existe;
    - sin componentes, sale con 1.
  - Pasan estas pruebas:
    - `test_F008_R001_tres_vistas`;
    - `test_F008_R002_usuarios_y_componentes`: los usuarios del brief en el contexto; C1 y C2 con su nombre en contenedores y componentes;
    - `test_F008_R003_dependencia_con_su_decision`: arista `C2 --> C1` con `ADR-0001`;
    - `test_F008_R004_no_sobrescribe`: un segundo `diagram` deja el archivo igual byte a byte y dice que ya existía.

### T002 — Lectura de los diagramas y comprobaciones

- **Estado:** `[ ]`
- **Requisitos:** R005, R006, R007, R009
- **Depende de:** T001
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - La lectura de nodos y aristas Mermaid y los cuatro códigos de D4 están en `FINDINGS` y en `analyze`.
  - Pasan estas pruebas:
    - `test_F008_R005_componente_inexistente`: C7 se nombra;
    - `test_F008_R006_componente_que_falta`: falta C2 en contenedores, y falta una vista;
    - `test_F008_R007_dependencia_contra_estandar`: la arista invertida y el par prohibido nombran el estándar;
    - `test_F008_R009_sin_diagramas_avisa`: aviso, y `approve` no se niega por ello.
  - Un esqueleto generado y completado sin errores no da ningún código `E-ARCH-DIAGRAM-*`.
  - La cobertura de códigos del selftest los incluye.

### T003 — Aprobación y guardrails

- **Estado:** `[ ]`
- **Requisitos:** R008, R010
- **Depende de:** T001
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `approve`, `check_approval`, `guarded_files` y `_guarded_target` incluyen `diagrams.md` (D1, D5).
  - Pasan estas pruebas:
    - `test_F008_R008_diagramas_en_la_aprobacion`: se sellan con el conjunto, y editarlos tras aprobar da `W-ARCH-NOT-APPROVED` con `diagrams.md`;
    - `test_F008_R010_guardrails_de_diagramas`: un Write o Edit que aprueba `diagrams.md` se deniega, y `audit` revierte un comando que lo aprueba.

### T004 — Skills, README y cierre

- **Estado:** `[ ]`
- **Requisitos:** R001, R002, R008
- **Depende de:** T002, T003
- **Archivos:** `plugins/architecture/skills/diagram/SKILL.md`, `plugins/architecture/skills/check/SKILL.md`, `plugins/architecture/skills/init/SKILL.md`, `plugins/architecture/README.md`
- **Hecho cuando:**
  - `/architecture:diagram` sigue D6, con las convenciones de D2 y ejemplos de sintaxis.
  - `check` lista los cuatro códigos, e `init` recomienda `/architecture:diagram` al terminar.
  - El README documenta los diagramas: vistas, convenciones, esqueleto, comprobaciones y aprobación.
  - `python3 scripts/validate.py --strict` y los tres selftests pasan, y `sdd.py trace` de la feature 008 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T001, T004 |
| R002 | T001, T004 |
| R003 | T001 |
| R004 | T001 |
| R005 | T002 |
| R006 | T002 |
| R007 | T002 |
| R008 | T003, T004 |
| R009 | T002 |
| R010 | T003 |

> Todo requisito MUST debe tener al menos una tarea.
