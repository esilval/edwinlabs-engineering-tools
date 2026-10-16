# Tasks: robustez de sdd: auditoría de todas las features

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-15  |
| Estado | Approved · 420264bbea8a       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F003_R001_auditoria_revierte_otra_feature`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Todas las pruebas viven en `plugins/sdd/tests/selftest.py`, como funciones
`test_F003_Rxxx_*` registradas en su `main()`. Las tareas marcadas con `P` no
dependen entre sí, pero comparten el selftest: se ejecutan una detrás de otra.

## Tareas

### T001 — `E-DONE-NO-TEST` ignora los requisitos obsoletos · P

- **Estado:** `[x]`
- **Requisitos:** R004
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_trace.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:** en `analyze`, `sin_test` excluye los IDs de `obsolete` (D3). Pasa `test_F003_R004_obsoleto_no_da_error_en_tarea_cerrada`: una tarea cerrada que cita un obsoleto sin prueba y un vigente con prueba no produce `E-DONE-NO-TEST`, y una que cita un vigente sin prueba sí lo produce. El selftest completo pasa.

### T002 — `next-req` a partir de los requisitos declarados · P

- **Estado:** `[x]`
- **Requisitos:** R003
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:** `cmd_next_req` usa `parse_spec(...)["requirements"]` (D2). Pasa `test_F003_R003_siguiente_id_ignora_menciones`: con R001–R006 declarados y el texto citando R007 y R009, `next-req` imprime `R007`; con R001–R005 y R005 obsoleto, imprime `R006`; con requisitos declarados solo como encabezados `## R001` a `## R003`, imprime `R004`. El selftest completo pasa.

### T003 — Auditoría de los artefactos de todas las features · P

- **Estado:** `[x]`
- **Requisitos:** R001, R002
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `guard_bash` guarda `all_approvals(root)` con clave `slug/archivo`, y `cmd_audit` compara y restaura por esa clave sin resolver la feature activa. `phase_approvals` desaparece (D1).
  - Pasan `test_F003_R001_auditoria_revierte_otra_feature`, con tres casos:
    - la 002 activa y un comando aprueba el `spec.md` de la 001: vuelve a Draft, con aviso y exit 2;
    - el puntero cambia a la 001, se aprueba su `plan.md` y el puntero se restaura: vuelve a su valor;
    - se reescribe la huella de un artefacto aprobado: se recupera la anterior.
  - Pasa `test_F003_R002_auditoria_silenciosa_sin_cambios`: con varias features y un comando que no toca nada, exit 0, stderr vacío y artefactos byte a byte iguales; en un repo sin `specs/`, exit 0 sin escribir nada; con un artefacto ilegible (no UTF-8 o sin permiso de lectura), la compuerta y la auditoría terminan sin excepción y siguen protegiendo los demás.
  - Sigue pasando la prueba de auditoría de la feature 002, y el selftest completo pasa.

### T004 — Atribución por función de prueba en Python

- **Estado:** `[x]`
- **Requisitos:** R005, R006, R007
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_trace.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - Antes de tocar el código se guarda en el scratchpad la salida de `sdd.py trace --json` de la feature 001.
  - `python_test_spans` y la rama `.py` de `scan_tests` hacen lo que dice D4, con la atribución anterior como respaldo cuando `ast.parse` falla.
  - Pasan estas pruebas:
    - `test_F003_R005_cita_fuera_de_prueba_no_cuenta`: una llamada desde `main()` y un comentario de módulo no son evidencia ni se atribuyen a otra prueba;
    - `test_F003_R006_nombre_y_cuerpo_cuentan`: una prueba con aserción y un método de clase con comentario cuentan a nombre de esa prueba;
    - `test_F003_R007_otros_lenguajes_identicos`: reutiliza `OTROS_LENGUAJES` y `ESPERADO` con evidencia exacta;
    - `test_F003_R006_python_sin_ast_usa_la_atribucion_anterior`: un archivo Python que `ast.parse` rechaza sigue dando la evidencia de su prueba, sin excepción.
  - La lista de pruebas de cada requisito MUST de la feature 001 es idéntica a la guardada antes del cambio, y se documenta en el reporte de la tarea.
  - El selftest completo pasa, y `trace` de la feature 002 no tiene `E-REQ-NO-TEST`.

### T005 — README y cierre

- **Estado:** `[x]`
- **Requisitos:** R001, R005
- **Depende de:** T001, T002, T003, T004
- **Archivos:** `plugins/sdd/README.md`
- **Hecho cuando:**
  - El README ya no dice que la auditoría solo vigila la feature activa.
  - Documenta dos límites de la auditoría: la reversión de aprobaciones traídas por git y los artefactos nuevos ya aprobados.
  - Dice que en Python solo cuentan como evidencia el nombre y el cuerpo de una prueba.
  - `python3 scripts/validate.py --strict` y los dos selftests pasan, y `sdd.py trace` de la feature 003 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T003, T005 |
| R002 | T003 |
| R003 | T002 |
| R004 | T001 |
| R005 | T004, T005 |
| R006 | T004 |
| R007 | T004 |

> Todo requisito MUST debe tener al menos una tarea.
