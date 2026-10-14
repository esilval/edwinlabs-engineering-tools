---
name: approve
description: Aprueba la siguiente fase SDD pendiente (spec, plan o tasks) de la feature activa tras la revisión del usuario. Solo el usuario la invoca; es lo que deja avanzar a la compuerta.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

# Aprobación de fase

El usuario revisó un artefacto y lo da por bueno. La aprobación ya se ejecutó
al invocar esta skill, antes de que leyeras este texto, porque la lanza Claude
Code directamente y no pasa por la herramienta Bash. Es la única vía que la
compuerta acepta. Se aprueba la primera fase que aún no lo esté; el orden
spec → plan → tasks hace que no haya otra aprobable.

Resultado:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" approve --skill`

## Qué hacer con el resultado

1. Muéstraselo al usuario tal cual.

2. Si aprobó, indica el siguiente paso que el script señala.

3. Si se negó, **no edites nada para forzarlo**. Explica qué falta, en el
   mismo orden en que lo listó el script, y qué skill lo completa. Las
   negativas posibles:
   - el artefacto conserva huecos de plantilla, o le faltan requisitos,
     criterios o cobertura;
   - todavía no existe el artefacto de la siguiente fase.

## Límite

No cambies tú el campo `Estado` con Write, Edit ni Bash, ni ejecutes
`sdd.py approve` por tu cuenta. La compuerta lo bloquea, y si un comando lo
consigue, la auditoría devuelve el campo a su valor anterior. La aprobación es
la prueba de que una persona revisó el artefacto.
