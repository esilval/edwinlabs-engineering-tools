# Spec: plugin operate: preparación operativa e incidentes con postmortems

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `011-plugin-operate-preparacion-operativa-incidentes`     |
| Fecha  | 2026-10-27     |
| Estado | Approved · 454908c4318d        |
| Tipo   | funcionalidad |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

La serie termina en una versión aprobada, pero nada prepara su puesta en
marcha ni recoge lo que pasa después. Quien pone una versión en marcha tiene
que improvisar tres cosas:
- cómo ponerla en marcha y comprobar que funciona;
- qué vigilar después, y a partir de qué cifra preocuparse;
- cómo volver atrás, y cuándo hacerlo.

Cuando algo falla en producción, el incidente y lo aprendido se quedan en una
conversación. Las acciones que salen de él no llegan a la serie: nadie las
convierte en trabajo trazable, y la corrección que acaba saliendo no cita el
incidente que la motivó.

Le pasa al equipo en cada versión que sale y en cada incidente.

## Contexto

- La serie es `discovery` → `architecture` → `sdd` → `release` → `operate`.
  Cada plugin es una etapa unida a las demás solo por archivos, y funciona
  aunque los demás no estén instalados (constitución).
- `release` (feature 010) deja una versión por archivo y la sella cuando el
  usuario la aprueba. Una versión aprobada alguna vez cuenta como publicada,
  aunque cambie después. `release` no despliega ni etiqueta.
- `architecture` describe los atributos de calidad como escenarios medibles
  (Q1, Q2…), cada uno con su motivo: un objetivo del producto o una
  restricción. Las decisiones de arquitectura citan los atributos que las
  motivan.
- `sdd` ya crea una feature desde una candidata del backlog de `discovery`
  (`/sdd:specify B03`). La spec nace con el problema, el contexto y la fila
  `Origen` de la candidata. Desde la feature 010, la spec lleva una fila
  `Tipo` (`funcionalidad` o `corrección`) que `release` usa para el número de
  versión.
- Decisiones del usuario (2026-10-27), al diseñar `operate`:
  - alcance: preparación operativa de cada versión, e incidentes con
    postmortems; sin desplegar ni ejecutar nada;
  - el usuario aprueba la preparación de cada versión y cada postmortem;
  - las acciones de un postmortem vuelven a la serie como features de
    corrección de `sdd`, creadas con el ID de la acción, como el traspaso desde
    `discovery`;
  - las señales a vigilar parten de los atributos de calidad de la
    arquitectura cuando existe.
- La constitución exige: lo determinista en scripts, solo con la biblioteca
  estándar; aprobación solo del usuario, con guardrails que fallan abiertos y
  tienen escape; códigos de hallazgo estables con prefijos reservados; y que
  cambiar el formato de un artefacto que lee otro plugin lo apruebe el usuario.

## Alcance

### Dentro

- La preparación operativa de una versión publicada: procedimiento de puesta
  en marcha y verificación, señales a vigilar con su umbral, y plan de vuelta
  atrás con lo que lo dispara. La aprueba el usuario.
- Un punto de partida generado sin el modelo, con las features de la versión
  y, con arquitectura, una señal propuesta por cada atributo de calidad
  relacionado.
- El registro de incidentes, cada uno con un identificador estable, y su
  postmortem: cronología, causas y acciones. El usuario aprueba el postmortem.
- La comprobación de todo lo anterior, igual en local y en CI.
- El traspaso a `sdd`: crear una feature de corrección a partir de una acción
  de un postmortem aprobado, con el origen que la cita.
- El aviso de las acciones que siguen sin feature.

### Fuera (non-goals)

- Desplegar, ejecutar el procedimiento o la vuelta atrás, o tocar
  infraestructura.
- Leer métricas, conectarse a sistemas de monitorización o de alertas, o
  detectar incidentes solos.
- Guardias, avisos a personas o comunicación con clientes.
- Cambios en `discovery`, `architecture` o `release`.
- Comprobar que la corrección arregla de verdad el incidente.

