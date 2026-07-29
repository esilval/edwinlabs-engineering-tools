# Spec: {{TITLE}}

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `{{ID}}`     |
| Fecha  | {{DATE}}     |
| Estado | Draft        |
| Issue  | _(opcional)_ |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.

## Problema

_El dolor concreto que se resuelve. Si no puedes nombrar a quién le duele y con
qué frecuencia, la spec no está lista._

## Contexto

_Qué existe hoy, qué restricciones hay (negocio, legales, de plazos), y qué se
intentó antes si aplica._

## Alcance

### Dentro

- _Cambio observable 1_
- _Cambio observable 2_

### Fuera (non-goals)

- _Lo que este cambio explícitamente NO cubre._

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

Patrones:

| Patrón      | Forma                                                       |
| ----------- | ----------------------------------------------------------- |
| Ubicuo      | El sistema DEBERÁ \<respuesta\>                             |
| Evento      | CUANDO \<disparador\>, el sistema DEBERÁ \<respuesta\>      |
| Estado      | MIENTRAS \<estado\>, el sistema DEBERÁ \<respuesta\>        |
| Opcional    | DONDE \<característica\>, el sistema DEBERÁ \<respuesta\>   |
| No deseado  | SI \<condición\>, ENTONCES el sistema DEBERÁ \<respuesta\>  |

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST      | _CUANDO ..., el sistema DEBERÁ ..._ |
| R002 | MUST      | _SI ..., ENTONCES el sistema DEBERÁ ..._ |
| R003 | SHOULD    | _..._ |
| R004 | COULD     | _..._ |

## Criterios de aceptación

### R001

- **Dado** _\<estado inicial\>_ **cuando** _\<acción\>_ **entonces** _\<resultado observable\>_
- **Dado** _\<caso borde\>_ **cuando** _\<acción\>_ **entonces** _\<resultado observable\>_

### R002

- **Dado** _..._ **cuando** _..._ **entonces** _..._

## Requisitos no funcionales

_Rendimiento, disponibilidad, privacidad, accesibilidad, coste. Solo los que
tengan un número o un umbral verificable; el resto es decoración._

## Supuestos

- _Cosas que damos por ciertas y que, si resultan falsas, invalidan la spec._

## Preguntas abiertas

- [ ] _Ambigüedad sin resolver. Debe quedar vacío antes de pasar a `plan.md`._
