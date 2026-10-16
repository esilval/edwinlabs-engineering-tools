# Spec: robustez de sdd: auditoría de todas las features

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `003-robustez-sdd-auditoria-todas-features`     |
| Fecha  | 2026-10-15     |
| Estado | Approved · b1b4107a1ff0        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

Cuatro fallos de `sdd` que aparecieron al usarlo en este repositorio, durante
las features 001 y 002:

1. **La auditoría posterior a un comando solo vigila la feature activa.** Un
   comando puede cambiar la feature activa, aprobar un artefacto de otra y
   volver a dejarla como estaba, sin que nada lo revierta. Desde que la compuerta
   previa deja pasar las menciones, es la única vía que queda para que una
   aprobación no la dé una persona.
2. **El siguiente ID libre de requisito cuenta cualquier mención.** La spec de la
   feature 002 saltó del sexto requisito al décimo porque su texto citaba
   requisitos de otra feature.
3. **Una tarea cerrada da error por requisitos obsoletos.** Tras una enmienda, una
   tarea cerrada que todavía citaba el requisito retirado dio
   `E-DONE-NO-TEST`, un error que en CI tumba el PR, por un requisito que ya no
   se puede probar.
4. **Las citas fuera de una prueba se atribuyen a la prueba anterior.** En el
   selftest de `sdd`, las llamadas a las pruebas desde su función principal
   aparecían como evidencia de la última prueba definida. Puede dar por probado
   un requisito con una prueba que no lo verifica.

Le duele a quien depende de la aprobación como garantía (1), de la trazabilidad
como medida de cobertura (3, 4) y de IDs legibles (2).

## Contexto

- La compuerta previa y la auditoría posterior se rediseñaron en la feature 002.
  La compuerta reconoce la ejecución de la orden de aprobar; la auditoría
  revierte lo que la compuerta no ve. Este límite de la auditoría quedó
  documentado en el README como pendiente de una feature propia.
- La vista de código para archivos de prueba Python (feature 002) ya distingue
  textos literales de código; fuera de Python, el texto se usa tal cual.
- La constitución exige que los guardrails fallen abiertos y no concedan
  permisos, y que el selftest cubra cada cambio.

## Alcance

### Dentro

- Que la auditoría proteja la aprobación de los artefactos de todas las
  features, no solo de la activa.
- Que el siguiente ID libre se calcule a partir de los requisitos declarados.
- Que una tarea cerrada no dé error por requisitos obsoletos.
- Que, en Python, una cita fuera de una prueba no se atribuya a ninguna prueba.

### Fuera (non-goals)

- Cambiar la compuerta previa al comando.
- El mismo falso positivo de la compuerta en el plugin `discovery`.
- Cambiar cómo se atribuyen las citas fuera de Python.
- Cambiar códigos de hallazgo o la forma del schema `sdd.trace/v1`.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | SI un comando cambia hacia aprobado el Estado de un artefacto de una feature que no es la activa, ENTONCES el sistema DEBERÁ devolverlo a su valor anterior. |
| R002 | MUST | SI un comando no cambia el Estado de ningún artefacto de ninguna feature, ENTONCES el sistema NO DEBERÁ avisar de ninguna aprobación ni modificar ningún artefacto. |
| R003 | MUST | CUANDO se pide el siguiente ID libre de requisito, el sistema DEBERÁ calcularlo solo a partir de los requisitos declarados en la tabla de requisitos, incluidos los obsoletos. |
| R004 | MUST | SI a una tarea cerrada solo le falta prueba para requisitos obsoletos, ENTONCES el sistema NO DEBERÁ informar de ella como tarea cerrada sin prueba. |
| R005 | MUST | SI en un archivo de pruebas Python una cita a un requisito aparece fuera de toda función de prueba, ENTONCES el sistema NO DEBERÁ contarla como evidencia. |
| R006 | MUST | CUANDO una prueba Python cita un requisito en su nombre o en un comentario de su cuerpo, el sistema DEBERÁ seguir contándola como evidencia de esa prueba. |
| R007 | MUST | CUANDO se calcula la trazabilidad de un archivo de pruebas que no es Python, el sistema DEBERÁ atribuir las citas exactamente igual que antes de esta feature. |

