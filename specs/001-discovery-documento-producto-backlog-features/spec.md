# Spec: discovery: de documento de producto a backlog de features

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `001-discovery-documento-producto-backlog-features`     |
| Fecha  | 2026-10-15     |
| Estado | Approved · 870215cf23e4        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

Quien diseña un producto lo describe en documentos (PRD, brief, notas de
iteraciones con otras personas), pero el flujo SDD empieza en `/sdd:specify`
con una frase por feature. Cada vez que se arranca una feature, el modelo
reconstruye el contexto explorando el repo: a quién le duele, qué entra, con
qué choca. Lo inventa o lo omite, y nada comprueba que el conjunto de features
cubra lo que los documentos pedían.

Le duele al autor del producto en cada documento nuevo que escribe y en cada
feature que arranca.

## Contexto

- El plugin `sdd` existe y cubre de la spec al código. Este plugin, `discovery`,
  es la etapa anterior de una serie (`discovery` → `architecture` → `sdd` →
  `release` → `operate`) unida por archivos.
- El diseño completo, con sus decisiones D1–D7 y las respuestas a las preguntas
  abiertas, está en el documento «discovery — diseño de un plugin previo a
  SDD» (claude.ai/code/artifact/b65d6dd1-a884-4977-998e-8115d7b2ab9c).
- Decisiones tomadas por el usuario que esta spec da por fijas:
  - La unidad es el **producto**: un solo brief y un solo backlog, que crecen con
    documentos que llegan a lo largo del tiempo.
  - Los documentos los escribe el usuario. Las preguntas de aclaración van a él
    y no se exportan a terceros.
  - Markdown es el formato principal; PDF y Word se aceptan convirtiéndolos.
- La constitución del repo exige: plugin independiente que funcione sin los
  demás, unión solo por archivos, lo determinista en scripts, aprobación solo
  por el usuario, guardrails que fallan abiertos y con escape.

## Alcance

### Dentro

- Ingerir documentos de producto (`/discovery:ingest`), con secciones citables.
- Aclarar huecos, contradicciones y supuestos con el usuario (`/discovery:clarify`).
- Descomponer los documentos en brief y backlog de features candidatas
  (`/discovery:decompose`).
- Comprobar la coherencia del producto, también en CI (`/discovery:check`).
- Aprobar brief y backlog, solo por el usuario (`/discovery:approve`).

### Fuera (non-goals)

- **El handoff a `sdd`** (`/discovery:handoff`, crear una spec desde una
  candidata). Requiere cambios en `sdd`; es una feature aparte.
- **Detectar qué candidatas afecta un documento editado.** Los documentos
  ingeridos no se editan: un cambio entra como documento nuevo. Esta feature solo
  detecta que un documento ingerido se modificó (R011).
