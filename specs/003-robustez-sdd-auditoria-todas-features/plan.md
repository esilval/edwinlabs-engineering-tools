# Plan: robustez de sdd: auditoría de todas las features

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-15         |
| Estado | Approved · e151fae38e93              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

Cuatro arreglos independientes en `plugins/sdd/scripts`, cada uno con sus
pruebas en el selftest. La auditoría pasa a tomar la instantánea del Estado de
los artefactos de todas las features, indexada por `slug/archivo`, en vez de
los de la feature activa. El siguiente ID y la regla de tarea cerrada sin
prueba usan los requisitos que la trazabilidad ya reconoce como declarados.
En Python, una cita se atribuye a la función de prueba que la contiene según el
árbol sintáctico (`ast`), no a la última declaración que aparece encima. Es el
mismo criterio de la feature 002: el cambio se limita a donde hay un analizador
real, y fuera de Python todo queda como estaba.

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Python 3.8, solo biblioteca estándar | sí | `ast` es de la biblioteca estándar, y `end_lineno` existe desde 3.8 |
| Lo determinista vive en un script | sí | todo el cambio está en `sdd.py` y `sdd_trace.py`; ninguna skill cambia |
| Un guardrail falla abierto | sí | si un archivo Python no se puede analizar, se vuelve a la atribución anterior. Un artefacto ilegible se salta en la instantánea, sin bloquear el comando |
| Un guardrail nunca concede permisos | sí | la compuerta previa no cambia; la auditoría solo restaura el campo Estado |
| Solo el usuario aprueba | sí | este plan cierra la vía que quedaba abierta: aprobar otra feature desde un comando |
| Códigos y schema como contrato | sí | no se añade, renombra ni elimina ningún código; el schema `sdd.trace/v1` no cambia. Solo cambia qué evidencia cuenta, y con ella cuándo se emiten `E-DONE-NO-TEST` y `E-REQ-NO-TEST` |
| Todo código de hallazgo alcanzable | sí | no se declaran códigos nuevos |
| El selftest cubre cada cambio | sí | pruebas `test_F003_RNNN_…` en `plugins/sdd/tests/selftest.py` para los siete requisitos |
| Plugins unidos solo por archivos | sí | `discovery` no cambia; su evidencia se verifica igual antes y después (D4) |

## Decisiones

### D1 — La instantánea abarca todas las features, con clave `slug/archivo`

- **Contexto:** `guard_bash` guarda `{archivo: Estado}` solo de la feature
  activa, y `cmd_audit` resuelve la feature activa *después* del comando. Un
  comando que mueva `.sdd/current` hace que se compare con otra feature, o con
  ninguna.
- **Decisión:** una función `all_approvals(root)` devuelve
  `{"NNN-slug/spec.md": Estado, …}` para cada artefacto de fase de cada
  directorio de `feature_dirs(root)`. `guard_bash` la guarda siempre que la
  aprobación esté activa en la configuración, haya o no feature activa.
  `cmd_audit` recorre esas claves contra `specs_dir(root)`, sin consultar la
  feature activa. Restaura y avisa cuando el artefacto queda aprobado con un
  Estado distinto del anterior, la misma condición que hoy. El aviso nombra
  `slug/archivo`. `phase_approvals(feature)` se sustituye por la nueva función,
  porque no tiene más usos.
- **Alternativas descartadas:**
  - *Guardar también la feature activa antes del comando y auditar esa.*
    Resuelve el caso del puntero, pero no un comando que apruebe otra feature
    sin tocarlo, que es el primer criterio de R001.
  - *Vigilar solo las features con artefactos en Draft.* El caso de la huella
    reescrita (tercer criterio) parte de un artefacto ya aprobado.
- **Consecuencias:**
  - Cada llamada a Bash lee la cabecera de todos los artefactos, unos pocos KB
    por feature. Con decenas de features sigue siendo despreciable frente al
    `git status` que ya se ejecuta. Es el supuesto de la spec.
  - Una instantánea antigua, guardada por la versión anterior con claves sin
    `/`, se ignora. Solo puede ocurrir en la llamada en curso al actualizar el
    plugin.
  - Un artefacto que no existía antes del comando no se vigila, igual que hoy
    (ver Riesgos).

### D2 — El siguiente ID sale de los requisitos que `parse_spec` reconoce

