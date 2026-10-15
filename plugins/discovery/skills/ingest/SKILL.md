---
name: ingest
description: Añade un documento de producto (Markdown, Word o PDF) al producto como D1, D2…, con sus secciones numeradas para citarlas (D2§4.2). Primer paso del flujo discovery.
disable-model-invocation: true
argument-hint: <ruta del documento>
---

# Ingest — añadir un documento al producto

Documento a ingerir: `$ARGUMENTS`

Un producto crece con documentos que llegan a lo largo del tiempo. Cada uno
entra entero, una sola vez, y no se edita después: un cambio entra como
documento nuevo.

## Procedimiento

1. Si `$ARGUMENTS` está vacío, pregunta qué documento ingerir y detente.

2. Según el formato:

   - **Markdown (`.md`, `.markdown`) o Word (`.docx`):** el script hace todo.

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" ingest "<ruta>"
     ```

   - **PDF:** el script no puede leer PDF sin dependencias externas, así que
     la conversión es tuya.
     1. Lee el PDF entero.
     2. Escribe su contenido como Markdown en un archivo temporal fuera del
        repositorio. Conserva la estructura: cada título del PDF es un
        encabezado (`#` para el título del documento, `##` para sus secciones,
        `###` para las subsecciones). No resumas, no reordenes, no añadas.
     3. **Revisa la conversión con el usuario antes de ingerirla.** Muéstrale
        los encabezados y avísale de cualquier parte que no pudiste leer bien
        (tablas, columnas, imágenes con texto). Corrige el Markdown temporal
        hasta que lo dé por bueno. Después ya no se puede: un documento
        ingerido no se edita (`check` lo marca como `E-SOURCE-MODIFIED`), y el
        mismo PDF no se puede volver a ingerir, porque es un duplicado.
     4. Ingiere el Markdown indicando el PDF como original:

        ```bash
        python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" ingest "<markdown temporal>" --original "<ruta del pdf>"
        ```

     5. Borra el Markdown temporal.

   - **Cualquier otro formato:** ejecuta igualmente el comando de Markdown con
     la ruta; el script lo rechaza y su mensaje lista los formatos admitidos.
     Muéstraselo al usuario.

3. **No crees, muevas ni edites nada en `product/sources/` a mano.** El
   identificador `Dn`, la numeración de secciones y las huellas son
   responsabilidad del script.

## Si el script rechaza el documento

Muestra el motivo tal cual. Los habituales:

- es idéntico a un documento ya ingerido (nombra cuál);
- el formato no está admitido, o el archivo no existe;
- el Word está dañado, o el Markdown no es UTF-8;
- un PDF pasado sin convertir, o `--original` usado con algo que no es un PDF.

El producto no cambia en ningún rechazo. No intentes forzarlo.

## Al terminar

1. Muestra el identificador asignado y cuántas secciones tiene.
2. Indica que el siguiente paso es `/discovery:clarify`, para aclarar huecos y
   contradicciones, y después `/discovery:decompose`.
