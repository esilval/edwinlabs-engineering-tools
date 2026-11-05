# Tasks: comando de diagnóstico por plugin: python3, scripts y hooks, con aviso al iniciar la sesión

| Campo  | Valor       |
| ------ | ----------- |
| Spec   | `spec.md`   |
| Plan   | `plan.md`   |
| Fecha  | 2026-11-04  |
| Estado | Approved · e8b109f7318a       |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/sdd:approve`. Las pruebas citan el requisito con el prefijo de la
> feature: `test_F012_R001_interprete_bien`.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

El original del diagnóstico vive en `sdd` (D8): T001–T004 lo construyen ahí, y
T005–T006 lo copian a los otros cuatro plugins. Las pruebas de `doctor.sh` viven
en `plugins/sdd/tests/selftest.py`; las de `doctor.py`, en el selftest de cada
plugin.

## Tareas

### T001 — `doctor.sh`: comprobación del intérprete y diagnóstico completo

- **Estado:** `[ ]`
- **Requisitos:** R001, R002, R006
- **Depende de:** —
- **Archivos:** `plugins/sdd/scripts/doctor.sh`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `doctor.sh` sigue D3 y D9:
    - los estados «falta», «no se ejecuta», «antigua» y «bien», con
      `MIN_MAJOR=3` y `MIN_MINOR=8`;
    - `DOCTOR_PYTHON` solo para pruebas;
    - la corrección según `uname`;
    - la frase de la compuerta solo si el plugin tiene `scripts/sdd.py`;
    - las comprobaciones de scripts y hooks como `[--] sin comprobar`, y el
      resumen;
    - 0, 1 o 2 como código de salida, y siempre 0 con `--skill`.
  - Con el intérprete válido, cede a `doctor.py`. Si este no imprime su resumen
    (aún no existe, o revienta), lo dice como fallo de scripts con su error
    (D1).
  - Lleva el comentario de copias de D8, que nombra las cinco copias desde el
    principio (el archivo es idéntico en todas).
  - Pasan estas pruebas:
    - `test_F012_R001_interprete_bien`: el intérprete real da `[ok]` y su
      versión; un `DOCTOR_PYTHON` falso que responde 3.11.4 da 3.11.4;
    - `test_F012_R002_interprete_falta_o_antiguo`:
      - uno inexistente dice que falta, que la compuerta y los guardrails no
        funcionan, y cómo instalarlo, sin ejecutar `doctor.py`;
      - 3.6.15 dice que 3.6 es anterior a 3.8;
      - uno que sale con 9009 dice que no se ejecuta;
    - `test_F012_R006_resumen_sin_interprete`: «no está listo» y el código de
      salida 1, o 0 con `--skill`.

### T002 — `doctor.sh session`: aviso al iniciar y marca por sesión

- **Estado:** `[ ]`
- **Requisitos:** R008, R009, R010, R011
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/doctor.sh`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - El modo `session` sigue D6 y D7:
    - el JSON con `systemMessage` y `additionalContext`;
    - el nombre del plugin, sacado de `plugin.json`;
    - la marca `${TMPDIR:-/tmp}/edwinlabs-doctor.<session_id>` con `mkdir`,
      avisando igual si no hay `session_id` o el `mkdir` falla por otra causa;
    - siempre sale con 0.
  - Pasan estas pruebas:
    - `test_F012_R008_aviso_sin_interprete`: JSON válido con `systemMessage`
      que nombra `/sdd:doctor`;
    - `test_F012_R009_silencio_con_interprete`: sin salida y con 0;
    - `test_F012_R010_fallo_no_bloquea`: un payload que no es JSON y un `TMPDIR`
      inexistente salen con 0;
    - `test_F012_R011_un_aviso_por_sesion`: cinco ejecuciones con el mismo
      `session_id` dan un aviso; otro `session_id` da otro;
    - `test_F012_N001_aviso_rapido`: con el intérprete real, menos de 1 s.
  - Las pruebas usan un `TMPDIR` propio, para no dejar marcas fuera de su
    directorio temporal.

### T003 — `doctor.py`: scripts y hooks contra un proyecto temporal

- **Estado:** `[ ]`
- **Requisitos:** R003, R004, R005, R006, R007
- **Depende de:** T001
- **Archivos:** `plugins/sdd/scripts/doctor.py`, `plugins/sdd/tests/selftest.py`
- **Hecho cuando:**
  - `doctor.py` sigue D4, D5, D8 y D9:
    - `CASE` de `sdd` arriba, y el cuerpo común bajo
      `# --- común a las cinco copias ---`;
    - la importación de cada script en un hijo;
    - cada hook de `python3` de `hooks.json`, lanzado contra un proyecto
      temporal sin variables `*_BYPASS`, con la petición inocua y la de
      aprobación;
    - `allow` en una salida cuenta como fallo;
    - los guardrails (`guard`, `audit`) y los demás hooks (`quality`,
      `context`) nombrados por separado en el resultado;
    - el comentario de copias, con las cinco;
    - el resumen.
  - Pasan estas pruebas:
    - `test_F012_R003_script_roto`: copia del plugin con un script con error de
      sintaxis; el resultado da `[falla]`, el nombre del script y el error;
    - `test_F012_R004_guardrails_responden`: el plugin real da `[ok]` en cada
      hook; una copia con `guard` que siempre sale con 0 da `[falla]` en el
      guardrail;
    - `test_F012_R005_no_modifica_el_proyecto`: misma huella de todos los
      archivos de un proyecto con artefactos en borrador y aprobados;
    - `test_F012_R006_resumen`: «está listo» con el plugin real; «no está
      listo» y el nombre del guardrail con la copia rota;
    - `test_F012_R007_sin_los_demas`: una copia solo de `plugins/sdd/` da «está
      listo»;
    - `test_F012_copias_del_diagnostico`: `sh -n` sobre `doctor.sh`, y
      `doctor.sh` y el cuerpo común de `doctor.py` iguales a los de los demás
      plugins presentes; se salta las copias que aún no existen.

