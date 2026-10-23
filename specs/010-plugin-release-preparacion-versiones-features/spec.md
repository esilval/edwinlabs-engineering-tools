# Spec: plugin release: preparación de versiones con features elegidas

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `010-plugin-release-preparacion-versiones-features`     |
| Fecha  | 2026-10-22     |
| Estado | Approved · 375b17637be4        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

Con `discovery`, `architecture` y `sdd`, un producto llega a tener features
especificadas, planificadas e implementadas, pero nada decide cuándo un
conjunto de ellas está listo para publicarse. Hoy esa decisión se toma de
memoria y faltan tres cosas:
- comprobar que cada feature está terminada de verdad: fases aprobadas, tareas
  cerradas, trazabilidad sin errores y decisiones vigentes;
- elegir el número de versión con un criterio;
- contar qué cambia, a los usuarios y al equipo.

Le pasa al responsable del producto en cada publicación. Un error en esa
decisión publica una feature a medio terminar o una versión cuyo número no
avisa de que rompe algo.

## Contexto

- La serie de plugins cubre el ciclo de vida, una etapa por plugin, unidos
  solo por archivos: `discovery` → `architecture` → `sdd` → `release` →
  `operate`. `release` es la cuarta etapa y hoy no existe.
- Lo que hay para leer:
  - `sdd` deja cada feature en `specs/NNN-slug/` con su spec, plan y tareas,
    cada fase aprobada con huella, y una trazabilidad requisito → tarea →
    prueba con contrato público;
  - `architecture` deja las decisiones (ADR) con su estado;
  - `discovery` deja los objetivos y las candidatas del producto, de las que
    salen las features.
- Decisiones del usuario (2026-10-22):
  - el plugin prepara la versión y deja la decisión de publicarla al usuario:
    no despliega;
  - el usuario elige qué features entran en cada versión;
  - el número de versión sigue el versionado semántico, lo propone el sistema
    y lo confirma el usuario;
  - hay notas para los usuarios del producto y un registro de cambios técnico;
  - cada spec de `sdd` dice si la feature añade funcionalidad o solo corrige,
    para proponer el número de versión; el usuario aprueba este cambio en el
    formato de `sdd` (aclaración del 2026-10-22).
- La constitución exige:
  - lo determinista va en scripts, solo con la biblioteca estándar;
  - aprueba solo el usuario, con guardrails que fallan abiertos y tienen
    escape;
  - códigos de hallazgo estables con prefijo reservado en el registro común;
  - un selftest por plugin.

## Alcance

### Dentro

- Una versión como artefacto: las features que incluye, el resultado de las
  comprobaciones, el número, las notas para usuarios y el registro de cambios
  técnico.
- La comprobación de que cada feature incluida está terminada.
- La propuesta del número de versión respecto a la última aprobada.
- La aprobación de la versión por el usuario como decisión de publicarla, y
  la protección de esa aprobación.
- La misma comprobación en local y en CI.

### Fuera (non-goals)

- Desplegar, etiquetar en el control de versiones o publicar paquetes: el
  usuario lo hace tras aprobar.
