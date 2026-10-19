# Plan: diagramas C4 en architecture: contexto, contenedores y componentes desde la arquitectura aprobada

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-19         |
| Estado | Approved · 1eda2a2a3808              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

Un artefacto nuevo y opcional del plugin `architecture`,
`architecture/diagrams.md`, con tres diagramas Mermaid (contexto, contenedores y
componentes):

- `architecture.py diagram` genera su esqueleto de forma determinista a partir
  del brief, `components.md` y `standards.md`.
- Una skill nueva, `/architecture:diagram`, lo completa con actores, sistemas
  externos y tecnologías.
- `check` comprueba los nodos y las dependencias contra lo aprobado.
- La aprobación del conjunto lo sella cuando existe.

Los diagramas usan `flowchart` de Mermaid con convenciones C4 y no la sintaxis C4
de Mermaid, que es experimental. Los nodos de componente se llaman como su ID
(`C1`), lo que hace la comprobación determinista.

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Lo determinista vive en un script | sí | esqueleto, lectura de nodos y aristas, comprobaciones y sellado en `architecture.py`; la skill solo completa lo que requiere criterio (actores, sistemas externos, tecnologías) |
| Python 3.8, solo biblioteca estándar | sí | Mermaid es texto: se genera y se analiza con `re`. Para verlo no hace falta instalar nada (lo dibujan GitHub y los editores) |
| Plugins unidos solo por archivos | sí | cambia solo `architecture`; `sdd` no se toca (non-goal) y su lectura de la arquitectura sigue igual (D5) |
| Cambiar el formato que lee otro plugin requiere aprobación | sí | `diagrams.md` es nuevo y ningún otro plugin lo lee; el resto de formatos no cambia |
| Solo el usuario aprueba; guardrail con escape | sí | `diagrams.md` entra en los archivos que protegen `guard` y `audit`, con el mismo escape `ARCHITECTURE_BYPASS=1` |
| Códigos como contrato y prefijos reservados | sí | cuatro códigos nuevos con `*-ARCH-*`, que ya es de `architecture` («la arquitectura en conjunto»); no hace falta tocar el registro |
| El selftest cubre cada cambio y todo código es alcanzable | sí | pruebas `test_F008_RNNN_…` y cobertura de los cuatro códigos |

## Decisiones

### D1 — `architecture/diagrams.md`: un artefacto opcional del conjunto

- **Contexto:** R008 pide que los diagramas se aprueben con la arquitectura. R009
  pide que una arquitectura sin ellos se siga pudiendo aprobar.