- La integración con `architecture`, que aún no existe.
- Escribir o editar los documentos de producto.
- Estimaciones, puntos, priorización por puntuación, sprints.
- Sincronizar con Jira, Linear o GitHub Issues.
- Google Docs y formatos distintos de Markdown, PDF y Word.
- Redactar requisitos EARS: siguen siendo trabajo de `/sdd:specify`.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO el usuario ingiere un documento Markdown, el sistema DEBERÁ añadirlo al producto con el siguiente identificador libre (D1, D2…) y numerar sus secciones para que se puedan citar (D2§4.2). |
| R002 | MUST | SI el contenido del documento a ingerir es idéntico al de uno ya ingerido, ENTONCES el sistema DEBERÁ rechazarlo indicando el documento que coincide, sin modificar el producto. |
| R003 | MUST | SI el documento a ingerir no es Markdown, PDF ni Word, ENTONCES el sistema DEBERÁ rechazarlo sin modificar el producto. |
| R004 | SHOULD | CUANDO el usuario ingiere un PDF o un Word, el sistema DEBERÁ convertirlo a Markdown y registrar el nombre del original y la fecha de ingesta. |
| R005 | MUST | CUANDO el usuario pide aclarar el producto, el sistema DEBERÁ presentarle los huecos, contradicciones y supuestos de los documentos como preguntas que citan su sección de origen, y registrar cada pregunta y su respuesta en el brief. |
| R006 | MUST | CUANDO el usuario descompone el producto, el sistema DEBERÁ crear o actualizar el brief con objetivos numerados (G1, G2…), usuarios, glosario, restricciones e invariantes propuestos para la constitución. |
| R007 | MUST | CUANDO el usuario descompone el producto, el sistema DEBERÁ crear o actualizar el backlog con features candidatas numeradas (B01, B02…), cada una con objetivos, secciones de origen, problema, resultado observable, alcance dentro y fuera, dependencias y estado. |
| R008 | MUST | CUANDO se descompone un producto que ya tiene backlog, el sistema DEBERÁ conservar los identificadores de las candidatas existentes y no reutilizar nunca un identificador, tampoco el de una candidata descartada. |
| R009 | MUST | SI un documento contradice a otro ya ingerido, ENTONCES el sistema DEBERÁ registrar la contradicción como pregunta abierta que cita ambas secciones, sin resolverla. |
| R010 | MUST | El sistema NO DEBERÁ redactar requisitos verificables en el brief ni en el backlog, ni modificar artefactos de otras etapas, como `specs/` o la constitución. |
| R011 | MUST | CUANDO el usuario comprueba el producto, el sistema DEBERÁ informar como error: un objetivo sin candidata; una sección de documento sin objetivo, candidata ni descarte explícito; una referencia a un documento, sección, objetivo o candidata inexistentes; una dependencia circular entre candidatas; y un documento modificado después de ingerirse. |
| R012 | SHOULD | CUANDO el usuario comprueba el producto, el sistema DEBERÁ informar como aviso una candidata sin objetivo y una candidata sin resultado observable. |
| R013 | SHOULD | El sistema DEBERÁ ofrecer el resultado de la comprobación en un formato legible por máquina y terminar con un código de salida distinto de cero cuando haya errores. |
| R014 | MUST | CUANDO el usuario aprueba el producto, el sistema DEBERÁ aprobar brief y backlog solo si la comprobación no da errores y no queda ninguna pregunta abierta que cite un objetivo. |
| R015 | MUST | SI una aprobación no la origina el usuario, ENTONCES el sistema DEBERÁ impedirla. |
| R016 | MUST | SI el brief o el backlog cambian después de aprobarse, ENTONCES el sistema DEBERÁ tratarlos como no aprobados hasta que el usuario los apruebe de nuevo. |

## Criterios de aceptación

### R001

- **Dado** un producto sin documentos **cuando** el usuario ingiere `vision.md` **entonces** el producto tiene el documento D1 y cada sección de D1 se puede citar como `D1§n`.
- **Dado** un documento cuyo único encabezado de primer nivel es su título **cuando** se ingiere **entonces** el título no es una sección ni se numera, y las secciones bajo él empiezan en `§1`.
- **Dado** un producto con D1 y D2 **cuando** el usuario ingiere otro documento **entonces** recibe el identificador D3.
- **Dado** un producto con D1 **cuando** se ingiere un documento con encabezados anidados **entonces** sus subsecciones se citan como `D2§4.2`.

### R002

- **Dado** un producto con D1 **cuando** el usuario ingiere un archivo con exactamente el mismo contenido que D1, aunque tenga otro nombre **entonces** se rechaza con un mensaje que nombra D1 y el producto no cambia.

### R003

- **Dado** cualquier producto **cuando** el usuario ingiere un `.xlsx` o un `.png` **entonces** se rechaza con un mensaje que lista los formatos admitidos y el producto no cambia.

### R005

- **Dado** un documento con una sección que no dice quién es el usuario objetivo **cuando** el usuario pide aclarar **entonces** recibe una pregunta que cita esa sección (`D1§2`).
- **Dado** una pregunta presentada **cuando** el usuario la contesta **entonces** pregunta y respuesta quedan en el brief, y la pregunta deja de estar abierta.
- **Dado** una pregunta que el usuario no contesta **cuando** termina la aclaración **entonces** sigue abierta en el brief.

