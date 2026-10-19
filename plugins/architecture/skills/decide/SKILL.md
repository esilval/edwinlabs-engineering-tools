---
name: decide
description: Redacta con el usuario las decisiones de arquitectura (ADR) que afectan a más de una feature o son caras de revertir, y los estándares comprobables que se derivan de ellas.
disable-model-invocation: true
argument-hint: [tema de la decisión, opcional]
---

# Decide — decisiones de arquitectura y estándares

Tema pedido (puede estar vacío): `$ARGUMENTS`

Convierte las decisiones que el producto necesita en ADRs y estándares. El
modelo **propone** opciones con sus consecuencias; **el usuario decide**.

## La regla de frontera

Una decisión va aquí si **afecta a más de una feature o es cara de revertir**:
stack y lenguaje, persistencia, despliegue e infraestructura, integración entre
componentes, autenticación, mensajería, formato de datos compartidos… Si solo
afecta a una feature y es barata de cambiar, va al `plan.md` de esa feature,
no aquí. Ante la duda, pregunta al usuario.

## Procedimiento

1. Estado actual:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" check
   ```

   Si no existe `architecture/`, pide `/architecture:init` y detente. Lee
   `architecture/quality.md`, `components.md`, `standards.md`,
   `questions.md`, los ADR de `architecture/adr/` y el brief.

2. Lista las decisiones pendientes que cumplen la regla de frontera (o la del
   tema pedido). Para **cada una**, antes de escribirla:
   - plantea al usuario dos o tres opciones con lo que cuesta y ata cada una,
     y qué atributo de calidad u objetivo favorece;
   - **no elijas tú la tecnología**. Si el usuario no decide todavía, escribe
     igualmente el ADR en `Draft` (paso 3) con Contexto, las opciones en
     Alternativas y en Decisión «Pendiente: ver la pregunta abierta»; después
     abre en `questions.md` la pregunta que lo cita con su número real
     (`- [ ] (ADR-0003) ¿…?`) y sigue con otra decisión. Así la pregunta nunca
     cita un ADR que no existe, y la aprobación queda bloqueada hasta que el
     usuario responda.

3. Escribe cada decisión en su archivo:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" next-id ADR
   ```

   Copia `${CLAUDE_PLUGIN_ROOT}/templates/adr.md` a
   `architecture/adr/NNNN-slug.md` (número del script, slug en minúsculas),
   sustituye `{{NUMBER}}`, `{{TITLE}}`, `{{DATE}}` y todo texto en cursiva:
   - **Motivo:** el atributo (`Q1`), objetivo (`G2`) o restricción (`D1§5`)
     que la motiva. Sin motivo, la comprobación da error.
   - **Contexto, Decisión, Alternativas descartadas** (con el porqué de cada
     una) y **Consecuencias**. Las cuatro con contenido.
   - **Estado:**
     - `Draft` si la arquitectura aún no se ha aprobado: se aprueba con el
       conjunto.
     - `Proposed` si ya estaba aprobada: la decide el usuario con
       `/architecture:review`. Si sustituye a otra, rellena `Sustituye`.

     Nunca `Approved`, `Rejected` ni `Superseded`: el guardrail lo impide.

4. **Estándares** (`architecture/standards.md`): las reglas comprobables que
   se derivan de las decisiones, con `next-id S`:
   - `Tipo: capas` (orden de capas), `dependencia` (`Detalle: C2 → C1`: C2
     depende de C1, nunca al revés) o `prohibida` (`Detalle: C1 → C3`: C1 no
     puede depender de C3; varios pares separados por comas). `check` contrasta
     los pares de estos dos tipos con las aristas de los diagramas. Una
     prohibición que no es entre componentes (una librería, un servicio) se
     escribe en prosa en el Detalle, sin flechas: no se comprueba;
   - `Decisión:` el ADR del que sale.

5. Comprueba y corrige:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" check
   ```

## Al terminar

Muestra las decisiones tomadas, las preguntas que quedan abiertas (bloquean la
aprobación) y los estándares. El siguiente paso es `/architecture:approve`, o
`/architecture:review` para una decisión propuesta.
