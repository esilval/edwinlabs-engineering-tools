---
name: approve
description: Aprueba la preparación de una versión (vX.Y.Z) o el postmortem de un incidente (I001) tras la revisión del usuario, solo si la comprobación no da errores ni quedan huecos. Solo el usuario la invoca.
disable-model-invocation: true
argument-hint: "<vX.Y.Z|I001>"
allowed-tools: Bash(python3:*)
---

# Aprobación de una preparación o un postmortem

El usuario revisó la preparación o el postmortem y lo da por bueno. La
aprobación ya se ejecutó al invocar esta skill, antes de que leyeras este
texto: la lanza Claude Code directamente, sin pasar por la herramienta Bash. Es
la única vía que el guardrail acepta.

Resultado:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/operate.py" approve "$ARGUMENTS" --skill`

## Qué hacer con el resultado

1. Muéstraselo al usuario tal cual.

2. Si aprobó, queda sellado con `Approved · <huella>`. Una preparación guarda
   además la huella de su versión: si la versión o la preparación cambian
   después, `/operate:check` lo avisa. Un postmortem aprobado lista los
   `/sdd:specify I001-A1` que convierten cada acción en una corrección.

3. Si se negó, **no edites nada para forzarlo**. Explica qué falta y qué lo
   corrige:
   - huecos o errores de una preparación (`E-PREP-*`) → `/operate:prepare`;
   - huecos o errores de un incidente (`E-INCIDENT-*`) → `/operate:postmortem`;
   - versión sin publicar → `/release:approve`;
   - sin objetivo, o un objetivo que no existe → volver a invocar con la
     preparación (`/operate:approve v0.4.0`) o el incidente
     (`/operate:approve I001`);
   - error inesperado → muéstralo al usuario tal cual.

## Límite

No cambies tú el campo Estado con Write, Edit ni Bash, ni ejecutes
`operate.py approve` por tu cuenta. El guardrail lo bloquea, y si un comando lo
consigue, la auditoría devuelve el campo a su valor anterior.
