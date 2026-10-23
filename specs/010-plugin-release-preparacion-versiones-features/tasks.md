# Tasks: plugin release: preparación de versiones con features elegidas

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-22  |
| Estado | Approved · 0bfac69cf5db       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F010_R007_numero_propuesto`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Las pruebas de `release` viven en `plugins/release/tests/selftest.py`, sobre
features de prueba escritas en el formato de `sdd`. Las de `sdd`, en
`plugins/sdd/tests/selftest.py`.

## Tareas

### T001 — `sdd`: fila `Tipo` en la spec `P`

- **Estado:** `[x]`
- **Requisitos:** R017
- **Depende de:** —
- **Archivos:** `plugins/sdd/templates/spec.md`, `plugins/sdd/skills/specify/SKILL.md`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - La plantilla de spec tiene `| Tipo   | funcionalidad |` tras `Estado`.
  - La skill dice cuándo cambiarlo a `corrección` (D5).
  - Pasa `test_F010_R017_tipo` en el selftest de `sdd`:
    - `sdd.py new` crea la spec con `Tipo` en `funcionalidad`;
    - el traspaso desde una candidata la conserva junto a `Origen`;
    - la fila no es un hueco de plantilla.
  - El selftest de `sdd` pasa entero.

### T002 — `sdd`: `trace --feature`

- **Estado:** `[x]`
- **Requisitos:** R018
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `trace --feature <NNN|NNN-slug>` sigue D4 y «Contratos»: con `--json` y `--check`, sin tocar `.sdd/current`.
  - Pasa `test_F010_R018_trace_de_otra_feature`:
    - con la 002 activa, `--feature 001` da el mismo JSON que con la 001 activa, y `.sdd/current` no cambia;
    - `--feature 042` sale con 1 y nombra 042.
  - El docstring de `sdd.py` documenta la opción.

### T003 — `release`: esqueleto y lectura de `specs/` `P`

- **Estado:** `[ ]`
- **Requisitos:** R002, R003, R006, R017
- **Depende de:** —
- **Archivos:** `plugins/release/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/release/scripts/release_specs.py`, `plugins/release/tests/selftest.py`
- **Hecho cuando:**
  - El plugin existe con su `plugin.json` y su entrada en el catálogo (D1).
  - `release_specs.py` sigue D3, con el comentario que nombra los originales de `sdd`.
  - El selftest lleva:
    - los fixtures de features en formato `sdd`;
    - una prueba de lectura;
    - la prueba de contrato `test_F010_R002_contrato_con_sdd`, que compara la lectura con el `sdd.py` real (fases aprobadas, spec cambiada tras aprobar y estados de tareas `[~]`/`[x]`).
  - `python3 scripts/validate.py --strict` pasa.

### T004 — `release.py check`: comprobaciones de features y CI

- **Estado:** `[ ]`
- **Requisitos:** R002, R003, R006, R014, R017
- **Depende de:** T003
- **Archivos:** `plugins/release/scripts/release.py`, `plugins/release/tests/selftest.py`
- **Hecho cuando:**
  - `check` sigue D7, con la lectura de `releases/*.md` (cabecera de D2), `FINDINGS`, `release.check/v1` y `--check`.
  - Incluye los códigos de R002, R003, R006 y R017, y `E-RELEASE-NO-FEATURES`.
  - Pasan estas pruebas:
    - `test_F010_R002_fases_sin_aprobar`;
    - `test_F010_R003_tareas_abiertas`;
    - `test_F010_R006_ya_publicada_o_inexistente`;
    - `test_F010_R017_tipo` (`release`);
    - `test_F010_R014_check_en_ci`.
  - El selftest compara los códigos declarados con los probados.

### T005 — Trazabilidad desde `release`

- **Estado:** `[ ]`
- **Requisitos:** R004, R005, R016
- **Depende de:** T002, T004
- **Archivos:** `plugins/release/scripts/release.py`, `plugins/release/tests/selftest.py`
- **Hecho cuando:**
  - La búsqueda de `sdd.py` y la lectura de `sdd.trace/v1` siguen D4.
  - Pasan estas pruebas:
    - `test_F010_R004_trazabilidad_con_errores` (un `sdd.py` falso con `SDD_SCRIPT`);
    - `test_F010_R005_adr_no_aprobado`;
    - `test_F010_R016_sin_trazabilidad`;
    - una ampliación de la prueba de contrato: el `trace --feature` real del repositorio se lee sin aviso.

### T006 — El número de versión

- **Estado:** `[ ]`
- **Requisitos:** R007, R008
- **Depende de:** T004
- **Archivos:** `plugins/release/scripts/release.py`, `plugins/release/tests/selftest.py`
- **Hecho cuando:**
  - La propuesta y las validaciones siguen D6.
  - Pasan estas pruebas:
    - `test_F010_R007_numero_propuesto`: 0.1.0, 0.3.2 → 0.4.0, 1.4.0 → 2.0.0, 0.x con obsoleto, 0.4.0 → 0.4.1 y spec sin `Tipo`;
    - `test_F010_R008_numero_invalido`: 0.3.9 tras 0.4.0, repetido, mal formado y distinto del archivo.

### T007 — `release.py new` y la plantilla

- **Estado:** `[ ]`
- **Requisitos:** R001, R009, R010, R015
- **Depende de:** T005, T006
- **Archivos:** `plugins/release/scripts/release.py`, `plugins/release/templates/release.md`, `plugins/release/tests/selftest.py`
- **Hecho cuando:**
  - `new` y el artefacto siguen D2 y D8, con `E-RELEASE-TEMPLATE` sobre los huecos.
  - Pasan estas pruebas:
    - `test_F010_R001_borrador`: con features, sin features, `--version` y un archivo que ya existe;
    - `test_F010_R009_notas_y_cambios`: los huecos citan B01 y G1, y los cambios técnicos traen los requisitos, ADR-0001, contratos y modelo de datos;
    - `test_F010_R015_sin_producto_ni_arquitectura`.

### T008 — `release.py approve` y cambios tras aprobar

- **Estado:** `[ ]`
- **Requisitos:** R010, R011, R012
- **Depende de:** T007
- **Archivos:** `plugins/release/scripts/release.py`, `plugins/release/tests/selftest.py`
- **Hecho cuando:**
  - `approve` sigue D8: se niega sin cambiar nada; si aprueba, reescribe la Comprobación, sella y muestra `git tag`.
  - Pasan estas pruebas:
    - `test_F010_R010_no_se_aprueba_incompleta`: con huecos y con errores;
    - `test_F010_R011_aprobacion`, que también comprueba que la versión anterior pasa a ser `Anterior` en la siguiente;
    - `test_F010_R012_cambio_tras_aprobar`.

### T009 — Guardrails de `release`

- **Estado:** `[ ]`
- **Requisitos:** R013
- **Depende de:** T008
- **Archivos:** `plugins/release/scripts/release.py`, `plugins/release/hooks/hooks.json`, `plugins/release/tests/selftest.py`, `plugins/sdd/scripts/sdd_bash.py`, `plugins/discovery/scripts/discovery.py`, `plugins/architecture/scripts/architecture.py`
- **Hecho cuando:**
  - `guard` y `audit` siguen D8, con el escape `RELEASE_BYPASS=1`.
  - El analizador de comandos es la copia de `architecture.py`. Las cuatro copias se nombran entre sí; en los otros tres plugins solo cambian comentarios.
  - Pasa `test_F010_R013_guardrails`:
    - deniega un Write o Edit que aprueba;
    - deniega `release.py approve` ejecutado y no lo bloquea si solo se menciona (con la misma lista `MENCIONES`/`EJECUCIONES` que `architecture`);
    - la auditoría revierte;
    - funcionan el escape y el fallo abierto;
    - nunca devuelve `allow`;
    - `hooks.json` registra los hooks en forma exec con timeout.
  - Pasan los cuatro selftests.

### T010 — Skills, documentación y cierre

- **Estado:** `[ ]`
- **Requisitos:** R001, R009, R011, R014
- **Depende de:** T009
- **Archivos:** `plugins/release/skills/new/SKILL.md`, `plugins/release/skills/check/SKILL.md`, `plugins/release/skills/approve/SKILL.md`, `plugins/release/README.md`, `README.md`, `plugins/sdd/README.md`, `plugins/sdd/docs/standards-roadmap.md`
- **Hecho cuando:**
  - Las skills siguen D9. `new` y `approve` llevan `disable-model-invocation`, y `approve` se ejecuta directamente.
  - El README de `release` documenta el artefacto, los comandos, los códigos, el número de versión, la trazabilidad y los guardrails.
  - El README raíz incluye `release` en la serie y en la instalación.
  - El README de `sdd` documenta `--feature` y `Tipo`.
  - El registro reserva `*-RELEASE-*`.
  - `python3 scripts/validate.py --strict` y los cuatro selftests pasan, y `sdd.py trace` de la feature 010 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T007, T010 |
| R002 | T003, T004 |
| R003 | T003, T004 |
| R004 | T005 |
| R005 | T005 |
| R006 | T003, T004 |
| R007 | T006 |
| R008 | T006 |
| R009 | T007, T010 |
| R010 | T007, T008 |
| R011 | T008, T010 |
| R012 | T008 |
| R013 | T009 |
| R014 | T004, T010 |
| R015 | T007 |
| R016 | T005 |
| R017 | T001, T003, T004 |
| R018 | T002 |

> Todo requisito MUST debe tener al menos una tarea.
