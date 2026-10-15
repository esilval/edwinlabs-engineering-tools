# Spec: arreglos de sdd: falsos positivos y fixtures como evidencia

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `002-arreglos-sdd-falsos-positivos-fixtures`     |
| Fecha  | 2026-10-15     |
| Estado | Approved · f4db4a40601d        |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

Al construir la feature 001 (`discovery`) con el propio `sdd`, aparecieron tres
fallos que confunden **texto** con **intención**:

1. La trazabilidad contó como pruebas de esta feature unas cadenas de ejemplo
   escritas dentro de otro archivo de pruebas (`"def test_F001_R001_algo():…"`
   en el selftest de `sdd`). Un requisito sin prueba real puede figurar como
   probado.
2. El aviso de prueba sin prefijo de feature dice siempre «R001 existe en cada
   feature», aunque el requisito afectado sea otro (salió con R004, R005, R007
   y R009).
3. La compuerta sobre Bash bloqueó dos comandos que solo **mencionaban** la
   aprobación: uno que editaba el código de pruebas de `discovery` y el que
   abría el PR #4, cuya descripción citaba la función que reescribe el campo
   Estado. Hubo que rodearlo escribiendo a un archivo aparte.

Le duele a quien usa `sdd` cada vez que trabaja en código o pruebas que hablan
de la propia aprobación, y a cualquiera que confíe en la cobertura que informa
la trazabilidad.

## Contexto

- Los tres fallos están documentados en el PR #4 y en la feature 001.
- La aprobación de `sdd` tiene dos capas: la compuerta antes de ejecutar un
  comando y la auditoría después, que devuelve el Estado a su valor anterior si
  un comando opaco lo cambió. Esta segunda capa no cambia.
- La constitución exige que los guardrails fallen abiertos y no concedan
  permisos, y que todo código de hallazgo siga siendo alcanzable en el selftest.
- `discovery` tiene el mismo falso positivo en su propia compuerta (está en sus
  límites conocidos). Se trata aparte, porque es otro plugin.

## Alcance

### Dentro

- Que la trazabilidad no cuente como evidencia lo que solo es texto dentro de un
  archivo de pruebas.
- Que el aviso de prueba sin prefijo nombre el requisito correcto.
- Que la compuerta sobre Bash distinga entre ejecutar la aprobación y
  mencionarla.

### Fuera (non-goals)

- El mismo falso positivo en la compuerta de `discovery`: feature aparte del
  plugin `discovery`.
- Cambiar códigos de hallazgo o la forma del schema `sdd.trace/v1`.
- Limitar la búsqueda de pruebas a ciertos directorios o plugins.
- La auditoría posterior al comando, que ya funciona.

## Requisitos

Notación EARS. Cada requisito lleva un ID estable que se referencia después en
`plan.md`, `tasks.md` y en los tests.

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | OBSOLETO | SI la cita a un requisito con prefijo de feature aparece en un archivo de pruebas solo como parte de un texto literal, ENTONCES el sistema NO DEBERÁ contarla como evidencia de prueba. (reemplazado por R010) |
| R002 | MUST | CUANDO una prueba cita un requisito en su nombre o en un comentario de su cuerpo, el sistema DEBERÁ seguir contándola como evidencia de prueba. |
| R003 | MUST | CUANDO el sistema avisa de una prueba que cita un requisito sin prefijo de feature, el sistema DEBERÁ nombrar en el mensaje el requisito afectado. |
| R004 | MUST | SI un comando solo menciona la orden de aprobación como texto, sin ejecutarla, ENTONCES el sistema NO DEBERÁ bloquearlo. |
| R005 | MUST | CUANDO un comando ejecuta la orden de aprobación de `sdd`, el sistema DEBERÁ seguir bloqueándolo. |
| R006 | MUST | SI un comando que la compuerta deja pasar cambia el Estado de un artefacto hacia aprobado, ENTONCES el sistema DEBERÁ seguir devolviéndolo a su valor anterior. |
| R010 | MUST | SI la cita a un requisito con prefijo de feature aparece en un archivo de pruebas Python solo como parte de un texto literal, ENTONCES el sistema NO DEBERÁ contarla como evidencia de prueba. |

## Criterios de aceptación

### R001

