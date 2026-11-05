# Spec: comando de diagnóstico por plugin: python3, scripts y hooks, con aviso al iniciar la sesión

| Campo  | Valor        |
| ------ | ------------ |
| ID     | `012-comando-diagnostico-plugin-python3-scripts`     |
| Fecha  | 2026-11-04     |
| Estado | Approved · 98fb1c656f74        |
| Tipo   | funcionalidad |
| Issue  | —            |

> Este documento describe **qué** y **por qué**, nunca **cómo**.
> Toda decisión de implementación (librerías, esquemas, servicios) va en `plan.md`.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Problema

Los cinco plugins de la serie necesitan el intérprete de Python, en una
versión mínima, para todo lo que hacen: comprobaciones, borradores, la
compuerta de `sdd` y los guardrails que impiden que el modelo apruebe.

Si el intérprete falta o es demasiado antiguo, nada lo dice con claridad. Los
guardrails fallan abiertos por diseño, así que dejan de proteger en silencio.
Quien instala un plugin cree que la compuerta y las aprobaciones están
protegidas y no lo están.

Le pasa a quien instala la serie en una máquina nueva, en especial en sistemas
donde el intérprete tiene otro nombre o no viene instalado. Hoy no tiene forma
de comprobar que la instalación funciona.

## Contexto

- La serie (`discovery`, `architecture`, `sdd`, `release`, `operate`) se
  instala plugin a plugin desde el marketplace. Cada plugin funciona sin los
  demás y no comparte código con ellos (constitución).
- La constitución fija Python 3.8 como versión mínima, solo con la biblioteca
  estándar.
- Todos los plugins registran hooks que protegen la aprobación. `sdd` registra
  además la compuerta y un hook al iniciar la sesión que da contexto al
  modelo. Ningún plugin comprueba hoy que su intérprete funciona.
- La constitución exige que un guardrail falle abierto: si un hook revienta,
  deja pasar. Es lo correcto para no bloquear al usuario, y es también la
  causa de que la pérdida de protección no se note.
- Decisiones del usuario (2026-11-04), al analizar la facilidad de
  instalación:
  - mantener la distribución como plugins, sin pasar a un servidor MCP, que no
    puede ofrecer la compuerta ni la aprobación solo del usuario;
  - un diagnóstico por plugin, que funcione aunque los demás no estén
    instalados;
  - que compruebe el intérprete y su versión, que los scripts del plugin
    arrancan y que sus guardrails responden;
  - que se lance a mano y que, además, avise al iniciar la sesión si falta el
    intérprete o no llega a la versión mínima.

## Alcance

### Dentro

- Un diagnóstico por plugin, que lanza el usuario o el modelo, con el
  resultado de cada comprobación y un resumen final.
- La comprobación del intérprete y de su versión, también cuando el intérprete
  no se puede ejecutar.
- La comprobación de que los scripts del plugin arrancan y de que sus
  guardrails responden a una petición de prueba.
- Un aviso al iniciar la sesión si el intérprete falta o es demasiado antiguo,
  y silencio si está bien.

### Fuera (non-goals)

- Instalar o actualizar el intérprete, o corregir solo lo que falle.
- Ejecutar las pruebas completas de cada plugin.
- Avisar de los escapes de los guardrails activos en el entorno.
- Diagnosticar el marketplace, la red o la configuración de Claude Code.
- Un servidor MCP u otra forma de distribución.

## Requisitos

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO el usuario pide el diagnóstico de un plugin, el sistema DEBERÁ comprobar que el intérprete existe y que su versión es la mínima de la constitución o posterior, e informar la versión encontrada. |
| R002 | MUST | SI el intérprete no existe o su versión es anterior a la mínima, ENTONCES el diagnóstico DEBERÁ decirlo, explicar que las comprobaciones, la compuerta y los guardrails del plugin no funcionan, y decir cómo resolverlo, sin depender de ese intérprete para hacerlo. |
| R003 | MUST | MIENTRAS el intérprete sea válido, el diagnóstico DEBERÁ comprobar que los scripts del plugin arrancan y responden, e informar el error si alguno no lo hace. |
| R004 | MUST | MIENTRAS el intérprete sea válido, el diagnóstico DEBERÁ comprobar que cada guardrail del plugin responde a una petición de prueba como debe: impide una aprobación escrita por el modelo y deja pasar una operación inocua. |
| R005 | MUST | El diagnóstico NO DEBERÁ modificar ningún archivo del proyecto ni el estado de ningún artefacto. |
| R006 | MUST | CUANDO el diagnóstico termina, el sistema DEBERÁ mostrar el resultado de cada comprobación y un resumen que diga si el plugin está listo o qué falta. |
| R007 | MUST | El diagnóstico de un plugin DEBERÁ funcionar aunque los demás plugins de la serie no estén instalados. |
| R008 | MUST | CUANDO empieza una sesión con el plugin instalado y el intérprete falta o es anterior a la mínima, el sistema DEBERÁ avisar al usuario nombrando el problema y el diagnóstico que lo detalla. |
| R009 | MUST | MIENTRAS el intérprete sea válido, el aviso de inicio de sesión NO DEBERÁ mostrar nada. |
| R010 | MUST | SI el aviso de inicio de sesión falla por un error inesperado, ENTONCES el sistema NO DEBERÁ impedir que la sesión empiece. |
| R011 | SHOULD | SI varios plugins de la serie están instalados y el intérprete falla, ENTONCES el sistema DEBERÁ evitar que el mismo aviso se repita idéntico por cada plugin. |

