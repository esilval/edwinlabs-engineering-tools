# Plan: architecture: de brief aprobado a componentes, ADRs y estandares

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-16         |
| Estado | Approved · 160f9ffc338d              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

Un tercer plugin, `plugins/architecture/`, con la forma de `discovery`:
- un script determinista, `scripts/architecture.py`, que crea los artefactos,
  numera, comprueba, aprueba, revisa decisiones y protege la aprobación;
- skills que redactan con el usuario;
- hooks que impiden que el modelo apruebe.

Los artefactos viven en `architecture/` del proyecto, en Markdown, con el mismo
`| Estado | Approved · <huella> |` y el mismo patrón `- **Campo:** valor` que
el resto de la serie. El producto de `discovery` se lee con una copia
documentada de su formato y de su huella, contrastada con el `discovery.py`
real en una prueba de contrato, como ya hace `sdd`.

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Lo determinista vive en un script | sí | IDs, comprobaciones, huellas, aprobación, revisión y guardrails están en `architecture.py`; las skills solo redactan y preguntan |
| Cada plugin es una etapa unida por archivos | sí | lee `product/` y escribe solo en `architecture/`; no importa `discovery` ni `sdd` (D5) |
| Un guardrail falla abierto y tiene escape | sí | errores inesperados del hook dejan pasar; escape `ARCHITECTURE_BYPASS=1`, documentado en el README y en cada denegación |
| Un guardrail nunca concede permisos | sí | el hook solo deniega o calla; el selftest lo comprueba |
| Solo el usuario aprueba | sí | `approve` y `review` solo los lanzan skills con `disable-model-invocation`; el modelo no puede escribir los estados que decide el usuario (D6) |
| Python 3.8, solo biblioteca estándar | sí | por eso los estándares van en Markdown y no en YAML (D2) |
| Estructura de plugin y hooks en forma exec con `timeout` | sí | `.claude-plugin/plugin.json`, `skills/`, `hooks/hooks.json`, `scripts/`, `templates/`, `tests/selftest.py`, `README.md`; entrada en `marketplace.json` |
| Selftest en CI y todo código de hallazgo alcanzable | sí | `plugins/architecture/tests/selftest.py`, recogido por el bucle de CI; comprueba que cada código declarado se prueba |
| Prefijos de hallazgo reservados antes de usarse | sí, con un cambio de registro | el registro está en `plugins/sdd/docs/standards-roadmap.md` §7. `*-ARCH-*` figura allí para la fase 3 de `sdd`; el diseño de la serie lo asigna a `architecture`, que es quien define capas y dependencias (D7). Es un cambio solo de documentación en un archivo de `sdd`, el único que esta feature toca fuera de su plugin |
| Cambiar el formato que lee otro plugin requiere aprobación | sí | los formatos de `architecture/` son nuevos; su contrato con `sdd` llega en la feature siguiente. Leer `product/` ya está aprobado como contrato |
| Selftest «2 de 2 plugins» en Comprobación | pendiente del usuario | pasa a 3 de 3; se actualiza con `/sdd:constitution` al cerrar la feature, porque solo el usuario cambia la constitución |

## Decisiones

### D1 — Cinco artefactos en `architecture/`, todos Markdown con Estado y huella

- **Contexto:** la spec pide atributos, componentes, decisiones, estándares y
  preguntas, y que todos se aprueben y detecten cambios.
- **Decisión:**

  | Archivo | Contenido | Ítems |
  | ------- | --------- | ----- |
  | `quality.md` | Atributos de calidad | `### Q1 — título`, con `Escenario` y `Motivo` |
  | `components.md` | Componentes | `### C1 — nombre`, con `Responsabilidad` y `Candidatas`; la cabecera lleva además la fila `Producto` (D4) |
  | `adr/NNNN-slug.md` | Una decisión por archivo | Cabecera con `Estado`, `Motivo` y `Sustituye`; secciones `## Contexto`, `## Decisión`, `## Alternativas descartadas` y `## Consecuencias` |
  | `standards.md` | Estándares comprobables | `### S1 — regla`, con `Tipo` (capas, dependencia, prohibida), `Detalle` y `Decisión` |
  | `questions.md` | Preguntas | `- [ ] (ADR-0002; Q1) ¿…?`, como el brief de `discovery` |

  - IDs: `Q1`, `C1` y `S1` crecen sin reciclarse; las decisiones son
    `ADR-0001`, con cuatro dígitos, y `next-id` cuenta todos los archivos de
    `adr/`, también los rechazados (R005).
  - Cada artefacto lleva `| Estado | … |` en su cabecera y la huella del
    contenido sin esa fila, con el mismo algoritmo que `discovery`.