- **Decisión:**
  - Un archivo con la cabecera de siempre (`| Estado | … |`) y tres secciones
    `## Contexto`, `## Contenedores` y `## Componentes`, cada una con un bloque
    ```` ```mermaid ````.
  - No entra en la tupla `SET_FILES`, que exige los cuatro artefactos de hoy:
    se trata aparte, como opcional.
  - Si existe, `approve` lo sella y `check_approval` avisa si está sin aprobar o
    cambió (R008). Si no existe, `check` da `W-ARCH-NO-DIAGRAMS` y `approve` no
    se niega por ello (R009).
- **Alternativas descartadas:**
  - *Añadirlo a `SET_FILES`.* Toda arquitectura aprobada antes de esta feature
    dejaría de poder aprobarse (contra R009), y la copia de `sdd` lo trataría
    distinto sin poder tocarla.
  - *Un archivo por vista.* Tres huellas para un mismo dibujo del sistema, y
    tres archivos que revisar juntos.
- **Consecuencias:** `sdd` no tiene en cuenta los diagramas al decidir si la
  arquitectura está aprobada (D5).

### D2 — `flowchart` de Mermaid con convenciones C4, no la sintaxis C4 de Mermaid

- **Contexto:** el usuario eligió Mermaid. Su sintaxis C4 (`C4Context`,
  `Container(…)`) es experimental, maqueta mal y su forma de nodos y relaciones
  es más difícil de analizar.
- **Decisión:** las tres vistas son `flowchart LR` con estas convenciones:

  | Elemento | ID del nodo | Etiqueta | Estilo |
  | -------- | ----------- | -------- | ------ |
  | Tipo de usuario | `U1`, `U2`… | nombre y `[Persona]` | clase `persona` |
  | El sistema (vista de contexto) | `SYS` | nombre y `[Sistema]` | clase `sistema` |
  | Componente o contenedor | el ID de `components.md` (`C1`) | nombre, `[Contenedor]` o `[Componente]` y responsabilidad | clase `contenedor` |
  | Sistema externo | `X` + nombre (`XPagos`) | nombre y `[Sistema externo]` | clase `externo` |

  - La frontera del sistema es un `subgraph SYS` en las vistas de contenedores y
    componentes.
  - Las relaciones son aristas `A -->|etiqueta| B`. Las que salen de un
    estándar llevan el ADR en la etiqueta (`usa · ADR-0001`).
  - Se definen `classDef` para que las cajas se distingan como en C4.
- **Alternativas descartadas:**
  - *Sintaxis C4 de Mermaid.* La razón está en el contexto. Si algún día deja de
    ser experimental, cambiar de sintaxis solo afecta al generador y al lector.
  - *Identificar componentes por su nombre.* Un cambio de nombre rompería la
    comprobación; el ID es estable.
- **Consecuencias:** la comprobación solo mira nodos `C\d+` y aristas entre
  ellos. Lo demás (personas, sistemas externos, etiquetas) es libre para el
  modelo.

### D3 — `architecture.py diagram`: el esqueleto

- **Contexto:** R001–R004.
- **Decisión:**
  - Si existe `diagrams.md`, no lo toca: indica que ya existía y sale con 0
    (R004).
  - Si no hay componentes, se niega con salida 1 y remite a
    `/architecture:init`.
  - Si no se niega, escribe el archivo en `Draft`:
    - **Contexto:** un nodo `U<n>` por viñeta de `## Usuarios` del brief, el
      nodo `SYS` y una arista de cada usuario al sistema.
    - **Contenedores:** `subgraph SYS` con cada componente (nombre y
      responsabilidad) y los usuarios fuera.
    - **Componentes:** cada componente y una arista por cada estándar de tipo
      `dependencia` (`C2 → C1`), etiquetada con la decisión del estándar
      (R003).
    - En las tres vistas, dos huecos en cursiva: el nombre del sistema, y una
      línea `%%` que pide añadir los sistemas externos y la tecnología de cada
      contenedor. `E-ARCH-TEMPLATE` los señala hasta que el modelo los
      complete, así que un esqueleto sin completar no se puede aprobar.
- **Alternativas descartadas:**
  - *Regenerar y fusionar con lo completado.* Fuera de alcance; `diagram` es
    idempotente.
- **Consecuencias:** para rehacer el esqueleto se borra el archivo y se vuelve a
  ejecutar `diagram`, y se pierde lo completado. Lo dice la skill.

### D4 — Comprobaciones nuevas en `check`

- **Decisión:** se leen los nodos (`ID[…]`, `ID(…)`, `ID{…}` o el ID suelto en
  una arista) y las aristas (`A --> B`, `A -->|x| B`, `A -- x --> B`,
  `A -.-> B`) de cada bloque Mermaid de `diagrams.md`.

  | Código | Requisito | Qué |
  | ------ | --------- | --- |
  | `E-ARCH-DIAGRAM-UNKNOWN` | R005 | un nodo `C\d+` que no es un componente de `components.md` |
  | `E-ARCH-DIAGRAM-MISSING` | R006 | un componente que falta en la vista de contenedores o en la de componentes; el mensaje nombra la vista |
  | `E-ARCH-DIAGRAM-VIOLATION` | R007 | una arista `Ca → Cb` en sentido contrario a un estándar `dependencia` `Cb → Ca`, o que coincide con un par de un estándar `prohibida` (`Detalle: C1 → C3`); el mensaje nombra el estándar |
  | `W-ARCH-NO-DIAGRAMS` | R009 | no existe `diagrams.md` |

  - Las vistas se reconocen por su encabezado de sección.
  - Si falta una vista, también es `E-ARCH-DIAGRAM-MISSING`, que nombra la
    vista y no un componente.
  - Las capas (`Tipo: capas`) no se comprueban contra los diagramas: la spec no
    lo pide.
- **Alternativas descartadas:**
  - *Validar la sintaxis Mermaid completa.* Necesitaría el propio Mermaid. Solo
    se analiza lo que la comprobación necesita, y un diagrama mal escrito se ve
    al abrirlo.
- **Consecuencias:** cuatro códigos nuevos, que pasan a ser contrato.

### D5 — Aprobación, guardrails y `sdd`

