---
name: approve
description: Aprueba la fase SDD actual (spec, plan o tasks) de la feature activa tras la revisión del usuario. Solo el usuario la invoca; es lo que deja avanzar a la compuerta.
disable-model-invocation: true
---

# Aprobación de fase

El usuario revisó un artefacto y lo da por bueno. Esta skill registra esa
decisión en el campo `Estado` de la cabecera, que es lo que la compuerta exige
antes de dejar escribir código.

Fase a aprobar (opcional: `spec`, `plan` o `tasks`): `$ARGUMENTS`

## Procedimiento

1. Ejecuta:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" approve $ARGUMENTS
   ```

   Sin argumento, aprueba la primera fase que aún no lo esté.

2. Muestra la salida al usuario.

3. Si el script se niega, **no edites nada para forzarlo**. Explica qué falta,
   en el mismo orden en que lo listó el script, y qué skill lo completa. Las
   negativas posibles:
   - el artefacto conserva huecos de plantilla, o le faltan requisitos,
     criterios o cobertura;
   - una fase anterior no está aprobada todavía.

## Límite

Esta es la única vía para aprobar. No cambies tú el campo `Estado` con
Write, Edit ni Bash, ni ejecutes `sdd.py approve` fuera de esta skill: la
aprobación es la prueba de que una persona revisó el artefacto.
