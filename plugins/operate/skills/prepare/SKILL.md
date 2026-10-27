---
name: prepare
description: Prepara la puesta en marcha de una versión publicada - procedimiento y verificación, señales a vigilar con umbral (propuestas desde los atributos de calidad de la arquitectura) y plan de vuelta atrás con su disparador. No despliega ni ejecuta nada.
disable-model-invocation: true
argument-hint: "vX.Y.Z"
---

# Prepare — preparación operativa de una versión

Versión: `$ARGUMENTS`

Deja en `operations/vX.Y.Z.md` cómo se pone en marcha una versión publicada,
qué se vigila después y cómo se vuelve atrás. Lo determinista lo genera el
script: las features de la versión y, con arquitectura, una señal por cada
atributo de calidad que tocan. Tú redactas el resto con el usuario.

## Procedimiento

1. Si `$ARGUMENTS` está vacío, pregunta qué versión preparar y detente.

2. Escribe el borrador:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/operate.py" prepare $ARGUMENTS
   ```

   - Si sale con 1, la versión no existe o no está publicada: muestra el motivo
     y detente. Una versión se publica con `/release:approve`.
   - Si dice que **ya existe**, no la sobrescribe: complétala o corrígela a mano.

3. Lee el borrador, la versión en `releases/` y, de cada feature, su `spec.md`
   y su `plan.md` (contratos, modelo de datos, despliegue). Con
   `architecture/`, lee también los atributos de calidad y las decisiones que
   citan las señales propuestas.

4. Completa con el usuario cada línea en cursiva:
   - **Puesta en marcha:** los pasos, en orden, y cómo comprobar después que
     la versión funciona. No los ejecutes: el plugin no despliega.
   - **Señales:** para cada una, el **umbral con cifra** (a partir de qué valor
     preocupa: «p95 > 2 s durante 5 minutos», no «que vaya lento») y **cómo se
     mide**. Una señal propuesta trae su atributo y su escenario: no los
     cambies. Añade las señales que falten con el siguiente `SG<n>`; si la
     sección dice por qué no hay propuesta, bórrala cuando ya no aplique.
   - **Vuelta atrás:** los pasos para volver a la versión anterior y el
     **disparador**: qué señal (`SG1`) o condición obliga a volver atrás.

   No toques la cabecera ni la sección «Features»: las escribe el script.

5. Comprueba:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/operate.py" check v<número>
   ```

   Corrige los errores (`E-PREP-*`). Si solo queda el aviso de que no está
   aprobada, pide al usuario que la revise y ejecute `/operate:approve v<número>`.

## Límite

No cambies el campo Estado ni ejecutes `operate.py approve`: la aprobación es
del usuario, y los guardrails lo impiden. No ejecutes los pasos de puesta en
marcha ni de vuelta atrás.
