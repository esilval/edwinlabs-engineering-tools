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
   | `E-PRODUCT-TEMPLATE`, `E-SOURCE-UNCOVERED`, `E-GOAL-NO-FEATURE`, `E-REF-UNKNOWN`, `E-BACKLOG-REQUIREMENT`, `E-BACKLOG-DEP-CYCLE` | `/discovery:decompose` |
   | `E-QUESTION-OPEN-GOAL` | `/discovery:clarify` |
   | `E-BACKLOG-ID-GAP` | Recuperar lo borrado y descartarlo en vez de borrarlo |

2. Agrupa los **avisos** (`W-`): no bloquean la aprobación.

3. **No arregles nada por tu cuenta.** Cubrir una sección inventando un
   objetivo, o cerrar una pregunta sin respuesta del usuario, satisface al
   comprobador y destruye su utilidad. Propón el arreglo real y espera.

## En CI

```bash
python3 discovery.py check --json    # schema discovery.check/v1
python3 discovery.py check --check   # sale con 1 si hay errores
```

Si no hay errores, el siguiente paso es que el usuario revise el producto y
ejecute `/discovery:approve`.
