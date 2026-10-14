---
name: specify
description: Arranca una feature nueva bajo el flujo SDD. Crea specs/NNN-slug/spec.md y redacta la especificación de qué y por qué, sin decisiones de implementación.
disable-model-invocation: true
---

# Fase 1 — Specify

Convierte una intención en lenguaje natural en una especificación estructurada.

Descripción de la feature: `$ARGUMENTS`

## Procedimiento

1. Si `$ARGUMENTS` está vacío, pregunta al usuario qué quiere construir y
   detente hasta que responda. No inventes una feature.

2. Ejecuta el andamiaje determinista:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" new "<descripción>"
   ```

   Devuelve JSON con el slug de la feature y la ruta del `spec.md` creado desde
   plantilla, y la marca como feature activa. **No crees el directorio a mano**:
   la numeración y el puntero de feature activa son responsabilidad del script.

3. Lee `specs/constitution.md` si existe. Es una restricción, no una sugerencia.

4. Explora el repositorio lo justo para entender el contexto: dónde vivirá el
   cambio, qué convenciones existen, qué hay ya resuelto.

5. Rellena `spec.md`. Aplica las reglas de redacción de la skill
   `sdd:spec-authoring`, que se activa sola al editar specs.
   Sustituye **todo** texto en cursiva de la plantilla: la compuerta trata
   cualquier hueco que quede como spec incompleta. Si una sección no aplica,
   escribe «No aplica.». Borra los requisitos de ejemplo que no uses.

## La regla que más se rompe

`spec.md` **no contiene decisiones de implementación**. Si escribes «usar Redis
para la caché», eso pertenece a `plan.md`. En la spec va el requisito que motiva
la caché: «CUANDO el usuario consulta el saldo, el sistema DEBERÁ responder en
menos de 300 ms en el percentil 95».

Ante la duda, pregúntate: si mañana cambiáramos toda la pila tecnológica,
¿seguiría siendo cierta esta frase? Si no, no va en la spec.

## Al terminar

1. Muestra al usuario los requisitos y los non-goals que redactaste. Es lo que
   más rápido revela un malentendido.
2. Si dejaste preguntas abiertas, dilo explícitamente.
3. Si hay preguntas abiertas, el siguiente paso es `/sdd:clarify`. Si no, pide
   al usuario que revise la spec y ejecute `/sdd:approve`; después viene
   `/sdd:plan`.
4. No cambies tú el campo `Estado`. La compuerta lo impide, y la aprobación es
   del usuario.
