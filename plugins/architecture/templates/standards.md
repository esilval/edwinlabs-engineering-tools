# Estándares

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

> Reglas comprobables que se derivan de las decisiones: capas, dirección de
> dependencias entre componentes, dependencias prohibidas. Cada estándar cita
> la decisión de la que sale.
>
> Sustituye todo texto en cursiva. Solo el usuario cambia el Estado, con
> `/architecture:approve`.

## Estándares

### S1 — _regla en una línea_

- **Tipo:** _capas, dependencia o prohibida_
- **Detalle:** _dependencia: C2 → C1 (C2 depende de C1); prohibida: C1 → C2 (C1 no puede depender de C2), un par por flecha; capas: la lista en orden_
- **Decisión:** _ADR-0001_
