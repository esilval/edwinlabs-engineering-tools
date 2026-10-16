# Plan: robustez de sdd y discovery: raíz del proyecto y falso positivo de la compuerta

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-15         |
| Estado | Approved · 5917deb58df3              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

Tres cambios pequeños e independientes:
- **Raíz del proyecto.** `project_root` de cada plugin, cuando no recibe
  `CLAUDE_PROJECT_DIR`, sube desde el directorio de partida hasta encontrar los
  datos del plugin, sin salir del repositorio git.
- **Compuerta de `discovery`.** Copia el analizador por palabras que `sdd`
  estrenó en su feature 002 para distinguir ejecutar la orden de aprobar de
  mencionarla. La constitución impide importarlo de `sdd`.
- **Aviso de trazabilidad.** Un comentario del selftest de `discovery` deja de
  citar un requisito sin prefijo.

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Python 3.8, solo biblioteca estándar | sí | `pathlib`, `shlex` y `re`, como el analizador de `sdd` |
| Plugins unidos solo por archivos | sí | `discovery` lleva su propia copia del analizador (D2); no importa nada de `sdd` |
| Un guardrail falla abierto | sí | la búsqueda de la raíz no lanza excepciones: un error de E/S cuenta como «no hay datos aquí». Un comando que no se puede analizar se evalúa por su texto, como en `sdd` |
| Un guardrail nunca concede permisos | sí | la compuerta solo deniega o calla, como hasta ahora |
| Solo el usuario aprueba | sí | ejecutar la orden sigue bloqueado (R006) y la auditoría revierte lo demás (R007) |
| Guardrail con escape documentado | sí | `DISCOVERY_BYPASS=1` no cambia; el README de `discovery` explica qué bloquea la compuerta |
| El selftest cubre cada cambio | sí | pruebas `test_F004_RNNN_…` en los selftests de `sdd` y de `discovery` |
| Códigos y schemas como contrato | sí | no cambia ningún código de hallazgo ni schema |

## Decisiones

### D1 — Subir hasta los datos del plugin, sin salir del repositorio git

- **Contexto:** las skills de aprobación ejecutan el script fuera de los hooks,
  sin `CLAUDE_PROJECT_DIR`, y con el directorio actual de la sesión, que puede
  ser un subdirectorio.
- **Decisión:**
  - En `project_root(payload)`, `CLAUDE_PROJECT_DIR` se usa tal cual, como
    hoy (R004).
  - Si no está, se parte del `cwd` del payload o del directorio actual y se
    sube hasta el primer directorio que contenga los datos del plugin, ese
    incluido.
  - La subida se detiene en el primer directorio con `.git`, sea carpeta o
    archivo (los worktrees usan un archivo), después de examinarlo. Sin git,
    llega a la raíz del sistema de archivos.
  - Si no encuentra nada, devuelve el directorio de partida, como hoy (R003).
- **Qué cuenta como datos:**
  - `sdd`: primero se busca el directorio más cercano con `.sdd/`. Si ninguno
    lo tiene, el más cercano con `specs/`.
  - `discovery`: el más cercano con `product/`.
- **Alternativas descartadas:**
  - *Usar siempre la raíz del repositorio git.* Rompe los monorepos en los que
    el proyecto que usa el plugin es un subdirectorio, y sin git no hay
    respuesta.
  - *Buscar solo `specs/` en `sdd`.* Un proyecto con una carpeta `specs/`
    propia, por ejemplo de pruebas JS (`src/specs/`), haría de `src/` la raíz.
    `.sdd/` es exclusivo del plugin y lo crea `sdd.py new`; `specs/` queda
    como respaldo para los repos que lo adoptaron sin `.sdd/`.
  - *Que la skill pase la raíz como argumento.* Exige que la skill la conozca,
    y la inyección de comandos de una skill no recibe `CLAUDE_PROJECT_DIR`.
- **Consecuencias:**
  - Una función por plugin, de unas 20 líneas, duplicada en los dos (D2).
  - Un proyecto anidado se resuelve al más cercano, como dice la spec.

### D2 — Copiar en `discovery` el analizador de comandos de `sdd`

- **Contexto:** `discovery` deniega cualquier comando cuyo texto case con
  `discovery\.py['"]?\s+approve\b`, también en un mensaje de commit.
- **Decisión:**
  - `discovery.py` incorpora una copia, adaptada en nombres y documentada como
    copia, de lo que usa `sdd_bash.invokes_approve`:
    - quitar los heredocs;
    - partir en palabras con `shlex`;
    - partir en segmentos por separadores;
    - quitar asignaciones y envoltorios (`sudo`, `env`…);
    - extraer el contenido de las sustituciones `$(…)` y de comillas invertidas,
      respetando las comillas.
  - Se bloquea si, en algún segmento, una palabra cuyo nombre de archivo es
    `discovery.py` va seguida de `approve`.
  - Si `shlex` no puede analizar el comando, vale la expresión actual (R006).