- **Dado** un archivo de pruebas que contiene la cadena `"def test_F001_R001_algo():\n    assert x\n"` como dato **cuando** se calcula la trazabilidad de la feature 001 **entonces** R001 no tiene esa evidencia.
- **Dado** una cita `F001-R002` dentro de un texto entre comillas de una prueba que no cita el requisito de otra forma **cuando** se calcula la trazabilidad **entonces** R002 no la cuenta.
- **Dado** el selftest actual de `sdd` en este repositorio **cuando** se calcula la trazabilidad de la feature 001 **entonces** ninguna evidencia de R001 ni de R002 apunta a `plugins/sdd/tests/selftest.py`.

### R002

- **Dado** una prueba `def test_F001_R001_algo():` con una aserción **cuando** se calcula la trazabilidad **entonces** cuenta como evidencia de R001.
- **Dado** una prueba con un comentario `# F001-R002` en su cuerpo **cuando** se calcula la trazabilidad **entonces** cuenta como evidencia de R002.
- **Dado** el selftest de `discovery` **cuando** se calcula la trazabilidad de la feature 001 **entonces** sus 13 requisitos MUST siguen teniendo prueba.

### R003

- **Dado** una prueba `test_R004_x` sin prefijo **cuando** se calcula la trazabilidad **entonces** el aviso nombra R004 y no R001.

### R004

- **Dado** un `git commit -m` cuyo mensaje cita la orden de aprobación **cuando** la compuerta lo evalúa **entonces** no lo bloquea.
- **Dado** un comando que crea un PR con una descripción que cita la función que reescribe el Estado **cuando** la compuerta lo evalúa **entonces** no lo bloquea.
- **Dado** un comando que escribe en un archivo un texto que contiene la orden de aprobación **cuando** la compuerta lo evalúa **entonces** no lo bloquea.

### R005

- **Dado** el comando `python3 <ruta>/sdd.py approve` **cuando** la compuerta lo evalúa **entonces** lo bloquea.
- **Dado** la orden de aprobación encadenada tras otra (`cd x && python3 sdd.py approve plan`) **cuando** la compuerta lo evalúa **entonces** lo bloquea.

### R006

- **Dado** un comando opaco que la compuerta deja pasar y que marca `spec.md` como aprobado **cuando** termina **entonces** la auditoría devuelve el Estado a su valor anterior.

### R010

- **Dado** un archivo de pruebas Python que contiene la cadena `"def test_F001_R001_algo():\n    assert x\n"` como dato **cuando** se calcula la trazabilidad de la feature 001 **entonces** R001 no tiene esa evidencia.
- **Dado** una cita `F001-R002` dentro de un texto entre comillas de una prueba Python que no cita el requisito de otra forma **cuando** se calcula la trazabilidad **entonces** R002 no la cuenta.
- **Dado** el selftest actual de `sdd` en este repositorio **cuando** se calcula la trazabilidad de la feature 001 **entonces** ninguna evidencia de R001 ni de R002 apunta a `plugins/sdd/tests/selftest.py`.
- **Dado** un archivo de pruebas en otro lenguaje (JS, Go, Ruby, Java…) **cuando** se calcula la trazabilidad **entonces** las citas cuentan exactamente igual que antes de esta feature, también las que van dentro de un texto.

## Requisitos no funcionales

No aplica. La constitución fija versión mínima, dependencias y comportamiento de
los guardrails.

## Supuestos

- Ejecutar código arbitrario que reescriba el Estado (un script o un intérprete
  con el código en línea) no es algo que la compuerta previa pueda distinguir de
  forma fiable de una mención; para eso existe la auditoría posterior (R006).

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.

- **2026-10-15 · R001 pasa a OBSOLETO, reemplazado por R010 (cambio de
  comportamiento).** No contar las citas dentro de textos literales se limita a
  los archivos de prueba Python; en los demás lenguajes las citas cuentan como
  antes. Motivo: dos revisiones de T003 demostraron que vaciar textos fuera de
  Python con un analizador hecho a mano pierde evidencia real en formas
  habituales (comentarios de varias líneas, títulos de RSpec, Kotlin, C#,
  subpruebas por tabla de Go), y eso rompía R002. Python tiene un analizador
  real (`tokenize`). El ID es R010 porque `next-req` cuenta también las
  menciones a R007 y R009 de la sección «Problema»; R007–R009 quedan sin usar.
  Afecta a: R001, R010, y a las pruebas `test_F002_R001_*`.
