# Tasks: traspaso de discovery a sdd: specify con un ID de candidata crea la spec desde el backlog aprobado

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-15  |
| Estado | Approved · f45dcece39d2       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F005_R001_crea_la_spec_desde_la_candidata`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Las pruebas viven en `plugins/sdd/tests/selftest.py`, como funciones
`test_F005_Rxxx_*` registradas en su `main()`. Los productos de prueba se
construyen con la plantilla y el formato de `discovery`, y se sellan con la
huella de `sdd_product`, salvo en la prueba de contrato.

## Tareas

### T001 — Aprobación del producto en `sdd_product.py` · P

- **Estado:** `[x]`
- **Requisitos:** R003
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_product.py`, `plugins/discovery/scripts/discovery.py` (solo comentario), `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `sdd_product.py` expone una función que, para `brief.md` y `backlog.md`, dice si cada uno falta, está sin aprobar, está aprobado o cambió tras aprobarse. Usa la copia de la huella de D2, con comentarios recíprocos en las dos copias.
  - Pasa `test_F005_R003_contrato_con_discovery`: con el `discovery.py` real, si `plugins/discovery` existe, se aprueba un producto coherente. `sdd_product` lo da por aprobado; tras editar el brief, por cambiado; y tras reformatearlo sin cambiar el contenido, sigue aprobado. Si `discovery` no está, la prueba se omite con un aviso.
  - El selftest de `sdd` pasa.

### T002 — Candidatas, objetivos y fuentes en `sdd_product.py` · P

- **Estado:** `[ ]`
- **Requisitos:** R004, R006
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_product.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `sdd_product.py` lee de `## Candidatas` cada candidata con su título, Estado y campos, y de `## Objetivos` del brief cada objetivo con su título y descripción.
  - Resuelve `D2§4.2` a `product/sources/D2-*.md` y la sección `4.2`.
  - Pasan estas pruebas:
    - `test_F005_R004_lee_candidatas_y_descartadas`: lee B03 con sus campos, marca B04 como descartada y da None para B09;
    - `test_F005_R006_resuelve_objetivos_y_fuentes`: G2 con su título y su descripción, y `D2§4.2` con su archivo.
  - El selftest de `sdd` pasa.

### T003 — `sdd.py new` en modo traspaso: crear o negarse

- **Estado:** `[ ]`
- **Requisitos:** R001, R002, R003, R004, R007, R008
- **Depende de:** T001, T002
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `cmd_new` sigue D1 y D3: detecta el ID, comprueba el producto, rellena Problema, Contexto y Alcance e inserta `Origen`. Si se niega, sale con exit 1, un motivo por stderr, y sin directorio ni cambio en `.sdd/current`.
  - Pasan estas pruebas:
    - `test_F005_R001_crea_la_spec_desde_la_candidata`: con `B03` y `b03`; el nombre sale del título, y la spec lleva el problema, el resultado observable, Dentro y Fuera;
    - `test_F005_R002_origen_en_la_cabecera`: `| Origen | B03 · G2 · D2§4.2 |`;
    - `test_F005_R003_producto_sin_aprobar`: backlog en Draft y brief cambiado tras aprobarse; mensajes con `/discovery:approve` y con «cambió»;
    - `test_F005_R004_candidata_inexistente_o_descartada`;
    - `test_F005_R007_sin_backlog_o_sin_id`: sin backlog, `new B03` crea `NNN-b03`; con backlog, una descripción normal crea la feature sin `Origen`;
    - `test_F005_R008_specs_sin_origen_igual`: `status`, `trace --json` y `approve` sobre una spec sin origen dan lo mismo con y sin un `product/` aprobado al lado.
  - El selftest de `sdd` pasa, y `status` de las features 001–004 del repo no cambia.

### T004 — Duplicados, dependencias y contexto en el JSON

- **Estado:** `[ ]`
- **Requisitos:** R005, R006, R009
- **Depende de:** T003
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `cmd_new` sigue D4 y D5: niega si una spec ya tiene esa candidata como origen; añade a `warnings` las dependencias sin feature; y el JSON trae `origin`, `context` y `warnings`.
  - Pasan estas pruebas:
    - `test_F005_R005_candidata_con_feature`: el mensaje nombra la feature existente y no se crea nada;
    - `test_F005_R006_contexto_en_el_json`: G2 con su título, y el archivo de D2 con la sección 4.2;
    - `test_F005_R009_dependencia_sin_feature`: se crea y `warnings` nombra B03.
  - El selftest de `sdd` pasa.

### T005 — Skill `specify`, README y cierre

- **Estado:** `[ ]`
- **Requisitos:** R001, R003, R006
- **Depende de:** T004
- **Archivos:** `plugins/sdd/skills/specify/SKILL.md`, `plugins/sdd/README.md`
- **Hecho cuando:**
  - La skill tiene el paso de D5: si el JSON trae `origin`, lee `context`, parte de las secciones rellenas y muestra `warnings`. Si `new` sale con exit 1, enseña el motivo y no crea nada a mano.
  - El README documenta el traspaso: uso, negativas, fila `Origen` y contrato con `discovery`.
  - `python3 scripts/validate.py --strict` y los dos selftests pasan, y `sdd.py trace` de la feature 005 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T003, T005 |
| R002 | T003 |
| R003 | T001, T003, T005 |
| R004 | T002, T003 |
| R005 | T004 |
| R006 | T002, T004, T005 |
| R007 | T003 |
| R008 | T003 |
| R009 | T004 |

> Todo requisito MUST debe tener al menos una tarea.
