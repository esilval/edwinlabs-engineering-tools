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
   5. Marca la tarea como `[x]` solo si la verificación pasó.

5. **Detente después de cada tarea** y reporta al usuario: qué cambió, qué
   verificaste, cuál es la siguiente. No encadenes tareas sin dar oportunidad de
   revisar, salvo que el usuario lo pida explícitamente.

## Si la realidad contradice al plan

Ocurrirá. Cuando al implementar descubras que el plan es inviable o incompleto:

1. **Detente.** No improvises una solución distinta y sigas adelante.
2. Explica al usuario qué supuesto del plan falló.
3. Propón volver a `/sdd:plan` (o a `/sdd:specify` si lo que falla es un
   requisito) y actualizar el artefacto.

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
