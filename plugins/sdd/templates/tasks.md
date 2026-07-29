# Tasks: {{TITLE}}

| Campo | Valor       |
| ----- | ----------- |
| Spec  | `spec.md`   |
| Plan  | `plan.md`   |
| Fecha | {{DATE}}    |

> Cada tarea debe ser verificable por sí sola y caber en una sola sesión de
> trabajo. Si una tarea necesita una decisión que no está en `plan.md`, la tarea
> está mal descompuesta.

## Leyenda

- `[ ]` pendiente · `[~]` en curso · `[x]` hecha
- `P` marca tareas paralelizables (sin dependencias entre sí)

## Tareas

### T001 — _\<título\>_

- **Estado:** `[ ]`
- **Requisitos:** R001
- **Depende de:** —
- **Archivos:** _rutas previstas_
- **Hecho cuando:** _condición observable y comprobable_

### T002 — _\<título\>_

- **Estado:** `[ ]`
- **Requisitos:** R001, R002
- **Depende de:** T001
- **Archivos:** _rutas previstas_
- **Hecho cuando:** _..._

## Cobertura

| Requisito | Tareas |
| --------- | ------ |
| R001 | T001, T002 |
| R002 | T002 |

_Todo requisito MUST debe tener al menos una tarea._
