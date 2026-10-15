# Tasks: arreglos de sdd: falsos positivos y fixtures como evidencia

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-15  |
| Estado | Approved · 1cbd1bd779ef       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F002_R001_fixture_en_cadena_no_cuenta`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Todas las pruebas viven en `plugins/sdd/tests/selftest.py`, como funciones
`test_F002_Rxxx_*` registradas en su `main()`.

## Tareas

### T001 — Mensaje de W-TEST-UNSCOPED con el ID real · P

- **Estado:** `[x]`
- **Requisitos:** R003
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_trace.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:** una prueba `test_R004_x` sin prefijo produce un `W-TEST-UNSCOPED` cuyo mensaje nombra R004 y no contiene «R001»; pasa `test_F002_R003_aviso_nombra_el_requisito`.

### T002 — Vista de código para archivos de prueba Python

- **Estado:** `[x]`
- **Requisitos:** R010, R002
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_trace.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:** `scan_tests` busca citas y declaraciones en una vista con los textos literales en blanco, calculada con `tokenize`; si el archivo no se tokeniza, usa el texto tal cual; pasan `test_F002_R001_fixture_en_cadena_no_cuenta` (también una cadena de varias líneas), `test_F002_R001_cita_en_texto_no_cuenta`, `test_F002_R002_nombre_y_comentario_cuentan` y `test_F002_R002_python_invalido_no_revienta`; el selftest de `sdd` entero pasa.

### T003 — Fuera de Python, el texto tal cual (redefinida tras retirar R001)

- **Estado:** `[~]`
- **Requisitos:** R010, R002
- **Depende de:** T002
- **Archivos:** `plugins/sdd/scripts/sdd_trace.py`, `plugins/sdd/tests/selftest.py`, `plugins/sdd/README.md`
- **Hecho cuando:** `code_view` devuelve las líneas tal cual en archivos que no son Python, y desaparecen el analizador por línea y sus patrones (`_blank_quotes`, `CALL_OPEN`, `RUBY_TITLE`); las pruebas `test_F002_R001_*` pasan a llamarse `test_F002_R010_*`; pasa `test_F002_R010_otros_lenguajes_como_antes`, en la que cuentan todas las citas que la revisión encontró perdidas (comentario `/* */` de varias líneas con apóstrofos, `xit` y `scenario` de RSpec, `@test` de Bats, nombre de Kotlin entre comillas invertidas, `DisplayName = "…"` de C#, ScalaTest, subprueba por tabla de Go, `it.only`, `test.each(…)(…)`, `t.Run` y `@DisplayName`); el README dice que las citas dentro de un texto solo dejan de contar en Python.

### T004 — Compuerta Bash por palabras del comando · P

- **Estado:** `[x]`
- **Requisitos:** R004, R005
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/sdd_bash.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:** `invokes_approve` solo da positivo si algún segmento del comando, o del contenido de una sustitución `$(…)` o con comillas invertidas, tiene una palabra cuyo nombre de archivo es `sdd.py` seguida de `approve`; si el comando no se puede analizar, da positivo solo si su texto contiene `sdd.py approve`; pasan `test_F002_R004_mencion_no_bloquea` (mensaje de commit, descripción de PR, heredoc a archivo, `echo`) y `test_F002_R005_ejecucion_bloquea` (relativo, ruta absoluta, encadenado tras `&&`, dentro de sustituciones y en un comando que no se puede analizar).

### T005 — Regresión de la auditoría y README

- **Estado:** `[x]`
- **Requisitos:** R006, R004
- **Depende de:** T004
- **Archivos:** `plugins/sdd/tests/selftest.py`, `plugins/sdd/README.md`
- **Hecho cuando:** pasa `test_F002_R006_auditoria_revierte_lo_que_la_compuerta_deja_pasar` (un comando que la compuerta ya no bloquea y que aprueba `spec.md` es revertido); el README dice que la compuerta reconoce la **ejecución** de `sdd.py approve` y que lo demás lo cubre la auditoría, documenta como límite conocido que la auditoría solo vigila la feature activa, y aclara que una cita a un requisito dentro de un texto (incluido un docstring) no cuenta como evidencia.

### T006 — Cierre sobre el caso real

- **Estado:** `[ ]`
- **Requisitos:** R010, R002
- **Depende de:** T003, T005
- **Archivos:** —
- **Hecho cuando:** `sdd.py trace --json` de la feature 001 no lista `plugins/sdd/tests/selftest.py` en la evidencia de R001 ni de R002 y no da errores; `sdd.py trace` de la feature 002 no da errores; `python3 scripts/validate.py --strict` y los selftests de los dos plugins pasan.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | — (obsoleto, reemplazado por R010) |
| R002 | T002, T003, T006 |
| R003 | T001 |
| R004 | T004, T005 |
| R005 | T004 |
| R006 | T005 |
| R010 | T002, T003, T006 |

> Todo requisito MUST debe tener al menos una tarea.