## Requisitos

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO el usuario pide la preparación operativa de una versión publicada, el sistema DEBERÁ crear, sin intervención del modelo, un borrador con las features de la versión y apartados para el procedimiento de puesta en marcha y verificación, las señales a vigilar y el plan de vuelta atrás. |
| R002 | MUST | SI la versión pedida no existe o no está publicada, ENTONCES el sistema NO DEBERÁ crear la preparación y DEBERÁ informar el motivo. |
| R003 | MUST | CUANDO el proyecto tiene una arquitectura aprobada, el sistema DEBERÁ proponer en el borrador una señal por cada atributo de calidad relacionado con las features de la versión, con el escenario medible del atributo. |
| R004 | MUST | SI una señal de la preparación no tiene un umbral con cifra, ENTONCES el sistema DEBERÁ informarlo nombrando la señal. |
| R005 | MUST | SI el plan de vuelta atrás no dice qué señal o condición lo dispara, ENTONCES el sistema DEBERÁ informarlo. |
| R006 | MUST | CUANDO el usuario registra un incidente, el sistema DEBERÁ asignarle un identificador que no se recicla nunca y pedir la fecha, la versión afectada, la severidad, qué pasó y el impacto. |
| R007 | MUST | SI un incidente cita una versión afectada que no existe, ENTONCES el sistema DEBERÁ informarlo nombrando el incidente y la versión. |
| R008 | MUST | El sistema DEBERÁ dar a cada postmortem una cronología, las causas y las acciones, con cada acción identificada de forma estable dentro de su incidente. |
| R009 | MUST | SI una preparación o un postmortem conserva huecos sin completar, o tiene errores de comprobación, ENTONCES el sistema NO DEBERÁ permitir aprobarlo. |
| R010 | MUST | CUANDO el usuario aprueba una preparación o un postmortem sin errores, el sistema DEBERÁ sellarlo de forma que cualquier cambio posterior sea detectable. |
| R011 | MUST | SI una preparación o un postmortem aprobados cambian después, o cambia la versión en la que se apoya una preparación aprobada, ENTONCES el sistema DEBERÁ avisar de que ya no cuenta como aprobado. |
| R012 | MUST | El sistema NO DEBERÁ permitir que el modelo apruebe una preparación o un postmortem por ninguna vía, y DEBERÁ ofrecer al usuario un escape documentado. |
| R013 | MUST | CUANDO el usuario pide en `sdd` una feature a partir de una acción de un postmortem aprobado, el sistema DEBERÁ crear la spec con tipo corrección, el problema tomado del incidente y de la acción, y un origen que cite la acción. |
| R014 | MUST | SI se pide una feature desde una acción cuyo postmortem no está aprobado o cambió tras aprobarse, que no existe, o que ya tiene feature, ENTONCES el sistema NO DEBERÁ crear nada y DEBERÁ informar el motivo. |
| R015 | MUST | MIENTRAS una acción de un postmortem aprobado no tenga feature, el sistema DEBERÁ avisarlo nombrando la acción. |
| R016 | MUST | El sistema DEBERÁ dar el mismo resultado de comprobación en local y en integración continua, con códigos de hallazgo estables y una salida legible por máquinas. |
| R017 | MUST | MIENTRAS el proyecto no tenga arquitectura, versiones o producto, el sistema DEBERÁ ofrecer lo que no depende de ellos sin fallar por su ausencia: preparación sin señales propuestas, e incidentes sin versión afectada. |
| R018 | MUST | MIENTRAS no exista el registro de incidentes, el sistema DEBERÁ crear las features de `sdd` exactamente como hasta ahora, también si la descripción parece el identificador de una acción. |

## Criterios de aceptación

### R001

- **Dado** la versión 0.4.0 publicada con las features 008 y 009 **cuando** el usuario pide su preparación operativa **entonces** existe un borrador que nombra 008 y 009 y tiene los apartados de procedimiento, señales y vuelta atrás por completar.
- **Dado** que la preparación de 0.4.0 ya existe **cuando** se pide otra vez **entonces** no cambia y se indica que ya existía.

### R002

- **Dado** la versión 0.5.0 en borrador **cuando** se pide su preparación **entonces** no se crea nada y se dice que la versión no está publicada.
- **Dado** que no existe la versión 9.9.9 **cuando** se pide su preparación **entonces** no se crea nada y se nombra 9.9.9.

### R003

- **Dado** una arquitectura aprobada con Q1 «p95 < 300 ms» motivado por G1, y la feature 008 creada desde una candidata que sirve a G1 **cuando** se crea la preparación de una versión con 008 **entonces** el borrador propone una señal para Q1 con su escenario, y el umbral queda por completar.
- **Dado** el plan de la feature 008 citando ADR-0002, motivada por Q2 **cuando** se crea la preparación **entonces** también se propone una señal para Q2.
- **Dado** un atributo Q3 que no se relaciona con ninguna feature de la versión **cuando** se crea la preparación **entonces** no se propone señal para Q3.