## Criterios de aceptación

### R001

- **Dado** el intérprete en la versión 3.11 **cuando** el usuario pide el diagnóstico de `release` **entonces** el resultado dice que el intérprete está bien e indica 3.11.

### R002

- **Dado** que el intérprete no existe en la máquina **cuando** el usuario pide el diagnóstico de `sdd` **entonces** el resultado dice que falta, que la compuerta y los guardrails de `sdd` no funcionan, y cómo instalarlo.
- **Dado** el intérprete en la versión 3.6 **cuando** se pide el diagnóstico **entonces** el resultado dice que 3.6 es anterior a 3.8 y qué hacer.

### R003

- **Dado** un script del plugin con un error que le impide arrancar **cuando** se pide el diagnóstico **entonces** el resultado nombra ese script y muestra el error.

### R004

- **Dado** el plugin bien instalado **cuando** se pide el diagnóstico **entonces** el resultado dice que su guardrail impide una aprobación de prueba y deja pasar una edición inocua.
- **Dado** un guardrail que no responde como debe **cuando** se pide el diagnóstico **entonces** el resultado dice que el guardrail no protege y que el plugin no está listo.

### R005

- **Dado** un proyecto con artefactos en borrador y aprobados **cuando** se pide el diagnóstico de cada plugin **entonces** ningún archivo del proyecto cambia.

### R006

- **Dado** el intérprete bien y un guardrail que falla **cuando** termina el diagnóstico **entonces** el resumen dice que el plugin no está listo y nombra el guardrail.

### R007

- **Dado** que solo `operate` está instalado **cuando** se pide su diagnóstico **entonces** se completa sin errores por la falta de los demás.

### R008

- **Dado** que el intérprete no existe **cuando** empieza una sesión con `release` instalado **entonces** aparece un aviso que dice que falta el intérprete y nombra el diagnóstico de `release`.

### R009

- **Dado** el intérprete en 3.11 **cuando** empieza una sesión **entonces** no aparece ningún aviso de diagnóstico.

### R010

- **Dado** un fallo inesperado al comprobar el intérprete en el inicio **cuando** empieza la sesión **entonces** la sesión empieza con normalidad.

### R011

- **Dado** los cinco plugins instalados y el intérprete ausente **cuando** empieza una sesión **entonces** el usuario no recibe cinco avisos idénticos.

## Requisitos no funcionales

| ID   | Requisito |
| ---- | --------- |
| N001 | El aviso de inicio de sesión DEBERÁ terminar en menos de 1 segundo cuando el intérprete está bien, para no retrasar el arranque. |

## Supuestos

- El intérprete que importa es el mismo que usan los hooks de los plugins: si
  el diagnóstico lo encuentra bien, los hooks también.
- El shell del sistema está disponible en todas las plataformas en que se
  ejecuta Claude Code, aunque falte Python.
- Una petición de prueba a un guardrail se puede hacer sin escribir nada en el
  proyecto.

## Preguntas abiertas

> Cita entre paréntesis el requisito al que afecta cada pregunta:
> `- [ ] (R002) ¿Cuánto dura la sesión?`. Una pregunta abierta sobre un MUST
> impide aprobar la spec. Al resolverla, conviértela en requisito o criterio y
> borra la línea.

## Historial de cambios

> Lo rellena `/sdd:amend` cuando cambian los requisitos después de aprobar la
> spec: fecha, qué cambió, por qué y los IDs afectados.
