---
name: trace
description: Comprueba la trazabilidad de la feature activa - qué requisitos MUST no tienen tarea, prueba o criterios de aceptación. Úsala antes de dar una feature por terminada y cuando quieras saber si la implementación cubre realmente la spec.
disable-model-invocation: true
---

# Trazabilidad

Ejecuta:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" trace
```

Muestra la salida completa al usuario. Después:

1. Si hay **errores**, explica en una frase qué implica cada uno y qué haría
   falta para cerrarlo. Ordénalos por lo que desbloquea más trabajo.
2. Si hay **avisos**, agrúpalos: no merecen el mismo peso que un error.
3. **No arregles nada por tu cuenta.** Corregir `E-REQ-NO-TEST` escribiendo un
   test vacío que mencione el ID destruye la utilidad del comprobador. Además
   no sirve: una prueba vacía no cuenta (`W-TEST-EMPTY`). Propón el arreglo
   real y espera.

## La convención que hace que esto funcione

La evidencia de prueba se detecta por el ID del requisito **con el prefijo de
la feature** en el archivo de test: en el nombre de la función
(`test_F001_R001_rechaza_token_expirado`) o en un comentario dentro de ella
(`# F001-R001`). Los `R001` se reinician en cada feature, así que un
`test_R001_…` sin prefijo es ambiguo y no cuenta (aviso `W-TEST-UNSCOPED`). Si
un requisito no aparece en ningún test, para el comprobador no está probado,
aunque exista cobertura de código.

Cuando escribas tests durante `/sdd:implement`, nombra siempre así.

## Códigos

Los que empiezan por `E-` son errores y hacen fallar `trace --check`, que es lo
que corre en CI. Los `W-` son avisos y no bloquean.
