# Plan: traspaso de discovery a sdd: specify con un ID de candidata crea la spec desde el backlog aprobado

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-15         |
| Estado | Approved · 036fc7c682b6              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

`sdd.py new` decide el modo por su argumento. Si es un ID de candidata (`B03`)
y existe `product/backlog.md`, lee el producto con un módulo nuevo,
`sdd_product.py`, y comprueba que está aprobado. Después crea la spec con
Problema, Contexto, Alcance y la fila `Origen` ya rellenos, y devuelve en el
JSON el contexto que `/sdd:specify` debe leer para redactar los requisitos. En
cualquier otro caso hace exactamente lo de hoy. `sdd` no importa nada de
`discovery`: lee sus archivos con una copia de la parte del formato y de la
huella que necesita.

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Lo determinista vive en un script | sí | detección del ID, comprobación de aprobación, duplicados, dependencias y relleno de la spec están en `sdd.py` y `sdd_product.py`; la skill solo redacta requisitos con el contexto que le dan |
| Plugins unidos solo por archivos | sí | `sdd` lee `product/`; no importa ni ejecuta `discovery`. La huella y el formato que necesita son una copia documentada (D2) |
| Cambiar el formato que lee otro plugin requiere aprobación | sí | el formato del backlog y la fila `Origen` como contrato quedaron aprobados con la spec |
| Python 3.8, solo biblioteca estándar | sí | `re`, `hashlib`, `pathlib`, `json` |
| Solo el usuario aprueba | sí | el traspaso exige el producto aprobado por `/discovery:approve` y no aprueba nada; la spec nace en Draft |
| Códigos y schemas como contrato | sí | ningún código de hallazgo nuevo; la salida JSON de `sdd.py new` solo gana campos (aditivo) |
| El selftest cubre cada cambio | sí | pruebas `test_F005_RNNN_…` en el selftest de `sdd`, más una prueba de contrato contra el `discovery` real cuando está en el repo (D2) |

## Decisiones

### D1 — `sdd.py new` detecta la candidata; la skill no decide

- **Contexto:** R007 exige que todo siga igual sin backlog o con otra
  descripción. Decidir el modo en la skill dejaría la regla en un prompt.
- **Decisión:**
  - `sdd.py new <descripción>` entra en modo traspaso solo si la descripción
    completa, sin espacios alrededor, casa con `^[Bb]\d+$` y existe
    `product/backlog.md` en la raíz.
  - En ese modo, o crea la feature o sale con código 1 y un mensaje en stderr
    (R003–R005), sin crear nada.
  - En cualquier otro caso sigue el camino de hoy, línea por línea.
- **Alternativas descartadas:**
  - *Un flag `--from product/backlog.md#B03`*, como decía el documento de
    diseño. Obliga a la skill a decidir cuándo usarlo y no aporta nada cuando
    la raíz ya fija dónde está el backlog.
  - *Un subcomando nuevo.* Duplica la numeración y el puntero de feature
    activa que ya hace `new`.
- **Consecuencias:** una feature que de verdad se quisiera llamar «B03» en un
  repo con backlog ya no se puede crear con ese nombre. Es el supuesto de la
  spec.

### D2 — `sdd_product.py`: lectura mínima del producto, copiada y probada contra el original

- **Contexto:** R003 exige distinguir un artefacto aprobado de uno que cambió
  tras aprobarse. Eso requiere recalcular la huella de `discovery`, y la
  constitución prohíbe importarlo.
- **Decisión:** un módulo nuevo, `plugins/sdd/scripts/sdd_product.py`, con:
  - **Aprobación:** lee el Estado de la cabecera; `aprobado` significa
    `Approved · <huella>`, y `cambiado` significa huella distinta de la del
    contenido. Copia de `text_digest`, `content_digest`, `doc_status` y
    `_header_end` de `discovery.py`.
  - **Candidatas:** copia de `section` y `parse_items` para leer `## Candidatas`
    y sus campos (Estado, Objetivos, Origen, Problema, Resultado observable,
    Dentro, Fuera, Depende de). También lee los objetivos de `## Objetivos` del
    brief.
  - **Fuentes:** resuelve `D2§4.2` a `product/sources/D2-*.md` y la sección
    `4.2`.
  - Cada copia lleva un comentario que nombra su original, y `discovery.py`
    recibe un comentario recíproco en `content_digest`. Solo es un comentario:
    ni el formato ni los comandos de `discovery` cambian.
  - Una prueba de contrato, en el selftest de `sdd`, aprueba un producto con el
    `discovery.py` real si `plugins/discovery` existe en el repo, y comprueba
    que `sdd_product` lo da por aprobado y por cambiado al editarlo. Sin
    `discovery`, la prueba se omite.
