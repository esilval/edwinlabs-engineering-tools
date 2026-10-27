---
name: incident
description: Registra un incidente de producción con un ID que no se recicla (I001, I002…) y completa con el usuario cuándo empezó, la versión afectada, la severidad, qué pasó y el impacto. El postmortem se redacta después, con /operate:postmortem.
disable-model-invocation: true
argument-hint: "<título del incidente>"
---

# Incident — registrar un incidente

Título: `$ARGUMENTS`

## Procedimiento

1. Si `$ARGUMENTS` está vacío, pregunta un título breve («Caída del resumen
   diario») y detente.

2. Registra el incidente:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/operate.py" incident "$ARGUMENTS"
   ```

   Devuelve el ID (`I003`) y el archivo. El número lo da el registro
   `operations/incidents.md`, que solo crece: no lo cambies ni lo reutilices.

3. Completa con el usuario, sin inventar nada que no te diga:
   - **Fecha:** cuándo empezó, `aaaa-mm-dd`.
   - **Versión afectada:** la que estaba en marcha (`0.4.0`), de `releases/`.
     Si no se sabe, `desconocida`.
   - **Severidad:** `crítica`, `alta`, `media` o `baja`.
   - **Qué pasó:** lo que se vio desde fuera.
   - **Impacto:** qué dejaron de poder hacer los usuarios, cuántos y cuánto
     tiempo.

   Deja la cronología, las causas y las acciones para `/operate:postmortem`.

4. Muestra al usuario el ID y el siguiente paso: `/operate:postmortem <ID>`
   cuando se haya resuelto.

## Límite

No cambies el campo Estado: el postmortem lo aprueba el usuario con
`/operate:approve`.
