# architecture — de producto aprobado a arquitectura

Decide de qué está hecho el sistema antes de su primera feature: **atributos de
calidad** medibles, **componentes** con las candidatas que alojan,
**decisiones de arquitectura** (ADR) y **estándares** comprobables. Parte del
producto que aprueba `discovery` y deja en `architecture/` las decisiones que
afectan a todo el producto, para que no acaben enterradas en el `plan.md` de la
primera feature que las necesitó.

Es la segunda etapa de la serie `discovery` → `architecture` → `sdd` → …, y
solo se usa en productos nuevos: no reconstruye la arquitectura a partir de
código existente.

## La regla de frontera

> Una decisión va a arquitectura si **afecta a más de una feature o es cara de
> revertir**. Si no, va al `plan.md` de la feature.

Stack, persistencia, despliegue, integración entre componentes o autenticación
van aquí. Una librería que usa una sola feature va a su plan.

## Uso

```
/architecture:init       # tras /discovery:approve: atributos de calidad y componentes
/architecture:decide     # decisiones (ADR) y estándares; lo que no decides queda como pregunta
/architecture:diagram    # vistas C4 (contexto, contenedores, componentes) en Mermaid
/architecture:check      # coherencia; también en CI
/architecture:approve    # tú apruebas el conjunto
/architecture:review ADR-0004 aceptar|rechazar   # tú decides una decisión propuesta
```

`init`, `decide`, `diagram`, `approve` y `review` los lanza el usuario
(`disable-model-invocation`). `check` lo puede lanzar también el modelo, porque
solo lee; en `discovery` no es así, pero aquí el plan lo decidió de este modo.
Por debajo usan `scripts/architecture.py`, que también se puede llamar a mano:

| Subcomando | Qué hace | Salida |
| ---------- | -------- | ------ |
| `init` | Crea `architecture/` desde las plantillas si el producto está aprobado; no sobrescribe | 0, o 1 si se niega |
| `diagram` | Crea `architecture/diagrams.md` con el esqueleto de las tres vistas; no sobrescribe | 0, o 1 sin componentes |
| `next-id Q\|C\|S\|ADR` | Siguiente atributo, componente, estándar o decisión libre; nunca recicla | 0; 2 con un tipo desconocido |
| `check [--json] [--check]` | Coherencia de la arquitectura | 0; 1 con `--check` y errores; 2 con un argumento desconocido |
| `approve [--skill]` | Aprueba el conjunto | 0, o 1 si se niega; con `--skill`, siempre 0 |
| `review ADR-NNNN aceptar\|rechazar [--skill]` | Decide una decisión propuesta | 0, o 1 si se niega; 2 con argumentos inválidos; con `--skill`, siempre 0 |
| `guard`, `audit` | Hooks que protegen la aprobación (leen JSON por stdin) | — |

## Artefactos

```
architecture/
├── quality.md       Q1… atributos de calidad: escenario medible y motivo
├── components.md    C1… componentes: responsabilidad y candidatas; fila Producto
├── standards.md     S1… estándares: tipo (capas, dependencia, prohibida), detalle, decisión
├── questions.md     preguntas abiertas: - [ ] (ADR-0002; Q1) ¿…?
├── diagrams.md      opcional: vistas C4 de contexto, contenedores y componentes
└── adr/
    └── 0001-slug.md una decisión: Motivo, Sustituye; Contexto, Decisión,
                     Alternativas descartadas, Consecuencias
```

Todos llevan `| Estado | … |` en la cabecera y el patrón `- **Campo:** valor`,
igual que el resto de la serie.

- **Motivo.** Un atributo o una decisión citan lo que los justifica: un objetivo
  del brief (`G2`), la sección de origen de una de sus restricciones (`D1§5`,
  la que va entre paréntesis en la viñeta) o, en un ADR, un atributo (`Q1`).
- **Estándares en Markdown, no en YAML.** El documento de diseño de la serie
  hablaba de `standards.yaml`, pero los plugins solo usan la biblioteca
  estándar de Python, que no trae parser de YAML.
- **Estados de un ADR.** `Draft`, `Proposed`, `Approved · <huella>`,
  `Rejected` y `Superseded by ADR-NNNN`. Un ADR rechazado o sustituido queda
  como historia: no se comprueba su forma ni sus citas.

## Comprobación

`check` da hallazgos con código estable. Los `E-` hacen fallar `--check` en CI;
los `W-` informan.

