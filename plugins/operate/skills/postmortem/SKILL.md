---
name: postmortem
description: Redacta con el usuario el postmortem de un incidente registrado - cronología, causas y acciones, cada acción con un ID estable (I001-A1) que después se convierte en una feature de corrección de sdd.
disable-model-invocation: true
argument-hint: "I001"
---

# Postmortem — qué pasó y qué se cambia

Incidente: `$ARGUMENTS`

## Procedimiento

1. Si `$ARGUMENTS` no es el ID de un incidente (`I001`), pregunta cuál y
   detente. Los incidentes están en `operations/incidents/`.

2. Lee el incidente. Si le faltan la fecha, la versión afectada, la severidad,
   qué pasó o el impacto, complétalos primero con el usuario.

3. Completa con el usuario, sin buscar culpables:
   - **Cronología:** lo que pasó en orden, con la hora: detección, decisiones
     y recuperación.
   - **Causas:** por qué pasó, la causa técnica y lo que dejó que llegara a
     producción.
   - **Acciones:** lo que evita que se repita. Para cada una, pide su ID:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/operate.py" next-action $ARGUMENTS
     ```

     y escríbela como `### I001-A1 — <título>` con el campo `- **Qué:** …`.
     Una acción no se renumera nunca: su feature la citará por su ID. Si una
     acción se descarta, bórrala; no reutilices su número a mano.

4. Comprueba:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/operate.py" check $ARGUMENTS
   ```

   Corrige los errores (`E-INCIDENT-*`). Después pide al usuario que revise el
   postmortem y ejecute `/operate:approve $ARGUMENTS`. Una vez aprobado, cada
   acción se convierte en una feature de corrección con `/sdd:specify I001-A1`.

## Límite

No cambies el campo Estado ni ejecutes `operate.py approve`: la aprobación es
del usuario, y los guardrails lo impiden.
