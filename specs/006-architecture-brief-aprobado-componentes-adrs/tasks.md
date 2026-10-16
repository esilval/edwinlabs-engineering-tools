# Tasks: architecture: de brief aprobado a componentes, ADRs y estandares

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-10-16  |
| Estado | Approved · e6cb1a4dd3ce       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F006_R001_init_sin_producto_aprobado`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

Salvo que se diga otra cosa, el código vive en
`plugins/architecture/scripts/architecture.py` y las pruebas en
`plugins/architecture/tests/selftest.py`, como funciones `test_F006_Rxxx_*`. Los
productos de prueba se construyen a mano en el formato de `discovery`: la prueba
de contrato es la única que ejecuta `discovery.py`.

## Tareas

### T001 — Esqueleto del plugin y reserva de prefijos

- **Estado:** `[x]`
- **Requisitos:** R008, R015
- **Depende de:** —
- **Archivos:** `plugins/architecture/.claude-plugin/plugin.json`, `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`, `plugins/architecture/README.md`, `.claude-plugin/marketplace.json`, `plugins/sdd/docs/standards-roadmap.md`
- **Hecho cuando:**
  - Existe el plugin con su `plugin.json` y su entrada en el marketplace.
  - `architecture.py` tiene la tabla de subcomandos, el fallo abierto para los hooks y el docstring de uso. Sin subcomando, sale con 2.
  - El selftest arranca, comprueba la cobertura de los códigos declarados (vacía de momento) y lo recoge el bucle de CI.
  - El registro de prefijos reserva `*-ARCH-*`, `*-ADR-*`, `*-QUALITY-*`, `*-COMPONENT-*` y `*-STANDARD-*` para `architecture` (D7).
  - Pasa `test_F006_R015_no_importa_otros_plugins`: el script y el selftest no importan `discovery`, `sdd` ni `sdd_product`.
  - `python3 scripts/validate.py --strict` da 3 plugins y 0 errores, y los tres selftests pasan.

### T002 — Lectura del producto e `init`

- **Estado:** `[x]`
- **Requisitos:** R001, R015
- **Depende de:** T001
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/templates/{quality,components,standards,questions,adr}.md`, `plugins/architecture/tests/selftest.py`, `plugins/discovery/scripts/discovery.py` (solo comentario)
- **Hecho cuando:**
  - Hay una copia documentada de la huella y del formato del producto: aprobación, objetivos, restricciones y candidatas con estado (D5), con comentarios recíprocos.
  - `init` copia las plantillas a `architecture/`. Si el producto falta, no está aprobado o cambió, se niega con exit 1 y sin crear nada.
  - Pasan estas pruebas:
    - `test_F006_R001_init_sin_producto_aprobado`: backlog en Draft, brief cambiado y sin `product/`; los mensajes nombran el artefacto y `/discovery:approve`, o `discovery`;
    - `test_F006_R001_init_crea_las_plantillas`;
    - `test_F006_R015_contrato_con_discovery`: un producto aprobado con el `discovery.py` real se reconoce como aprobado, y como cambiado tras editarlo. Se omite si no está.

### T003 — Lectura de los artefactos de arquitectura y `next-id`

- **Estado:** `[ ]`
- **Requisitos:** R003, R005
- **Depende de:** T002
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - Se leen los atributos, componentes, ADR (estado, motivo, sustituye y secciones), estándares y preguntas de D1.
  - `next-id Q|C|S|ADR` da el siguiente ID sin reciclar; `ADR` cuenta todos los archivos de `adr/`, también los rechazados.
  - Pasan estas pruebas:
    - `test_F006_R003_lee_componentes_y_candidatas`: C1 con su responsabilidad y B01, B02;
    - `test_F006_R005_numeracion_no_reutiliza`: con 0001 y 0002 rechazada, el siguiente es ADR-0003.

### T004 — Comprobación de atributos y componentes · P

- **Estado:** `[ ]`
- **Requisitos:** R002, R004
- **Depende de:** T003
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `check` emite `E-QUALITY-NOT-MEASURABLE`, `E-QUALITY-NO-MOTIVE`, `E-COMPONENT-NO-RESPONSIBILITY` y `E-COMPONENT-CANDIDATE-UNPLACED` según D3.
  - Pasan estas pruebas:
    - `test_F006_R002_atributo_no_medible_o_sin_motivo`: también acepta un motivo que cita una restricción del brief;
    - `test_F006_R004_candidata_sin_componente`: error por B02 y ninguno por B03, que está descartada.

### T005 — Comprobación de decisiones, estándares, citas y preguntas · P

- **Estado:** `[ ]`
- **Requisitos:** R005, R006, R007, R009
- **Depende de:** T003
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `check` emite estos códigos según D3: `E-ADR-INCOMPLETE`, `E-ADR-NO-MOTIVE`, `E-ADR-ID-DUPLICATE`, `E-STANDARD-NO-ADR`, `E-ARCH-REF-UNKNOWN`, `E-ARCH-OPEN-QUESTION` y `E-ARCH-TEMPLATE`.
  - Pasan estas pruebas:
    - `test_F006_R005_adr_incompleto_o_sin_motivo`, que incluye un número duplicado;
    - `test_F006_R006_estandar_sin_decision`;
    - `test_F006_R007_citas_inexistentes`: B09 y ADR-0009 se nombran en el mensaje;
    - `test_F006_R009_pregunta_abierta_bloquea`: la pregunta sobre ADR-0002 da error; una respondida no lo da.

