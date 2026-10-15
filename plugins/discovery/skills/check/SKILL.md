---
name: check
description: Comprueba la coherencia del producto - objetivos sin candidata, secciones sin cubrir, citas rotas, dependencias circulares, documentos editados - antes de aprobarlo o en CI.
disable-model-invocation: true
---

# Check — coherencia del producto

Ejecuta:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/discovery.py" check
```

Muestra la salida completa al usuario. Después:

1. Si hay **errores** (`E-`), explica en una frase qué implica cada uno y qué
   lo corrige. Ordénalos por lo que más desbloquea:

   | Código | Lo corrige |
   | ------ | ---------- |
   | `E-SOURCE-MODIFIED` | Restaurar el documento; un cambio entra como documento nuevo con `/discovery:ingest` |
   | `E-PRODUCT-TEMPLATE`, `E-SOURCE-UNCOVERED`, `E-GOAL-NO-FEATURE`, `E-BACKLOG-REQUIREMENT`, `E-BACKLOG-DEP-CYCLE` | `/discovery:decompose` |
   | `E-REF-UNKNOWN` | `/discovery:decompose`; si la cita rota está en una pregunta, `/discovery:clarify` |
   | `E-QUESTION-OPEN-GOAL` | `/discovery:clarify` |
   | `E-BACKLOG-ID-GAP`, hueco en objetivos o candidatas | Recuperar lo borrado y descartarlo en vez de borrarlo |
   | `E-BACKLOG-ID-GAP`, ID repetido | Fusionar los dos elementos o dar al segundo un ID nuevo con `next-id` |
   | `E-BACKLOG-ID-GAP`, hueco o repetido en documentos | Restaurar el documento borrado, o quitar la copia duplicada de `product/sources/` |

2. Agrupa los **avisos** (`W-`): no bloquean la aprobación.

3. **No arregles nada por tu cuenta.** Cubrir una sección inventando un
   objetivo, o cerrar una pregunta sin respuesta del usuario, satisface al
   comprobador y destruye su utilidad. Propón el arreglo real y espera.

## En CI

```bash
python3 <ruta del plugin>/scripts/discovery.py check --json    # schema discovery.check/v1
python3 <ruta del plugin>/scripts/discovery.py check --check   # sale con 1 si hay errores
```

Si no hay errores, el siguiente paso es que el usuario revise el producto y
ejecute `/discovery:approve`.
