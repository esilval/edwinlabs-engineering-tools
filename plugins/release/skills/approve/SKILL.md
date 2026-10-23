---
name: approve
description: Aprueba una versión de releases/ tras la revisión del usuario, solo si la comprobación no da errores ni quedan huecos, y muestra el comando para etiquetarla. Solo el usuario la invoca.
disable-model-invocation: true
argument-hint: "[vX.Y.Z]"
allowed-tools: Bash(python3:*)
---

# Aprobación de una versión

El usuario revisó la versión y la da por buena. La aprobación ya se ejecutó al
invocar esta skill, antes de que leyeras este texto: la lanza Claude Code
directamente, sin pasar por la herramienta Bash. Es la única vía que el
guardrail acepta.

Resultado:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" approve "$ARGUMENTS" --skill`

## Qué hacer con el resultado

1. Muéstraselo al usuario tal cual.

2. Si aprobó, la versión queda sellada con `Approved · <huella>`, con la
   comprobación del momento de aprobar como evidencia. Cualquier cambio
   posterior se avisa en `/release:check`; la versión sigue publicada, y se
   vuelve a aprobar nombrándola. El plugin **no etiqueta ni publica**: los
   comandos `git tag` y `git push` que muestra los ejecuta el usuario cuando
   quiera. No los ejecutes tú salvo que te lo pida.

3. Si se negó, **no edites nada para forzarlo**. Explica qué falta y qué lo
   corrige:
   - huecos sin completar (`E-RELEASE-TEMPLATE`) → `/release:new`, que
     redacta las notas y los cambios técnicos;
   - errores de las features → la fase de `sdd` que los corrige, como explica
     `/release:check`;
   - número de versión → crear el borrador con otro `--version`;
   - varias versiones en borrador → volver a invocar con la versión:
     `/release:approve v0.4.0`;
   - error inesperado → muéstralo al usuario tal cual.

## Límite

No cambies tú el campo Estado con Write, Edit ni Bash, ni ejecutes
`release.py approve` por tu cuenta. El guardrail lo bloquea, y si un comando lo
consigue, la auditoría devuelve el campo a su valor anterior.
