---
name: check
description: Comprueba las versiones de releases/ - features sin aprobar, con tareas abiertas, con errores de trazabilidad o ya publicadas, número de versión inválido, huecos sin completar y cambios tras aprobar.
argument-hint: "[vX.Y.Z]"
---

# Check — comprobación de las versiones

Ejecuta, con la versión que nombre el usuario o sin ella para todas:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" check $ARGUMENTS
```

Explica al usuario cada hallazgo y qué lo corrige:

| Código | Qué lo corrige |
| ------ | -------------- |
| `E-RELEASE-NO-FEATURES` | elegir las features de la versión con `/release:new` |
| `E-RELEASE-FEATURE-UNKNOWN` | corregir el número de la feature en la cabecera `Features` |
| `E-RELEASE-FEATURE-RELEASED` | quitar la feature: ya salió en la versión que se nombra |
| `E-RELEASE-FEATURE-NOT-APPROVED` | aprobar la fase que se nombra en `sdd` (`/sdd:approve`), revisándola antes si cambió |
| `E-RELEASE-FEATURE-OPEN-TASKS` | terminar las tareas nombradas con `/sdd:implement`, o sacar la feature de la versión |
| `E-RELEASE-FEATURE-TRACE` | corregir la trazabilidad de la feature (`/sdd:trace`) |
| `E-RELEASE-FEATURE-ADR` | decidir la decisión de arquitectura con `/architecture:review`, o quitar la cita del plan |
| `E-RELEASE-FEATURE-TYPE` | dejar la fila `Tipo` de la spec en `funcionalidad` o `corrección` |
| `E-RELEASE-VERSION` | elegir un número mayor que la última versión publicada, que no exista, y que coincida con el archivo |
| `E-RELEASE-TEMPLATE` | completar las notas para usuarios y los cambios técnicos |
| `W-RELEASE-NOT-APPROVED` | el usuario revisa y aprueba con `/release:approve` |
| `W-RELEASE-NO-TRACE` | instalar `sdd` o fijar `SDD_SCRIPT` con la ruta de `sdd.py`; mientras, no se comprueban la trazabilidad ni las decisiones de arquitectura |

En CI: `release.py check --check` sale con 1 si hay errores, y `--json` emite
`release.check/v1`.

No cambies el campo Estado: lo aprueba el usuario.
