# Plan: {{TITLE}}

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | {{DATE}}           |
| Estado | Draft              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

_Dos o tres frases: qué se construye, cuál es la decisión arquitectónica clave
y por qué esa vía._

## Comprobación de constitución

> Una fila por regla de `specs/constitution.md` que este plan toque. Si una
> decisión contradice una regla, no se ignora: se justifica aquí o se cambia
> la regla. Sin constitución, escribe «No aplica.».

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| _regla de la constitución_ | _sí / no_ | _..._ |

## Decisiones

### D1 — _\<título de la decisión\>_

- **Contexto:** _qué fuerza la decisión_
- **Decisión:** _lo que se hará_
- **Alternativas descartadas:** _opción B, y por qué no_
- **Consecuencias:** _lo que esto nos cuesta o nos ata_

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| _ruta o módulo_ | _qué cambia_ | R001, R002 |

## Modelo de datos

_Entidades nuevas o modificadas, migraciones necesarias._

## Contratos

_Endpoints, firmas de funciones públicas, eventos, formatos de mensaje.
Solo los que cruzan una frontera de módulo._

## Estrategia de pruebas

| Requisito | Tipo de prueba | Dónde vive |
| --------- | -------------- | ---------- |
| R001 | _unitaria / integración / e2e_ | _ruta_ |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |

## Trazabilidad

_Todo requisito MUST de `spec.md` debe aparecer al menos una vez en la tabla de
componentes o en la de pruebas. Los que no aparezcan, se listan aquí con su
motivo._
