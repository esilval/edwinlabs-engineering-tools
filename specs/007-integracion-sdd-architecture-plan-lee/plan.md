# Plan: integracion de sdd con architecture: el plan lee y comprueba la arquitectura

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-16         |
| Estado | Approved · 6db42968018a              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

Un módulo nuevo de `sdd`, `scripts/sdd_architecture.py`, lee `architecture/`
con una copia documentada del formato de `architecture`, contrastada con el
`architecture.py` real en una prueba de contrato. Sobre él se construyen cuatro
piezas:

- **Contexto para planificar:** dos subcomandos de `sdd.py`, `arch-context`
  (R002) y `propose-adr` (R006).
- **Trazabilidad:** cuatro códigos `*-PLAN-*` en `sdd_trace.py` (R003–R005).
- **Traspaso:** el modo traspaso de `sdd.py new` consulta la arquitectura
  (R007, R008).
- **Skills:** las de plan e implementación cuentan cuándo usarlo.

Todo se activa solo si existe `architecture/`. Sin ella, cada camino es el de hoy
(R001).

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Lo determinista vive en un script | sí | leer la arquitectura, numerar una propuesta, comprobar citas y alojar candidatas son código; las skills solo deciden qué es estructural y redactan |
| Plugins unidos solo por archivos | sí | `sdd` lee `architecture/` y escribe solo ADR propuestos; no importa ni ejecuta `architecture` (R009) |
| Código copiado entre plugins, referenciado y contrastado | sí | `sdd_architecture.py` nombra el original (`architecture.py`) y las demás copias de la huella. Su prueba de contrato aprueba una arquitectura con el `architecture.py` real. El original no se toca: `architecture` está fuera de alcance, y la regla solo exige el comentario en la copia |
| Cambiar el formato que lee otro plugin requiere aprobación | sí | leer `architecture/` y el grupo de componentes en `Origen` quedaron aprobados con la spec |
| Prefijos de hallazgo reservados | sí | los códigos nuevos usan `*-PLAN-*`, que es de `sdd`. `*-ARCH-*` es de `architecture` desde la feature 006 (D1) |
| Códigos y schemas como contrato | sí | cuatro códigos nuevos (aditivo) y ningún cambio en la forma de `sdd.trace/v1` |
| Python 3.8, solo biblioteca estándar | sí | — |
| El selftest cubre cada cambio | sí | pruebas `test_F007_RNNN_…`; los cuatro códigos nuevos entran en la cobertura de `test_trazabilidad` |
| Solo el usuario aprueba | sí | `propose-adr` escribe el ADR en `Proposed`; aprobarlo sigue siendo `/architecture:review`, protegido por el guardrail de `architecture` |

## Decisiones

### D1 — Códigos de `sdd` con prefijo `*-PLAN-*`, no `*-ARCH-*`

- **Contexto:** el documento de diseño de la serie nombraba `E-ARCH-UNDECIDED`
  y `E-ARCH-VIOLATION`. La feature 006 reservó `*-ARCH-*` para el plugin
  `architecture`, que ya emite `E-ARCH-REF-UNKNOWN`, `W-ARCH-NOT-APPROVED` y
  otros.
- **Decisión:** los hallazgos de esta feature los emite la trazabilidad de
  `sdd` sobre `plan.md`, así que van con su prefijo:

  | Código | Requisito | Qué |
  | ------ | --------- | --- |
  | `E-PLAN-ADR-UNKNOWN` | R003 | el plan cita un `ADR-NNNN` que no existe |
  | `E-PLAN-ADR-NOT-APPROVED` | R003 | el plan cita un ADR en `Draft`, `Proposed`, `Rejected` o cambiado tras aprobarse. Si está `Proposed`, el mensaje remite a `/architecture:review`. Se excluye el caso de R005 |
  | `W-PLAN-NO-ARCHITECTURE-CHECK` | R004 | hay `architecture/` y el plan no tiene la sección «Comprobación de arquitectura» |
  | `W-PLAN-ADR-SUPERSEDED` | R005 | un plan **aprobado** cita un ADR `Superseded by ADR-NNNN`; el mensaje nombra el sustituto |

  Un plan aprobado que cita un ADR que se sustituyó después recibe el aviso de
  R005 y no el error de R003. Así una feature ya cerrada no tumba la CI por una
  decisión que se tomó más tarde; un plan sin aprobar sí recibe el error.
- **Alternativas descartadas:**
  - *Usar `E-ARCH-*` desde `sdd`.* Dos plugins emitirían el mismo prefijo, y el
    registro común existe para evitarlo.
- **Consecuencias:** al cerrar, el documento de diseño se actualiza con los
  nombres reales.

### D2 — `sdd_architecture.py`: lectura de `architecture/`, copiada y contrastada

