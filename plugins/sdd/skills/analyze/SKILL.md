---
name: analyze
description: Revisa de solo lectura la coherencia entre constitución, spec, plan y tareas de la feature activa antes de implementar. Úsala antes de aprobar tasks.md o de lanzar /sdd:implement.
disable-model-invocation: true
---

# Análisis de consistencia

Encuentra las contradicciones entre artefactos **antes** de que se conviertan
en código. Es de solo lectura: reporta, no arregla.

## Procedimiento

1. Comprobaciones deterministas:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" status
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" trace
   ```

   De `trace` interesan aquí los hallazgos de spec, plan y tareas
   (`*-SPEC-*`, `*-PLAN-*`, `*-TASK-*`, `E-REQ-NO-TASK`, `E-REQ-NO-CRITERIA`).
   Los de pruebas (`E-REQ-NO-TEST`, `E-DONE-NO-TEST`) son esperables antes de
   implementar: no los cuentes como problemas.

2. Lee `specs/constitution.md` (si existe), `spec.md`, `plan.md` y `tasks.md`
   de la feature activa.

3. Busca lo que un script no puede ver. Para cada pasada, cita el fragmento
   concreto de cada artefacto implicado:

   | Pasada | Pregunta |
   | ------ | -------- |
   | Constitución | ¿Alguna decisión del plan viola una regla de la constitución sin justificarlo en «Comprobación de constitución»? |
   | Cobertura real | ¿Las tareas que citan un requisito lo implementan de verdad, o solo lo mencionan? ¿Algún criterio de aceptación no tiene tarea que lo haga cierto? |
   | Plan → tareas | ¿Hay componentes o decisiones del plan sin tarea? ¿Tareas que hacen algo que el plan no decidió? |
   | Contradicciones | ¿Dos requisitos, o un requisito y una decisión, se contradicen? |
   | Terminología | ¿El mismo concepto aparece con nombres distintos entre artefactos? |
   | Spec contaminada | ¿La spec contiene decisiones de implementación (librerías, tablas, endpoints)? |
   | No deseados | ¿Faltan requisitos `SI … ENTONCES` para errores o casos límite evidentes? |
   | Dependencias | ¿El orden de las tareas es ejecutable? ¿Alguna tarea toca demasiados archivos para ser atómica? |

4. Clasifica cada hallazgo:
   - **Crítico:** viola la constitución, contradice un MUST o deja un MUST sin
     implementar de verdad. Debe resolverse antes de implementar.
   - **Importante:** producirá retrabajo probable.
   - **Menor:** redacción, terminología.

## Al terminar

Presenta una tabla: severidad, pasada, artefactos implicados, hallazgo, y qué
skill lo corrige (`/sdd:specify`, `/sdd:clarify`, `/sdd:plan`, `/sdd:tasks`).
Ordénala por severidad.

**No edites ningún artefacto.** Si el usuario quiere corregir algo, lo hará
con la skill de esa fase. Si un artefacto ya aprobado cambia, tendrá que
volver a aprobarlo.

Si no hay hallazgos críticos, dilo, y recuerda el siguiente paso pendiente
según `status` (normalmente `/sdd:approve` o `/sdd:implement`).