- **Alternativas descartadas:**
  - *Todo en un solo `architecture.md`.* Una decisión cambiaría la huella de
    todo el conjunto, y el documento de diseño ya fija un ADR por archivo.
  - *Preguntas dentro de `quality.md`.* Mezcla lo decidido con lo pendiente.
- **Consecuencias:**
  - Cinco formatos que `sdd` leerá en la feature siguiente, que pasan a ser
    contrato desde ese momento.
  - Responder una pregunta cambia `questions.md` y obliga a reaprobar, igual
    que en `discovery`.

### D2 — Estándares en `standards.md`, no en `standards.yaml`

- **Contexto:** el documento de diseño nombra `standards.yaml`. La
  constitución exige solo biblioteca estándar, y Python no trae un parser de
  YAML.
- **Decisión:** `standards.md`, con ítems `### S1` y campos fijos que el
  script lee como el resto de artefactos.
  - `Tipo` admite `capas`, `dependencia` o `prohibida`.
  - `Detalle` admite `C1 → C2` para una dirección de dependencia, o una lista
    de capas o de dependencias prohibidas.
  - `Decisión` cita el ADR del que sale (R006).
- **Alternativas descartadas:**
  - *Un subconjunto de YAML con parser propio.* Es un parser frágil para un
    formato que la gente escribe a mano.
  - *JSON.* No tiene cabecera de Estado, y sellarlo exigiría otro mecanismo de
    huella.
- **Consecuencias:** el documento de diseño se actualiza al cerrar la feature
  (`standards.yaml` → `standards.md`).

### D3 — Comprobaciones y códigos

- **Contexto:** R002–R009, R011 y R014 se resuelven con hallazgos estables
  (R008).
- **Decisión:** `architecture.py check [--json] [--check]`, con schema
  `architecture.check/v1`. Los códigos son estos, y `E-` hace fallar `--check`:

  | Código | Requisito | Qué |
  | ------ | --------- | --- |
  | `E-QUALITY-NOT-MEASURABLE` | R002 | el escenario no contiene ninguna cifra |
  | `E-QUALITY-NO-MOTIVE` | R002 | `Motivo` no cita un objetivo `Gn` del brief ni la sección de origen (`Dn§x`) de una de sus restricciones |
  | `E-COMPONENT-NO-RESPONSIBILITY` | R003 | componente sin responsabilidad |
  | `E-COMPONENT-CANDIDATE-UNPLACED` | R004 | candidata vigente sin componente; las descartadas no cuentan |
  | `E-ADR-INCOMPLETE` | R005 | falta contexto, decisión, alternativas o consecuencias |
  | `E-ADR-NO-MOTIVE` | R005 | `Motivo` no cita ningún `Qn`, `Gn` ni sección de restricción `Dn§x` |
  | `E-ADR-ID-DUPLICATE` | R005 | dos archivos con el mismo número |
  | `E-STANDARD-NO-ADR` | R006 | estándar sin decisión de origen |
  | `E-ARCH-REF-UNKNOWN` | R007 | cita a un `ADR-`, `Q`, `C`, `G` o `B` inexistente |
  | `E-ARCH-OPEN-QUESTION` | R009 | pregunta abierta que cita un ADR o un atributo |
  | `E-ARCH-TEMPLATE` | R002–R006 | huecos de plantilla sin rellenar |
  | `W-ARCH-NOT-APPROVED` | R011 | artefacto sin aprobar o cambiado tras aprobarse; el mensaje nombra cuál |
  | `W-ARCH-PRODUCT-CHANGED` | R014 | el brief o el backlog cambiaron desde la aprobación de la arquitectura |

  Que un escenario sea «medible» se reduce a que contenga una cifra. Es una
  heurística determinista; el juicio fino queda para la skill y el usuario.

  **Cómo se cita una restricción.** En el brief, las restricciones son
  viñetas sin ID, y cada una lleva entre paréntesis la sección de documento de
  la que sale (`- Datos solo en la UE (D1§5)`). Un `Motivo` cita la restricción
  por esa sección (`Motivo: D1§5`), y `check` la acepta si alguna viñeta de
  `## Restricciones` del brief cita esa misma sección. Un objetivo se cita por
  su ID (`G2`). La misma regla vale para el `Motivo` de un ADR, que además
  admite atributos (`Q1`).
