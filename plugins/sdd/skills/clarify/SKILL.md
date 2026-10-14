---
name: clarify
description: Resuelve las ambigüedades pendientes de una spec SDD mediante preguntas dirigidas al usuario, antes de pasar a la fase de plan.
disable-model-invocation: true
---

# Fase 1b — Clarify

Cierra las preguntas abiertas de la spec antes de que se conviertan en
suposiciones enterradas en el código.

## Procedimiento

1. Resuelve la feature activa:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" current
   ```

   Si no devuelve nada, dile al usuario que ejecute `/sdd:specify` primero y
   detente.

2. Lee `spec.md` y busca tres cosas:
   - La sección **Preguntas abiertas**.
   - Requisitos **no verificables**: los que no permiten escribir un criterio de
     aceptación objetivo («la interfaz debe ser intuitiva»).
   - Requisitos **sin criterio de aceptación** asociado.

3. Presenta al usuario las ambigüedades **de una en una o en grupos pequeños**,
   con opciones concretas cuando puedas proponerlas. Una lista de quince
   preguntas de golpe no se responde; tres sí.

4. Tras cada respuesta, edita `spec.md` de inmediato: convierte la respuesta en
   un requisito EARS o en un criterio de aceptación, y borra la pregunta de la
   sección de preguntas abiertas.

5. No inventes respuestas ni marques algo como resuelto por inferencia. Si el
   usuario no contesta a algo, sigue siendo una pregunta abierta.

## Al terminar

Reporta cuántas preguntas quedaron cerradas y cuántas siguen abiertas. Si quedan
abiertas de tipo MUST, dilo claramente: pasar a `/sdd:plan` con requisitos MUST
ambiguos es la vía más común de reescribir todo dos veces.

Si la spec ya estaba aprobada y la cambiaste, díselo al usuario: la aprobación
que dio fue sobre otra versión. Si no lo estaba, el siguiente paso es que la
revise y ejecute `/sdd:approve spec`.