- **Alternativas descartadas:**
  - *Ejecutar `discovery.py check --json`.* `sdd` no conoce su ruta: cada
    plugin solo ve su `${CLAUDE_PLUGIN_ROOT}`, y `discovery` puede no estar
    instalado.
  - *Comprobar solo que el Estado dice Approved.* No detecta un brief editado
    después de aprobarse (segundo criterio de R003).
  - *Mover la huella a un archivo común.* No hay paso de publicación que
    comparta código entre plugins.
- **Consecuencias:** el algoritmo de huella de `discovery` pasa a ser
  contrato. Si cambia, la prueba de contrato falla en CI.

### D3 — La spec se rellena por secciones y la fila `Origen` solo existe en el traspaso

- **Contexto:** R001 y R002 piden contenido y origen. R007 y R008 piden que las
  demás specs no cambien.
- **Decisión:**
  - Se parte de la plantilla de siempre. La spec toma el título de la
    candidata (`slugify` del título para el nombre) y se sustituye el cuerpo de
    tres secciones:
    - **Problema:** el campo Problema de la candidata.
    - **Contexto:** «Candidata B03 del backlog», cada objetivo citado con su
      título y su descripción del brief, y las secciones de origen.
    - **Alcance:** en Dentro, el Resultado observable y el campo Dentro; en
      Fuera, el campo Fuera.
  - Se inserta `| Origen | B03 · G2 · D2§4.2 |` tras la fila Issue.
  - Requisitos, Criterios y el resto quedan como en la plantilla, para
    `/sdd:specify`.
  - La plantilla `templates/spec.md` no cambia.
- **Alternativas descartadas:**
  - *Añadir `| Origen | — |` a la plantilla.* Cambiaría todas las specs
    nuevas, incluidas las que no vienen de `discovery` (R007).
  - *Dejar el contenido en un archivo aparte.* La spec es la fuente de verdad:
    el problema tiene que estar en ella.
- **Consecuencias:** las secciones rellenas ya no tienen texto en cursiva de
  plantilla, así que la compuerta las da por completas. Requisitos y Criterios
  siguen vacíos y la spec sigue sin poder aprobarse hasta que se redacten.

### D4 — Duplicados y dependencias se leen de las cabeceras de las specs

- **Contexto:** R005 y R009 necesitan saber qué candidatas tienen ya feature,
  sin modificar el backlog (non-goal).
- **Decisión:**
  - Se recorren `specs/*/spec.md` y se lee la fila `Origen` de la cabecera.
    Una candidata tiene feature si es el primer elemento del origen de alguna.
  - R005 niega y nombra la feature existente.
  - R009 añade a `warnings` del JSON cada candidata de «Depende de» sin
    feature, y la creación sigue adelante.
- **Alternativas descartadas:**
  - *Un registro en `.sdd/`.* Duplica una información que ya está en las specs
    y puede divergir de ellas.
- **Consecuencias:** borrar la fila `Origen` de una spec hace que su candidata
  parezca libre. Es el mismo grado de confianza que ya se deposita en el campo
  Estado.

### D5 — El JSON de `new` lleva el contexto, y la skill lo usa

- **Contexto:** R006 pide indicar qué leer para redactar los requisitos.
- **Decisión:**
  - En modo traspaso, el JSON añade tres campos:
    - `origin`: `{candidate, goals, sections}`;
    - `context`: la ruta del brief, los objetivos con su título, y por cada
      sección su archivo de `product/sources/` y su número;
    - `warnings`.
  - `skills/specify/SKILL.md` gana un paso: si el JSON trae `origin`, leer ese
    contexto, partir de las secciones ya rellenas sin reescribirlas desde cero,
    y redactar requisitos y criterios. Si trae `warnings`, mostrarlos.
- **Alternativas descartadas:**
  - *Que la skill busque sola el brief y las fuentes.* Deja en el prompt una
    resolución de referencias que el script ya sabe hacer.
