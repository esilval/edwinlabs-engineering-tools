---
name: status
description: Muestra el estado del flujo SDD en este proyecto: feature activa, artefactos presentes y siguiente paso.
disable-model-invocation: true
---

# Estado del flujo SDD

Ejecuta:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" status
```

Muestra la salida al usuario. Si hay varias features y ninguna activa, explica
que puede fijar una escribiendo su slug en `.sdd/current`, o cambiando de rama
git al nombre de la feature.

Si la compuerta está bloqueando trabajo, di cuál es el artefacto que falta y qué
skill lo produce. La leyenda del reporte:

- `[ ]` falta: lo produce la skill indicada.
- `[~]` incompleto: existe pero tiene huecos de plantilla o le falta cobertura.
  Lista los problemas.
- `[a]` sin aprobar: está completo. El usuario debe revisarlo y ejecutar
  `/sdd:approve`.
- `[x]` listo.
