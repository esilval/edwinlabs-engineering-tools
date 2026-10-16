---
name: review
description: Decide una decisión de arquitectura propuesta - aceptarla (y sustituir la que cite) o rechazarla. Solo el usuario la invoca.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
argument-hint: ADR-NNNN aceptar|rechazar
---

# Revisión de una decisión propuesta

El usuario decidió sobre una decisión `Proposed`. La revisión ya se ejecutó al
invocar esta skill, antes de que leyeras este texto, sin pasar por la
herramienta Bash.

Resultado:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" review $ARGUMENTS --skill`

## Qué hacer con el resultado

1. Muéstraselo al usuario tal cual.

2. Si se aceptó, la decisión queda aprobada; si citaba otra en `Sustituye`,
   esa queda `Superseded by ADR-NNNN` y deja de regir. Si se rechazó, queda
   `Rejected` y conserva su número.

3. Si el resultado es el modo de uso, faltó el argumento: el usuario debe
   invocar `/architecture:review ADR-NNNN aceptar` o `… rechazar`.

4. Si se negó, **no edites nada para forzarlo**. Explica el motivo:
   - el ADR no existe → revisar el número con el usuario;
   - la decisión no está propuesta → una en borrador se aprueba con el
     conjunto (`/architecture:approve`);
   - tiene errores propios → corregirlos (`/architecture:decide`) y volver a
     revisarla;
   - sustituye a una decisión que no está aprobada, o que cambió tras
     aprobarse → aprobar antes esa (`/architecture:approve`) o corregir
     `Sustituye`;
   - error inesperado → muéstralo al usuario tal cual.

## Límite

No cambies tú el campo Estado ni ejecutes `architecture.py review` por tu
cuenta: el guardrail lo bloquea y la auditoría lo revierte.