- **Contexto:** `cmd_next_req` aplica `REQ_ID` a todo el texto de la spec.
- **Decisión:** `cmd_next_req` toma `parse_spec(spec)["requirements"]`, el
  mismo conjunto que usa la trazabilidad, con obsoletos incluidos. Esa función
  lee las filas de la tabla de requisitos y, como respaldo, los encabezados
  `## RNNN` de las specs antiguas sin tabla.
- **Alternativas descartadas:**
  - *Una expresión nueva que solo lea filas de tabla.* Duplica la de
    `parse_spec`, y las dos acabarían divergiendo. Además, en una spec antigua
    declarada con encabezados devolvería `R001`, es decir, reciclaría IDs, que
    es lo que el comando existe para impedir.
- **Consecuencias:** para una spec hecha con la plantilla, que es el caso de R003,
  el resultado es exactamente el de la tabla. Para una spec con encabezados se
  mantiene la numeración que la trazabilidad ya le reconoce.

### D3 — `E-DONE-NO-TEST` ignora los requisitos obsoletos

- **Contexto:** la comprobación de tareas cerradas busca pruebas para todos los
  requisitos que cita la tarea. Los obsoletos tienen siempre `tests: []`.
- **Decisión:** al calcular `sin_test`, se excluyen los IDs del conjunto
  `obsolete`, que ya se calcula unas líneas antes en `analyze`.
- **Alternativas descartadas:**
  - *Emitir un aviso (`W-`) en vez del error.* Haría falta un código nuevo, y el
    caso ya lo describe `W-TASK-OBSOLETE-REQ` para las tareas abiertas. Para una
    tarea cerrada, citar un requisito retirado es historia, no un problema.
- **Consecuencias:** una tarea cerrada que cite solo requisitos obsoletos queda
  sin hallazgos de prueba.

### D4 — En Python, la cita se atribuye a la función de prueba que la contiene

- **Contexto:** `scan_tests` busca hacia atrás, hasta 25 líneas, la última
  declaración de prueba y le atribuye la cita. Si no la encuentra, la atribuye
  al archivo. Así, las llamadas desde `main()` del selftest de `sdd` aparecen
  como evidencia de una prueba o del archivo entero.
- **Decisión:**
  - Una función nueva, `python_test_spans(content)`, analiza el archivo con
    `ast` y devuelve `(primera_línea, última_línea, nombre)` de cada
    `FunctionDef` o `AsyncFunctionDef` cuyo nombre empieza por `test`, también
    las anidadas y los métodos de clase.
  - En `scan_tests`, para archivos `.py`, una línea con cita solo cuenta si cae
    dentro de algún rango, y se atribuye al más interior, el de mayor primera
    línea. La etiqueta es el nombre de esa función, y `test_body_kind` se
    calcula desde su línea `def`.
  - Las citas se siguen buscando en la vista de código de la feature 002, que
    deja los textos literales en blanco.
  - Si `ast.parse` falla, por sintaxis inválida o de una versión de Python más
    nueva, el archivo usa la atribución anterior.
  - Los demás lenguajes no pasan por esta rama.
- **Alternativas descartadas:**
  - *Seguir mirando hacia atrás, pero cortar en cualquier `def` que no sea de
    prueba.* No cubre los comentarios a nivel de módulo ni el código que sigue a
    una prueba sin pasar por otro `def`, que es el caso de `main()` tras la
    última prueba.
  - *Hacerlo con `tokenize` y la indentación.* Vuelve a construir a mano un
    analizador que `ast` ya da, con `end_lineno` exacto.