- **Alternativas descartadas:**
  - *Importar `sdd_bash` desde `discovery`.* Viola la constitución: cada
    plugin debe funcionar sin el otro instalado.
  - *Extraer un módulo común y copiarlo al publicar.* No hay paso de
    publicación; se instala desde el repositorio tal cual.
  - *Ajustar la expresión regular.* `sdd` ya lo intentó: una expresión no
    distingue entre comillas y ejecución.
- **Consecuencias:**
  - Unas 100 líneas duplicadas. Un arreglo futuro en el analizador de `sdd`
    habrá que replicarlo, y el comentario de cabecera de la copia lo dice.
  - Los mismos límites que en `sdd`: un `\$(…)` escapado fuera de comillas o
    una mención sin comillas se siguen bloqueando, y un script opaco lo
    resuelve la auditoría (R007).

### D3 — El comentario del selftest de `discovery` deja de citar un requisito

- **Contexto:** `test_huella_de_texto` explica en un comentario qué prueba otro
  test, citando el requisito sin prefijo. Desde la feature 003 el comentario
  cuenta como cita dentro de una prueba y genera `W-TEST-UNSCOPED` en cada
  feature.
- **Decisión:** se reescribe el comentario para describir el criterio sin citar
  el ID.
- **Alternativas descartadas:**
  - *Añadir el prefijo `F001-`.* Convertiría el comentario en evidencia de un
    requisito que esa prueba no verifica.
  - *Hacer que `trace` ignore los comentarios.* Rompería la convención
    documentada de citar el requisito en un comentario de la prueba.
- **Consecuencias:** ninguna funcional.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/sdd/scripts/sdd.py` · `project_root` | subida hasta `.sdd/` o `specs/`, con tope en git (D1) | R001, R003, R004 |
| `plugins/discovery/scripts/discovery.py` · `project_root` | subida hasta `product/`, con tope en git (D1) | R002, R003, R004 |
| `plugins/discovery/scripts/discovery.py` · `cmd_guard` y analizador copiado | bloquea la ejecución, no la mención (D2) | R005, R006 |
| `plugins/discovery/scripts/discovery.py` · `cmd_audit` | sin cambios; se prueba como regresión | R007 |
| `plugins/discovery/tests/selftest.py` | comentario de `test_huella_de_texto` (D3); pruebas `test_F004_RNNN_…` | R002, R003, R004, R005, R006, R007, R008 |
| `plugins/sdd/tests/selftest.py` | pruebas `test_F004_RNNN_…` | R001, R003, R004 |
| `plugins/discovery/README.md`, `plugins/sdd/README.md` | qué bloquea la compuerta de `discovery` y cómo se resuelve la raíz | R001, R002, R005 |

## Modelo de datos

No aplica.

## Contratos

`project_root(payload=None)` mantiene su firma en los dos plugins, y la salida
de todos los comandos no cambia. Solo cambia qué directorio se usa cuando
falta `CLAUDE_PROJECT_DIR`.

## Estrategia de pruebas

| Requisito | Tipo de prueba | Dónde vive |
| --------- | -------------- | ---------- |
| R001 | integración: `status` y la aprobación lanzados desde `specs/<feature>/` sin `CLAUDE_PROJECT_DIR`; un `specs/` ajeno más cercano no gana a `.sdd/` | `plugins/sdd/tests/selftest.py` |
| R002 | integración: `check` lanzado desde `product/sources/` sin `CLAUDE_PROJECT_DIR` | `plugins/discovery/tests/selftest.py` |
| R003 | integración, en los dos plugins: un directorio sin datos dentro de un repo git vacío da el mismo resultado que hoy; la subida no pasa del `.git` | ambos selftests |
| R004 | integración, en los dos plugins: `CLAUDE_PROJECT_DIR` apunta a un proyecto y el `cwd` a otro | ambos selftests |
| R005 | unitaria e integración: una lista de menciones (commit, PR, heredoc, comillas simples) que la compuerta no bloquea | `plugins/discovery/tests/selftest.py` |
| R006 | unitaria e integración: una lista de ejecuciones (directa, `&&`, `;`, `$(…)`, comillas invertidas, comando no analizable) que la compuerta bloquea | `plugins/discovery/tests/selftest.py` |
| R007 | integración: un `bash -c` que la compuerta deja pasar y aprueba el backlog; la auditoría lo revierte | `plugins/discovery/tests/selftest.py` |
| R008 | verificación única en la tarea: `trace` del repositorio sin `W-TEST-UNSCOPED` que señale el selftest de `discovery` | tarea de `discovery` |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| Las dos copias del analizador divergen | Un arreglo en una no llega a la otra | El comentario de cabecera de cada copia nombra la otra. Las listas de menciones y de ejecuciones de los dos selftests son equivalentes |
| Un `.sdd/` o `product/` ajeno por encima del proyecto, dentro del mismo repo | Se elegiría ese directorio | Solo ocurre sin `CLAUDE_PROJECT_DIR` y desde un subdirectorio sin datos propios. Gana siempre el más cercano |
| La subida lee directorios sin permiso | Excepción en un guardrail | Un `OSError` cuenta como «no hay datos aquí»; se sigue subiendo |

## Trazabilidad

Los siete requisitos MUST (R001–R007) aparecen en la tabla de componentes y en
la de pruebas. R008 (SHOULD) también está en las dos.