| Código | Qué |
| ------ | --- |
| `E-QUALITY-NOT-MEASURABLE` | el escenario no tiene ninguna cifra (los números de una cita, como `G1`, no cuentan) |
| `E-QUALITY-NO-MOTIVE` | el atributo no cita un objetivo del brief ni la sección de una restricción |
| `E-COMPONENT-NO-RESPONSIBILITY` | componente sin responsabilidad |
| `E-COMPONENT-CANDIDATE-UNPLACED` | candidata vigente del backlog que no vive en ningún componente |
| `E-ADR-INCOMPLETE` | falta contexto, decisión, alternativas o consecuencias |
| `E-ADR-NO-MOTIVE` | la decisión no cita atributo, objetivo ni restricción |
| `E-ADR-ID-DUPLICATE` | dos archivos con el mismo número |
| `E-STANDARD-NO-ADR` | estándar sin la decisión de la que se deriva |
| `E-ARCH-REF-UNKNOWN` | cita a una decisión, atributo, componente, objetivo o candidata que no existe |
| `E-ARCH-OPEN-QUESTION` | pregunta abierta sobre una decisión o un atributo: impide aprobar |
| `E-ARCH-TEMPLATE` | hueco de plantilla sin rellenar |
| `W-ARCH-NOT-APPROVED` | artefacto sin aprobar o cambiado después de aprobarse |
| `W-ARCH-PRODUCT-CHANGED` | el brief o el backlog cambiaron desde que se aprobó la arquitectura |
| `E-ARCH-DIAGRAM-UNKNOWN` | un diagrama dibuja un componente que no existe |
| `E-ARCH-DIAGRAM-MISSING` | a la vista de contenedores o de componentes le falta un componente, o falta una vista |
| `E-ARCH-DIAGRAM-VIOLATION` | un diagrama dibuja una dependencia que un estándar prohíbe o declara al revés |
| `W-ARCH-NO-DIAGRAMS` | no hay `diagrams.md`; no impide aprobar |

Las citas a candidatas, componentes y estándares se comprueban en los campos
(Candidatas, Detalle, Decisión, Motivo, Sustituye) y en el paréntesis de las
preguntas. En el cuerpo de un ADR solo se buscan citas `ADR-NNNN`: una «S3» o
una «C2» en prosa pueden no ser una cita.

`--json` emite el schema `architecture.check/v1`:
`{schema, ok, counts, findings: [{code, severity, message, artifact}]}`.

En CI del repositorio de producto:

```yaml
- run: python3 path/to/plugins/architecture/scripts/architecture.py check --check
```

## Diagramas

`/architecture:diagram` deja en `architecture/diagrams.md` tres vistas del
modelo C4 en Mermaid, que GitHub y los editores muestran dibujadas: **Contexto**
(usuarios, sistema y sistemas externos), **Contenedores** (cada componente,
con su tecnología) y **Componentes** (las dependencias entre ellos, con su
ADR). La cuarta vista, código, no se dibuja.

- **Esqueleto.** `architecture.py diagram` lo genera sin el modelo: un nodo
  `U<n>` por viñeta de primer nivel de `## Usuarios` del brief, cada
  componente con su ID (`C1`), nombre y responsabilidad, y una arista por cada
  estándar `dependencia` (`C2 -->|usa · ADR-0001| C1`). Deja dos huecos por
  vista: el nombre del sistema y una línea `%%` que pide sistemas externos y
  tecnologías. Si el archivo ya existe, no lo toca.
- **Completar.** La skill añade los sistemas externos (`X<Nombre>`) y las
  tecnologías a partir de los ADR y del brief, y borra los huecos; mientras
  queden, `E-ARCH-TEMPLATE` impide aprobar.
- **Convenciones.** `flowchart LR` (no la sintaxis C4 experimental de
  Mermaid), frontera `subgraph SYS`, clases `persona`, `sistema`,
  `contenedor` y `externo`, comillas como `#quot;`.
- **Comprobación.** `check` lee los nodos y las aristas (`-->`, `-->|x|`,
  `-- x -->`, `-.->`, `-. x .->`) de cada vista, reconocida por su encabezado,
  y los contrasta con `components.md` y con los estándares `dependencia` y
  `prohibida` (`Detalle: C1 → C3`). No comprueba las capas, los sistemas
  externos ni las tecnologías, ni valida la sintaxis Mermaid completa.
