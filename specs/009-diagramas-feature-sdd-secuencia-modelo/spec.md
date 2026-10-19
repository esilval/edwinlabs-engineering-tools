# Spec: diagramas por feature en sdd: secuencia, modelo de datos y clases en el plan

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `009-diagramas-feature-sdd-secuencia-modelo`     |
| Fecha  | 2026-10-19     |
| Estado | Approved · 3edb976bf71d        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

En la prueba real de la serie (2026-10-19), el usuario vio que los planes de
`sdd` son solo texto. Para entender cómo resuelve una feature lo que pide su
spec, quien revisa el plan tiene que reconstruir de cabeza tres cosas:
- quién llama a quién y en qué orden;
- qué datos se crean o cambian;
- qué piezas nuevas aparecen y cómo se relacionan.

Tampoco ve de un vistazo si el flujo respeta la arquitectura aprobada. Le pasa
en cada plan que revisa antes de aprobarlo, y de nuevo a quien implementa o
revisa las tareas.

## Contexto

- `sdd` planifica cada feature en `plan.md`. Con `architecture/` en el
  proyecto, el plan parte de la arquitectura aprobada:
  - `arch-context` lista los componentes que alojan la feature, las decisiones
    vigentes y los estándares;
  - `trace` comprueba que el plan solo cita decisiones aprobadas.
- La feature 008 añadió a `architecture` las vistas C4 de contexto,
  contenedores y componentes, en Mermaid, contrastadas con los componentes y
  los estándares. El usuario las probó en un proyecto real y funcionan.
- Decisiones del usuario (2026-10-19), al pedir la diagramación de la serie:
  - formato Mermaid, como texto dentro de los artefactos, que GitHub y los
    editores muestran dibujado;
  - las vistas del producto en `architecture` y los diagramas de cada feature
    en `sdd`: secuencia, modelo de datos y clases;
  - un script genera lo determinista, el modelo lo completa y una comprobación
    vigila que no se aparte de lo aprobado.
- La constitución exige:
  - `sdd` funciona igual sin `architecture/`;
  - los plugins se unen solo por archivos;
  - lo determinista va en scripts, solo con la biblioteca estándar.

## Alcance

### Dentro

- Diagramas de cada feature en su plan:
  - secuencia del flujo principal;
  - modelo de datos, cuando la feature crea o cambia datos;
  - clases o estructura, cuando la feature introduce piezas nuevas.
- Un punto de partida generado sin el modelo para el diagrama de secuencia,
  con los componentes de la arquitectura que alojan la feature.
- La comprobación de que los diagramas del plan no nombran componentes que no
  existen ni contradicen los estándares de la arquitectura.
- Que el diagrama cite la decisión del plan o de la arquitectura en la que se
  apoya cada interacción relevante.

### Fuera (non-goals)

- Las vistas C4 del producto: ya las da `architecture` (feature 008).
- Diagramas en `spec.md`: la spec describe qué, no cómo.
- Contrastar los diagramas con el código implementado.
- Convertir los diagramas en imágenes o controlar su disposición.
- Cambios en `architecture` o en `discovery`.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO se planifica una feature, el sistema DEBERÁ ofrecer en el plan un lugar para sus diagramas: secuencia, modelo de datos y clases, cada uno con la opción de declarar que no aplica. |
| R002 | MUST | CUANDO se planifica una feature sobre una arquitectura aprobada, el sistema DEBERÁ generar, sin intervención del modelo, un esqueleto del diagrama de secuencia con los componentes que alojan la feature como participantes. |
| R003 | MUST | SI un plan ya tiene diagramas, ENTONCES el sistema NO DEBERÁ sobrescribirlos al generar el esqueleto. |
| R004 | MUST | SI un diagrama del plan nombra un componente que no existe en la arquitectura, ENTONCES el sistema DEBERÁ informarlo. |
| R005 | MUST | SI un diagrama del plan dibuja entre dos componentes una interacción que un estándar prohíbe o declara en sentido contrario, ENTONCES el sistema DEBERÁ informarlo nombrando el estándar. |
| R006 | MUST | SI un plan no tiene diagramas ni declara que no aplican, ENTONCES el sistema DEBERÁ avisarlo sin impedir su aprobación. |
| R007 | MUST | MIENTRAS el proyecto no tenga `architecture/`, el sistema DEBERÁ ofrecer los diagramas del plan sin esqueleto ni comprobaciones contra la arquitectura, y sin fallar por su ausencia. |
| R008 | SHOULD | CUANDO el modelo completa los diagramas, el sistema DEBERÁ pedir que cada interacción entre componentes cite la decisión del plan o de la arquitectura en la que se apoya. |

## Criterios de aceptación

### R001

- **Dado** una feature con la spec aprobada **cuando** se crea su plan **entonces** el plan tiene una sección de diagramas con los apartados de secuencia, modelo de datos y clases.
- **Dado** una feature que no toca datos **cuando** se completa el plan **entonces** el apartado de modelo de datos puede decir «No aplica.» sin que la comprobación lo marque como hueco.

### R002

- **Dado** una feature creada desde la candidata B01, alojada en C1 Ventas, y una arquitectura aprobada **cuando** se genera el esqueleto **entonces** el diagrama de secuencia tiene a C1 como participante con su nombre.
- **Dado** una feature que no viene de una candidata **cuando** se genera el esqueleto **entonces** no se inventan participantes: se indica que el modelo los elige entre los componentes de la arquitectura.

### R003

- **Dado** un plan cuyo diagrama de secuencia ya completó el modelo **cuando** se vuelve a generar el esqueleto **entonces** el plan no cambia y se indica que ya tenía diagramas.

### R004

- **Dado** un diagrama del plan que nombra C7, inexistente **cuando** se comprueba la trazabilidad **entonces** hay un hallazgo que nombra C7.

### R005

- **Dado** el estándar S1 «C2 → C1» **cuando** el diagrama de secuencia dibuja una llamada de C1 a C2 **entonces** hay un hallazgo que nombra S1.
- **Dado** un estándar que prohíbe que C1 dependa de C3 **cuando** un diagrama dibuja una llamada de C1 a C3 **entonces** hay un hallazgo.

### R006

- **Dado** un plan aprobado antes de esta feature, sin sección de diagramas **cuando** se comprueba la trazabilidad **entonces** hay un aviso que pide añadirlos y no un error.

### R007

- **Dado** un proyecto sin `architecture/` **cuando** se planifica una feature **entonces** el plan tiene la sección de diagramas, el esqueleto no se genera y la comprobación no da hallazgos de arquitectura sobre los diagramas.

### R008

- **Dado** el modelo completando el diagrama de secuencia **cuando** dibuja una llamada de C2 a C1 **entonces** las instrucciones le piden citar la decisión (D2 del plan o ADR-0001) en la interacción.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento
de los guardrails.

## Supuestos

- Los componentes que alojan una feature son los que `arch-context` ya da para
  su candidata.
- Fuera de los componentes, los participantes del diagrama de secuencia (el
  usuario, módulos internos, sistemas externos) los elige el modelo y no se
  comprueban.
- El modelo de datos y las clases de una feature no tienen un artefacto
  estructurado con el que contrastarlos: se dibujan y se revisan al aprobar el
  plan, sin comprobación automática.
- Los planes de features anteriores siguen siendo válidos: les falta la
  sección, y eso solo da un aviso.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.
