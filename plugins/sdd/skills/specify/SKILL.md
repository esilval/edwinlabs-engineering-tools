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

   **Traspaso desde `discovery`.** Si la descripción es el ID de una candidata
   del backlog (`B03`) y existe `product/backlog.md`, el script crea la feature
   desde esa candidata:
   - Si sale con código 1, muestra al usuario el motivo tal cual y detente: el
     script ya dice qué falta y cómo resolverlo. No crees nada a mano ni lo
     intentes con otra descripción.
   - Si el JSON trae `origin`, la spec ya tiene Problema, Contexto, Alcance y la
     fila `Origen`, tomados del producto aprobado. Lee lo que indica `context`:
     el brief (`brief`), los objetivos (`goals`) y cada sección de origen en su
     archivo (`sources`: `file` y `section`). Parte de esas secciones: matízalas
     si hace falta, pero no las reescribas desde cero ni toques la fila `Origen`.
   - Si trae `warnings`, enséñaselos al usuario al terminar: dependencias
     sin feature o secciones cuyo documento ya no está en `product/sources/`.

   **Traspaso desde `operate`.** Si la descripción es el ID de una acción de
   un postmortem (`I001-A2`) y existe `operations/incidents.md`, el script crea
   una feature de corrección desde esa acción:
   - Si sale con código 1, muestra el motivo tal cual y detente: el postmortem
     no está aprobado o cambió, la acción no existe, o ya tiene feature.
   - Si el JSON trae `origin`, la spec ya tiene `Tipo` en `corrección`, la fila
     `Origen` (`I001-A2 · 0.4.0`), el Problema (qué pasó, el impacto y la
     acción) y el Contexto (el incidente y sus causas). Lee el incidente que
     indica `context` y parte de ahí. No toques las filas `Tipo` ni `Origen`.

3. Lee `specs/constitution.md` si existe. Es una restricción, no una sugerencia.

4. Explora el repositorio lo justo para entender el contexto: dónde vivirá el
   cambio, qué convenciones existen, qué hay ya resuelto.

5. Rellena `spec.md`. Aplica las reglas de redacción de la skill
   `sdd:spec-authoring`, que se activa sola al editar specs.
   Sustituye **todo** texto en cursiva de la plantilla: la compuerta trata
   cualquier hueco que quede como spec incompleta. Si una sección no aplica,
   escribe «No aplica.». Borra los requisitos de ejemplo que no uses.

6. **Tipo.** La fila `Tipo` de la cabecera nace en `funcionalidad`. Si la
   feature solo corrige comportamiento existente, sin añadir funcionalidad,
   cámbiala a `corrección`. Pregúntaselo al usuario si no está claro. El
   plugin `release` la usa para proponer el número de versión: una versión
   solo de correcciones sube el parche. Cualquier otro valor es un error al
   preparar la versión.

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
