# Spec: architecture: de brief aprobado a componentes, ADRs y estandares

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `006-architecture-brief-aprobado-componentes-adrs`     |
| Fecha  | 2026-10-16     |
| Estado | Approved · cc6d47b5095d        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

En un producto nuevo, tras `discovery` y el traspaso a `sdd`, `/sdd:plan` no
tiene dónde apoyar las decisiones que afectan a todo el producto: el stack, los
componentes, la persistencia, el despliegue. Las pregunta en el plan de la
primera feature, y el usuario las responde ahí o deja la feature especificada
pero sin planear, como ocurrió en la primera prueba real del traspaso
(2026-10-16). Respondidas así, esas decisiones quedan enterradas en el plan de
una feature: la siguiente no las ve, nadie las aprueba como decisiones del
producto y cambiarlas no deja rastro. Pasa en cada producto nuevo, antes de su
primera feature.

## Contexto

- La serie va `discovery` → `architecture` → `sdd` → … y sus plugins se unen
  solo por archivos (constitución). El documento de diseño de la serie define
  los artefactos de este plugin y la regla de frontera: una decisión va a
  arquitectura si afecta a más de una feature o es cara de revertir; si no, va
  al plan de la feature.
- Decisiones de la serie ya tomadas: la constitución sigue en `sdd` para las
  reglas de cómo se escribe el código; `architecture` solo arranca en productos
  nuevos, sin reconstruir la arquitectura desde código existente; `sdd` podrá
  proponer decisiones nuevas, pero se aceptan en `architecture`.
- `discovery` deja un brief (objetivos, restricciones, invariantes propuestos)
  y un backlog de candidatas, aprobados con huella. Este plugin los lee; leer
  ese formato es un contrato entre plugins, como ya lo es para `sdd`.
- La integración con `sdd` (que `/sdd:plan` lea y compruebe la arquitectura, y
  que proponga decisiones) es una feature aparte, la siguiente.

## Alcance

### Dentro

- Un plugin nuevo, `architecture`, que parte del producto aprobado y produce:
  atributos de calidad medibles, componentes con las candidatas que viven en
  cada uno, decisiones de arquitectura con su motivo y alternativas, y
  estándares comprobables derivados de esas decisiones.
- Preguntas abiertas para lo que el producto no decide.
- Una comprobación de coherencia con hallazgos estables, en local y en CI.
- Aprobación del conjunto solo por el usuario, con huella y detección de
  cambios, y guardrails que impiden que el modelo la conceda.
- Revisión por el usuario de decisiones propuestas: aceptarlas, rechazarlas o
  sustituir con ellas una anterior.

### Fuera (non-goals)

- Cambios en `sdd` o en `discovery`: la integración con `sdd` es la siguiente
  feature; `discovery` no cambia.
- Contratos entre componentes (interfaces, esquemas de API).
- Reconstruir la arquitectura a partir de código existente.
- Diagramas, generación de código o de estructura de proyecto.
- Elegir tecnologías sin el usuario: el modelo propone, el usuario decide.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | SI el brief o el backlog del producto faltan, no están aprobados o cambiaron después de aprobarse, ENTONCES el sistema NO DEBERÁ iniciar la arquitectura y DEBERÁ indicar qué falta. |
| R002 | MUST | CUANDO se define un atributo de calidad, el sistema DEBERÁ exigir que sea un escenario medible y que cite la restricción u objetivo del brief que lo motiva. |
| R003 | MUST | CUANDO se define un componente, el sistema DEBERÁ registrar su responsabilidad y las candidatas del backlog que viven en él. |
| R004 | MUST | SI una candidata vigente del backlog no está en ningún componente, ENTONCES el sistema DEBERÁ informarlo como error. |
| R005 | MUST | CUANDO se registra una decisión de arquitectura, el sistema DEBERÁ asignarle un número que no se reutiliza nunca y exigir contexto, alternativas descartadas, consecuencias y al menos un atributo de calidad u objetivo que la motive. |
| R006 | MUST | CUANDO se define un estándar comprobable, el sistema DEBERÁ exigir que cite la decisión de la que se deriva. |
| R007 | MUST | SI un artefacto de arquitectura cita una decisión, atributo, componente, objetivo o candidata que no existe, ENTONCES el sistema DEBERÁ informarlo como error. |
| R008 | MUST | CUANDO se comprueba la arquitectura, el sistema DEBERÁ dar el mismo resultado en local y en CI, con códigos de hallazgo estables y un error que haga fallar la comprobación en CI. |
| R009 | MUST | SI una pregunta abierta afecta a una decisión o atributo de calidad, ENTONCES el sistema NO DEBERÁ permitir aprobar la arquitectura. |
| R010 | MUST | CUANDO el usuario aprueba la arquitectura sin errores ni preguntas abiertas que la bloqueen, el sistema DEBERÁ sellar todos sus artefactos con la huella de su contenido. |
| R011 | MUST | SI un artefacto aprobado cambia después de aprobarse, ENTONCES el sistema DEBERÁ dejar de considerarlo aprobado e indicar cuál cambió. |
| R012 | MUST | SI el modelo intenta aprobar un artefacto de arquitectura o una decisión, por escritura directa o por un comando, ENTONCES el sistema DEBERÁ impedirlo o revertirlo, con un escape documentado para el usuario. |
| R013 | MUST | CUANDO el usuario revisa una decisión propuesta, el sistema DEBERÁ permitir aceptarla, rechazarla o aceptarla sustituyendo a una decisión aprobada, que queda marcada como sustituida por la nueva. |
| R014 | SHOULD | SI el brief o el backlog cambiaron después de aprobarse la arquitectura, ENTONCES el sistema DEBERÁ avisar de que la arquitectura se apoya en una versión anterior del producto. |
| R015 | MUST | CUANDO `discovery` o `sdd` no están instalados, el sistema DEBERÁ funcionar igual a partir de los archivos del producto. |