### R006

- **Dado** un producto con D1 **cuando** el usuario descompone **entonces** el brief contiene al menos un objetivo `G1`, y cada objetivo cita la sección de la que sale.
- **Dado** un documento que exige «todo dato personal cifrado» **cuando** se descompone **entonces** aparece como invariante propuesto en el brief y la constitución no cambia.

### R007

- **Dado** un producto con D1 **cuando** el usuario descompone **entonces** el backlog tiene candidatas `B01`, `B02`…, cada una con objetivos, origen, problema, resultado observable, alcance, dependencias y estado.

### R008

- **Dado** un backlog con B01–B05 y B03 descartada **cuando** se ingiere D2 y se descompone **entonces** B01–B05 conservan su identificador y las candidatas nuevas empiezan en B06.

### R009

- **Dado** D1 dice «solo usuarios registrados» y D2 dice «acceso anónimo» **cuando** se descompone **entonces** hay una pregunta abierta que cita las dos secciones, y ni el brief ni el backlog eligen una de las dos.

### R010

- **Dado** cualquier producto **cuando** se ejecutan ingest, clarify, decompose, check o approve **entonces** ningún archivo bajo `specs/` cambia.
- **Dado** un backlog tras descomponer **cuando** se revisan sus candidatas **entonces** ninguna contiene requisitos con forma EARS («el sistema DEBERÁ»).

### R011

- **Dado** un objetivo G3 que ninguna candidata cita **cuando** se comprueba **entonces** se informa un error que nombra G3.
- **Dado** una sección D1§5 que ningún objetivo ni candidata cita y no está descartada **cuando** se comprueba **entonces** se informa un error que nombra D1§5.
- **Dado** una candidata que cita G9 o D4§1 inexistentes **cuando** se comprueba **entonces** se informa un error por cada referencia.
- **Dado** B02 depende de B04 y B04 de B02 **cuando** se comprueba **entonces** se informa un error de dependencia circular.
- **Dado** D1 se editó después de ingerirlo **cuando** se comprueba **entonces** se informa un error que nombra D1.

### R014

- **Dado** una comprobación con errores **cuando** el usuario aprueba **entonces** no se aprueba nada y se listan los errores.
- **Dado** una pregunta abierta que cita G2 **cuando** el usuario aprueba **entonces** no se aprueba nada y se nombra la pregunta.
- **Dado** una comprobación sin errores y sin preguntas abiertas sobre objetivos **cuando** el usuario aprueba **entonces** brief y backlog quedan aprobados.

### R015

- **Dado** un backlog sin aprobar **cuando** el modelo intenta marcarlo como aprobado, por edición directa o por comando **entonces** se impide y el backlog sigue sin aprobar.

### R016

- **Dado** un backlog aprobado **cuando** se cambia el texto de una candidata **entonces** el producto figura como no aprobado y la comprobación lo indica.
- **Dado** un backlog aprobado **cuando** solo se reformatean espacios o líneas en blanco **entonces** sigue aprobado.

## Requisitos no funcionales

No aplica. Los límites de red, dependencias y versión mínima los fija la
constitución del repo.

## Supuestos

- Hay un solo producto por repositorio.
- Los documentos de producto son texto estructurado con encabezados; un documento
  sin encabezados se trata como una única sección.
- El usuario es el único autor de los documentos y el único que aprueba.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

- [ ] (R004) ¿Se guarda en el repo el PDF o Word original, o solo su nombre y fecha? Propuesta: no se guarda; lo revisado y aprobado es el Markdown.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.

- **2026-10-15 · Aclaración de R001 (mismo ID).** El primer criterio decía «cada
  encabezado» y pasa a decir «cada sección»; se añade un criterio para el
  título: un único encabezado de primer nivel es el título del documento y no
  se numera. Motivo: `/sdd:analyze` detectó que el criterio contradecía la
  decisión D3 del plan. El comportamiento que pide R001 no cambia. Afecta a:
  R001.
