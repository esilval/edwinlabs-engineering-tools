# Versión {{VERSION}}

| Campo    | Valor |
| -------- | ----- |
| Estado   | Draft |
| Versión  | {{VERSION}} |
| Fecha    | {{DATE}} |
| Anterior | {{PREVIOUS}} |
| Features | {{FEATURES}} |

> Borrador escrito por `release.py new`. Sustituye todo texto en cursiva.
> Lo que manda es `/release:check`: la sección «Comprobación» es el resultado
> del momento en que se escribió, y `/release:approve` la reescribe al
> aprobar. Solo el usuario cambia el Estado, con `/release:approve`.

## Contenido

{{CONTENT}}

## Comprobación

{{CHECK}}

## Notas para usuarios

> Qué cambia para quien usa el producto, en su lenguaje: sin requisitos, ni
> nombres de archivo, ni decisiones técnicas.

{{NOTES}}

## Cambios técnicos

> Qué cambia para el equipo técnico. Los datos de cada feature los genera
> `release.py new`; el resumen lo redacta `/release:new`.

{{CHANGES}}
