# Incidente {{ID}} — {{TITLE}}

| Campo            | Valor |
| ---------------- | ----- |
| Estado           | Draft |
| ID               | {{ID}} |
| Fecha            | _cuándo empezó: aaaa-mm-dd_ |
| Versión afectada | _la versión en marcha, 0.4.0, o desconocida_ |
| Severidad        | _crítica, alta, media o baja_ |

> Registrado con `operate.py incident`. El incidente se completa al
> registrarlo (`/operate:incident`) y el postmortem después
> (`/operate:postmortem`). Sustituye todo texto en cursiva. Solo el usuario
> cambia el Estado, con `/operate:approve`: aprobar este archivo es aprobar el
> postmortem.

## Qué pasó

_Qué se vio desde fuera: síntomas, desde cuándo y a quién afectó._

## Impacto

_Qué dejaron de poder hacer los usuarios, cuántos y durante cuánto tiempo._

## Cronología

_Lo que pasó en orden, con la hora: detección, decisiones y recuperación._

## Causas

_Por qué pasó: la causa técnica y lo que dejó que llegara a producción._

## Acciones

> Una subsección por acción, `### I001-A1 — <título>` con el campo
> `- **Qué:** …`, y cada ID de `operate.py next-action`. Una acción no se
> renumera nunca: su feature de corrección la cita por su ID
> (`/sdd:specify I001-A1`).

_Las acciones que evitan que se repita; las añade /operate:postmortem._