- **Límites.** Un `subgraph C3` cuenta como C3 dibujado, y una etiqueta en
  cursiva (`_así_`) se toma por un hueco.

`sdd` no lee los diagramas: los de cada feature son otra feature.

## Aprobación y revisión

`/architecture:approve` sella con `Approved · <huella>` el conjunto:
`quality.md`, `components.md`, `standards.md`, `questions.md`,
`diagrams.md` si existe, y cada ADR en `Draft` o que cambió tras aprobarse.
Sin `diagrams.md` la aprobación sigue adelante, con el aviso
`W-ARCH-NO-DIAGRAMS`; con él, editarlo tras aprobar da `W-ARCH-NOT-APPROVED`
como con el resto, y el guardrail impide que el modelo lo apruebe.

La aprobación se niega, sin cambiar nada, en estos casos:

- el producto de `discovery` no está aprobado o cambió;
- falta algún artefacto, o alguno no tiene la fila `| Estado |` en su cabecera;
- la comprobación da errores, incluida una pregunta abierta que bloquea.

Al aprobar, `components.md` guarda la huella del brief y del backlog en la fila
`Producto`. Si el producto cambia después, `check` lo avisa
(`W-ARCH-PRODUCT-CHANGED`). La huella excluye la fila Estado y normaliza
espacios, así que reformatear un artefacto no lo invalida y editarlo sí.

Las decisiones `Proposed`, por ejemplo una nueva tras la aprobación, se deciden
una a una con `/architecture:review ADR-NNNN aceptar|rechazar`:

- **Aceptar:** exige que el ADR no tenga errores propios y lo sella. Si su
  campo `Sustituye` cita otro ADR, ese tiene que estar aprobado y pasa a
  `Superseded by ADR-NNNN`.
- **Rechazar:** lo deja en `Rejected` con su número, que no se reutiliza.

## Guardrails

Aprobar, rechazar o sustituir es del usuario:

- Un hook `PreToolUse` sobre Write, Edit y Bash deniega cualquier escritura que
  lleve un artefacto o un ADR a `Approved`, `Rejected` o `Superseded`, o que
  reescriba una huella. También deniega cualquier comando que **ejecute**
  `architecture.py approve` o `review`: directamente, encadenado o dentro de
  una sustitución `$(…)` o con comillas invertidas. Mencionarlo (un commit, un
  PR, un heredoc) no bloquea. El modelo sí puede dejar una decisión en `Draft`
  o en `Proposed`. Nunca devuelve `allow`.
- Un hook `PostToolUse` sobre Bash revierte, con un aviso, lo que un comando
  opaco (`bash -c`, un script) haya llevado a uno de esos estados.
- Sin `architecture/`, los hooks no hacen nada. Un error inesperado de un hook
  deja pasar.

Escape: `ARCHITECTURE_BYPASS=1`.

Límites conocidos:

- Un `\$(…)` escapado fuera de comillas dobles, o una mención sin comillas
  (`echo python3 architecture.py approve`), se bloquea aunque no se ejecute:
  peca de prudente.
- Una edición múltiple (`MultiEdit`) no se analiza; solo Write, Edit y Bash.

## Relación con los demás plugins

`architecture` no importa código de `discovery` ni de `sdd`, y funciona sin
ellos instalados a partir de los archivos de `product/`. Lo que necesita de
otros plugins lo lleva copiado y documentado:

- **El formato y la huella del producto de `discovery`** (aprobación,
  objetivos, restricciones, candidatas). Lo comparte con
  `plugins/sdd/scripts/sdd_product.py`. Una prueba de contrato del selftest
  aprueba un producto con el `discovery.py` real y comprueba que coinciden.
- **El analizador de comandos de los guardrails**, copia del de `discovery`, que
  a su vez copia el de `plugins/sdd/scripts/sdd_bash.py`. Las tres copias se
  nombran entre sí, y sus selftests usan listas de casos equivalentes.

La integración con `sdd` (que `/sdd:plan` lea y compruebe la arquitectura, y
proponga decisiones nuevas) es una feature posterior. Mientras tanto, `sdd`
funciona igual con o sin `architecture/`.

## Pruebas

```bash
python3 plugins/architecture/tests/selftest.py
```

Cada prueba cita el requisito de la feature de este repositorio que comprueba
(`test_F006_R0NN_…`, `test_F008_R0NN_…` para los diagramas). El selftest
falla si un código de hallazgo declarado no se prueba.
