---
name: amend
description: Cambia los requisitos de una feature SDD ya aprobada o en implementación sin romper la trazabilidad - añade, modifica o retira requisitos con IDs estables y deja registro del cambio.
disable-model-invocation: true
argument-hint: <qué cambia y por qué>
---

# Enmienda de requisitos

La spec es la fuente de verdad, así que cuando el requisito cambia, cambia
primero la spec. Esta skill lo hace sin reciclar IDs ni perder el rastro de
tareas y pruebas que citan los requisitos antiguos.

Cambio pedido: `$ARGUMENTS`

## Procedimiento

1. Si `$ARGUMENTS` está vacío, pregunta qué cambia y por qué, y detente.

2. Estado y contexto:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" status
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" trace
   ```

   Lee `spec.md`, `plan.md` y `tasks.md` de la feature activa.

3. Clasifica el cambio y **confírmalo con el usuario antes de editar**:

   | Tipo | Qué se hace en `spec.md` |
   | ---- | ------------------------ |
   | Requisito nuevo | Fila nueva con el siguiente ID libre, más sus criterios. |
   | Cambio de comportamiento | El requisito viejo pasa a `OBSOLETO` y se añade uno nuevo con ID nuevo. |
   | Requisito retirado | Pasa a `OBSOLETO`. |
   | Aclaración sin cambio de comportamiento | Se edita en su sitio, con el mismo ID. |

   La prueba para distinguir los dos últimos tipos: si un test que hoy pasa
   para ese requisito tendría que cambiar, es un cambio de comportamiento.

4. El siguiente ID libre lo da el script. Cuenta también los obsoletos,
   porque un ID no se recicla nunca:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" next-req
   ```

5. Edita `spec.md`:
   - Un requisito obsoleto lleva `OBSOLETO` en la columna de prioridad y, al
     final del texto, `(reemplazado por R00N)` si aplica. Sus criterios se
     quedan como estaban, como historia.
   - Los requisitos nuevos siguen las reglas de `sdd:spec-authoring`.
   - Añade una entrada al final de `## Historial de cambios` (créala si no
     existe): fecha, qué cambió, por qué y los IDs afectados.
   - No toques el campo `Estado`.

6. Muestra el impacto, a partir de `trace` y de los artefactos:
   - tareas abiertas que sirven a un requisito obsoleto (`W-TASK-OBSOLETE-REQ`);
   - tareas cerradas cuyo comportamiento hay que retirar o adaptar;
   - pruebas que citan IDs obsoletos y habrá que reescribir o borrar;
   - requisitos nuevos sin tarea ni prueba.

## Al terminar

Explica la consecuencia: la spec cambió después de aprobarse, así que la
compuerta queda cerrada (`[!]` en `/sdd:status`) hasta que el usuario la
revise y ejecute `/sdd:approve`. Al reaprobarla, `plan.md` y `tasks.md`
vuelven a borrador. El camino es:

1. `/sdd:approve` → spec.
2. `/sdd:plan` para actualizar el plan con el cambio, y `/sdd:approve`.
3. `/sdd:tasks` para añadir o retirar tareas, y `/sdd:approve`.
4. `/sdd:implement`.

No edites código en esta skill.
