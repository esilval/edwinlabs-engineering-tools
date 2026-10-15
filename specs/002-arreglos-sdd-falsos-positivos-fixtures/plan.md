# Plan: arreglos de sdd: falsos positivos y fixtures como evidencia

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-15         |
| Estado | Approved · 6cef81d5c0a2              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

Tres cambios pequeños en `plugins/sdd/scripts/`. La trazabilidad busca citas a
requisitos en una **vista de código** de los archivos de prueba Python, con los
textos literales en blanco; en los demás lenguajes el texto se usa tal cual. La compuerta sobre Bash reconoce la aprobación por las
**palabras del comando** (`… sdd.py approve`), no por una cadena en cualquier
parte del texto. El aviso de prueba sin prefijo usa el ID real. La auditoría
posterior no cambia y sigue siendo la red de lo que la compuerta no ve.

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Lo determinista en un script | sí | Todo el cambio está en `sdd_trace.py` y `sdd_bash.py` |
| Python 3.8, solo biblioteca estándar | sí | `tokenize` es de la biblioteca estándar y existe en 3.8 |
| Guardrail que falla abierto y con escape | sí | Un comando que no se puede analizar solo se bloquea si su texto contiene la orden de aprobar; lo demás lo cubre la auditoría. Un archivo Python que no se tokeniza se lee tal cual. El escape `SDD_BYPASS=1` no cambia |
| Ningún hook devuelve `allow` | sí | Solo se estrecha cuándo se deniega; las salidas no cambian |
| Solo el usuario aprueba | sí | `sdd.py approve` ejecutado sigue bloqueado (R005) y la auditoría sigue revirtiendo (R006) |
| Códigos y schemas como contrato | sí | No cambia ningún código ni campo de `sdd.trace/v1`; cambia el texto de un mensaje |
| Todo código de hallazgo alcanzable | sí | El selftest de `sdd` sigue comparando declarados con probados |
| Selftest cubre el cambio | sí | Pruebas `test_F002_Rxxx_*` nuevas en `plugins/sdd/tests/selftest.py` |

## Decisiones

### D1 — Vista de código de un archivo de pruebas Python (R010, R002)

- **Contexto:** hoy se busca `F001_R001` en cada línea del archivo, y la
  declaración de prueba más cercana por encima se toma de las líneas tal cual.
  Una cadena `"def test_F001_R001_algo():…"` cuenta como prueba y como cita.
- **Decisión:** antes de buscar, se construye una vista del archivo con las
  mismas líneas y columnas, en la que el contenido de los textos literales se
  sustituye por espacios. En esa vista se buscan las citas y las declaraciones
  de prueba. Los nombres de función y los comentarios se conservan (R002). La
  clasificación del cuerpo (vacía, sin aserción) sigue usando el texto real.
  - **Python:** la vista se calcula con `tokenize`, que conoce las cadenas de
    varias líneas, sobre las mismas líneas que `splitlines()` para que las filas
    coincidan. Si el archivo no se puede tokenizar, se usa el texto tal cual,
    como hoy.
  - **Resto de lenguajes:** la vista es el texto tal cual, como antes de esta
    feature (R010).
- **Alternativas descartadas:**
  - Excluir los archivos de prueba de los plugins (no-goal de la spec, y el
    problema reaparece en cualquier repo con fixtures).
  - Marcar los fixtures con una convención especial (obliga a recordarla).
  - **Vaciar también los textos fuera de Python, intentado dos veces en T003 y
    descartado.** Primero, vaciando todo salvo el título de `it/test/describe`;
    después, con un analizador por línea que conservaba comentarios y primeros
    argumentos de llamada. Las dos revisiones encontraron pérdidas de evidencia
    real en formas habituales: comentarios con apóstrofos o de varias líneas,
    títulos de RSpec (`xit`, `scenario`), Bats, nombres de Kotlin entre comillas
    invertidas, `DisplayName = "…"` de C#, ScalaTest y subpruebas por tabla de
    Go. Sin un analizador real por lenguaje, la lista no se acaba, y perder una
    cita real tumba el CI.
- **Consecuencias:** un fixture escrito en otro lenguaje dentro de un test sigue
  contando como evidencia, como hoy. El caso que motivó la feature (el selftest
  de `sdd`) está en Python.

### D2 — Reconocer la aprobación por las palabras del comando (R004, R005)

- **Contexto:** hoy la compuerta busca `sdd.py approve` o el nombre de la
  función que reescribe el Estado en cualquier parte del comando, incluidos
  mensajes de commit, descripciones de PR y heredocs.