- **Decisión:**
  - **`approve`:** sella `diagrams.md` si existe, igual que el resto del
    conjunto.
  - **`check_approval`:** lo incluye.
  - **`guarded_files` y `_guarded_target`:** lo incluyen, así que `guard`
    deniega aprobarlo y `audit` lo revierte (R010).
  - **`sdd_architecture.py` no cambia (non-goal):** `sdd` sigue considerando
    aprobada una arquitectura cuyos diagramas cambiaron. Es aceptable porque los
    diagramas explican decisiones, no las toman: los componentes, los ADR y los
    estándares, que sí lee `sdd`, siguen exigiendo aprobación.
- **Alternativas descartadas:**
  - *Actualizar la copia de `sdd`.* Toca otro plugin, fuera de alcance. La
    feature 009 lo puede reconsiderar.

### D6 — Skill `/architecture:diagram`

- **Decisión:** la lanza el usuario (`disable-model-invocation`). Hace esto:
  1. ejecuta `diagram`;
  2. completa las tres vistas con los sistemas externos y la tecnología de cada
     contenedor, sacados de los ADR y el brief, con la decisión de la que sale
     cada uno en la etiqueta;
  3. rellena el nombre del sistema y quita la línea de huecos;
  4. mantiene los IDs `C\d+` y no inventa componentes;
  5. ejecuta `check`.

  Las skills `check` (tabla de códigos) e `init` (último paso, que recomienda
  `/architecture:diagram`) se actualizan.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/architecture/scripts/architecture.py` · `diagram` (nuevo) | esqueleto determinista (D3) | R001, R002, R003, R004 |
| `plugins/architecture/scripts/architecture.py` · lectura de Mermaid y `check` | nodos, aristas y cuatro códigos (D4) | R005, R006, R007, R009 |
| `plugins/architecture/scripts/architecture.py` · `approve`, `check_approval`, `guard`, `audit` | `diagrams.md` en el conjunto y en los guardrails (D1, D5) | R008, R010 |
| `plugins/architecture/skills/diagram/SKILL.md` (nueva), `skills/check`, `skills/init` | D6 | R001, R002 |
| `plugins/architecture/tests/selftest.py` | pruebas `test_F008_RNNN_…` y cobertura | R001–R010 |
| `plugins/architecture/README.md` | la sección de diagramas | R001, R008 |

## Modelo de datos

`architecture/diagrams.md`: la cabecera con Estado y tres secciones (`Contexto`,
`Contenedores` y `Componentes`), cada una con un bloque Mermaid `flowchart` según
las convenciones de D2.

## Contratos

- `architecture.py diagram`: exit 0 al crear el archivo, o si ya existía
  (indicando que ya existía); exit 1 sin componentes.
- `architecture.check/v1` gana cuatro códigos, de forma aditiva.

## Estrategia de pruebas

Todas viven en `plugins/architecture/tests/selftest.py`.

| Requisito | Tipo de prueba | Qué cubre |
| --------- | -------------- | --------- |
| R001 | integración | `diagram` crea las tres secciones con un bloque Mermaid cada una |
| R002 | integración | los usuarios del brief en el contexto; C1 y C2 con su nombre en contenedores y componentes |
| R003 | integración | arista `C2 --> C1` con `ADR-0001` en la vista de componentes |
| R004 | integración | segundo `diagram` sobre un archivo completado: no cambia y lo indica |
| R005 | integración | nodo C7 inexistente |
| R006 | integración | contenedores sin C2; vista que falta |
| R007 | integración | arista C1 → C2 contra «C2 → C1»; par prohibido C1 → C3 |
| R008 | integración | aprobar con diagramas coherentes los sella; editar tras aprobar avisa |
| R009 | integración | sin `diagrams.md`: aviso y aprobación sin negarse |
| R010 | integración | `guard` deniega un Write o Edit que aprueba `diagrams.md`; `audit` lo revierte |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| El modelo escribe Mermaid inválido | El diagrama no se dibuja, aunque `check` pase | La skill da ejemplos exactos de la sintaxis. Un error se ve al abrir el archivo en GitHub o el editor |
| El modelo cambia los IDs `C\d+` por nombres | Falsos «falta componente» | El mensaje dice que los nodos de componente se llaman por su ID |
| La lectura de aristas no cubre una forma rara de Mermaid | Una dependencia prohibida no se detecta | Se cubren las formas que genera el esqueleto y que pide la skill; el resto se documenta como límite |

## Trazabilidad

Los diez requisitos MUST (R001–R010) aparecen en la tabla de componentes y en la
de pruebas.
