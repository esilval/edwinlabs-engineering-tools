---
name: check
description: Comprueba la coherencia de la arquitectura - atributos no medibles, candidatas sin componente, decisiones incompletas o sin motivo, citas rotas, preguntas abiertas, diagramas que se apartan de componentes y estándares, cambios tras aprobar.
---

# Check — coherencia de la arquitectura

Ejecuta:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/architecture.py" check
```

Explica al usuario cada hallazgo y qué lo corrige:

| Código | Qué lo corrige |
| ------ | -------------- |
| `E-QUALITY-NOT-MEASURABLE`, `E-QUALITY-NO-MOTIVE` | reescribir el atributo con cifra y motivo (`/architecture:init`) |
| `E-COMPONENT-NO-RESPONSIBILITY`, `E-COMPONENT-CANDIDATE-UNPLACED` | completar `components.md` (`/architecture:init`) |
| `E-ADR-INCOMPLETE`, `E-ADR-NO-MOTIVE`, `E-ADR-ID-DUPLICATE` | completar o renumerar el ADR (`/architecture:decide`) |
| `E-STANDARD-NO-ADR` | citar la decisión de origen del estándar (`/architecture:decide`) |
| `E-ARCH-REF-UNKNOWN` | corregir la cita o crear lo que falta |
| `E-ARCH-OPEN-QUESTION` | responder la pregunta con el usuario y convertirla en decisión o atributo |
| `E-ARCH-TEMPLATE` | rellenar los huecos de plantilla (también los del esqueleto de `diagrams.md`) |
| `E-ARCH-DIAGRAM-UNKNOWN` | quitar del diagrama el componente inexistente, o añadirlo a `components.md` con `next-id C` |
| `E-ARCH-DIAGRAM-MISSING` | añadir el componente a la vista que se nombra, o la vista que falta (`/architecture:diagram`) |
| `E-ARCH-DIAGRAM-VIOLATION` | dar la vuelta o quitar la arista que contradice el estándar que se nombra |
| `W-ARCH-NOT-APPROVED` | el usuario revisa y aprueba con `/architecture:approve` |
| `W-ARCH-PRODUCT-CHANGED` | revisar la arquitectura frente al producto nuevo y aprobarla de nuevo |
| `W-ARCH-NO-DIAGRAMS` | generar las vistas C4 con `/architecture:diagram`; no impide aprobar |

En CI: `architecture.py check --check` sale con 1 si hay errores, y
`--json` emite `architecture.check/v1`.

No cambies el campo Estado: lo aprueba el usuario.