### R004

- **Dado** una señal «latencia de exportación» con el umbral «que vaya rápido» **cuando** se comprueba la preparación **entonces** hay un error que nombra la señal.

### R005

- **Dado** un plan de vuelta atrás con pasos pero sin disparador **cuando** se comprueba la preparación **entonces** hay un error.

### R006

- **Dado** que existen I001 e I002, e I002 se borró **cuando** el usuario registra un incidente **entonces** recibe I003.
- **Dado** un incidente nuevo **cuando** se registra **entonces** tiene apartados por completar para fecha, versión afectada, severidad, qué pasó e impacto.

### R007

- **Dado** el incidente I001 que cita la versión 0.9.0, que no existe **cuando** se comprueba **entonces** hay un error que nombra I001 y 0.9.0.

### R008

- **Dado** el incidente I001 **cuando** se redacta su postmortem **entonces** tiene cronología, causas y acciones, y cada acción tiene un identificador (I001-A1, I001-A2) que no cambia al editarla ni al borrar otra.

### R009

- **Dado** un postmortem con las causas sin completar **cuando** el usuario intenta aprobarlo **entonces** se niega, dice qué falta y no cambia nada.
- **Dado** una preparación con una señal sin umbral **cuando** el usuario intenta aprobarla **entonces** se niega y no cambia nada.

### R010

- **Dado** un postmortem completo y sin errores **cuando** el usuario lo aprueba **entonces** queda aprobado con una huella de su contenido.

### R011

- **Dado** el postmortem de I001 aprobado **cuando** se edita una causa **entonces** la comprobación avisa de que cambió tras aprobarse.
- **Dado** la preparación de 0.4.0 aprobada **cuando** la versión 0.4.0 cambia **entonces** la comprobación avisa de que la preparación se apoya en una versión distinta.

### R012

- **Dado** el modelo trabajando **cuando** intenta marcar como aprobada una preparación o un postmortem, escribiendo el archivo o ejecutando la aprobación **entonces** se le impide o se revierte con un aviso.
- **Dado** el usuario con el escape activado **cuando** aprueba a mano **entonces** no se le impide.

### R013

- **Dado** el postmortem de I001 aprobado con la acción I001-A2 **cuando** el usuario pide en `sdd` una feature para I001-A2 **entonces** la spec nace con tipo corrección, un problema que cuenta el incidente y la acción, y un origen que cita I001-A2.

### R014

- **Dado** el postmortem de I001 sin aprobar **cuando** se pide una feature para I001-A2 **entonces** no se crea nada y se dice que el postmortem no está aprobado.
- **Dado** que no existe I001-A9 **cuando** se pide su feature **entonces** no se crea nada y se nombra I001-A9.
- **Dado** que I001-A2 ya tiene feature **cuando** se pide otra **entonces** no se crea nada y se nombra la feature existente.

### R015

- **Dado** el postmortem de I001 aprobado con I001-A1 con feature e I001-A2 sin ella **cuando** se comprueba **entonces** hay un aviso que nombra I001-A2 y ninguno para I001-A1.

### R016

- **Dado** un postmortem con un error **cuando** se comprueba en modo CI **entonces** la comprobación falla y el resultado legible por máquinas trae el código del error.

### R017

- **Dado** un proyecto sin `architecture/` **cuando** se crea la preparación de una versión **entonces** se crea sin señales propuestas y sin hallazgos de arquitectura.
- **Dado** un proyecto sin versiones **cuando** el usuario registra un incidente **entonces** se registra, y la versión afectada puede quedar como desconocida sin error.

### R018

- **Dado** un proyecto sin registro de incidentes **cuando** el usuario pide en `sdd` la feature «I001-A2» **entonces** se crea igual que cualquier descripción de texto, como antes de esta feature.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento
de los guardrails.

## Supuestos

- Un atributo de calidad se relaciona con una feature si su motivo es un
  objetivo al que sirve la feature (según su origen), o si motiva una decisión
  de arquitectura que cita el plan de la feature.
- La versión afectada de un incidente es la que estaba en marcha cuando
  ocurrió; la anota el usuario.
- Una acción tiene feature cuando una spec la cita como origen, igual que una
  candidata de `discovery`.
- Una preparación se hace para una versión publicada; si la versión cambia
  después, basta con avisar.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.
