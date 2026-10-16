# Spec: traspaso de discovery a sdd: specify con un ID de candidata crea la spec desde el backlog aprobado

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `005-traspaso-discovery-sdd-specify-id`     |
| Fecha  | 2026-10-15     |
| Estado | Approved · 10c2b5914464        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

`discovery` deja un backlog aprobado de features candidatas, cada una con su
problema, su alcance, los objetivos del brief que persigue y las secciones del
documento de las que sale. Pero `/sdd:specify` recibe una línea de texto, y el
modelo reconstruye todo eso explorando el repositorio. El usuario copia a mano
lo que ya estaba escrito, o el modelo lo reinventa, y la cadena que va del
documento de producto al código se corta justo en la entrada de `sdd`: ninguna
spec dice de qué candidata sale. Ocurre en cada feature de un producto que pasó
por `discovery`.

## Contexto

- La serie de plugins va `discovery` → `architecture` → `sdd` → … y se une
  solo por archivos (constitución). `sdd` debe funcionar sin `discovery`.
- El documento de diseño de la serie fija el traspaso: la spec nace con
  problema, contexto y alcance desde la candidata, y con su origen en la
  cabecera; requisitos y criterios los sigue redactando `/sdd:specify`. Lo
  lanza `/sdd:specify` con el ID de la candidata (decisión del 2026-10-15).
- El backlog y el brief tienen formato propio, Estado y huella de aprobación
  (`/discovery:approve`). Una candidata puede estar descartada; su ID no se
  reutiliza.
- Que `sdd` lea el backlog convierte su formato en contrato entre plugins, y
  añadir el origen a la spec cambia el formato de un artefacto de `sdd`. La
  constitución exige aprobación explícita del usuario para ambos: la da al
  aprobar esta spec.

## Alcance

### Dentro

- Crear una feature desde una candidata del backlog, con su problema, contexto,
  alcance y origen.
- Negarse cuando el producto no está aprobado, la candidata no existe o está
  descartada, o ya tiene feature.
- Dar a `/sdd:specify` el contexto de la candidata para redactar requisitos.
- Mantener intacto el comportamiento actual cuando no hay backlog o el
  argumento no es un ID de candidata.

### Fuera (non-goals)

- Cambiar `discovery`: ni su formato ni sus comandos.
- Marcar en el backlog qué candidatas ya tienen feature: el backlog aprobado no
  se modifica.
- Redactar automáticamente requisitos o criterios a partir de la candidata.
- La integración con `architecture` (componente y ADRs en el origen): ese
  plugin aún no existe.
- Crear varias features de una vez.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO se especifica una feature con el ID de una candidata del backlog, el sistema DEBERÁ crearla con su problema, su contexto y su alcance tomados de esa candidata. |
| R002 | MUST | CUANDO se crea una feature desde una candidata, la spec DEBERÁ registrar su origen: la candidata, los objetivos que persigue y las secciones de documento que cita. |
| R003 | MUST | SI el brief o el backlog no están aprobados, o cambiaron después de aprobarse, ENTONCES el sistema NO DEBERÁ crear la feature y DEBERÁ indicar qué falta. |
| R004 | MUST | SI la candidata no existe o está descartada, ENTONCES el sistema NO DEBERÁ crear la feature y DEBERÁ decir por qué. |
| R005 | MUST | SI ya existe una feature cuyo origen es esa candidata, ENTONCES el sistema NO DEBERÁ crear otra y DEBERÁ nombrar la existente. |
| R006 | MUST | CUANDO se crea una feature desde una candidata, el sistema DEBERÁ indicar los objetivos del brief y las secciones de documento que la candidata cita, para redactar los requisitos con ese contexto. |
| R007 | MUST | SI no hay backlog o el argumento no es el ID de una candidata, ENTONCES el sistema DEBERÁ especificar la feature como hasta ahora. |
| R008 | MUST | CUANDO una spec no registra origen, el sistema DEBERÁ tratarla en el estado, la aprobación y la trazabilidad exactamente como hasta ahora. |
| R009 | SHOULD | SI la candidata depende de otras candidatas que aún no tienen feature, ENTONCES el sistema DEBERÁ avisar sin impedir la creación. |

## Criterios de aceptación

### R001

- **Dado** un producto aprobado con la candidata B03 «Exportar movimientos» **cuando** se especifica con `B03` **entonces** se crea la feature con un nombre derivado del título de B03, y su spec contiene el problema, el resultado observable y el alcance dentro y fuera de B03.
- **Dado** lo mismo **cuando** se especifica con `b03` **entonces** se reconoce igual.

### R002

- **Dado** la candidata B03 con objetivos G2 y origen D2§4.2 **cuando** se crea su feature **entonces** la cabecera de la spec registra `B03 · G2 · D2§4.2`.

### R003

- **Dado** un backlog en Draft **cuando** se especifica con `B03` **entonces** no se crea ninguna feature y el mensaje dice que el producto no está aprobado y que lo aprueba `/discovery:approve`.
- **Dado** un brief aprobado que se editó después **cuando** se especifica con `B03` **entonces** no se crea y el mensaje dice que cambió tras aprobarse.

### R004

- **Dado** un backlog aprobado sin B09 **cuando** se especifica con `B09` **entonces** no se crea y el mensaje dice que B09 no existe.
- **Dado** B04 descartada **cuando** se especifica con `B04` **entonces** no se crea y el mensaje dice que está descartada.

### R005

- **Dado** una feature `004-exportar-movimientos` con origen B03 **cuando** se especifica con `B03` **entonces** no se crea otra y el mensaje nombra `004-exportar-movimientos`.

### R006

- **Dado** B03 con objetivos G2 y origen D2§4.2 **cuando** se crea su feature **entonces** el resultado indica G2 en el brief y la sección 4.2 del documento D2 como contexto para redactar.

### R007

- **Dado** un repositorio sin `product/backlog.md` **cuando** se especifica con `B03` **entonces** se crea una feature con esa descripción, como hasta ahora.
- **Dado** un backlog aprobado **cuando** se especifica con «login con Google» **entonces** se crea la feature como hasta ahora, sin origen.

### R008

- **Dado** las specs existentes de este repositorio, sin origen **cuando** se consultan el estado y la trazabilidad y se aprueban fases **entonces** el resultado es el mismo que antes de esta feature.

### R009

- **Dado** B05 que depende de B03 y B03 sin feature **cuando** se especifica con `B05` **entonces** se crea la feature y se avisa de que B03 aún no tiene feature.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento de
los guardrails.

## Supuestos

- Un ID de candidata tiene la forma de `discovery`: `B` seguido de dígitos.
  Una descripción que sea solo un ID así se trata como candidata si hay backlog.
- El producto está en `product/` en la raíz del proyecto, como lo deja
  `discovery`.
- El origen registrado en la spec forma parte de su contenido: cambiarlo tras
  aprobar la spec cuenta como cambio, como cualquier otra línea.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.
