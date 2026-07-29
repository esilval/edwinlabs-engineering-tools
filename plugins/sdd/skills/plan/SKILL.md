---
name: plan
description: Traduce una spec SDD a decisiones de arquitectura e implementación en plan.md, con alternativas descartadas y trazabilidad hacia los requisitos.
disable-model-invocation: true
---

# Fase 2 — Plan

Decide **cómo** se construye lo que la spec describe.

## Procedimiento

1. Resuelve la feature activa con
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" current`.
   Si no hay ninguna, detente y pide `/sdd:specify`.

2. Lee, en este orden: `specs/constitution.md` (si existe), el `spec.md` de la
   feature, y el código relevante del repositorio.

3. **Comprueba las preguntas abiertas.** Si `spec.md` tiene preguntas abiertas
   que afectan a requisitos MUST, detente y recomienda `/sdd:clarify`. Planificar
   sobre ambigüedad genera trabajo que hay que tirar.

4. Copia `${CLAUDE_PLUGIN_ROOT}/templates/plan.md` al directorio de la feature y
   rellénalo.

5. Para cada decisión relevante, documenta también **la alternativa que
   descartaste y por qué**. Es la parte del plan que más valor tiene dentro de
   seis meses, y la que siempre se omite.

6. Cierra con la tabla de trazabilidad: todo requisito MUST de la spec debe
   aparecer en la tabla de componentes o en la de pruebas. Si alguno no aparece,
   o falta cobertura en el plan o sobra el requisito en la spec. Señálalo, no lo
   silencies.

## Límite

Si al planificar descubres un requisito que no está en la spec, no lo añadas
aquí. Dile al usuario que hace falta volver a `spec.md`, y ofrécete a editarlo.
El plan que introduce requisitos por la puerta de atrás rompe la premisa de que
la spec es la fuente de verdad.

## Al terminar

Resume las decisiones principales y sus consecuencias. Indica que el siguiente
paso es `/sdd:tasks`.