## Criterios de aceptación

### R001

- **Dado** un backlog en Draft **cuando** se inicia la arquitectura **entonces** no se crea nada y el mensaje dice que el producto no está aprobado y que lo aprueba `/discovery:approve`.
- **Dado** un repositorio sin `product/` **cuando** se inicia la arquitectura **entonces** no se crea nada y el mensaje dice que hace falta pasar antes por `discovery`.

### R002

- **Dado** un atributo «el sistema es escalable» sin cifra **cuando** se comprueba **entonces** hay un hallazgo de atributo no medible.
- **Dado** un atributo sin cita al brief **cuando** se comprueba **entonces** hay un hallazgo de atributo sin motivo.

### R003

- **Dado** un componente con responsabilidad y las candidatas B01 y B02 **cuando** se comprueba **entonces** las dos constan como alojadas en él.

### R004

- **Dado** un backlog con B01, B02 y B03 descartada, y componentes que solo alojan B01 **cuando** se comprueba **entonces** hay un error por B02 y ninguno por B03.

### R005

- **Dado** las decisiones 0001 y 0002, la 0002 rechazada **cuando** se registra una nueva **entonces** recibe el número 0003.
- **Dado** una decisión sin alternativas descartadas **cuando** se comprueba **entonces** hay un error.
- **Dado** una decisión que no cita ningún atributo ni objetivo **cuando** se comprueba **entonces** hay un error de decisión sin motivo.

### R006

- **Dado** un estándar sin decisión de origen **cuando** se comprueba **entonces** hay un error.

### R007

- **Dado** un componente que aloja B09, inexistente **cuando** se comprueba **entonces** hay un error que nombra B09.
- **Dado** un estándar que cita la decisión 0009, inexistente **cuando** se comprueba **entonces** hay un error que la nombra.

### R008

- **Dado** una arquitectura con un error **cuando** se ejecuta la comprobación en modo CI **entonces** termina con fallo; sin errores, termina bien aunque haya avisos.
- **Dado** la comprobación con salida legible por máquina **cuando** se ejecuta **entonces** cada hallazgo trae su código, su severidad y el artefacto afectado.

### R009

- **Dado** una pregunta abierta que cita la decisión 0002 **cuando** se intenta aprobar **entonces** se niega y la nombra.

### R010

- **Dado** una arquitectura coherente sin preguntas que bloqueen **cuando** el usuario aprueba **entonces** cada artefacto queda aprobado con la huella de su contenido.
- **Dado** una arquitectura con un error **cuando** el usuario aprueba **entonces** se niega y lista los errores.

### R011

- **Dado** una arquitectura aprobada **cuando** se edita la responsabilidad de un componente **entonces** la comprobación informa de que los componentes cambiaron tras aprobarse.
- **Dado** lo mismo **cuando** solo se reformatea un artefacto sin cambiar su contenido **entonces** sigue aprobado.

### R012

- **Dado** el modelo trabajando **cuando** escribe «Approved» en el Estado de un artefacto o de una decisión **entonces** la escritura se deniega.
- **Dado** un comando que el guardrail no detecta y que aprueba un artefacto **cuando** termina **entonces** el Estado vuelve a su valor anterior y se avisa.
- **Dado** el escape documentado activo **cuando** el usuario aprueba a mano **entonces** no se bloquea.

### R013

- **Dado** la decisión 0004 propuesta **cuando** el usuario la acepta **entonces** queda aprobada.
- **Dado** la decisión 0004 propuesta **cuando** el usuario la rechaza **entonces** queda rechazada y conserva su número.
- **Dado** la decisión 0004 propuesta que sustituye a la 0002 aprobada **cuando** el usuario la acepta **entonces** la 0004 queda aprobada y la 0002 queda sustituida por la 0004.

### R014

- **Dado** una arquitectura aprobada **cuando** se aprueba de nuevo el backlog con una candidata nueva **entonces** la comprobación avisa de que el producto cambió desde la arquitectura, y da error por la candidata sin componente.

### R015

- **Dado** un repositorio con `product/` aprobado y sin los plugins `discovery` ni `sdd` instalados **cuando** se usa `architecture` **entonces** inicia, comprueba y aprueba igual.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento de
los guardrails.

## Supuestos

- `architecture` siempre parte de un producto de `discovery`; sin él no hay de
  dónde sacar restricciones ni candidatas. Un producto sin `discovery` usa
  `sdd` como hasta ahora.
- La aprobación cubre el conjunto: atributos, componentes, estándares y las
  decisiones que no estén propuestas, rechazadas ni sustituidas. Una decisión
  propuesta se decide aparte, con la revisión (R013).
- El backlog aprobado no se modifica: qué candidatas aloja cada componente se
  dice en los artefactos de arquitectura.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.
