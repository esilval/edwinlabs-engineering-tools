---
name: clarify
description: Aclara con el usuario los huecos, contradicciones y supuestos de los documentos del producto, y registra cada pregunta y su respuesta en el brief con su origen (D2§4.2).
disable-model-invocation: true
---

# Clarify — aclarar los documentos del producto

Los documentos los escribe el usuario. Las preguntas van a él, y sus
respuestas quedan en `product/brief.md`, donde las leen las fases siguientes.

## Procedimiento

1. Estado actual:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" questions
   ```

   Si no hay documentos en `product/sources/`, pide `/discovery:ingest` y
   detente.

2. Si no existe `product/brief.md`, cópialo de
   `${CLAUDE_PLUGIN_ROOT}/templates/brief.md`. Deja el campo Estado como está
   y no rellenes todavía objetivos ni candidatas: eso es `/discovery:decompose`.
   Mientras tanto, `check` informará de los huecos de plantilla, y es normal.

3. Lee los documentos de `product/sources/` y busca:
   - **Huecos:** lo que hace falta saber y ningún documento dice (quién es el
     usuario, qué pasa cuando algo falla, qué límites hay).
   - **Contradicciones:** entre secciones de un documento o entre documentos.
     Un documento nuevo que contradice a uno anterior es una pregunta, nunca
     una elección tuya.
   - **Supuestos:** lo que los documentos dan por hecho sin decirlo.

4. Cada pregunta va en la sección `## Preguntas` del brief con su origen entre
   paréntesis y, si afecta a un objetivo que ya existe, también el objetivo:

   ```markdown
   - [ ] (D1§2; G1) ¿Quién es el usuario objetivo?
   - [ ] (D1§3 contra D2§1) ¿Acceso solo para registrados o también anónimo?
   ```

5. Presenta las preguntas **de pocas en pocas**, con opciones concretas cuando
   puedas proponerlas. Quince preguntas de golpe no se contestan; tres sí.

6. Tras cada respuesta, márcala `[x]` y añade la respuesta debajo, con las
   palabras del usuario:

   ```markdown
   - [x] (D1§2; G1) ¿Quién es el usuario objetivo?
     - **Respuesta:** dueños de comercios pequeños, sin conocimientos técnicos.
   ```

7. **No inventes respuestas** ni des una pregunta por resuelta por inferencia.
   Si el usuario no contesta, la pregunta sigue abierta (`[ ]`). Si la respuesta
   depende de otra persona, el usuario la llevará a su próxima iteración y
   volverá como un documento nuevo.

## Límites

- No redactes requisitos («el sistema DEBERÁ…»): eso es de `/sdd:specify`.
- No edites `product/sources/`, `specs/` ni la constitución.
- No cambies el campo Estado del brief: la aprobación es del usuario, con
  `/discovery:approve`.

## Al terminar

1. Ejecuta de nuevo `discovery.py questions` y corrige cualquier cita rota que
   señale.
2. Reporta cuántas preguntas se cerraron y cuántas siguen abiertas. Si alguna
   abierta cita un objetivo, dilo: impide aprobar el producto.
3. El siguiente paso es `/discovery:decompose`.