- **Contexto:** R002, R003, R005, R007, R008 y R009 necesitan los componentes,
  los ADR con su estado y los estándares. La constitución impide importar
  `architecture.py`.
- **Decisión:** un módulo de `sdd` que reutiliza `sdd_product.py`, del mismo
  plugin (huella, `section`, `parse_items`, `artifact_state`), y añade:
  - **componentes**, desde `components.md`: ID, título, responsabilidad y
    candidatas;
  - **ADR**, desde `architecture/adr/NNNN*.md`: estado (`draft`, `proposed`,
    `approved`, `stale`, `rejected`, `superseded`) y sustituto;
  - **estándares**, desde `standards.md`;
  - **aprobación del conjunto:** los cuatro artefactos y los ADR vigentes,
    aprobados y sin cambios;
  - el siguiente número de ADR, contando todos los archivos.

  El comentario de cabecera nombra `architecture.py` como original. La prueba de
  contrato del selftest de `sdd` aprueba una arquitectura con el
  `architecture.py` real, si `plugins/architecture` existe, y comprueba que
  `sdd_architecture` la da por aprobada, que ve sus componentes y ADR, y que una
  edición la deja cambiada.
- **Alternativas descartadas:**
  - *Ejecutar `architecture.py check --json`.* `sdd` no conoce la ruta del otro
    plugin (R009).
  - *Leer solo los ID con expresiones sueltas.* Haría falta el estado de cada
    ADR y de cada artefacto, que es justo la lógica de huella de la copia.
- **Consecuencias:** una tercera lectura del formato de `architecture`. Si ese
  formato cambia, la prueba de contrato falla en CI.

### D3 — `sdd.py arch-context [--json]` para el plan

- **Contexto:** R002. Sin un comando, la skill tendría que deducir sola qué
  componentes tocan a la feature.
- **Decisión:**
  - Con `architecture/`, el comando lee la fila `Origen` de la spec activa e
    imprime estas listas:
    - `components`: los que alojan su candidata. Si la feature no tiene
      candidata, todos, marcados como tales.
    - `adrs`: los aprobados y vigentes, con título y motivo. Los propuestos van
      aparte, como pendientes.
    - `standards`.
    - `approved`: si la arquitectura está aprobada.
  - Sin `architecture/`, imprime `{"architecture": false}` y sale con 0.
- **Alternativas descartadas:**
  - *Ampliar `sdd.py context`, que usa el hook de inicio de sesión.* Mezclaría
    el arranque de cada sesión con un contexto que solo necesita el plan.
- **Consecuencias:** `/sdd:plan` gana un paso: si el comando devuelve
  arquitectura, el plan parte de ella y añade la sección «Comprobación de
  arquitectura». La plantilla `plan.md` no cambia, porque sin arquitectura esa
  sección sería un hueco (R001).

### D4 — `sdd.py propose-adr "<título>"`

- **Contexto:** R006. La regla de frontera la aplica la skill, pero el número,
  el estado y el origen son deterministas.
- **Decisión:**
  - Requiere `architecture/`. Calcula `ADR-NNNN` con D2 y escribe
    `architecture/adr/NNNN-slug.md` con:
    - una copia de la plantilla de ADR de `architecture`, en
      `plugins/sdd/templates/adr.md`;
    - `| Estado | Proposed |`;
    - una fila `| Propuesto por | specs/<feature>/plan.md |`;
    - los huecos en cursiva para que la skill los rellene.
  - Imprime el ID y la ruta. La compuerta de `sdd` no lo bloquea, porque `*.md`
    está exento, y el guardrail de `architecture` permite `Proposed`.
- **Alternativas descartadas:**
  - *Que la skill copie la plantilla y numere a mano.* Repite el error que
    `next-id` evita: números reciclados.
- **Consecuencias:**
  - La plantilla de ADR queda copiada en `sdd`, con un comentario que nombra
    la original.
  - `architecture` lee la fila extra sin problema, porque `header_fields` es
    genérico.

### D5 — Traspaso con arquitectura

- **Contexto:** R007 y R008.
- **Decisión:** en `prepare_handoff`, después de comprobar el producto, si
  existe `architecture/`:
  - si la arquitectura no está aprobada o cambió, se niega y remite a
    `/architecture:approve`;
  - si la candidata no está en las candidatas de ningún componente, se niega
    y remite a `/architecture:init`, que redacta los componentes;
  - si no, `Origen` gana un cuarto grupo con los componentes, por ejemplo
    `B02 · G2 · D1§4 · C2`.

  Sin `architecture/`, `Origen` sigue con tres grupos (R001), y D4 de la
  feature 004 no cambia: se lee el primer elemento.
- **Alternativas descartadas:**
  - *Añadir también los ADR que afectan a la candidata.* No hay un criterio
    determinista para saber cuáles son. Se excluye en la spec, y el plan los
    cita.