- **Decisión:** la compuerta reutiliza el análisis de comandos que ya tiene
  `sdd_bash.py`: quita los heredocs, separa el comando en segmentos y palabras
  respetando las comillas, y deniega solo si algún segmento tiene una palabra
  cuyo nombre de archivo es `sdd.py` seguida de la palabra `approve`. Un texto
  entre comillas es una sola palabra, así que una mención no coincide. El
  contenido de las sustituciones de comandos (`$(…)` y comillas invertidas) se
  analiza aparte, porque se ejecuta aunque vaya entre comillas dobles. La
  búsqueda del nombre de la función se retira de la compuerta previa. Si el
  comando no se puede analizar (algo que el analizador no entiende y bash sí),
  se busca en el texto solo `sdd.py approve`, como hacía la compuerta anterior:
  así un trozo ilegible no sirve para colar una aprobación.
- **Alternativas descartadas:** mantener la búsqueda de texto con excepciones
  para `git commit` y `gh pr` (lista que nunca se acaba); seguir bloqueando
  `python3 -c` con la función dentro (es justo lo que la compuerta no puede
  distinguir de una mención; la auditoría ya lo resuelve después).
- **Consecuencias:** `bash -c "python3 sdd.py approve"` o un script que llame a
  la función pasan la compuerta. Los cubre la auditoría, que devuelve el Estado
  a su valor anterior (R006); es el supuesto de la spec. Una mención dentro de
  un comando que no se puede analizar se sigue bloqueando; es raro y es el mal
  menor. La auditoría solo vigila la feature activa: un comando que cambie
  `.sdd/current` puede aprobar otra feature sin que lo vea. Se documenta como
  límite conocido y se resuelve en una feature aparte.

### D3 — Mensaje de `W-TEST-UNSCOPED` (R003)

- **Contexto:** el mensaje tiene «R001» escrito a mano.
- **Decisión:** usar el ID del requisito afectado.
- **Alternativas descartadas:** ninguna razonable.
- **Consecuencias:** cambia el texto del mensaje, no el código ni los campos.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/sdd/scripts/sdd_trace.py` | vista de código para Python en `scan_tests`; texto tal cual en otros lenguajes; mensaje de `W-TEST-UNSCOPED` | R010, R002, R003 |
| `plugins/sdd/scripts/sdd_bash.py` | `invokes_approve` por palabras del comando | R004, R005 |
| `plugins/sdd/tests/selftest.py` | pruebas `test_F002_Rxxx_*` | R010, R002, R003, R004, R005, R006 |
| `plugins/sdd/README.md` | la compuerta reconoce la ejecución, no la mención; las citas en textos solo dejan de contar en Python | R004, R010 |

## Modelo de datos

No aplica.

## Contratos

No cambian. Los códigos de hallazgo y el schema `sdd.trace/v1` quedan igual; la
interfaz de los hooks también.

## Estrategia de pruebas

| Requisito | Tipo de prueba | Dónde vive |
| --------- | -------------- | ---------- |
| R010 | integración: en Python, fixture en cadena (también de varias líneas) y cita en texto no cuentan; en JS, Go, Ruby, Java y Kotlin las citas cuentan como antes | `plugins/sdd/tests/selftest.py` |
| R002 | integración: nombre de prueba y comentario en el cuerpo siguen contando; un salto de página no desalinea la vista | ídem |
| R003 | integración: `test_R004_x` sin prefijo produce un aviso que nombra R004 | ídem |
| R004 | integración: commit con mensaje, PR con descripción, heredoc a archivo y `echo` con la orden no se bloquean | ídem |
| R005 | integración: `python3 sdd.py approve`, ruta absoluta y encadenado tras `&&` se bloquean | ídem |
| R006 | integración: comando opaco que aprueba `spec.md` es revertido por la auditoría (la prueba actual sigue pasando) | ídem |

Además, al cerrar: `sdd trace` de la feature 001 no debe apuntar a
`plugins/sdd/tests/selftest.py` para R001 ni R002 (criterio de R010).

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| Un archivo de pruebas Python con errores de sintaxis no se tokeniza | vuelve el comportamiento de hoy en ese archivo | se usa el texto tal cual; nunca falla ni bloquea |
| Un fixture en otro lenguaje sigue contando | un requisito podría figurar como probado sin serlo | consecuencia aceptada en R010; documentada en el README |
| La compuerta deja pasar más comandos | una autoaprobación por script no se bloquea antes | la auditoría la revierte después (R006, probado) |

## Trazabilidad

Los seis requisitos MUST vigentes (R002–R006 y R010) aparecen en la tabla de
componentes y en la de pruebas. R001 es obsoleto (reemplazado por R010).