- Planes de despliegue y vuelta atrás, y configuración de CI/CD.
- Incluir cambios que no son una feature de `specs/`.
- Operar el producto publicado: es el plugin `operate`.
- Cambios en `discovery` o `architecture`. En `sdd` solo cambia lo que piden
  R017 (que la spec diga el tipo de la feature) y R018 (trazar una feature
  concreta).

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO el usuario pide una versión con un conjunto de features, el sistema DEBERÁ crear su borrador, sin intervención del modelo, con esas features, sus requisitos y el resultado de las comprobaciones. |
| R002 | MUST | SI una feature incluida no tiene la spec, el plan y las tareas aprobados, o alguno cambió después de aprobarse, ENTONCES el sistema DEBERÁ informarlo como error nombrando la feature y la fase. |
| R003 | MUST | SI una feature incluida tiene tareas sin cerrar, ENTONCES el sistema DEBERÁ informarlo como error nombrando las tareas. |
| R004 | MUST | SI la trazabilidad de una feature incluida tiene errores, ENTONCES el sistema DEBERÁ informarlo como error. |
| R005 | MUST | SI el plan de una feature incluida cita una decisión de arquitectura que no está aprobada, ENTONCES el sistema DEBERÁ informarlo como error. |
| R006 | MUST | SI una feature incluida ya está en otra versión aprobada, o no existe, ENTONCES el sistema DEBERÁ informarlo como error. |
| R007 | MUST | CUANDO se crea el borrador, el sistema DEBERÁ proponer el número de versión según el versionado semántico respecto a la última versión aprobada: mayor si alguna feature retira requisitos (en la serie 0.x, la menor), menor si alguna añade funcionalidad y parche si todas solo corrigen; la primera versión es 0.1.0. |
| R008 | MUST | SI el número de una versión no es mayor que el de la última versión aprobada, o ya existe, ENTONCES el sistema DEBERÁ informarlo como error. |
| R009 | MUST | CUANDO se crea el borrador, el sistema DEBERÁ dejar por completar las notas para usuarios y el registro de cambios técnico, con lo que cada feature aporta: los objetivos y candidatas del producto de los que sale, y sus requisitos, decisiones de arquitectura, contratos y cambios de datos. |
| R010 | MUST | SI una versión tiene errores o partes sin completar, ENTONCES el sistema NO DEBERÁ permitir aprobarla. |
| R011 | MUST | CUANDO el usuario aprueba una versión, el sistema DEBERÁ sellarla con la huella de su contenido e indicarle cómo etiquetarla en el control de versiones, sin hacerlo. |
| R012 | MUST | SI una versión aprobada cambia después de aprobarse, ENTONCES el sistema DEBERÁ dejar de considerarla aprobada e indicarlo. |
| R013 | MUST | SI el modelo intenta aprobar una versión, por escritura directa o por un comando, ENTONCES el sistema DEBERÁ impedirlo o revertirlo, con un escape documentado para el usuario. |
| R014 | MUST | CUANDO se comprueba una versión, el sistema DEBERÁ dar el mismo resultado en local y en CI, con códigos de hallazgo estables y un error que haga fallar la comprobación en CI. |
| R015 | MUST | MIENTRAS el proyecto no tenga producto de `discovery` o arquitectura, el sistema DEBERÁ funcionar igual, sin citar objetivos y candidatas ni comprobar decisiones de arquitectura. |
| R016 | SHOULD | SI la trazabilidad de una feature no se puede obtener, ENTONCES el sistema DEBERÁ avisarlo y aplicar el resto de comprobaciones. |
| R017 | MUST | CUANDO se crea la spec de una feature, el sistema DEBERÁ registrar si la feature añade funcionalidad o solo corrige, con «añade funcionalidad» por defecto. |
| R018 | MUST | CUANDO se pide la trazabilidad de una feature concreta, el sistema DEBERÁ darla con el mismo resultado y formato que la de la feature activa, sin cambiar cuál es la feature activa. |

## Criterios de aceptación

### R001

- **Dado** las features 008 y 009 terminadas **cuando** el usuario pide una versión con ellas **entonces** existe un borrador que las nombra con sus requisitos y sin errores de comprobación.
- **Dado** que el usuario no nombra ninguna feature **cuando** pide una versión **entonces** no se crea nada y se indica cómo elegirlas.

### R002

- **Dado** una feature cuyo plan está en borrador **cuando** se comprueba la versión **entonces** hay un error que nombra la feature y el plan.
- **Dado** una feature cuya spec cambió después de aprobarse **cuando** se comprueba **entonces** hay un error que nombra la feature y la spec.

### R003

- **Dado** una feature con T004 en curso **cuando** se comprueba la versión **entonces** hay un error que nombra la feature y T004.

### R004

- **Dado** una feature con un requisito MUST sin prueba **cuando** se comprueba la versión **entonces** hay un error que nombra la feature.

### R005

- **Dado** una feature cuyo plan cita ADR-0004, propuesta y sin decidir **cuando** se comprueba la versión **entonces** hay un error que nombra la feature y ADR-0004.

### R006

- **Dado** la versión 0.1.0 aprobada con la feature 008 **cuando** se comprueba un borrador que también la incluye **entonces** hay un error que nombra 008 y 0.1.0.
- **Dado** que el usuario pide la feature 042, que no existe **cuando** se comprueba **entonces** hay un error que la nombra.

### R007

- **Dado** que no hay ninguna versión aprobada **cuando** se crea el borrador **entonces** el número propuesto es 0.1.0.
- **Dado** la última versión aprobada 0.3.2 y una feature que añade funcionalidad **cuando** se crea el borrador **entonces** el número propuesto es 0.4.0.
- **Dado** la última versión aprobada 1.4.0 y una feature con un requisito retirado **cuando** se crea el borrador **entonces** el número propuesto es 2.0.0.
- **Dado** la última versión aprobada 0.3.2 y una feature con un requisito retirado **cuando** se crea el borrador **entonces** el número propuesto es 0.4.0.
- **Dado** la última versión aprobada 0.4.0 y dos features cuya spec dice que solo corrigen **cuando** se crea el borrador **entonces** el número propuesto es 0.4.1.
- **Dado** una feature cuya spec no dice su tipo (creada antes de esta feature) **cuando** se crea el borrador **entonces** cuenta como funcionalidad nueva.