- **Alternativas descartadas:**
  - *Medibilidad por lista de palabras vagas.* No detecta un escenario sin
    cifra que no use ninguna palabra de la lista.
  - *Citar la restricción por su texto literal.* Una errata o un cambio de
    redacción en el brief rompería la cita, y comparar texto libre es frágil.
  - *Dar IDs a las restricciones (`K1`).* Cambia el formato del brief, y
    `discovery` queda fuera de alcance.
- **Consecuencias:** trece códigos nuevos, que pasan a ser contrato público.

### D4 — Aprobación del conjunto, revisión de decisiones y la huella del producto

- **Contexto:** R010, R011, R013 y R014.
- **Decisión:**
  - **`approve`:** se niega si `check` da errores (y con eso si hay una
    pregunta que bloquea) o si el producto no está aprobado. Si no se niega,
    escribe en la cabecera de `components.md` la fila
    `| Producto | brief <huella> · backlog <huella> |` y sella con
    `Approved · <huella>`:
    - `quality.md`, `components.md`, `standards.md` y `questions.md`;
    - cada ADR en `Draft`;
    - cada ADR aprobado que cambió después de aprobarse. Si no, un ADR aprobado
      que se edita quedaría en aviso para siempre: `review` solo decide
      propuestos, y el resto del conjunto sí se vuelve a sellar al editarlo.
    Los ADR `Proposed`, `Rejected` o `Superseded` no se tocan.
  - **`review ADR-NNNN aceptar|rechazar`:** solo para ADR `Proposed`. Aceptar
    exige que ese ADR no tenga errores propios. Lo sella y, si su campo
    `Sustituye` cita un ADR, pasa ese a `Superseded by ADR-NNNN`. Si el ADR
    citado no está aprobado (borrador, propuesto, rechazado o ya sustituido),
    la revisión se niega y lo nombra.
    Rechazar lo deja en `Rejected` y conserva su número.
  - La huella excluye la fila Estado. Por eso un ADR sustituido conserva su
    contenido, y deja de contar como aprobado sin contar como cambiado.
  - `check` compara la fila `Producto` con las huellas actuales del brief y el
    backlog (R014).
- **Alternativas descartadas:**
  - *Aprobar cada artefacto por separado.* Una arquitectura medio aprobada no
    le sirve a `sdd`, y la spec pide el conjunto.
  - *Guardar las huellas del producto en `.architecture/`.* Un archivo fuera
    del conjunto aprobado podría cambiar sin dejar rastro.
- **Consecuencias:** un `review` cambia la arquitectura aprobada sin
  reaprobar el resto, porque solo toca el ADR revisado y el que sustituye.

### D5 — Leer el producto: tercera copia del formato de `discovery`, con prueba de contrato

- **Contexto:** R001 y R015. `sdd_product.py` ya copia el formato y la
  huella de `discovery`, y la constitución impide compartir código.
- **Decisión:**
  - `architecture.py` lleva su propia copia del formato y la huella:
    aprobación, objetivos, restricciones y candidatas con su estado. El
    comentario de cabecera nombra el original y la otra copia, y `discovery.py`
    gana una mención a esta.
  - `init` comprueba el producto y se niega con un mensaje que nombra el
    artefacto y `/discovery:approve` (R001), o que pide pasar por `discovery`
    si no hay `product/`. Si no se niega, copia las plantillas a
    `architecture/`.
  - La prueba de contrato del selftest aprueba un producto con el
    `discovery.py` real cuando está en el repositorio, y se omite si no está.