- **Consecuencias:** el JSON de `new` gana `context.components`, aditivo.

### D6 — Skills

- **Decisión:**
  - **`skills/plan/SKILL.md`:** nuevo paso con `arch-context`. Para cada
    decisión que cumpla la regla de frontera y no esté cubierta por un ADR
    aprobado, la skill la propone con `propose-adr`, la redacta con el usuario
    y la cita en el plan. Avisa de que el plan no se podrá aprobar hasta que el
    usuario la revise (`/architecture:review`).
  - **`skills/implement/SKILL.md`:** en «Si la realidad contradice al plan»,
    lo mismo cuando la decisión es de arquitectura.
- **Alternativas descartadas:**
  - *Que el modelo apruebe la propuesta para no bloquear el plan.* Lo prohíben
    la constitución y el guardrail de `architecture`.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/sdd/scripts/sdd_architecture.py` (nuevo) | lectura de `architecture/` (D2) | R002, R003, R005, R007, R008, R009 |
| `plugins/sdd/scripts/sdd_trace.py` | cuatro códigos, ADR citados por el plan y sección de arquitectura (D1) | R003, R004, R005, R001 |
| `plugins/sdd/scripts/sdd.py` | `arch-context` (D3), `propose-adr` (D4) y traspaso con componentes (D5) | R002, R006, R007, R008, R001 |
| `plugins/sdd/templates/adr.md` (nuevo) | copia de la plantilla de ADR de `architecture` | R006 |
| `plugins/sdd/skills/plan/SKILL.md`, `plugins/sdd/skills/implement/SKILL.md` | D6 | R002, R006 |
| `plugins/sdd/tests/selftest.py` | pruebas `test_F007_RNNN_…`, prueba de contrato y códigos nuevos en la cobertura | R001–R009 |
| `plugins/sdd/README.md` | integración con `architecture` | R002, R006, R008 |

## Modelo de datos

- **`Origen` de la spec:** cuarto grupo opcional con los componentes
  (`B02 · G2 · D1§4 · C2`), solo con arquitectura.
- **ADR propuesto por `sdd`:** fila de cabecera `| Propuesto por | specs/…/plan.md |`.

## Contratos

- `sdd.py arch-context [--json]`: `{architecture, approved, components, adrs,
  proposed, standards}`. Sin `architecture/`, `{"architecture": false}`.
- `sdd.py propose-adr "<título>"`: imprime `{id, file}`. Sale con 1 si no hay
  `architecture/` y con 2 sin título.
- `sdd.trace/v1`: cuatro códigos nuevos y la misma forma.
- Lectura de `architecture/`: el formato de la feature 006, que pasa a ser
  contrato aprobado con esta spec.

## Estrategia de pruebas

Todas viven en `plugins/sdd/tests/selftest.py`.

| Requisito | Tipo de prueba | Qué cubre |
| --------- | -------------- | --------- |
| R001 | integración | sin `architecture/`: `trace --json` de un plan con o sin la sección da lo mismo que hoy; `new B02` da `Origen` de tres grupos; `arch-context` da `{"architecture": false}` |
| R002 | integración | `arch-context` de la feature de B02: C2, ADR-0001 y S1, sin ADR-0003 rechazada; la propuesta va aparte |
| R003 | integración | plan que cita ADR-0009, ADR-0004 propuesta y ADR-0001 aprobada |
| R004 | integración | con arquitectura y sin la sección: aviso; con la sección: ninguno |
| R005 | integración | plan aprobado que cita ADR-0002, sustituida después por ADR-0004: aviso que nombra ADR-0004 y ningún error |
| R006 | integración | `propose-adr` con ADR-0001 a ADR-0003: crea ADR-0004 `Proposed`, con «Propuesto por» y sin aprobar; sin `architecture/`, sale con 1 |
| R007 | integración | `new B02` con arquitectura aprobada: `Origen` con C2 |
| R008 | integración | B02 sin componente; arquitectura sin aprobar; arquitectura cambiada. Ninguno crea nada y el mensaje dice qué falta |
| R009 | integración | todo lo anterior sin importar `architecture`; la prueba de contrato con el `architecture.py` real se omite si no está |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| La copia del formato de `architecture` diverge | `sdd` ve aprobada una arquitectura que no lo está, o al revés | prueba de contrato en CI contra `architecture.py` |
| Un plan antiguo cita un ADR que luego se rechaza | error en CI para una feature cerrada | solo el caso de sustitución es aviso (D1); un rechazo posterior a la aprobación es raro y obliga a revisar la feature |
| La skill de plan propone de más (todo parece estructural) | ruido en `architecture` | la regla de frontera en la skill y la revisión del usuario, que puede rechazar |

## Trazabilidad

Los nueve requisitos MUST (R001–R009) aparecen en la tabla de componentes y en
la de pruebas.
