---
name: tasks
description: Descompone un plan SDD en tareas atómicas y verificables en tasks.md, con dependencias y cobertura de requisitos.
disable-model-invocation: true
---

# Fase 3 — Tasks

Convierte el plan en unidades de trabajo ejecutables.

## Procedimiento

1. Resuelve la feature activa y su estado con
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py" status`. Si `plan.md` no
   está en `[x] listo`, detente y di qué falta: `/sdd:plan` o
   `/sdd:approve plan`.

2. Lee `spec.md` y `plan.md`.

3. Copia `${CLAUDE_PLUGIN_ROOT}/templates/tasks.md` al directorio de la feature
   y rellénalo. Sustituye `{{TITLE}}`, `{{DATE}}` y todo texto en cursiva, y
   borra las tareas de ejemplo que no uses. Deja `Estado: Draft`.

4. Criterios para que una tarea esté bien formada:
   - **Atómica:** cabe en una sesión de trabajo y se puede verificar sola.
   - **Trazable:** referencia al menos un ID de requisito de la spec.
   - **Ordenada:** declara de qué otras tareas depende.
   - **Cerrable:** su «hecho cuando» es una condición observable, no una
     sensación. «Los tests de `test_auth.py` pasan» sirve; «la autenticación
     funciona» no.

5. Marca con `P` las tareas paralelizables entre sí.

6. Rellena la tabla de cobertura. Si un requisito MUST se queda sin tareas,
   dilo en voz alta antes de terminar.

## Convención de pruebas

Cuando la tarea implique escribir pruebas, indícalo en el «hecho cuando» y usa
el ID del requisito **con el prefijo de la feature** en el nombre del test:
`test_F001_R001_rechaza_token_expirado` para el R001 de la feature `001-…`.
Los IDs `R001` se repiten en cada feature, así que un `test_R001_…` sin prefijo
no cuenta. Es lo que permite a `/sdd:trace` verificar la cobertura de forma
determinista.

## Sobre el tamaño

Prefiere más tareas pequeñas que pocas grandes. Una tarea que toca doce archivos
es un plan disfrazado de tarea, y es donde la implementación se descarrila.

## Al terminar

Muestra la lista de tareas con sus dependencias. Pide al usuario que las revise
y ejecute `/sdd:approve tasks`; con eso la compuerta deja escribir código y el
siguiente paso es `/sdd:implement`.