- **Alternativas descartadas:**
  - *Reutilizar `sdd_product.py`.* `architecture` dependería de `sdd`
    instalado (R015).
  - *Pedir a `discovery` que exporte un JSON.* Cambiaría `discovery`, y eso
    está fuera de alcance.
- **Consecuencias:** tres copias de la huella de `discovery`. Las tres pruebas
  de contrato fallan en CI si cambia el algoritmo.

### D6 — Guardrails: copia del de `discovery`, extendida a los estados que decide el usuario

- **Contexto:** R012. `discovery` ya resuelve el mismo problema con un guard,
  una auditoría y el analizador de comandos que copió de `sdd`.
- **Decisión:**
  - **`guard` (PreToolUse sobre Write, Edit y Bash):** deniega una escritura en
    `architecture/` que lleve un Estado a `Approved`, `Rejected` o
    `Superseded`, o que reescriba una huella. Deniega también un comando que
    **ejecute** `architecture.py approve` o `review`, detectado con la copia del
    analizador por palabras.
  - El modelo sí puede escribir `Draft` y `Proposed`.
  - **`audit` (PostToolUse sobre Bash):** toma una instantánea del Estado de
    todos los artefactos, incluidos todos los ADR. Revierte los cambios hacia
    un estado que decide el usuario y avisa con exit 2.
  - Escape: `ARCHITECTURE_BYPASS=1`. Sin `architecture/`, los hooks no hacen
    nada.
- **Alternativas descartadas:**
  - *Hooks compartidos entre plugins.* Prohibidos por la constitución, y cada
    plugin tiene que funcionar solo.
- **Consecuencias:** una cuarta copia del analizador. El comentario de
  cabecera nombra las otras, y el selftest usa las mismas listas de menciones y
  ejecuciones.

### D7 — Prefijos de hallazgo

- **Decisión:** se reservan `*-ARCH-*`, `*-ADR-*`, `*-QUALITY-*`,
  `*-COMPONENT-*` y `*-STANDARD-*` para `architecture` en el registro común.
  La fila `*-ARCH-*` pasa de «fase 3 de `sdd`» al plugin, porque las capas y
  la dirección de dependencias son ahora decisiones de arquitectura (estándares
  de tipo `capas` y `dependencia`).
- **Alternativas descartadas:**
  - *Un prefijo nuevo, como `*-ARCHITECTURE-*`.* Contradice el documento de
    diseño, que ya usa `E-ARCH-*` para la integración con `sdd`.
- **Consecuencias:** la fase 3 de la hoja de ruta de `sdd` queda para la
  feature de integración, que comprobará los estándares desde `/sdd:plan`.

### D8 — Skills

- **Decisión:**

  | Skill | Quién la lanza | Qué hace |
  | ----- | -------------- | -------- |
  | `/architecture:init` | el usuario | ejecuta `init`; después redacta atributos desde las restricciones y objetivos del brief, y componentes con las candidatas del backlog |
  | `/architecture:decide` | el usuario | redacta los ADR que cumplen la regla de frontera y los estándares que se derivan de ellos, y deja en `questions.md` lo que el producto no decide |
  | `/architecture:check` | cualquiera | ejecuta `check` y lo explica |
  | `/architecture:approve` | solo el usuario (`disable-model-invocation`) | aprueba el conjunto por inyección |
  | `/architecture:review` | solo el usuario | `review ADR-NNNN aceptar\|rechazar` |