### T006 — Contrato de `check` y cobertura de códigos

- **Estado:** `[ ]`
- **Requisitos:** R008
- **Depende de:** T004, T005
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `check` tiene salida legible, `--json` (`architecture.check/v1`) y `--check`; un argumento desconocido sale con 2.
  - Pasa `test_F006_R008_check_en_ci`: con un error, `--check` sale con 1; con solo avisos, con 0; cada hallazgo trae `code`, `severity`, `message` y `artifact`.
  - La comprobación de cobertura del selftest exige una prueba para cada código declarado hasta ahora.

### T007 — Aprobación, cambios tras aprobar y huella del producto

- **Estado:** `[ ]`
- **Requisitos:** R009, R010, R011, R014
- **Depende de:** T006
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `approve [--skill]` sigue D4: se niega si hay errores o el producto no está aprobado; escribe la fila `Producto`; sella el conjunto y los ADR en `Draft`, y no toca los `Proposed`, `Rejected` ni `Superseded`.
  - `check` emite `W-ARCH-NOT-APPROVED` y `W-ARCH-PRODUCT-CHANGED`.
  - Pasan estas pruebas:
    - `test_F006_R010_aprueba_el_conjunto`, con su negativa con errores;
    - `test_F006_R009_pregunta_abierta_impide_aprobar`: `approve` se niega y el mensaje nombra la pregunta sobre ADR-0002;
    - `test_F006_R011_cambio_tras_aprobar`: la edición se nombra y el reformateo no cuenta;
    - `test_F006_R014_producto_cambiado`: backlog reaprobado con una candidata nueva; avisa del cambio y da error por la candidata sin componente.

### T008 — Revisión de decisiones propuestas

- **Estado:** `[ ]`
- **Requisitos:** R013
- **Depende de:** T007
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `review ADR-NNNN aceptar|rechazar [--skill]` sigue D4: solo acepta ADR `Proposed` sin errores propios, y marca el sustituido.
  - Pasa `test_F006_R013_revision`, con cuatro casos:
    - aceptar;
    - rechazar, conservando el número;
    - sustituir: 0004 aprobada y 0002 `Superseded by ADR-0004`, sin contar como cambiada;
    - negativa con un ADR que no está propuesto, y con uno que sustituye a un ADR no aprobado.

### T009 — Guardrails

- **Estado:** `[ ]`
- **Requisitos:** R012
- **Depende de:** T003
- **Archivos:** `plugins/architecture/scripts/architecture.py`, `plugins/architecture/hooks/hooks.json`, `plugins/architecture/tests/selftest.py`
- **Hecho cuando:**
  - `guard` y `audit` siguen D6, con la copia del analizador de comandos y comentarios que nombran las otras copias.
  - `hooks.json` está en forma exec, con `timeout`.
  - Pasan estas pruebas:
    - `test_F006_R012_guard_escrituras`: Write y Edit a `Approved`, `Rejected` o `Superseded`, o con la huella reescrita, se deniegan; a `Draft` y `Proposed`, no;
    - `test_F006_R012_guard_comandos`: las listas de menciones y de ejecuciones, equivalentes a las de `discovery`;
    - `test_F006_R012_auditoria_revierte`: un `bash -c` que aprueba un ADR se revierte con exit 2;
    - `test_F006_R012_escape_y_nunca_allow`: `ARCHITECTURE_BYPASS=1`, y sin `architecture/` no hace nada.

### T010 — Skills

- **Estado:** `[ ]`
- **Requisitos:** R001, R009, R010, R013
- **Depende de:** T007, T008, T009
- **Archivos:** `plugins/architecture/skills/{init,decide,check,approve,review}/SKILL.md`
- **Hecho cuando:**
  - Las cinco skills existen según D8.
  - `approve` y `review` tienen `disable-model-invocation: true` y ejecutan el script por inyección.
  - `init` y `decide` aplican la regla de frontera y piden escenarios con estímulo, respuesta y medida.
  - `decide` deja en `questions.md` lo que el producto no decide.
  - `python3 scripts/validate.py --strict` pasa.

### T011 — README y cierre

- **Estado:** `[ ]`
- **Requisitos:** R012, R015
- **Depende de:** T010
- **Archivos:** `plugins/architecture/README.md`
- **Hecho cuando:**
  - El README documenta el flujo, los artefactos, los códigos, la aprobación y la revisión.
  - También documenta los guardrails con su escape, la independencia de los demás plugins y el contrato con `discovery`.
  - `validate --strict` y los tres selftests pasan, y `sdd.py trace` de la feature 006 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T002, T010 |
| R002 | T004 |
| R003 | T003 |
| R004 | T004 |
| R005 | T003, T005 |
| R006 | T005 |
| R007 | T005 |
| R008 | T001, T006 |
| R009 | T005, T007, T010 |
| R010 | T007, T010 |
| R011 | T007 |
| R012 | T009, T011 |
| R013 | T008, T010 |
| R014 | T007 |
| R015 | T001, T002, T011 |

> Todo requisito MUST debe tener al menos una tarea.
