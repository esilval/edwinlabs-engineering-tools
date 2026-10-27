# Tasks: plugin operate: preparación operativa e incidentes con postmortems

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-27  |
| Estado | Approved · c14c39f8f141       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F011_R004_umbral_sin_cifra`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Las pruebas de `operate` viven en `plugins/operate/tests/selftest.py`, sobre
`releases/`, `architecture/` y `specs/` escritos en el formato de cada plugin.
Las del traspaso, en `plugins/sdd/tests/selftest.py`.

## Tareas

### T001 — Esqueleto de `operate`, lectura de los otros plugins y prefijos

- **Estado:** `[x]`
- **Requisitos:** R003, R011, R015
- **Depende de:** —
- **Archivos:** `plugins/operate/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/operate/scripts/operate_sources.py`, `plugins/operate/skills/check/SKILL.md`, `plugins/operate/tests/selftest.py`, `plugins/sdd/docs/standards-roadmap.md`
- **Hecho cuando:**
  - El plugin existe con su `plugin.json` y su entrada en el catálogo (D1).
  - `*-PREP-*` e `*-INCIDENT-*` están reservados en el registro antes de usarse.
  - `operate_sources.py` sigue D3, con el comentario que nombra los originales.
  - Pasa `test_F011_R003_contrato_con_los_demas`, frente a los `release.py`, `architecture.py`, `discovery.py` y `sdd.py` reales:
    - versión aprobada vista como publicada, y editada como cambiada;
    - arquitectura aprobada vista aprobada, con atributos y motivos;
    - `Origen` y citas de ADR de una feature, y qué spec cita cada acción.
  - La skill `/operate:check` existe (la exige `validate.py --strict`), y `python3 scripts/validate.py --strict` pasa.

### T002 — Registro de incidentes y `check` `P`

- **Estado:** `[x]`
- **Requisitos:** R006, R007, R016, R017
- **Depende de:** T001
- **Archivos:** `plugins/operate/scripts/operate.py`, `plugins/operate/templates/incident.md`, `plugins/operate/tests/selftest.py`
- **Hecho cuando:**
  - `incident` sigue D2 y D6: registro que solo crece, incidente con sus huecos.
  - `check` sigue D5, con `FINDINGS`, `operate.check/v1`, `--check` y el 2 de uso incorrecto.
  - Están `E-INCIDENT-RELEASE`, `E-INCIDENT-TEMPLATE` y `W-INCIDENT-NOT-APPROVED` (borrador).
  - Pasan estas pruebas:
    - `test_F011_R006_registro_de_incidentes`: I001, I002 borrado → I003; los huecos;
    - `test_F011_R007_version_inexistente`: 0.9.0 inexistente nombra I001 y 0.9.0;
    - `test_F011_R016_check_en_ci`;
    - `test_F011_R017_sin_los_demas` (incidente sin `releases/`, versión `desconocida`).
  - El selftest compara los códigos declarados con los probados.

### T003 — Acciones del postmortem

- **Estado:** `[x]`
- **Requisitos:** R008, R015
- **Depende de:** T002
- **Archivos:** `plugins/operate/scripts/operate.py`, `plugins/operate/tests/selftest.py`
- **Hecho cuando:**
  - `next-action` sigue D6, y están `E-INCIDENT-ACTION-ID` y `W-INCIDENT-ACTION-NO-FEATURE` (D5).
  - Pasan estas pruebas:
    - `test_F011_R008_acciones`: siguiente acción libre, no se renumera al editar ni al borrar otra; repetida o de otro incidente da error;
    - `test_F011_R015_accion_sin_feature`: aviso para I001-A2 y ninguno para I001-A1.

### T004 — `prepare` y la plantilla de preparación `P`

- **Estado:** `[x]`
- **Requisitos:** R001, R002, R017
- **Depende de:** T001
- **Archivos:** `plugins/operate/scripts/operate.py`, `plugins/operate/templates/preparation.md`, `plugins/operate/tests/selftest.py`
- **Hecho cuando:**
  - `prepare` y el artefacto siguen D2 y D6, con `E-PREP-RELEASE` y `E-PREP-TEMPLATE`.
  - Pasan estas pruebas:
    - `test_F011_R001_borrador_de_preparacion`: nombra 008 y 009, con sus apartados; una segunda llamada no cambia nada;
    - `test_F011_R002_version_no_publicada`: borrador e inexistente, sin crear nada;
    - una ampliación de `test_F011_R017_sin_los_demas`: sin `architecture/`, una señal con huecos y ningún hallazgo de arquitectura.

### T005 — Señales desde la arquitectura, umbral y disparador

- **Estado:** `[ ]`
- **Requisitos:** R003, R004, R005
- **Depende de:** T004
- **Archivos:** `plugins/operate/scripts/operate.py`, `plugins/operate/tests/selftest.py`
- **Hecho cuando:**
  - Las señales propuestas siguen D4, y están `E-PREP-SIGNAL-THRESHOLD` y `E-PREP-ROLLBACK-TRIGGER` (D5).
  - Pasan estas pruebas:
    - `test_F011_R003_senales_de_la_arquitectura`: Q1 por objetivo, Q2 por ADR del plan, Q3 sin señal; arquitectura sin aprobar, sin propuesta;
    - `test_F011_R004_umbral_sin_cifra`: nombra la señal;
    - `test_F011_R005_sin_disparador`.

### T006 — `approve` y cambios tras aprobar

- **Estado:** `[ ]`
- **Requisitos:** R009, R010, R011
- **Depende de:** T003, T005
- **Archivos:** `plugins/operate/scripts/operate.py`, `plugins/operate/tests/selftest.py`
- **Hecho cuando:**
  - `approve` sigue D8: se niega sin cambiar nada; si aprueba, sella y, en una preparación, reescribe la huella de la versión.
  - Están `W-PREP-NOT-APPROVED`, `W-PREP-RELEASE-CHANGED` y el aviso de cambio de `W-INCIDENT-NOT-APPROVED`.
  - Pasan estas pruebas:
    - `test_F011_R009_no_se_aprueba_incompleto`: preparación con señal sin umbral y postmortem con causas sin completar;
    - `test_F011_R010_aprobacion`: preparación y postmortem;
    - `test_F011_R011_cambio_tras_aprobar`: postmortem editado y versión cambiada.

### T007 — Guardrails de `operate`

- **Estado:** `[ ]`
- **Requisitos:** R012
- **Depende de:** T006
- **Archivos:** `plugins/operate/scripts/operate.py`, `plugins/operate/hooks/hooks.json`, `plugins/operate/tests/selftest.py`, `plugins/sdd/scripts/sdd_bash.py`, `plugins/discovery/scripts/discovery.py`, `plugins/architecture/scripts/architecture.py`, `plugins/release/scripts/release.py`
- **Hecho cuando:**
  - `guard` y `audit` siguen D8, con el escape `OPERATE_BYPASS=1`.
  - El analizador es la quinta copia. Las cinco se nombran entre sí; en los otros cuatro plugins solo cambian comentarios.
  - Pasa `test_F011_R012_guardrails`:
    - deniega Write/Edit que aprueban una preparación o un incidente;
    - deniega `operate.py approve` ejecutado y no lo bloquea si solo se menciona (lista `MENCIONES`/`EJECUCIONES` común);
    - la auditoría revierte, también sin `operations/` al empezar;
    - escape y fallo abierto;
    - nunca devuelve `allow`;
    - `hooks.json` en forma exec con timeout.
  - Pasan los cinco selftests.

### T008 — El traspaso a `sdd` desde una acción

- **Estado:** `[ ]`
- **Requisitos:** R013, R014, R018
- **Depende de:** T006
- **Archivos:** `plugins/sdd/scripts/sdd.py`, `plugins/sdd/scripts/sdd_operate.py`, `plugins/sdd/skills/specify/SKILL.md`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `sdd.py new I001-A2` sigue D7 y «Contratos», y `sdd_operate.py` nombra su original.
  - `/sdd:specify` documenta el traspaso desde una acción.
  - Pasan en el selftest de `sdd`:
    - `test_F011_R013_feature_desde_accion`: Tipo corrección, problema y contexto del incidente, `| Origen | I001-A2 · 0.4.0 |`;
    - `test_F011_R014_traspaso_denegado`: sin aprobar o cambiado, acción inexistente, acción con feature (la nombra);
    - `test_F011_R018_sin_registro_igual`;
    - `test_F011_R013_contrato_con_operate`, frente al `operate.py` real.
  - El selftest de `sdd` pasa entero.

### T009 — Skills, documentación y cierre

- **Estado:** `[ ]`
- **Requisitos:** R008, R012, R016
- **Depende de:** T007, T008
- **Archivos:** `plugins/operate/skills/prepare/SKILL.md`, `plugins/operate/skills/incident/SKILL.md`, `plugins/operate/skills/postmortem/SKILL.md`, `plugins/operate/skills/approve/SKILL.md`, `plugins/operate/skills/check/SKILL.md`, `plugins/operate/README.md`, `README.md`, `plugins/sdd/README.md`
- **Hecho cuando:**
  - Las skills siguen D9. `prepare`, `incident`, `postmortem` y `approve` llevan `disable-model-invocation`, y `approve` se ejecuta directamente.
  - `postmortem` pide cada acción con `next-action`.
  - El README de `operate` documenta:
    - los artefactos y los comandos, con sus salidas;
    - los códigos y la relación atributo–feature;
    - el traspaso a `sdd`;
    - los guardrails con su escape.
  - El README raíz incluye `operate` en la serie y en la instalación.
  - El README de `sdd` documenta el traspaso desde una acción.
  - `python3 scripts/validate.py --strict` y los cinco selftests pasan, y `sdd.py trace` de la feature 011 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T004 |
| R002 | T004 |
| R003 | T001, T005 |
| R004 | T005 |
| R005 | T005 |
| R006 | T002 |
| R007 | T002 |
| R008 | T003, T009 |
| R009 | T006 |
| R010 | T006 |
| R011 | T001, T006 |
| R012 | T007, T009 |
| R013 | T008 |
| R014 | T008 |
| R015 | T001, T003 |
| R016 | T002, T009 |
| R017 | T002, T004 |
| R018 | T008 |

> Todo requisito MUST debe tener al menos una tarea.