- **Alternativas descartadas:**
  - *Una sola skill que lo haga todo.* Mezcla «qué partes hay» con «qué
    tecnología se usa», y son conversaciones distintas con el usuario.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/architecture/scripts/architecture.py` (nuevo) | `init`, `next-id`, `check`, `approve`, `review`, `guard`, `audit`, y la lectura de `product/` | R001–R015 |
| `plugins/architecture/templates/` (nuevo) | `quality.md`, `components.md`, `standards.md`, `questions.md` y `adr.md` | R002, R003, R005, R006, R009 |
| `plugins/architecture/skills/{init,decide,check,approve,review}/SKILL.md` (nuevo) | D8 | R001, R009, R010, R013 |
| `plugins/architecture/hooks/hooks.json` (nuevo) | guard y audit, en forma exec con `timeout` | R012 |
| `plugins/architecture/.claude-plugin/plugin.json`, `README.md` (nuevos) | metadatos y documentación | R012, R015 |
| `.claude-plugin/marketplace.json` | entrada del plugin | R015 |
| `plugins/architecture/tests/selftest.py` (nuevo) | pruebas `test_F006_RNNN_…`, prueba de contrato y cobertura de códigos | R001–R015 |
| `plugins/discovery/scripts/discovery.py` | solo comentario: menciona la copia en `architecture.py` | R015 |
| `plugins/sdd/docs/standards-roadmap.md` | registro de prefijos (D7), solo documentación | R008 |

## Modelo de datos

Los cinco formatos de D1. En la cabecera de `components.md`, además,
`| Producto | brief <huella> · backlog <huella> |`. Los estados posibles de un
ADR son `Draft`, `Proposed`, `Approved · <huella>`, `Rejected` y
`Superseded by ADR-NNNN`.

## Contratos

- `architecture.py check --json`: schema `architecture.check/v1`, con
  `{schema, ok, counts, findings: [{code, severity, message, artifact}]}`,
  la misma forma que `discovery.check/v1`.
- Salida de los comandos:
  - `--check`: 1 si hay errores;
  - `approve` y `review`: 1 si se niegan; con `--skill`, siempre 0 y el
    resultado por stdout;
  - `init`: 1 si se niega.
- Lectura de `product/`: el contrato ya aprobado con `discovery`.

## Estrategia de pruebas

Todas viven en `plugins/architecture/tests/selftest.py`.

| Requisito | Tipo de prueba | Qué cubre |
| --------- | -------------- | --------- |
| R001 | integración | `init` con backlog en Draft, con brief cambiado y sin `product/`: no crea nada y el mensaje nombra lo que falta |
| R002 | integración | escenario sin cifra y atributo sin motivo |
| R003 | integración | componente con responsabilidad y candidatas |
| R004 | integración | B02 sin componente da error y B03 descartada no |
| R005 | integración | numeración tras un rechazado, ADR incompleto, ADR sin motivo y número duplicado |
| R006 | integración | estándar sin ADR |
| R007 | integración | citas a B09 y a ADR-0009 |
| R008 | integración | `--check` con error y con solo avisos; forma del JSON |
| R009 | integración | pregunta abierta sobre ADR-0002: no se aprueba y se nombra |
| R010 | integración | aprobación coherente sellada y negativa con errores |
| R011 | integración | edición tras aprobar y reformateo sin cambios |
| R012 | integración | guard con Write, Edit y Bash; listas de menciones y ejecuciones; auditoría con `bash -c`; escape; nunca `allow` |
| R013 | integración | aceptar, rechazar y sustituir |
| R014 | integración | backlog reaprobado con una candidata nueva |
| R015 | integración | todo lo anterior corre sin importar `discovery` ni `sdd`, con `product/` construido a mano; la prueba de contrato contra el `discovery.py` real se omite si no está |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| La copia de la huella de `discovery` diverge | El producto aprobado parece no aprobado | Prueba de contrato en CI; comentarios recíprocos |
| La heurística de «medible» deja pasar escenarios pobres | Atributos con una cifra irrelevante | La skill pide escenarios con estímulo, respuesta y medida; el usuario aprueba |
| El plugin es grande para una sola feature | Revisiones largas | Tareas pequeñas por comando y por requisito; `sdd` integra en la feature siguiente |
| Cuarta copia del analizador de comandos | Un arreglo en una copia no llega a las otras | Comentarios recíprocos y listas de casos equivalentes en los selftests |

## Trazabilidad

Los catorce requisitos MUST (R001–R013 y R015) aparecen en la tabla de
componentes y en la de pruebas. R014 (SHOULD) también está en las dos.