### T004 — Skill `/sdd:doctor`, hook `SessionStart` y README de `sdd`

- **Estado:** `[ ]`
- **Requisitos:** R006, R008
- **Depende de:** T002, T003
- **Archivos:** `plugins/sdd/skills/doctor/SKILL.md`, `plugins/sdd/hooks/hooks.json`, `plugins/sdd/README.md`
- **Hecho cuando:**
  - La skill sigue D2:
    - sin `disable-model-invocation`, con `allowed-tools: Bash(sh:*)`;
    - inyecta `doctor.sh --skill`;
    - pide mostrar el resultado tal cual, explicar la corrección indicada y no
      instalar nada.
  - `hooks.json` añade el `SessionStart` de D6, junto a `context`, en forma
    exec y con `timeout` de 5.
  - El README de `sdd` tiene una sección «Diagnóstico», con:
    - qué comprueba;
    - un ejemplo de salida;
    - el aviso de inicio y su marca.
  - Pasan `python3 scripts/validate.py --strict` y el selftest de `sdd`. El
    diagnóstico real (`sh plugins/sdd/scripts/doctor.sh`) da «está listo».

### T005 — El diagnóstico en `discovery` y `architecture` `P`

- **Estado:** `[ ]`
- **Requisitos:** R003, R004, R005, R006, R007, R008
- **Depende de:** T004
- **Archivos:** `plugins/{discovery,architecture}/scripts/doctor.sh`, `plugins/{discovery,architecture}/scripts/doctor.py`, `plugins/{discovery,architecture}/skills/doctor/SKILL.md`, `plugins/{discovery,architecture}/hooks/hooks.json`, `plugins/{discovery,architecture}/tests/selftest.py`, `plugins/{discovery,architecture}/README.md`
- **Hecho cuando:**
  - Cada plugin tiene:
    - `doctor.sh` idéntico al de `sdd`;
    - `doctor.py` con su `CASE` (`product/brief.md` y
      `architecture/quality.md`) y el cuerpo común;
    - la skill, el `SessionStart` y la sección «Diagnóstico» del README.
  - En el selftest de cada uno pasan `test_F012_R003_script_roto`,
    `test_F012_R004_guardrails_responden`,
    `test_F012_R005_no_modifica_el_proyecto`, `test_F012_R006_resumen`,
    `test_F012_R007_sin_los_demas`, `test_F012_copias_del_diagnostico` y
    `test_F012_R008_aviso_nombra_el_plugin` (`doctor.sh session` de la copia,
    sin intérprete, nombra `/discovery:doctor` o `/architecture:doctor`).
  - Pasan `validate.py --strict` y los selftests de los dos plugins y de `sdd`.

### T006 — El diagnóstico en `release` y `operate` `P`

- **Estado:** `[ ]`
- **Requisitos:** R003, R004, R005, R006, R007, R008
- **Depende de:** T004
- **Archivos:** `plugins/{release,operate}/scripts/doctor.sh`, `plugins/{release,operate}/scripts/doctor.py`, `plugins/{release,operate}/skills/doctor/SKILL.md`, `plugins/{release,operate}/hooks/hooks.json`, `plugins/{release,operate}/tests/selftest.py`, `plugins/{release,operate}/README.md`
- **Hecho cuando:**
  - Lo mismo que T005, con `CASE` en `releases/v0.0.1.md` y
    `operations/v0.0.1.md`.
  - En el selftest de cada uno pasan las mismas siete pruebas `test_F012_…`;
    la del aviso nombra `/release:doctor` u `/operate:doctor`.
  - Pasan `validate.py --strict` y los selftests de los dos plugins y de `sdd`.

### T007 — README raíz y cierre

- **Estado:** `[ ]`
- **Requisitos:** R006, R007
- **Depende de:** T005, T006
- **Archivos:** `README.md`
- **Hecho cuando:**
  - La instalación del README raíz pide ejecutar `/<plugin>:doctor` tras
    instalar cada plugin. También explica el aviso de inicio y que un solo
    plugin basta para avisar.
  - `test_F012_copias_del_diagnostico` pasa en los cinco selftests sin
    saltarse ninguna copia.
  - Pasan `python3 scripts/validate.py --strict` y los cinco selftests, y
    `sdd.py trace` de la feature 012 no tiene errores.

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T001 |
| R002 | T001 |
| R003 | T003, T005, T006 |
| R004 | T003, T005, T006 |
| R005 | T003, T005, T006 |
| R006 | T001, T003, T004, T005, T006, T007 |
| R007 | T003, T005, T006, T007 |
| R008 | T002, T004, T005, T006 |
| R009 | T002 |
| R010 | T002 |
| R011 | T002 |

> Todo requisito MUST debe tener al menos una tarea.
