# Tasks: integracion de sdd con architecture: el plan lee y comprueba la arquitectura

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-16  |
| Estado | Approved · 1a6a0fe5e18f       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F007_R003_plan_cita_adr_no_aprobado`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Las pruebas viven en `plugins/sdd/tests/selftest.py`, como funciones
`test_F007_Rxxx_*` registradas en su `main()`. Las arquitecturas de prueba se
construyen a mano en el formato de `architecture`, sobre los productos de prueba
de la feature 005, y se sellan con la huella de `sdd_product`. Solo la prueba de
contrato ejecuta `architecture.py`.

## Tareas

### T001 — Lectura de la arquitectura en `sdd_architecture.py`

- **Estado:** `[x]`
- **Requisitos:** R009, R002
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_architecture.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - El módulo sigue D2: componentes, ADR con estado y sustituto, estándares, aprobación del conjunto y siguiente número de ADR. El comentario de cabecera nombra el original.
  - Pasan estas pruebas:
    - `test_F007_R002_lee_la_arquitectura`: C1 y C2 con sus candidatas; ADR-0001 aprobada, ADR-0003 rechazada y ADR-0004 propuesta; S1; el siguiente número es ADR-0005;
    - `test_F007_R009_contrato_con_architecture`: una arquitectura aprobada con el `architecture.py` real se reconoce aprobada, y cambiada tras editar un componente. Se omite si no está.
  - El selftest de `sdd` pasa.

### T002 — Trazabilidad de las decisiones que cita el plan · P

- **Estado:** `[x]`
- **Requisitos:** R003, R004, R005, R001
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/sdd_trace.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `analyze` emite los cuatro códigos de D1 solo si existe `architecture/`, y los declara en el catálogo de códigos.
  - `test_trazabilidad` los cubre en la comprobación de que cada código es alcanzable.
  - Pasan estas pruebas:
    - `test_F007_R003_plan_cita_adr_no_aprobado`: ADR-0009 da error; ADR-0004 propuesta da error y remite a `/architecture:review`; ADR-0001 aprobada no da nada;
    - `test_F007_R004_plan_sin_comprobacion_de_arquitectura`;
    - `test_F007_R005_adr_sustituido_tras_aprobar`: un plan aprobado da aviso con ADR-0004 y ningún error; un plan sin aprobar da error;
    - `test_F007_R001_trace_sin_arquitectura_igual`: `trace --json` sin `architecture/` da lo mismo con un plan que cita ADR que sin citarlos.
  - El selftest de `sdd` pasa.

### T003 — `sdd.py arch-context` · P

- **Estado:** `[x]`
- **Requisitos:** R002, R001
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `arch-context [--json]` sigue D3 y el contrato del plan.
  - Pasan estas pruebas:
    - `test_F007_R002_contexto_de_planificacion`: para la feature de B02, C2, ADR-0001 y S1, sin ADR-0003, y ADR-0004 entre las propuestas. Para una feature sin candidata, todos los componentes;
    - `test_F007_R001_contexto_sin_arquitectura`: `{"architecture": false}` con salida 0.

### T004 — `sdd.py propose-adr` · P

- **Estado:** `[x]`
- **Requisitos:** R006
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/templates/adr.md`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `propose-adr "<título>"` sigue D4 con la copia de la plantilla.
  - Pasa `test_F007_R006_propone_una_decision`, con estos casos:
    - con ADR-0001 a ADR-0003, crea ADR-0004 en `Proposed`, con «Propuesto por» = el plan de la feature activa;
    - `sdd_architecture` la lee como propuesta;
    - sin `architecture/`, sale con 1; sin título, con 2.

### T005 — Traspaso con arquitectura · P

- **Estado:** `[x]`
- **Requisitos:** R007, R008, R001
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `prepare_handoff` y `fill_from_candidate` siguen D5.
  - Pasan estas pruebas:
    - `test_F007_R007_origen_con_componentes`: `| Origen | B02 · G2 · D1§4 · C2 |`;
    - `test_F007_R008_traspaso_sin_arquitectura_lista`: B02 sin componente, arquitectura sin aprobar y arquitectura cambiada. Ninguno crea nada, y los mensajes remiten a `architecture`;
    - `test_F007_R001_traspaso_sin_arquitectura_igual`: sin `architecture/`, `Origen` de tres grupos.
  - Las pruebas de traspaso de la feature 005 siguen pasando.

### T006 — Skills, README y cierre

- **Estado:** `[ ]`
- **Requisitos:** R002, R006, R008
- **Depende de:** T002, T003, T004, T005
- **Archivos:** `plugins/sdd/skills/plan/SKILL.md`, `plugins/sdd/skills/implement/SKILL.md`, `plugins/sdd/README.md`
- **Hecho cuando:**
  - Las skills tienen los pasos de D6.
  - El README documenta la integración: contexto, comprobación, propuestas, traspaso y los cuatro códigos.
  - `python3 scripts/validate.py --strict` y los tres selftests pasan, y `sdd.py trace` de la feature 007 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T002, T003, T005 |
| R002 | T001, T003, T006 |
| R003 | T002 |
| R004 | T002 |
| R005 | T002 |
| R006 | T004, T006 |
| R007 | T005 |
| R008 | T005, T006 |
| R009 | T001 |

> Todo requisito MUST debe tener al menos una tarea.
