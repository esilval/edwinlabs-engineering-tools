---
name: approve
description: Aprueba la arquitectura (atributos, componentes, estándares, preguntas y decisiones en borrador) tras la revisión del usuario, solo si la comprobación no da errores. Solo el usuario la invoca.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

# Aprobación de la arquitectura

El usuario revisó la arquitectura y la da por buena. La aprobación ya se
ejecutó al invocar esta skill, antes de que leyeras este texto: la lanza Claude
Code directamente, sin pasar por la herramienta Bash. Es la única vía que el
guardrail acepta.

Resultado:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" approve --skill`

## Qué hacer con el resultado

1. Muéstraselo al usuario tal cual.

2. Si aprobó, el conjunto queda sellado con `Approved · <huella>` y
   `components.md` guarda la huella del producto en que se apoya. Un cambio
   posterior en un artefacto, o en el brief o el backlog, se avisa en
   `/architecture:check`. Las decisiones propuestas no se tocan: se deciden con
   `/architecture:review`.

3. Si se negó, **no edites nada para forzarlo**. Explica qué falta y qué lo
   corrige:
   - producto de discovery sin aprobar o cambiado → `/discovery:approve`;
   - faltan artefactos → `/architecture:init`;
   - errores de comprobación → los explica `/architecture:check`. Una pregunta
     abierta sobre una decisión o un atributo (`E-ARCH-OPEN-QUESTION`) se
     cierra respondiéndola con el usuario;
   - error inesperado → muéstralo al usuario tal cual.

## Límite

No cambies tú el campo Estado con Write, Edit ni Bash, ni ejecutes
`architecture.py approve` por tu cuenta. El guardrail lo bloquea, y si un
comando lo consigue, la auditoría devuelve el campo a su valor anterior.
