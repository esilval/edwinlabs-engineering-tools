---
name: implement
description: Ejecuta las tareas pendientes de tasks.md una a una, actualizando el estado y verificando cada una contra sus criterios de aceptación.
disable-model-invocation: true
---

# Fase 4 — Implement

Ejecuta el trabajo descrito en `tasks.md`.

Tarea concreta a ejecutar (opcional): `$ARGUMENTS`

## Procedimiento

1. Resuelve la feature activa con
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" current`, y su estado con
   `sdd.py status`.

2. Lee `specs/constitution.md`, `spec.md`, `plan.md` y `tasks.md`.

3. Elige la tarea:
   - Si `$ARGUMENTS` nombra un ID (`T003`), esa.
   - Si no, la primera con estado `[ ]` cuyas dependencias estén todas en `[x]`.

4. Para cada tarea, en este orden:
   1. Marca la tarea como `[~]` en `tasks.md`. Cambiar el estado de las tareas
      no afecta a la aprobación; el campo `Estado` de la cabecera no se toca.
   2. Implementa **solo esa tarea**. No aproveches para arreglar otras cosas que
      veas de paso: eso rompe la trazabilidad y la revisión.
   3. Verifica contra el «hecho cuando» de la tarea y contra los criterios de
      aceptación de los requisitos que referencia. Ejecuta las pruebas si las hay.
   4. Nombra las pruebas con el ID del requisito precedido del número de
      feature (`test_F001_R001_rechaza_token_expirado`, o un comentario
      `# F001-R001` dentro del test). Es lo que hace verificable la
      trazabilidad; sin ello, `/sdd:trace` dará el requisito por no probado.
      Una prueba vacía (solo `pass` o `...`) no cuenta como prueba.
   5. Lanza el agente `sdd:implementation-reviewer` con la feature
      (`specs/NNN-slug/`) y el ID de la tarea. Es
      un revisor independiente y de solo lectura: contrasta el diff con los
      criterios de aceptación, el plan y la constitución.
      - Si devuelve **NO CUMPLE**, corrige lo que señala y vuelve a lanzarlo.
        Si el arreglo exige cambiar el plan o la spec, ve a «Si la realidad
        contradice al plan».
      - Si devuelve **CUMPLE CON RESERVAS**, muestra las reservas al usuario
        en el reporte del paso 5.
      - No discutas el veredicto ni lo omitas del reporte.
   6. Marca la tarea como `[x]` solo si la verificación y la revisión pasaron.

5. **Detente después de cada tarea** y reporta al usuario: qué cambió, qué
   verificaste, el veredicto del revisor, cuál es la siguiente. No encadenes tareas sin dar oportunidad de
   revisar, salvo que el usuario lo pida explícitamente.

## Si la realidad contradice al plan

Ocurrirá. Cuando al implementar descubras que el plan es inviable o incompleto:

1. **Detente.** No improvises una solución distinta y sigas adelante.
2. Explica al usuario qué supuesto del plan falló.
3. Propón volver a `/sdd:plan` (o a `/sdd:specify` si lo que falla es un
   requisito) y actualizar el artefacto.
4. Si lo que falta es una **decisión de arquitectura** (afecta a más de una
   feature o es cara de revertir, y el proyecto tiene `architecture/`), no la
   tomes en el código: en `/sdd:plan` se propone con
   `sdd.py propose-adr "<título>"` y la decide el usuario con
   `/architecture:review`.

Ese es el mecanismo que mantiene la especificación como fuente de verdad. Si el
código se aleja de la spec en silencio, el plugin entero deja de tener sentido.

## Control de calidad automático

Tras cada escritura corre un hook que aplica formateador y linter al archivo.
Si devuelve errores, **son tuyos y los corriges en el momento**: no es una
denegación de permiso ni una petición del usuario. No te detengas a preguntar.

## Al terminar

Ejecuta `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" trace` y reporta el
estado. Si quedan errores de trazabilidad, dilo: la feature no está terminada
aunque todas las tareas estén en `[x]`.
