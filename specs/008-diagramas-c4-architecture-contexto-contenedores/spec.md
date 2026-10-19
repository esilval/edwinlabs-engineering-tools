# Spec: diagramas C4 en architecture: contexto, contenedores y componentes desde la arquitectura aprobada

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `008-diagramas-c4-architecture-contexto-contenedores`     |
| Fecha  | 2026-10-19     |
| Estado | Approved · 1c58ad4c642a        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

En la prueba real del plugin `architecture` (2026-10-19), el usuario vio que todo
lo que entrega es texto: atributos, componentes, decisiones y estándares en
listas. Entender cómo encajan las partes, quién usa el sistema, con qué sistemas
externos habla y por qué las dependencias van en un sentido y no en otro exige
reconstruir el dibujo de cabeza leyendo varios archivos. Le pasa a quien aprueba
la arquitectura y a quien planifica cada feature sobre ella, en cada producto.

## Contexto

- El plugin `architecture` deja en `architecture/` atributos de calidad,
  componentes con las candidatas que alojan, decisiones (ADR) y estándares
  comprobables (capas, dependencias entre componentes, dependencias
  prohibidas), aprobados por el usuario con huella.
- Decisiones del usuario para esta feature (2026-10-19):
  - los diagramas se escriben como texto dentro de los artefactos, en un formato
    que GitHub y los editores habituales muestran dibujado sin instalar nada
    (Mermaid);
  - aquí van las tres primeras vistas del modelo C4 (contexto, contenedores y
    componentes), que describen el producto; los diagramas de cada feature
    (secuencia, modelo de datos, clases) son otra feature, en `sdd`;
  - un script genera el esqueleto a partir de lo aprobado y el modelo lo
    completa; una comprobación vigila que lo dibujado no se aparte de lo
    aprobado.
- La constitución exige lo determinista en scripts, solo biblioteca estándar y
  aprobación solo del usuario.

## Alcance

### Dentro

- Tres vistas C4 de la arquitectura de un producto: contexto, contenedores y
  componentes.
- Un esqueleto generado sin intervención del modelo a partir de los usuarios del
  brief, los componentes y las dependencias de los estándares, con la decisión
  de la que sale cada dependencia.
- La comprobación de que los diagramas son coherentes con los componentes y los
  estándares aprobados.
- Los diagramas como parte del conjunto que el usuario aprueba.

### Fuera (non-goals)

- La cuarta vista C4 (código).
- Diagramas de cada feature (secuencia, modelo de datos, clases): feature
  siguiente, en `sdd`.
- Convertir los diagramas en imágenes o controlar su disposición en pantalla.
- Fusionar automáticamente un esqueleto nuevo con diagramas ya completados.
- Cambios en `discovery` o en `sdd`.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO se pide la diagramación de una arquitectura, el sistema DEBERÁ producir tres vistas: contexto del sistema, contenedores y componentes. |
| R002 | MUST | CUANDO se genera el esqueleto, el sistema DEBERÁ incluir, sin intervención del modelo, los tipos de usuario del brief en el contexto y cada componente de la arquitectura en las vistas de contenedores y componentes. |
| R003 | MUST | CUANDO se genera el esqueleto, el sistema DEBERÁ dibujar cada dependencia entre componentes que declaran los estándares, indicando la decisión de la que se deriva. |
| R004 | MUST | SI los diagramas ya existen, ENTONCES el sistema NO DEBERÁ sobrescribirlos al generar el esqueleto. |
| R005 | MUST | SI un diagrama nombra un componente que no existe en la arquitectura, ENTONCES el sistema DEBERÁ informarlo como error. |
| R006 | MUST | SI a la vista de contenedores o a la de componentes le falta un componente de la arquitectura, ENTONCES el sistema DEBERÁ informarlo como error. |
| R007 | MUST | SI un diagrama dibuja entre dos componentes una dependencia que un estándar prohíbe o declara en sentido contrario, ENTONCES el sistema DEBERÁ informarlo como error. |
| R008 | MUST | CUANDO el usuario aprueba la arquitectura, el sistema DEBERÁ incluir los diagramas en el conjunto aprobado, con su huella y la detección de cambios posteriores. |
| R009 | MUST | SI una arquitectura no tiene diagramas, ENTONCES el sistema DEBERÁ avisarlo sin impedir su comprobación ni su aprobación. |
| R010 | MUST | SI el modelo intenta aprobar los diagramas, por escritura directa o por un comando, ENTONCES el sistema DEBERÁ impedirlo o revertirlo, como con el resto del conjunto. |

## Criterios de aceptación

### R001

- **Dado** una arquitectura con componentes y estándares **cuando** se genera el esqueleto **entonces** existen las tres vistas, cada una identificada como contexto, contenedores o componentes.

### R002

- **Dado** un brief con los usuarios «Dueños de comercios pequeños» y «Gestor», y los componentes C1 y C2 **cuando** se genera el esqueleto **entonces** el contexto muestra los dos tipos de usuario y el sistema, y las otras dos vistas muestran C1 y C2 con su nombre.

### R003

- **Dado** el estándar S1 «C2 → C1» derivado de ADR-0001 **cuando** se genera el esqueleto **entonces** la vista de componentes dibuja la dependencia de C2 a C1 indicando ADR-0001.

### R004

- **Dado** unos diagramas que el modelo ya completó con un sistema externo **cuando** se vuelve a generar el esqueleto **entonces** el archivo no cambia y se indica que ya existía.

### R005

- **Dado** una vista de componentes que dibuja C7, inexistente **cuando** se comprueba la arquitectura **entonces** hay un error que nombra C7.

### R006

- **Dado** la arquitectura con C1 y C2 y una vista de contenedores que solo dibuja C1 **cuando** se comprueba **entonces** hay un error que nombra C2 y la vista.

### R007

- **Dado** el estándar «C2 → C1» **cuando** la vista de componentes dibuja una dependencia de C1 a C2 **entonces** hay un error que nombra el estándar.
- **Dado** un estándar que prohíbe que C1 dependa de C3 **cuando** un diagrama dibuja C1 → C3 **entonces** hay un error.

### R008

- **Dado** una arquitectura con diagramas coherentes **cuando** el usuario la aprueba **entonces** los diagramas quedan aprobados con su huella.
- **Dado** una arquitectura aprobada **cuando** se edita un diagrama **entonces** la comprobación avisa de que cambió tras aprobarse.

### R009

- **Dado** una arquitectura aprobada antes de esta feature, sin diagramas **cuando** se comprueba y se aprueba **entonces** hay un aviso que pide generarlos y la aprobación no se niega por ello.

### R010

- **Dado** el modelo trabajando **cuando** escribe «Approved» en el Estado de los diagramas **entonces** la escritura se deniega.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento de
los guardrails.

## Supuestos

- En C4, cada componente de `architecture/components.md` es a la vez un
  contenedor (una pieza desplegable o un almacén) y el elemento de la vista de
  componentes; el modelo puede detallar más la vista de componentes, pero no
  inventar componentes que la arquitectura no tiene.
- Los sistemas externos y las tecnologías no están en ningún artefacto
  estructurado: los añade el modelo a partir de los ADR y el brief, y no se
  comprueban.
- Los tipos de usuario del brief son las viñetas de su sección de usuarios.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.
