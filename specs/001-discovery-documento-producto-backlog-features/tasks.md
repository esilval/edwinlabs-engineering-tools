# Tasks: discovery: de documento de producto a backlog de features

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-15  |
| Estado | Approved · 1e5b66ab5ad8       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F001_R001_rechaza_token_expirado`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Todas las pruebas viven en `plugins/discovery/tests/selftest.py`, como
funciones `test_F001_Rxxx_*` que usan el ayudante `expect(...)`.

## Tareas

### T001 — Esqueleto del plugin y CI

- **Estado:** `[~]`
- **Requisitos:** R010
- **Depende de:** —
- **Archivos:** `plugins/discovery/.claude-plugin/plugin.json`, `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`, `plugins/discovery/README.md`, `.claude-plugin/marketplace.json`, `.github/workflows/validate.yml`, `specs/constitution.md`
- **Hecho cuando:** `python3 scripts/validate.py --strict` da 2 plugins sin errores; `discovery.py` sin subcomando sale con 2 y muestra la ayuda; el ayudante de rutas rechaza escribir fuera de `product/` (`test_F001_R010_escritura_solo_en_product` pasa); el workflow ejecuta todo `plugins/*/tests/selftest.py`; la fila «Selftest de cada plugin en CI» de la constitución describe el recorrido automático y su suelo pasa a «2 de 2 plugins».

### T002 — Huella y campo Estado

- **Estado:** `[~]`
- **Requisitos:** R002, R011, R016
- **Depende de:** T001
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** existen las funciones de huella normalizada, lectura y escritura del Estado de cabecera, y la que dice si un artefacto aprobado cambió; `test_F001_R016_huella_ignora_formato` y `test_F001_R016_huella_detecta_cambio` pasan.

### T003 — Ingesta de Markdown

- **Estado:** `[ ]`
- **Requisitos:** R001, R002, R003
- **Depende de:** T002
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** `discovery.py ingest <md>` crea `product/sources/Dn-slug.md` con cabecera (Documento, Original, Ingesta, Huella original, Huella) y encabezados numerados; pasan `test_F001_R001_ids_correlativos`, `test_F001_R001_numeracion_anidada`, `test_F001_R001_h1_unico_es_titulo`, `test_F001_R001_sin_encabezados_es_una_seccion`, `test_F001_R002_duplicado_rechazado`, `test_F001_R003_formato_no_admitido`; en los rechazos, `product/` no cambia.

### T004 — Conversión de Word y registro del original · P

- **Estado:** `[ ]`
- **Requisitos:** R004
- **Depende de:** T003
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** un `.docx` fabricado en la prueba con estilos de título se ingiere con sus encabezados; `ingest <md> --original x.pdf` registra el nombre y la huella del PDF, calculada sobre sus bytes en bruto, sin normalizar; pasan `test_F001_R004_docx_convertido` y `test_F001_R004_original_registrado`.

### T005 — Skill ingest

- **Estado:** `[ ]`
- **Requisitos:** R001, R003, R004
- **Depende de:** T004
- **Archivos:** `plugins/discovery/skills/ingest/SKILL.md`
- **Hecho cuando:** la skill lleva `disable-model-invocation: true`, delega todo lo determinista en `discovery.py ingest`, describe la conversión de PDF por el modelo con `--original`, y `validate.py --strict` pasa.

### T006 — Plantillas, lectura de brief y backlog, y `next-id` · P

- **Estado:** `[ ]`
- **Requisitos:** R006, R007, R008
- **Depende de:** T002
- **Archivos:** `plugins/discovery/templates/brief.md`, `plugins/discovery/templates/backlog.md`, `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** se leen objetivos, candidatas (con sus campos), preguntas y descartes; `next-id G` y `next-id B` devuelven máximo + 1 contando las descartadas; pasan `test_F001_R006_lee_objetivos`, `test_F001_R007_lee_candidata_completa` y `test_F001_R008_next_id_no_reutiliza`.

### T007 — Preguntas abiertas

- **Estado:** `[ ]`
- **Requisitos:** R005, R009
- **Depende de:** T003, T006
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** `discovery.py questions` lista las preguntas abiertas con sus citas y señala las que citan documentos, secciones u objetivos inexistentes; pasan `test_F001_R005_lista_abiertas`, `test_F001_R005_respondida_no_cuenta` y `test_F001_R009_pregunta_cita_dos_documentos`.

### T008 — `check`: errores

- **Estado:** `[ ]`
- **Requisitos:** R008, R010, R011, R014
- **Depende de:** T007
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** `discovery.py check` informa `E-GOAL-NO-FEATURE`, `E-SOURCE-UNCOVERED`, `E-REF-UNKNOWN`, `E-BACKLOG-DEP-CYCLE`, `E-SOURCE-MODIFIED`, `E-BACKLOG-ID-GAP`, `E-BACKLOG-REQUIREMENT`, `E-QUESTION-OPEN-GOAL` y `E-PRODUCT-TEMPLATE`, con una prueba `test_F001_Rxxx_*` por código; un producto coherente no da errores.

### T009 — `check`: avisos, JSON y modo CI

- **Estado:** `[ ]`
- **Requisitos:** R012, R013
- **Depende de:** T008
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** se informan `W-FEATURE-NO-GOAL`, `W-FEATURE-NO-OUTCOME` y `W-QUESTION-OPEN`; `--json` emite `discovery.check/v1` con `code/severity/title/message` en cada hallazgo; `--check` sale con 1 si hay errores y con 0 si no; el selftest falla si un código declarado no se prueba; pasan `test_F001_R012_avisos`, `test_F001_R013_json_schema` y `test_F001_R013_check_exit`.

### T010 — `approve` y deriva tras aprobar

- **Estado:** `[ ]`
- **Requisitos:** R014, R016
- **Depende de:** T009
- **Archivos:** `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** `discovery.py approve` sella brief y backlog con `Approved · <huella>` solo si `check` no da errores, y `approve --skill` siempre sale con 0; si falta `brief.md` o `backlog.md`, `approve` se niega y lo dice, sin crear ninguno; tras un cambio de palabras, `check` informa `W-PRODUCT-NOT-APPROVED`; pasan `test_F001_R014_rechaza_sin_artefactos`, `test_F001_R014_rechaza_con_errores`, `test_F001_R014_rechaza_pregunta_sobre_objetivo`, `test_F001_R014_aprueba_coherente`, `test_F001_R016_cambio_invalida` y `test_F001_R016_reformateo_no_invalida`.

### T011 — Guard y auditoría de la aprobación

- **Estado:** `[ ]`
- **Requisitos:** R015
- **Depende de:** T010
- **Archivos:** `plugins/discovery/hooks/hooks.json`, `plugins/discovery/scripts/discovery.py`, `plugins/discovery/tests/selftest.py`
- **Hecho cuando:** el guard deniega un Write o Edit que aprueba `brief.md` o `backlog.md`, y un Bash que llama a `discovery.py approve`; nunca devuelve `allow`; no hace nada sin `product/` ni con `DISCOVERY_BYPASS=1`; la auditoría restaura un Estado cambiado por un comando opaco; pasan `test_F001_R015_guard_edit`, `test_F001_R015_guard_bash`, `test_F001_R015_auditoria_restaura` y `test_F001_R015_sin_product_no_opina`.

### T012 — Skills clarify y decompose

- **Estado:** `[ ]`
- **Requisitos:** R005, R006, R007, R009, R010
- **Depende de:** T007, T008
- **Archivos:** `plugins/discovery/skills/clarify/SKILL.md`, `plugins/discovery/skills/decompose/SKILL.md`
- **Hecho cuando:** ambas llevan `disable-model-invocation: true`; clarify presenta preguntas de pocas en pocas con su cita y las registra en el brief; decompose usa `next-id`, aplica el criterio de granularidad (valor observable, no capas), registra contradicciones como preguntas, prohíbe redactar requisitos y termina ejecutando `check`; `validate.py --strict` pasa.

### T013 — Skills check y approve

- **Estado:** `[ ]`
- **Requisitos:** R011, R014, R015
- **Depende de:** T010, T011
- **Archivos:** `plugins/discovery/skills/check/SKILL.md`, `plugins/discovery/skills/approve/SKILL.md`
- **Hecho cuando:** ambas llevan `disable-model-invocation: true`; approve ejecuta `discovery.py approve --skill` por inyección `` !`…` `` y prohíbe aprobar por otra vía; check explica cada error y no arregla nada por su cuenta; `validate.py --strict` pasa.

### T014 — Documentación y reserva de prefijos

- **Estado:** `[ ]`
- **Requisitos:** R011, R012, R013
- **Depende de:** T013
- **Archivos:** `plugins/discovery/README.md`, `README.md`, `plugins/sdd/docs/standards-roadmap.md`
- **Hecho cuando:** el README del plugin documenta comandos, artefactos, códigos de hallazgo, schema JSON, escapes y uso en CI; el README raíz lista el plugin; los prefijos `*-GOAL-*`, `*-SOURCE-*`, `*-REF-*`, `*-BACKLOG-*`, `*-FEATURE-*`, `*-QUESTION-*` y `*-PRODUCT-*` figuran reservados en §7; `sdd trace` de la feature no da errores.

### T015 — Aceptación en sesión real

- **Estado:** `[ ]`
- **Requisitos:** R005, R006, R007, R009
- **Depende de:** T014
- **Archivos:** `specs/001-discovery-documento-producto-backlog-features/acceptance.md`
- **Hecho cuando:** en una sesión de Claude Code con el plugin cargado se ejecuta el flujo completo sobre dos documentos de ejemplo, el segundo contradiciendo al primero; `acceptance.md` anota, por cada criterio de R005, R006, R007 y R009, si se cumplió y la evidencia (cita del brief o del backlog generado); ningún criterio queda sin resultado.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T003, T005 |
| R002 | T002, T003 |
| R003 | T003, T005 |
| R004 | T004, T005 |
| R005 | T007, T012, T015 |
| R006 | T006, T012, T015 |
| R007 | T006, T012, T015 |
| R008 | T006, T008 |
| R009 | T007, T012, T015 |
| R010 | T001, T008, T012 |
| R011 | T002, T008, T013, T014 |
| R012 | T009, T014 |
| R013 | T009, T014 |
| R014 | T008, T010, T013 |
| R015 | T011, T013 |
| R016 | T002, T010 |

> Todo requisito MUST debe tener al menos una tarea.
