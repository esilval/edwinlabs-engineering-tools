# Preparación de la versión {{VERSION}}

| Campo    | Valor |
| -------- | ----- |
| Estado   | Draft |
| Versión  | {{VERSION}} · {{RELEASE_DIGEST}} |
| Fecha    | {{DATE}} |
| Features | {{FEATURES}} |

> Borrador escrito por `operate.py prepare` para la versión publicada
> {{VERSION}}. Sustituye todo texto en cursiva. Solo el usuario cambia el
> Estado, con `/operate:approve`, que guarda en la fila Versión la huella de la
> versión que aprueba: si la versión cambia después, `/operate:check` lo avisa.

## Features

{{FEATURE_LIST}}

## Puesta en marcha

_Los pasos para poner la versión en marcha, y cómo comprobar después que funciona._

## Señales

> Una subsección por señal, `### SG1 — <nombre>`, con `Atributo` (el atributo
> de calidad que vigila, o `—`), `Escenario`, `Umbral` (a partir de qué cifra
> preocupa) y `Cómo se mide`.

{{SIGNALS}}

## Vuelta atrás

- **Pasos:** _cómo volver a la versión anterior_
- **Disparador:** _qué señal (SG1) o condición obliga a volver atrás_
