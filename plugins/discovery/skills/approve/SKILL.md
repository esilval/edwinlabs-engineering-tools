---
name: approve
description: Aprueba el brief y el backlog del producto tras la revisión del usuario, solo si la comprobación no da errores. Solo el usuario la invoca.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

# Aprobación del producto

El usuario revisó el brief y el backlog y los da por buenos. La aprobación ya
se ejecutó al invocar esta skill, antes de que leyeras este texto: la lanza
Claude Code directamente, sin pasar por la herramienta Bash. Es la única vía
que el guardrail acepta.

Resultado:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" approve --skill`

## Qué hacer con el resultado

1. Muéstraselo al usuario tal cual.

2. Si aprobó, el producto queda sellado con `Approved · <huella>`. Cualquier
   cambio posterior en el brief o el backlog lo deja sin aprobar hasta que el
   usuario vuelva a ejecutar `/discovery:approve`.

3. Si se negó, **no edites nada para forzarlo**. Explica qué falta, en el orden
   del script, y qué lo corrige:
   - falta el brief o el backlog → `/discovery:decompose`;
   - errores de comprobación → los de `/discovery:check`;
   - una pregunta abierta sobre un objetivo → `/discovery:clarify`.

## Límite

No cambies tú el campo Estado con Write, Edit ni Bash, ni ejecutes
`discovery.py approve` por tu cuenta. El guardrail lo bloquea, y si un comando
lo consigue, la auditoría devuelve el campo a su valor anterior. La aprobación
es la prueba de que una persona revisó el producto.
