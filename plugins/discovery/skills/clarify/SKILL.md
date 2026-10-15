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
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" check
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" questions
   ```

   Si `check` dice que hay 0 documentos, pide `/discovery:ingest` y detente.

2. Si no existe `product/brief.md`, cópialo de
   `${CLAUDE_PLUGIN_ROOT}/templates/brief.md` y **borra la pregunta de ejemplo**
   de `## Preguntas`: si no, cuenta como una pregunta abierta real. Deja el
   campo Estado como está y no rellenes todavía objetivos: eso es
   `/discovery:decompose`. El `### G1` de la plantilla es un ejemplo, no un
   objetivo; no lo cites. Mientras tanto, `check` informará de los huecos de
   plantilla, y es normal.

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

5. Presenta las preguntas **de pocas en pocas**, cada una con su cita (`D1§2`)
   para que el usuario sepa de dónde sale, y con opciones concretas cuando
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
  `/discovery:approve`. Si el brief ya estaba aprobado, añadir o cerrar
  preguntas lo deja sin aprobar hasta que el usuario lo vuelva a aprobar.

## Al terminar

1. Ejecuta de nuevo `discovery.py questions` y corrige cualquier cita rota que
   señale.
2. Reporta cuántas preguntas se cerraron y cuántas siguen abiertas. Si alguna
   abierta cita un objetivo, dilo: impide aprobar el producto.
3. El siguiente paso es `/discovery:decompose`.