- **Consecuencias:**
  - Un comentario de cita a nivel de módulo, o encima de un `def`, deja de
    contar. Es el supuesto de la spec.
  - Comprobado con un prototipo sobre este repositorio: las pruebas de
    `discovery` siguen siendo exactamente las mismas. En `sdd` desaparecen las
    seis referencias de la feature 002 a nivel de archivo, sin nombre de
    prueba, que salían de `main()`. Esos requisitos siguen teniendo sus pruebas
    con nombre.
  - El tercer criterio de R006 (`discovery`) se verifica una vez, en la tarea,
    comparando el JSON de `trace` antes y después. No se convierte en una prueba
    permanente, porque ataría el selftest de `sdd` al contenido de las pruebas
    de otro plugin, y cualquier prueba nueva de `discovery` lo rompería.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/sdd/scripts/sdd.py` · `guard_bash`, `all_approvals` (sustituye a `phase_approvals`) | instantánea de todas las features con clave `slug/archivo` | R001, R002 |
| `plugins/sdd/scripts/sdd.py` · `cmd_audit` | compara y restaura por clave contra `specs/`, sin la feature activa | R001, R002 |
| `plugins/sdd/scripts/sdd.py` · `cmd_next_req` | usa `parse_spec(...)["requirements"]` | R003 |
| `plugins/sdd/scripts/sdd_trace.py` · `analyze` | `E-DONE-NO-TEST` excluye obsoletos | R004 |
| `plugins/sdd/scripts/sdd_trace.py` · `python_test_spans`, `scan_tests` | atribución por rango de función de prueba en `.py`, con la anterior como respaldo | R005, R006, R007 |
| `plugins/sdd/tests/selftest.py` | pruebas `test_F003_RNNN_…` y su registro en `main()` | R001–R007 |
| `plugins/sdd/README.md` | quitar el límite «la auditoría solo vigila la feature activa»; anotar qué citas cuentan en Python | R001, R005 |

## Modelo de datos

La instantánea de la auditoría, un JSON temporal por llamada, cambia la clave
`approved` de `{"spec.md": "Draft"}` a `{"003-x/spec.md": "Draft"}`. Es interna
al hook y no se persiste más allá de la llamada.

## Contratos

- `sdd.py next-req` mantiene su salida: una línea con `RNNN`.
- `sdd.trace/v1` no cambia de forma. En Python, la etiqueta de una prueba sigue
  siendo `ruta::nombre`, y deja de haber evidencia de una línea suelta con solo
  `ruta`.
- Los mensajes de la auditoría siguen el formato actual y ya nombraban
  `feature/archivo`.

## Estrategia de pruebas

| Requisito | Tipo de prueba | Dónde vive |
| --------- | -------------- | ---------- |
| R001 | integración: repo git con dos features; guard → mutación → audit. Casos: otra feature aprobada; puntero cambiado y restaurado; huella reescrita | `plugins/sdd/tests/selftest.py` |
| R002 | integración: comando sin cambios con varias features (exit 0, sin stderr, sin escrituras); repo sin `specs/` | `plugins/sdd/tests/selftest.py` |
| R003 | integración: `next-req` sobre una spec cuyo texto menciona requisitos de otra feature y sobre una spec cuyo último requisito es obsoleto | `plugins/sdd/tests/selftest.py` |
| R004 | integración: `trace --json` con una tarea cerrada que cita un obsoleto sin prueba, y con otra que cita un vigente sin prueba | `plugins/sdd/tests/selftest.py` |
| R005 | integración: archivo con `main()` que llama a una prueba y con un comentario de módulo; la evidencia no los incluye | `plugins/sdd/tests/selftest.py` |
| R006 | integración: prueba con aserción y método de clase con comentario. Más la comparación única de `discovery` en la tarea (D4) | `plugins/sdd/tests/selftest.py` |
| R007 | integración: los archivos de JS, Go, Ruby, Kotlin, C# y Java de la feature 002 dan exactamente la evidencia esperada | `plugins/sdd/tests/selftest.py` (reutiliza `OTROS_LENGUAJES` y `ESPERADO`) |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| Un `git checkout`, `pull` o `rebase` lanzado por el modelo trae una versión aprobada de un artefacto que localmente estaba en Draft, y la auditoría la revierte | El árbol queda modificado y el modelo recibe un aviso. Hoy ya ocurre con la feature activa; al vigilar todas, ocurre más a menudo | El aviso pide detenerse y avisar al usuario. Los comandos que el usuario lanza con `!` no pasan por hooks, y queda `SDD_BYPASS=1`. Se documenta en el README. Distinguir una aprobación traída por git de una fabricada por el comando sería un requisito nuevo, fuera de esta spec |
| Un comando crea un artefacto nuevo ya aprobado, por ejemplo una feature entera desde un script | La aprobación no se revierte, igual que hoy | Vigilarlo revertiría también las features que llegan aprobadas con un `git pull`. Queda como límite en el README |
| `ast.parse` falla en archivos con sintaxis de una versión más nueva que la del intérprete | Ese archivo usa la atribución anterior | Es fallar abierto. Se prueba con un archivo inválido |
| Un decorador o un comentario encima del `def` con una cita deja de contar | Un requisito puede pasar a `E-REQ-NO-TEST` en otro repo | Es el supuesto de la spec. El README dice que en Python solo cuentan el nombre y el cuerpo de la prueba |

## Trazabilidad

Los siete requisitos MUST (R001–R007) aparecen en la tabla de componentes y en
la de pruebas. No queda ninguno sin cubrir.
