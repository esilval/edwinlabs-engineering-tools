# Tasks: diagramas por feature en sdd: secuencia, modelo de datos y clases en el plan

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-19  |
| Estado | Approved · 6441dc14d2b4       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F009_R004_componente_inexistente`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Las pruebas viven en `plugins/sdd/tests/selftest.py`, como funciones
`test_F009_Rxxx_*`, sobre la arquitectura de prueba de la feature 007.

## Tareas

### T001 — Sección `## Diagramas` en la plantilla del plan `P`

- **Estado:** `[x]`
- **Requisitos:** R001
- **Depende de:** —
- **Archivos:** `plugins/sdd/templates/plan.md`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - La plantilla sigue D1: `## Diagramas` tras «Contratos», con `### Secuencia`, `### Modelo de datos` y `### Clases`, cada uno con su línea de hueco en cursiva.
  - Pasa `test_F009_R001_seccion_de_diagramas`:
    - un plan con los huecos sin tocar da `E-PLAN-TEMPLATE` y la compuerta no lo aprueba;
    - con «No aplica.» en los tres apartados, ningún hueco de diagramas.

### T002 — `sdd.py diagram`: el esqueleto de secuencia

- **Estado:** `[ ]`
- **Requisitos:** R002, R003, R007
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `diagram` sigue D3 y sus salidas de «Contratos». El esqueleto tiene:
    - un `participant` por componente de la candidata;
    - un hueco `%%` con `...`;
    - `;` escrito como `#59;`.
  - Pasan estas pruebas:
    - `test_F009_R002_esqueleto_con_componentes`:
      - una feature de B01 tiene `participant C1 as Ventas`, y el plan da `E-PLAN-TEMPLATE` hasta completarlo;
      - sin candidata no hay participantes, y el hueco lista C1 y C2;
      - un plan sin sección la recibe al final;
      - un plan aprobado se escribe y se avisa.
    - `test_F009_R003_no_sobrescribe`: un segundo `diagram`, o un apartado con «No aplica.», deja el plan igual byte a byte y dice que ya tenía diagramas.
    - `test_F009_R007_sin_arquitectura` (parte de `diagram`): sin `architecture/`, sale con 0 y no escribe.

### T003 — `standard_pairs` en `sdd_architecture.py` y contrato `P`

- **Estado:** `[ ]`
- **Requisitos:** R005
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_architecture.py`, `plugins/architecture/scripts/architecture.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `sdd_architecture.standard_pairs(root, kind)` sigue D4.
  - Su docstring y el de `standard_pairs` en `architecture.py` se nombran entre sí; en `architecture.py` solo cambia el comentario.
  - La prueba de contrato de la feature 007 compara los pares `dependencia` y `prohibida` de las dos copias sobre un `standards.md` con un estándar de cada tipo, y pasa.

### T004 — Comprobación de los diagramas en `trace`

- **Estado:** `[ ]`
- **Requisitos:** R004, R005, R006, R007
- **Depende de:** T001, T003
- **Archivos:** `plugins/sdd/scripts/sdd_trace.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - La lectura de `sequenceDiagram` y los tres códigos de D5 están en `FINDINGS` y en `analyze`.
  - Pasan estas pruebas:
    - `test_F009_R004_componente_inexistente`: C7, declarado o solo en un mensaje, se nombra;
    - `test_F009_R005_llamada_contra_estandar`:
      - `C1->>C2` contra S1 y un par prohibido nombran el estándar;
      - la respuesta `C1-->>C2` no da hallazgo;
      - se reconocen las flechas de D2;
    - `test_F009_R006_sin_diagramas_avisa`: aviso y ningún error;
    - `test_F009_R007_sin_arquitectura` (parte de `trace`): sin `architecture/`, ningún `E-PLAN-DIAGRAM-*`.
  - Un esqueleto completado que respeta los estándares no da ningún `E-PLAN-DIAGRAM-*`.
  - La cobertura de códigos del selftest los incluye.

### T005 — Skill del plan, README, registro y cierre

- **Estado:** `[ ]`
- **Requisitos:** R001, R008
- **Depende de:** T002, T004
- **Archivos:** `plugins/sdd/skills/plan/SKILL.md`, `plugins/sdd/README.md`, `plugins/sdd/docs/standards-roadmap.md`
- **Hecho cuando:**
  - `/sdd:plan` sigue D6: ejecuta `diagram`, completa los tres apartados con las convenciones de D2 o escribe «No aplica.», y pide citar la decisión en cada llamada entre componentes.
  - Sin arquitectura, la skill pide los diagramas igualmente.
  - El README documenta la sección, el comando, las convenciones y los tres códigos.
  - El registro amplía la descripción de `*-PLAN-*`.
  - `python3 scripts/validate.py --strict` y los tres selftests pasan, y `sdd.py trace` de la feature 009 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T001, T005 |
| R002 | T002 |
| R003 | T002 |
| R004 | T004 |
| R005 | T003, T004 |
| R006 | T004 |
| R007 | T002, T004 |
| R008 | T005 |

> Todo requisito MUST debe tener al menos una tarea.
