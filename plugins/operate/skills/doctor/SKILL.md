---
name: doctor
description: Diagnostica la instalación del plugin operate - que python3 existe y es 3.8 o posterior, que sus scripts arrancan y que sus guardrails responden. Úsala tras instalar el plugin o si los guardrails no parecen actuar.
allowed-tools: Bash(sh:*)
---

# Diagnóstico de operate

El diagnóstico ya se ejecutó al cargar esta skill. No modifica el proyecto: los
scripts se cargan y los hooks se prueban contra un proyecto temporal.

Resultado:

!`sh "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh" --skill`

## Qué hacer con el resultado

1. Muéstraselo al usuario tal cual.

2. Si el resumen dice «está listo», no hace falta nada más.

3. Si no, explica cada línea `[falla]` y qué la corrige:
   - **intérprete**: sigue la línea «Cómo resolverlo». Sin un Python válido,
     los guardrails dejan pasar todo. Después hay que reiniciar la sesión y
     repetir `/operate:doctor`.
   - **script … no arranca**: el plugin está incompleto o modificado. Se
     corrige reinstalándolo o actualizándolo con `/plugin`.
   - **guardrail … no protege**, o un hook que no responde o concede permisos:
     igual, reinstalar o actualizar el plugin. Si sigue fallando, el usuario
     puede abrir una incidencia con la salida del diagnóstico.

## Límite

No instales ni actualices nada, ni cambies la configuración de Claude Code: el
diagnóstico solo informa, y lo que se instala lo decide el usuario. Tampoco
repitas a mano sus comprobaciones con Bash: el resultado de arriba es el del
script.
