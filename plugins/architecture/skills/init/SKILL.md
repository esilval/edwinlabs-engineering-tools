---
name: init
description: Inicia la arquitectura de un producto nuevo desde el brief y el backlog aprobados por discovery - atributos de calidad medibles y componentes con las candidatas que alojan.
disable-model-invocation: true
---

# Init — atributos de calidad y componentes

Arranca `architecture/` desde el producto aprobado y redacta las dos primeras
piezas: **cómo debe comportarse** el sistema (atributos de calidad) y **de qué
partes está hecho** (componentes). Las decisiones de tecnología van después,
con `/architecture:decide`.

## Procedimiento

1. Crea los artefactos:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" init
   ```

   Si sale con código 1, muestra el motivo al usuario tal cual y **detente**:
   el producto de discovery falta, no está aprobado o cambió. No crees nada a
   mano. Si `architecture/` ya existía, `init` no sobrescribe nada: actualiza
   los artefactos en lugar de reescribirlos.

2. Lee `product/brief.md` (objetivos, usuarios, restricciones, invariantes) y
   `product/backlog.md` (candidatas vigentes; las descartadas no cuentan).

3. **Atributos de calidad** (`architecture/quality.md`). Uno por cada
   exigencia de comportamiento que el producto pide: rendimiento, volumen,
   disponibilidad, seguridad, privacidad, coste, plazos…
   - El escenario es **medible**: estímulo, respuesta y medida con cifra («al
     cerrar la caja, el total aparece en menos de 2 s con 5000 ventas»). Nunca
     «rápido», «escalable», «seguro». La comprobación rechaza un escenario sin
     cifra.
   - El motivo cita lo que lo justifica: un objetivo (`G1`) o la sección de
     origen de una restricción del brief (`D1§5`, la que lleva la viñeta entre
     paréntesis).
   - Si el producto no da la cifra, **no la inventes**: pregúntasela al
     usuario. Si no la sabe todavía, déjala como pregunta abierta en
     `architecture/questions.md` citando el atributo: `- [ ] (Q2) ¿Cuántas
     ventas tiene un día de cierre malo?`. Mientras tanto, el escenario sin
     cifra dará también `E-QUALITY-NOT-MEASURABLE`: avisa al usuario de que
     los dos hallazgos son el mismo hueco y se cierran juntos al responder.

4. **Componentes** (`architecture/components.md`). Las partes del sistema que
   tienen responsabilidad propia, al nivel que ayuda a decidir: no módulos de
   código ni clases.
   - Cada uno dice qué hace y qué deja a otros.
   - Cada candidata vigente del backlog vive en al menos un componente
     (`Candidatas: B01, B03`). La comprobación da error por una candidata sin
     componente.

5. **Identificadores.** Los da el script, nunca tú:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" next-id Q
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" next-id C
   ```

   El bloque de ejemplo de una plantilla recién copiada **es** el primero
   (`Q1`, `C1`): rellénalo en su sitio. Sustituye todo texto en cursiva.

6. Comprueba y corrige lo que salga:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" check
   ```

## Al terminar

Muestra al usuario los atributos y los componentes, y las preguntas que dejaste
abiertas. El siguiente paso es `/architecture:decide`.

No cambies el campo Estado: lo aprueba el usuario con `/architecture:approve`.
