---
name: check
description: Comprueba la operación - preparaciones de versión sin umbrales con cifra, sin disparador de vuelta atrás o de una versión no publicada, incidentes con versión inexistente o acciones repetidas, huecos sin completar, cambios tras aprobar y acciones de postmortems aprobados sin feature.
argument-hint: "[vX.Y.Z|I001]"
---

# Check — comprobación de la operación

Ejecuta, con la preparación (`v0.4.0`) o el incidente (`I001`) que nombre el
usuario, o sin argumento para todo `operations/`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/operate.py" check $ARGUMENTS
```

Explica al usuario cada hallazgo y qué lo corrige:

| Código | Qué lo corrige |
| ------ | -------------- |
| `E-PREP-RELEASE` | preparar una versión publicada (`/release:approve` la publica) |
| `E-PREP-SIGNAL-THRESHOLD` | dar a la señal nombrada un umbral con cifra (`/operate:prepare`) |
| `E-PREP-ROLLBACK-TRIGGER` | decir qué señal o condición dispara la vuelta atrás |
| `E-PREP-TEMPLATE` | completar la preparación (`/operate:prepare`) |
| `W-PREP-NOT-APPROVED` | el usuario la revisa y aprueba con `/operate:approve` |
| `W-PREP-RELEASE-CHANGED` | revisar la preparación frente a la versión cambiada y aprobarla de nuevo |
| `E-INCIDENT-RELEASE` | corregir la versión afectada, o escribir `desconocida` |
| `E-INCIDENT-ACTION-ID` | dar a la acción un ID nuevo con `operate.py next-action` |
| `E-INCIDENT-TEMPLATE` | completar el incidente o su postmortem (`/operate:postmortem`) |
| `W-INCIDENT-NOT-APPROVED` | el usuario revisa el postmortem y lo aprueba con `/operate:approve` |
| `W-INCIDENT-ACTION-NO-FEATURE` | crear la corrección con `/sdd:specify` y el ID de la acción |

En CI: `operate.py check --check` sale con 1 si hay errores, y `--json` emite
`operate.check/v1`.

No cambies el campo Estado: lo aprueba el usuario.
