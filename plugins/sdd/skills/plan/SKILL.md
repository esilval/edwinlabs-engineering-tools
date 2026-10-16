---
name: plan
description: Traduce una spec SDD a decisiones de arquitectura e implementación en plan.md, con alternativas descartadas y trazabilidad hacia los requisitos.
disable-model-invocation: true
---

# Fase 2 — Plan

Decide **cómo** se construye lo que la spec describe.

## Procedimiento

1. Resuelve la feature activa y su estado con
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" status`.
   Si no hay ninguna, detente y pide `/sdd:specify`. Si `spec.md` no está en
   `[x] listo`, detente: o falta completarla, o falta que el usuario ejecute
   `/sdd:approve`. Planificar sobre una spec sin revisar es planificar
   sobre una suposición.

2. Lee, en este orden: `specs/constitution.md` (si existe), el `spec.md` de la
   feature, y el código relevante del repositorio.

3. **Comprueba las preguntas abiertas.** Si `spec.md` tiene preguntas abiertas
   que afectan a requisitos MUST, detente y recomienda `/sdd:clarify`. Planificar
   sobre ambigüedad genera trabajo que hay que tirar.

4. Si `plan.md` ya existe (por ejemplo, tras `/sdd:amend`), **actualízalo**:
   no lo sobrescribas con la plantilla, y cubre el cambio de la spec. Si no
   existe, copia `${CLAUDE_PLUGIN_ROOT}/templates/plan.md` al directorio de la feature y
   rellénalo. Sustituye `{{TITLE}}`, `{{DATE}}` y todo texto en cursiva; la
   compuerta trata cualquier hueco que quede como plan incompleto. Deja
   `Estado: Draft`.

5. Rellena «Comprobación de constitución» con cada regla que el plan toque. Si
   una decisión contradice una regla, justifícalo ahí o propón cambiar la
   regla; no la ignores. `trace` avisa si existe constitución y esta sección
   falta.

   **Arquitectura.** Si el proyecto tiene `architecture/`, parte de ella:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" arch-context
   ```

   - Si dice que la arquitectura no está aprobada o que la candidata no tiene
     componente, detente: se resuelve en `architecture` (`/architecture:init`,
     `/architecture:approve`) antes de planificar.
   - El plan **no vuelve a decidir** lo que ya decide la arquitectura (stack,
     persistencia, despliegue…): lo cita (`ADR-0001`) y lo respeta. Añade la
     sección `## Comprobación de arquitectura` con una fila por decisión
     vigente y estándar que el plan toca, y cómo lo cumple. `trace` avisa si
     falta, y da error si el plan cita una decisión que no existe o no está
     aprobada.
   - Si el plan necesita una decisión que **afecta a más de una feature o es
     cara de revertir** y ningún ADR aprobado la cubre, no la tomes en el plan:
     propónla a la arquitectura y redáctala con el usuario.

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" propose-adr "<título>"
     ```

     Rellena el archivo que indica (motivo, contexto, decisión, alternativas
     descartadas, consecuencias) y cítalo en el plan. Dile al usuario que el
     plan **no se podrá aprobar** hasta que decida la propuesta con
     `/architecture:review`. No cambies tú su Estado.
   - Una decisión que solo afecta a esta feature y es barata de cambiar va en
     el plan, como siempre.

   Sin `architecture/`, sigue como hasta ahora.

6. Para cada decisión relevante, documenta también **la alternativa que
   descartaste y por qué**. Es la parte del plan que más valor tiene dentro de
   seis meses, y la que siempre se omite.

7. Cierra con la tabla de trazabilidad: todo requisito MUST de la spec debe
   aparecer en la tabla de componentes o en la de pruebas. Si alguno no aparece,
   o falta cobertura en el plan o sobra el requisito en la spec. Señálalo, no lo
   silencies. Cita solo IDs que existan en la spec: un `R0xx` que no esté ahí
   es un requisito colado por la puerta de atrás (`E-PLAN-UNKNOWN-REQ`).

## Límite

Si al planificar descubres un requisito que no está en la spec, no lo añadas
aquí. Dile al usuario que hace falta volver a `spec.md`, y ofrécete a editarlo.
El plan que introduce requisitos por la puerta de atrás rompe la premisa de que
la spec es la fuente de verdad.

## Al terminar

Resume las decisiones principales y sus consecuencias. Pide al usuario que
revise el plan y ejecute `/sdd:approve`; después viene `/sdd:tasks`.
