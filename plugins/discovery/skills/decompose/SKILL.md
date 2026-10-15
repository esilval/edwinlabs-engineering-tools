---
name: decompose
description: Descompone los documentos del producto en un brief (objetivos, usuarios, glosario, restricciones, invariantes propuestos) y un backlog de features candidatas con su origen, sin redactar requisitos.
disable-model-invocation: true
---

# Decompose — de documentos a brief y backlog

Convierte lo que dicen los documentos en objetivos y features candidatas, cada
una con su origen citado. No redacta requisitos: eso lo hará `/sdd:specify`
cuando la feature arranque.

## Procedimiento

1. Estado actual:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" check
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" questions
   ```

   Si no hay documentos, pide `/discovery:ingest` y detente. Si hay preguntas
   abiertas que afectan a lo que vas a descomponer, recomienda antes
   `/discovery:clarify`.

2. Lee `product/sources/`, `product/brief.md` (incluidas las respuestas) y
   `product/backlog.md` si existe. Si falta alguno, cópialo de
   `${CLAUDE_PLUGIN_ROOT}/templates/` y sustituye todo texto en cursiva. Si ya
   existen, **actualízalos**: no los reescribas desde cero.

3. **Identificadores.** Los da el script, nunca tú:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" next-id G
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" next-id B
   ```

   Los objetivos y candidatas que ya existen conservan su ID. Nada se borra:
   una candidata que deja de tener sentido pasa a `**Estado:** descartada
   (motivo)`. Un ID nunca se reutiliza.

4. **Brief.** Objetivos (`### G1 — …` con `**Origen:**` y
   `**Descripción:**`), usuarios, glosario, restricciones e **invariantes
   propuestos para la constitución**: reglas transversales que los documentos
   exigen («todo dato personal cifrado»). Son propuestas: la constitución solo
   la cambia el usuario, con `/sdd:constitution`.

5. **Backlog.** Una candidata es una unidad de **valor observable**:

   - entrega algo que el usuario puede hacer y hoy no puede;
   - cabe en una spec de 3 a 12 requisitos MUST;
   - se puede probar sola.

   «Backend de autenticación» no es una candidata: es una capa, y las capas son
   tareas de una feature. Trocear por secciones del documento en vez de por
   valor es el error típico.

   Cada candidata lleva todos sus campos: Estado, Objetivos, Origen, Problema,
   Resultado observable, Dentro, Fuera y Depende de. Si una candidata no tiene
   un resultado observable claro, probablemente no es una candidata.

6. **Cobertura.** Toda sección de todo documento queda citada en el Origen de
   un objetivo o de una candidata, o se descarta explícitamente en
   `## Secciones descartadas` con su motivo. Nada se queda en silencio.

7. **Contradicciones.** Si un documento contradice a otro, no elijas: registra
   la pregunta en el brief citando las dos secciones (`(D1§3 contra D2§1)`) y
   sigue con lo que no depende de ella.

## Límites

- No redactes requisitos: nada de «el sistema DEBERÁ…». `check` lo marca como
  error (`E-BACKLOG-REQUIREMENT`).
- No edites `product/sources/`, `specs/` ni la constitución.
- No cambies el campo Estado. Si el brief o el backlog estaban aprobados,
  cualquier cambio exige que el usuario los vuelva a aprobar.

## Al terminar

1. Ejecuta `discovery.py check`. Corrige lo que sea tuyo: citas rotas, huecos
   de plantilla, secciones sin cubrir, numeración. No arregles nada inventando:
   si para cubrir una sección hace falta una decisión, es una pregunta para el
   usuario.
2. Muestra al usuario los objetivos y una tabla de candidatas (ID, título,
   objetivos, depende de), y las preguntas que siguen abiertas.
3. El siguiente paso es revisar el producto y ejecutar `/discovery:approve`.