### R008

- **Dado** la última versión aprobada 0.4.0 **cuando** el usuario fija el número 0.3.9 **entonces** hay un error que nombra los dos números.

### R009

- **Dado** una feature creada desde la candidata B01, que sirve al objetivo G1 **cuando** se crea el borrador **entonces** las notas para usuarios tienen un hueco que cita B01 y G1, y el registro de cambios cita los requisitos de la feature y los ADR de su plan.

### R010

- **Dado** un borrador con las notas sin completar **cuando** el usuario intenta aprobarlo **entonces** la aprobación se niega, dice qué falta y no cambia nada.
- **Dado** un borrador con un error de comprobación **cuando** el usuario intenta aprobarlo **entonces** la aprobación se niega y no cambia nada.

### R011

- **Dado** un borrador completo y sin errores **cuando** el usuario lo aprueba **entonces** queda aprobado con su huella y se le indica el comando para etiquetar la versión, que nadie ejecuta.

### R012

- **Dado** una versión aprobada **cuando** se editan sus notas **entonces** la comprobación avisa de que cambió tras aprobarse.

### R013

- **Dado** el modelo trabajando **cuando** escribe «Approved» en el Estado de una versión **entonces** la escritura se deniega.
- **Dado** el modelo trabajando **cuando** un comando opaco aprueba una versión **entonces** la aprobación se revierte con un aviso.

### R014

- **Dado** una versión con un error **cuando** se comprueba en modo CI **entonces** la comprobación falla y el resultado legible por máquinas trae el código del error.

### R015

- **Dado** un proyecto sin `product/` ni `architecture/` **cuando** se crea y se comprueba una versión **entonces** funciona, las notas no citan objetivos ni candidatas y no hay hallazgos de arquitectura.

### R016

- **Dado** que la trazabilidad de una feature no se puede obtener **cuando** se comprueba la versión **entonces** hay un aviso que lo dice y las demás comprobaciones se aplican.

### R017

- **Dado** que se crea una feature nueva **cuando** se genera su spec **entonces** la cabecera dice que añade funcionalidad, y el usuario puede cambiarlo a que solo corrige.
- **Dado** una spec que dice un tipo que no es ninguno de los dos **cuando** se comprueba una versión que la incluye **entonces** hay un error que nombra la feature y el valor.

### R018

- **Dado** la feature activa 010 **cuando** se pide la trazabilidad de la feature 008 **entonces** el resultado es el mismo que daría con 008 activa, y la feature activa sigue siendo 010.
- **Dado** que se pide la trazabilidad de la feature 042, que no existe **cuando** se ejecuta **entonces** falla, nombra 042 y no cambia nada.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento
de los guardrails.

## Supuestos

- Una feature está terminada cuando sus tres fases están aprobadas sin
  cambios, todas sus tareas están cerradas y su trazabilidad no tiene errores.
- Las notas y el registro de cambios los redacta el modelo; el sistema solo
  aporta de qué features, requisitos, decisiones y objetivos tratan.
- Cada versión incluye al menos una feature; una versión sin features no tiene
  sentido en esta serie.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.


## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.

- 2026-10-22 (antes de aprobar, `/sdd:clarify`): la spec de `sdd` dirá si la
  feature añade funcionalidad o solo corrige (R017), y R007 propone el parche a
  partir de ese dato. Una spec sin el dato cuenta como funcionalidad nueva.
- 2026-10-22 (`/sdd:amend`, al planificar): requisito nuevo R018. La
  trazabilidad de `sdd` solo cubría la feature activa, y `release` necesita la
  de cada feature incluida (R004) sin cambiar la activa ni importar código de
  `sdd`. El non-goal sobre `sdd` se amplía a R017 y R018. IDs afectados: R004,
  R018.
- 2026-10-22 (`/sdd:amend`, tras `/sdd:analyze`): aclaración de R007 en su
  sitio. En la serie 0.x, retirar un requisito sube la menor y no la mayor,
  como define SemVer para el desarrollo inicial. El texto anterior decía
  «mayor» sin excepción y contradecía la decisión D6 del plan. ID afectado:
  R007.
