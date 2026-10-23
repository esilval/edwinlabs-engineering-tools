---
name: new
description: Prepara una versión con las features que elige el usuario - comprueba que están aprobadas, cerradas y trazadas, propone el número SemVer y redacta las notas para usuarios y los cambios técnicos. No despliega ni etiqueta.
disable-model-invocation: true
argument-hint: "<features…> [--version X.Y.Z]"
---

# New — preparar una versión

Features elegidas: `$ARGUMENTS`

Deja en `releases/vX.Y.Z.md` el borrador de una versión. Lo determinista lo
genera el script: las features, sus requisitos, la comprobación y el número
propuesto. Tú redactas las notas para usuarios y el resumen de los cambios
técnicos.

## Procedimiento

1. Si `$ARGUMENTS` está vacío, pregunta qué features entran (`008 009`, o
   `008-slug`) y detente hasta que responda. No elijas tú las features.

2. Escribe el borrador:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" new $ARGUMENTS
   ```

   - Sale con 1 sin features o con un número mal formado: muestra el motivo y
     detente.
   - Si dice que el archivo **ya existe**, no lo sobrescribe: dile al usuario
     qué features tiene y que, si quiere otra versión, fije el número con
     `--version`.
   - Si propuso un número, explica por qué: sin versión publicada, 0.1.0; con
     un requisito retirado (`OBSOLETO`), la mayor (en 0.x, la menor); con
     funcionalidad nueva, la menor; solo correcciones, el parche. Un
     `OBSOLETO` de una enmienda durante el desarrollo, que no retira nada
     publicado, sube la mayor igual: si no es un cambio que rompe, el usuario
     fija el número con `--version`.

3. Si la comprobación da errores, explícalos y di qué los corrige, **sin
   editar nada en `specs/`**: una versión no arregla sus features, las
   arregla `sdd`.

   | Código | Qué lo corrige |
   | ------ | -------------- |
   | `E-RELEASE-FEATURE-NOT-APPROVED` | revisar y aprobar la fase nombrada (`/sdd:approve`) |
   | `E-RELEASE-FEATURE-OPEN-TASKS` | terminar las tareas (`/sdd:implement`) o sacar la feature |
   | `E-RELEASE-FEATURE-TRACE` | la trazabilidad de la feature (`/sdd:trace`) |
   | `E-RELEASE-FEATURE-ADR` | decidir la decisión en `/architecture:review` |
   | `E-RELEASE-FEATURE-TYPE` | la fila `Tipo` de la spec: `funcionalidad` o `corrección` |
   | `E-RELEASE-FEATURE-UNKNOWN`, `E-RELEASE-FEATURE-RELEASED` | elegir otras features |
   | `E-RELEASE-VERSION` | otro número con `--version` |

   El borrador sirve igualmente para redactar: sigue con el paso 4.

4. Lee el borrador y, de cada feature, su `spec.md` (problema, alcance,
   requisitos) y su `plan.md`. Si la fila Origen cita candidatas y objetivos y
   existe `product/`, lee también la candidata en `product/backlog.md` y los
   objetivos en `product/brief.md`.

5. Sustituye cada línea en cursiva:
   - **Notas para usuarios:** qué cambia para quien usa el producto, en su
     lenguaje y desde el problema que resuelve: sin requisitos, archivos ni
     decisiones técnicas. Una o pocas frases por feature. Si el hueco cita una
     candidata o un objetivo, que la nota se entienda desde ellos y los
     conserve al final entre paréntesis: `(B01, G1)`.
   - **Cambios técnicos:** resume para el equipo lo que dicen los datos de
     encima (requisitos, decisiones de arquitectura, contratos y modelo de
     datos). Si hay requisitos retirados, di qué deja de funcionar. No
     cambies los datos generados.

   No toques la cabecera, «Contenido» ni «Comprobación»: los escribe el
   script, y `approve` reescribe la comprobación al aprobar.

6. Comprueba:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" check v<número>
   ```

   Si solo queda el aviso de versión sin aprobar, pide al usuario que la
   revise y ejecute `/release:approve`.

## Límite

No cambies el campo Estado ni ejecutes `release.py approve`: la aprobación es
del usuario, y los guardrails lo impiden. El plugin no etiqueta ni publica.
