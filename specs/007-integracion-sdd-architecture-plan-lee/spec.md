# Spec: integracion de sdd con architecture: el plan lee y comprueba la arquitectura

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `007-integracion-sdd-architecture-plan-lee`     |
| Fecha  | 2026-10-16     |
| Estado | Approved · 97bdf989657e        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

En la primera prueba real de la serie (2026-10-16), `/sdd:plan` preguntó por el
stack, la arquitectura y el despliegue de un producto nuevo, y la feature quedó
especificada pero sin planear. El plugin `architecture` ya existe para decidir
eso una vez, para todo el producto, con la aprobación del usuario. Pero `sdd` no
lo lee: el plan de cada feature sigue sin saber qué componentes hay, qué está
decidido ni qué reglas cumplir, y puede contradecir una decisión aprobada sin que
nada lo note. Le pasa al usuario en cada feature de un producto que pasó por
`architecture`.

## Contexto

- La serie va `discovery` → `architecture` → `sdd`, y sus plugins se unen solo
  por archivos (constitución). `architecture` deja en `architecture/`
  componentes con las candidatas que alojan, decisiones (ADR) con su estado, y
  estándares; aprobados con huella.
- Decisiones de la serie ya tomadas: `sdd` funciona igual sin `architecture/`;
  `architecture` solo arranca en productos nuevos; una decisión nueva que surge
  al planificar o implementar la propone `sdd`, pero se decide en `architecture`
  (`/architecture:review`). La regla de frontera: una decisión es de
  arquitectura si afecta a más de una feature o es cara de revertir.
- Leer el formato de `architecture/` convierte ese formato en contrato entre
  plugins; añadir el componente al origen de la spec cambia un artefacto de
  `sdd`. La constitución exige aprobación explícita del usuario: la da al
  aprobar esta spec.

## Alcance

### Dentro

- Que el plan de una feature parta de la arquitectura aprobada: los componentes
  de su candidata, las decisiones vigentes y los estándares.
- Que la trazabilidad compruebe las decisiones que cita el plan y avise de las
  que se sustituyeron después.
- Que `sdd` pueda proponer una decisión nueva a `architecture` sin aprobarla.
- Que el traspaso desde `discovery` registre el componente de la candidata y se
  niegue si la arquitectura no la aloja o no está aprobada.

### Fuera (non-goals)

- Comprobar los estándares contra el código (dirección real de dependencias o
  imports prohibidos).
- Aprobar, rechazar o sustituir decisiones desde `sdd`: eso es de
  `/architecture:review`.
- Cambios en el plugin `architecture` o en `discovery`.
- Decidir automáticamente si una decisión es estructural: lo juzgan el modelo y
  el usuario.
- Contratos entre componentes.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | SI el proyecto no tiene arquitectura, ENTONCES `sdd` DEBERÁ especificar, planificar, comprobar y traspasar exactamente como hasta ahora. |
| R002 | MUST | CUANDO se planifica una feature de un proyecto con arquitectura, el sistema DEBERÁ indicar como contexto los componentes de su candidata, las decisiones vigentes y los estándares. |
| R003 | MUST | SI el plan cita una decisión de arquitectura que no existe o que no está aprobada, ENTONCES la trazabilidad DEBERÁ informarlo como error, salvo si un plan aprobado cita una decisión sustituida después, caso que se rige por R005. |
| R004 | MUST | SI el proyecto tiene arquitectura y el plan no contrasta sus decisiones con ella, ENTONCES la trazabilidad DEBERÁ avisar. |
| R005 | MUST | SI una decisión que cita un plan aprobado fue sustituida, ENTONCES la trazabilidad DEBERÁ avisar y nombrar la decisión que la sustituye. |
| R006 | MUST | CUANDO `sdd` propone una decisión de arquitectura, el sistema DEBERÁ registrarla como propuesta, con un número que no se reutiliza y con el plan que la propone, sin aprobarla. |
| R007 | MUST | CUANDO se crea una feature desde una candidata en un proyecto con arquitectura aprobada, la spec DEBERÁ registrar en su origen los componentes que alojan la candidata. |
| R008 | MUST | SI el proyecto tiene arquitectura y no está aprobada, cambió después de aprobarse, o no aloja la candidata en ningún componente, ENTONCES el traspaso NO DEBERÁ crear la feature y DEBERÁ indicar qué falta. |
| R009 | MUST | CUANDO el plugin `architecture` no está instalado, `sdd` DEBERÁ aplicar todo lo anterior igual a partir de los archivos de la arquitectura. |

## Criterios de aceptación

### R001

- **Dado** un proyecto sin `architecture/` **cuando** se planifica, se comprueba la trazabilidad y se traspasa una candidata **entonces** el resultado es el mismo que antes de esta feature.

### R002

- **Dado** una arquitectura aprobada donde B02 vive en C2, con ADR-0001 aprobada, ADR-0003 rechazada y el estándar S1 **cuando** se pide el contexto de planificación de la feature de B02 **entonces** incluye C2, ADR-0001 y S1, y no incluye ADR-0003.

### R003

- **Dado** un plan que cita ADR-0009, inexistente **cuando** se comprueba la trazabilidad **entonces** hay un error que la nombra.
- **Dado** un plan que cita ADR-0004 propuesta **cuando** se comprueba **entonces** hay un error que dice que está pendiente de `/architecture:review`.
- **Dado** un plan que cita ADR-0001 aprobada **cuando** se comprueba **entonces** no hay error por ella.

### R004

- **Dado** un proyecto con arquitectura y un plan sin comprobación de arquitectura **cuando** se comprueba la trazabilidad **entonces** hay un aviso.

### R005

- **Dado** un plan aprobado que cita ADR-0002 **cuando** la ADR-0004 la sustituye **entonces** la trazabilidad avisa y nombra ADR-0004.

### R006

- **Dado** una arquitectura con ADR-0001 a ADR-0003 **cuando** `sdd` propone una decisión desde el plan de la feature 008 **entonces** queda como ADR-0004 en estado propuesto, con el plan de la 008 como origen, y no aprobada.

### R007

- **Dado** una arquitectura aprobada donde B02 vive en C2 **cuando** se especifica con `B02` **entonces** el origen de la spec registra B02, sus objetivos, sus secciones y C2.

### R008

- **Dado** una arquitectura aprobada sin componente para B02 **cuando** se especifica con `B02` **entonces** no se crea nada y el mensaje dice que B02 no tiene componente y que se corrige en `architecture`.
- **Dado** una arquitectura sin aprobar **cuando** se especifica con `B02` **entonces** no se crea nada y el mensaje remite a `/architecture:approve`.

### R009

- **Dado** un repositorio con `architecture/` aprobada y sin el plugin `architecture` instalado **cuando** se usa `sdd` **entonces** el contexto, las comprobaciones y el traspaso funcionan igual.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento de
los guardrails.

## Supuestos

- «Tener arquitectura» es que exista `architecture/` en la raíz del proyecto.
- Una decisión vigente es una aprobada; las propuestas, rechazadas y sustituidas
  no lo son.
- Las features ya especificadas antes de que existiera la arquitectura no se
  reabren: sus planes aprobados solo reciben los avisos de R004 y R005.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.

- **2026-10-16 · R003 (aclaración):** R003 («una decisión no aprobada → error»)
  y R005 («un plan aprobado que cita una decisión sustituida → aviso») se
  solapaban: una decisión sustituida ya no está aprobada. Se dice cuál manda:
  en ese caso, R005. Es lo que ya decidía el plan (D1); no cambia el
  comportamiento ni los criterios. IDs afectados: R003, R005.