## Criterios de aceptación

### R001

- **Dado** dos features con la 002 activa y el `spec.md` de la 001 en Draft **cuando** un comando aprueba ese `spec.md` **entonces** al terminar vuelve a Draft y se avisa.
- **Dado** la 002 activa **cuando** un comando cambia la feature activa a la 001, aprueba su `plan.md` y deja activa la 002 **entonces** el `plan.md` de la 001 vuelve a su valor anterior.
- **Dado** un artefacto ya aprobado con una huella **cuando** un comando reescribe la huella **entonces** recupera la huella anterior.

### R002

- **Dado** varias features **cuando** un comando no toca ningún artefacto **entonces** la auditoría no avisa ni escribe nada.
- **Dado** un repo sin `specs/` **cuando** se ejecuta cualquier comando **entonces** la auditoría no hace nada.

### R003

- **Dado** una spec con los requisitos R001 a R006 cuyo texto menciona R007 y R009 de otra feature **cuando** se pide el siguiente ID **entonces** es R007.
- **Dado** una spec cuyo último requisito declarado es R005 y está obsoleto **cuando** se pide el siguiente ID **entonces** es R006.

### R004

- **Dado** una tarea cerrada que cita un requisito obsoleto sin prueba y uno vigente con prueba **cuando** se calcula la trazabilidad **entonces** no hay `E-DONE-NO-TEST`.
- **Dado** una tarea cerrada que cita un requisito vigente sin prueba **cuando** se calcula la trazabilidad **entonces** sigue habiendo `E-DONE-NO-TEST`.

### R005

- **Dado** una función `main()` que llama a `test_F001_R001_algo(base)` **cuando** se calcula la trazabilidad **entonces** esa línea no es evidencia de R001 ni se atribuye a otra prueba.
- **Dado** un comentario de módulo con `# F001-R002`, fuera de toda función **cuando** se calcula la trazabilidad **entonces** no cuenta como evidencia de R002.

### R006

- **Dado** una prueba `def test_F001_R001_algo():` con una aserción **cuando** se calcula la trazabilidad **entonces** cuenta como evidencia de R001 a nombre de esa prueba.
- **Dado** un método de prueba `def test_x(self):` dentro de una clase, con un comentario `# F001-R002` **cuando** se calcula la trazabilidad **entonces** cuenta como evidencia de R002 a nombre de esa prueba.
- **Dado** el selftest de `discovery` **cuando** se calcula la trazabilidad de la feature 001 **entonces** sus requisitos MUST siguen teniendo exactamente las mismas pruebas.

### R007

- **Dado** archivos de prueba en JS, Go, Ruby, Kotlin, C# y Java **cuando** se calcula la trazabilidad **entonces** la evidencia es idéntica, etiquetas incluidas, a la que daba la versión anterior.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento de
los guardrails.

## Supuestos

- Un comando no aprueba a propósito más de unos pocos artefactos a la vez; vigilar
  todos los artefactos de todas las features es asumible en cada comando.
- En Python, «fuera de toda función de prueba» incluye el nivel de módulo y las
  funciones que no son pruebas (`main()`, ayudantes). Un comentario de módulo con
  una cita deja de contar; en Python es un uso raro.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.

- **2026-10-15 · R002 (aclaración):** el requisito decía «NO DEBERÁ avisar ni
  modificar nada», lo que al pie de la letra prohibía el aviso que la auditoría
  ya da cuando un comando cambia código con la compuerta cerrada. Se limita a lo
  que siempre quiso decir: ningún aviso de aprobación y ningún artefacto
  modificado. Ese otro aviso no cambia. Los criterios no cambian.