- **Consecuencias:** la salida de `new` crece de forma aditiva. Los
  consumidores actuales leen solo `feature`, `dir`, `spec` y `next`.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/sdd/scripts/sdd_product.py` (nuevo) | lectura del producto: aprobación y huella, candidatas, objetivos, fuentes (D2) | R001, R002, R003, R004, R006 |
| `plugins/sdd/scripts/sdd.py` · `cmd_new` | detección del ID (D1), relleno y fila `Origen` (D3), duplicados y dependencias (D4), JSON ampliado (D5) | R001, R002, R003, R004, R005, R006, R007, R009 |
| `plugins/sdd/skills/specify/SKILL.md` | paso para el modo traspaso (D5) | R006 |
| `plugins/discovery/scripts/discovery.py` | solo un comentario recíproco en `content_digest` (D2) | R003 |
| `plugins/sdd/tests/selftest.py` | pruebas `test_F005_RNNN_…` y la prueba de contrato | R001–R009 |
| `plugins/sdd/README.md` | el traspaso: uso, negativas, origen y contrato con `discovery` | R001, R003 |

## Modelo de datos

- Cabecera de la spec: una fila nueva y opcional, `| Origen | <candidata> · <objetivos> · <secciones> |`,
  con los elementos separados por ` · `. Solo aparece en el traspaso.
- Salida JSON de `sdd.py new`: en el traspaso añade `origin`, `context` y
  `warnings`.

## Contratos

- **Entrada leída de `discovery`:** cabecera con `| Estado | Approved · <12 hex> |`.
  - `## Objetivos` en `product/brief.md` y `## Candidatas` en
    `product/backlog.md`, con ítems `### G1 — título` y `### B03 — título` y
    campos `- **Campo:** valor`.
  - Documentos en `product/sources/Dn-slug.md`.
  - La huella es la de `content_digest`: todo menos la fila Estado,
    normalizando espacios y quitando líneas vacías.
- **`sdd.py new` en modo traspaso:**
  - Si se crea la feature: exit 0 y JSON con `feature`, `dir`, `spec`, `next`,
    `origin`, `context` y `warnings`.
  - Si se niega: exit 1, stderr con el motivo, y ni directorio ni cambio de
    `.sdd/current`.

## Estrategia de pruebas

| Requisito | Tipo de prueba | Dónde vive |
| --------- | -------------- | ---------- |
| R001 | integración: producto aprobado con B03; `new B03` y `new b03` crean la spec con nombre del título, problema, resultado observable y alcance | `plugins/sdd/tests/selftest.py` |
| R002 | integración: la cabecera tiene `\| Origen \| B03 · G2 · D2§4.2 \|` | ídem |
| R003 | integración: backlog en Draft, brief editado tras aprobar; ninguno crea nada y el mensaje dice qué falta. Más la prueba de contrato con el `discovery.py` real | ídem |
| R004 | integración: B09 inexistente y B04 descartada | ídem |
| R005 | integración: una spec con origen B03 ya existe; el mensaje la nombra | ídem |
| R006 | integración: el JSON trae G2 con su título y `product/sources/D2-…md` con la sección 4.2 | ídem |
| R007 | integración: sin backlog, `new B03` crea `NNN-b03`; con backlog, `new "login con Google"` crea la feature de siempre, sin `Origen` | ídem |
| R008 | integración: `status`, `trace` y `approve` sobre una spec sin origen dan lo mismo que antes; las features 001–004 del repo no cambian de estado | ídem |
| R009 | integración: B05 depende de B03 sin feature; se crea y `warnings` nombra B03 | ídem |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| La copia de la huella diverge de `discovery` | Un producto aprobado parece cambiado, o al revés | La prueba de contrato contra el `discovery.py` real falla en CI; comentarios recíprocos en las dos copias |
| `discovery` cambia el formato de candidatas | El traspaso deja de leer campos | La constitución ya exige aprobación para cambiar ese formato; la prueba de contrato usa la plantilla real de `discovery` |
| Un campo de la candidata trae texto con aspecto de plantilla (`_…_`) | La compuerta tomaría la spec por incompleta | Es lo correcto: el backlog aprobado no debería tenerlo, y `/sdd:specify` lo corrige al redactar |

## Trazabilidad

Los ocho requisitos MUST (R001–R008) aparecen en la tabla de componentes y en
la de pruebas. R008 se cubre en la de pruebas: ningún componente cambia el
camino de una spec sin origen. R009 (SHOULD) está en las dos.
