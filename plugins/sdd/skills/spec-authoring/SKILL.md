---
name: spec-authoring
user-invocable: false
description: Reglas de redacción para especificaciones SDD (notación EARS, IDs de requisito, criterios de aceptación, non-goals). Úsala siempre que escribas o edites un archivo bajo specs/, redactes requisitos, o revises una especificación en busca de ambigüedad.
---

# Cómo se redacta una especificación

Aplica estas reglas al escribir o editar cualquier archivo bajo `specs/`.

## Notación EARS para requisitos

Todo requisito usa uno de estos cinco patrones. La forma rígida no es
burocracia: elimina la ambigüedad que hace que un agente rellene huecos por su
cuenta.

| Patrón     | Forma                                                    | Cuándo |
| ---------- | -------------------------------------------------------- | ------ |
| Ubicuo     | El sistema DEBERÁ \<respuesta\>                          | Siempre cierto |
| Evento     | CUANDO \<disparador\>, el sistema DEBERÁ \<respuesta\>   | Reacción a algo |
| Estado     | MIENTRAS \<estado\>, el sistema DEBERÁ \<respuesta\>     | Durante una condición |
| Opcional   | DONDE \<característica\>, el sistema DEBERÁ \<respuesta\> | Solo si existe la función |
| No deseado | SI \<condición\>, ENTONCES el sistema DEBERÁ \<respuesta\> | Errores y casos límite |

Los requisitos de tipo «no deseado» son los que más se olvidan y los que más
bugs previenen. Si una spec no tiene ninguno, casi seguro está incompleta.

## IDs y prioridad

- Cada requisito lleva un ID estable: `R001`, `R002`, …
- Los IDs **no se reutilizan ni se renumeran**. Si un requisito muere, se marca
  como obsoleto pero su número no se recicla: hay tareas, commits y tests que lo
  referencian.
- Prioridad: `MUST` (sin esto no se entrega), `SHOULD` (importante, no
  bloqueante), `COULD` (deseable), `OBSOLETO` (retirado; no exige tarea ni
  prueba, y su ID queda reservado).
- Cambiar un requisito ya aprobado es trabajo de `/sdd:amend`. Si el cambio
  altera el comportamiento, el requisito viejo pasa a `OBSOLETO` y nace uno con
  ID nuevo; así las pruebas antiguas no dan por verificado lo que ya no se pide.

## Criterios de aceptación

Cada requisito MUST necesita al menos un criterio en forma
**Dado / Cuando / Entonces**, con un resultado observable. Si no sabes cómo
comprobar que se cumple, el requisito está mal escrito.

Cada criterio debería poder convertirse en una prueba con el ID del requisito
en el nombre. Si no ves cómo, el criterio no es observable todavía.

## Qué NO va en una spec

- Nombres de librerías, servicios, tablas, endpoints o patrones de diseño.
- Estimaciones de esfuerzo.
- Cualquier frase que dejaría de ser cierta si cambiáramos la pila tecnológica.

Todo eso vive en `plan.md`.

## Non-goals

La sección de fuera de alcance es el control de alcance más barato que existe.
Escríbela siempre, aunque parezca obvia. Lo que hoy es obvio, en la tercera
sesión de implementación ya no lo es.

## Señales de que una spec no está lista

- Adjetivos sin umbral: «rápido», «intuitivo», «robusto», «escalable».
- Requisitos que describen una solución en vez de una necesidad.
- Requisitos MUST sin criterio de aceptación.
- La sección de preguntas abiertas tiene entradas que afectan a requisitos MUST.

## Preguntas abiertas

Cada pregunta cita el requisito al que afecta: `- [ ] (R002) ¿Cuánto dura la
sesión?`. Es lo que permite al comprobador saber cuáles bloquean. Una pregunta
abierta sobre un MUST impide aprobar la spec; una que no cita ninguno solo
genera un aviso.

Cuando detectes alguna, dilo explícitamente al usuario en vez de rellenar el
hueco con una suposición.
