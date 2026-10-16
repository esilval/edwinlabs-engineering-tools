# Spec: robustez de sdd y discovery: raíz del proyecto y falso positivo de la compuerta

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `004-robustez-sdd-discovery-raiz-proyecto`     |
| Fecha  | 2026-10-15     |
| Estado | Approved · 7c8f8f5b3e05        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

Tres fallos que aparecieron al usar los plugins en este repositorio:

1. **Una aprobación lanzada desde un subdirectorio no encuentra el proyecto.**
   Durante la feature 003, el directorio de trabajo de la sesión quedó dentro de
   `specs/`, y `/sdd:approve` respondió «No hay una feature activa». Sin la
   variable de entorno con la raíz del proyecto, los dos plugins toman el
   directorio actual como raíz. Al usuario le cuesta una aprobación fallida y
   una explicación, y `discovery` tiene el mismo problema.
2. **La compuerta de `discovery` bloquea las menciones a su orden de aprobar.**
   Un mensaje de commit, la descripción de un PR o un documento que cite esa
   orden se bloquea como si se ejecutara. `sdd` ya lo resolvió en su feature
   002; `discovery` sigue igual, y obliga a reescribir mensajes para esquivarlo.
3. **El selftest de `discovery` genera un aviso de trazabilidad en cada feature
   de este repositorio.** Un comentario explica que una prueba no verifica un
   requisito, citándolo sin prefijo de feature, y la trazabilidad lo informa
   como cita ambigua en cada `trace`.

## Contexto

- Las skills de aprobación ejecutan el script fuera de los hooks, con el
  directorio actual de la sesión. Los hooks sí reciben la raíz del proyecto.
- La compuerta de `sdd` distingue ejecutar la orden de aprobar de mencionarla;
  lo que no ve lo revierte su auditoría. `discovery` también tiene auditoría
  posterior al comando.
- La constitución exige que los plugins se unan solo por archivos: `discovery`
  no puede usar código de `sdd`.

## Alcance

### Dentro

- Que `sdd` y `discovery` encuentren la raíz del proyecto desde un
  subdirectorio cuando el entorno no la indica.
- Que la compuerta de `discovery` bloquee la ejecución de su orden de aprobar y
  deje pasar las menciones.
- Que el selftest de `discovery` deje de provocar avisos de trazabilidad.

### Fuera (non-goals)

- Cambiar cómo se resuelve la feature activa una vez conocida la raíz.
- Cambiar la auditoría de `discovery` o la de `sdd`.
- Compartir código entre plugins.
- Proyectos anidados: un proyecto dentro de otro se trata como el más cercano.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO `sdd` se ejecuta en un subdirectorio de un proyecto que lo usa y el entorno no indica la raíz, el sistema DEBERÁ usar como raíz el directorio ascendente más cercano que contenga sus datos. |
| R002 | MUST | CUANDO `discovery` se ejecuta en un subdirectorio de un proyecto que lo usa y el entorno no indica la raíz, el sistema DEBERÁ usar como raíz el directorio ascendente más cercano que contenga sus datos. |
| R003 | MUST | SI ningún directorio ascendente contiene los datos del plugin, ENTONCES el sistema DEBERÁ usar el directorio actual, como hasta ahora. |
| R004 | MUST | CUANDO el entorno indica la raíz del proyecto, el sistema DEBERÁ usarla sin buscar en otros directorios. |
| R005 | MUST | SI un comando solo menciona la orden de aprobar de `discovery` como texto, ENTONCES la compuerta de `discovery` NO DEBERÁ bloquearlo. |
| R006 | MUST | CUANDO un comando ejecuta la orden de aprobar de `discovery`, la compuerta DEBERÁ bloquearlo, también si va encadenada a otro comando o dentro de una sustitución que se ejecuta. |
| R007 | MUST | SI un comando que la compuerta deja pasar cambia hacia aprobado el Estado del brief o del backlog, ENTONCES el sistema DEBERÁ devolverlo a su valor anterior. |
| R008 | SHOULD | CUANDO se calcula la trazabilidad de una feature de este repositorio, el sistema NO DEBERÁ informar de citas sin prefijo procedentes del selftest de `discovery`. |

## Criterios de aceptación

### R001

- **Dado** un proyecto con una feature activa y la sesión en `specs/<feature>/` **cuando** se consulta el estado sin la variable de la raíz **entonces** muestra la feature activa del proyecto.
- **Dado** el mismo proyecto **cuando** se aprueba desde ese subdirectorio **entonces** se aprueba el artefacto de la feature activa.

### R002

- **Dado** un proyecto con `product/` y la sesión en `product/sources/` **cuando** se ejecuta la comprobación sin la variable de la raíz **entonces** analiza el brief y el backlog del proyecto.

### R003

- **Dado** un directorio sin datos de ningún plugin en él ni por encima **cuando** se ejecuta un comando **entonces** se comporta como hasta ahora con el directorio actual.

### R004

- **Dado** la variable de la raíz apuntando a un proyecto y la sesión en otro proyecto **cuando** se ejecuta un comando **entonces** actúa sobre el proyecto de la variable.

### R005

- **Dado** un `product/` con brief y backlog **cuando** el modelo lanza un `git commit -m` cuyo mensaje cita la orden de aprobar de `discovery` **entonces** la compuerta no lo bloquea.
- **Dado** lo mismo **cuando** la orden aparece en el cuerpo de un heredoc, entre comillas simples o en la descripción de un PR **entonces** no se bloquea.

### R006

- **Dado** un `product/` con brief y backlog **cuando** el modelo ejecuta la orden de aprobar de `discovery` directamente, tras `&&` o `;`, o dentro de `$(…)` o de comillas invertidas **entonces** la compuerta la bloquea.
- **Dado** un comando que no se puede analizar y contiene la orden **cuando** se evalúa **entonces** se bloquea.

### R007

- **Dado** un comando opaco que la compuerta deja pasar **cuando** marca el backlog como aprobado **entonces** al terminar vuelve a su Estado anterior y se avisa.

### R008

- **Dado** el repositorio tras esta feature **cuando** se calcula la trazabilidad **entonces** no hay `W-TEST-UNSCOPED` que señale el selftest de `discovery`.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento de
los guardrails.

## Supuestos

- Los datos de cada plugin identifican su proyecto: `.sdd/` o `specs/` para
  `sdd`, y `product/` para `discovery`.
- La búsqueda hacia arriba no necesita salir del repositorio en el que está la
  sesión; si no lo hay, basta con llegar a la raíz del sistema de archivos.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.
