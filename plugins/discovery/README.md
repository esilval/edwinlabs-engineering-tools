# discovery — de documento de producto a backlog de features

Etapa previa a `sdd`. Convierte los documentos de un producto en un **brief**
(objetivos, usuarios, glosario, restricciones) y un **backlog** de features
candidatas, con trazabilidad documento → objetivo → candidata. No redacta
requisitos: eso lo hace `/sdd:specify` cuando una feature arranca.

Un producto, grande o pequeño, tiene un solo brief y un solo backlog, y crece
con documentos que llegan a lo largo del tiempo.

## Uso

```
/discovery:ingest <documento>   # añade un documento como D1, D2…
/discovery:clarify              # huecos, contradicciones y supuestos → preguntas
/discovery:decompose            # objetivos y candidatas, cada uno con su origen
/discovery:check                # coherencia del producto
/discovery:approve              # tú apruebas brief y backlog
```

Todas las skills las lanza el usuario (`disable-model-invocation`).

## Artefactos

```
product/
├── sources/D1-vision.md      un archivo por documento ingerido; no se edita
├── brief.md                  objetivos G1…, usuarios, glosario, restricciones,
│                             invariantes propuestos, descartes, preguntas
└── backlog.md                candidatas B01…
```

- **Documentos.** Markdown entra tal cual; Word (`.docx`) se convierte con la
  biblioteca estándar; un PDF lo convierte el modelo y se ingiere con
  `--original`. Los encabezados se numeran (`## 4.2 Pagos recurrentes`) para
  citarlos como `D2§4.2`. Un único H1 es el título y no se numera. Un documento
  idéntico a uno ya ingerido se rechaza.
- **Brief y backlog.** Markdown con campos legibles por el script:
  `### G1 — título` y `### B03 — título` con viñetas `- **Origen:** D1§4.2`.
  Una candidata nunca se borra: se descarta (`**Estado:** descartada`).
- **Preguntas.** En el brief: `- [ ] (D1§2; G1) ¿…?`; al responder, `[x]` y
  `- **Respuesta:** …` debajo.

## Comprobación

```bash
discovery.py check           # informe legible, siempre exit 0
discovery.py check --json    # contrato estable para CI (schema discovery.check/v1)
discovery.py check --check   # exit 1 si hay algún error
```

| Código | Detecta |
| ------ | ------- |
| `E-GOAL-NO-FEATURE` | Objetivo que no persigue ninguna candidata viva |
| `E-SOURCE-UNCOVERED` | Sección sin objetivo, candidata ni descarte explícito |
| `E-REF-UNKNOWN` | Cita a un documento, sección, objetivo o candidata inexistentes |
| `E-BACKLOG-DEP-CYCLE` | Dependencias circulares entre candidatas |
| `E-SOURCE-MODIFIED` | Documento editado después de ingerirse |
| `E-BACKLOG-ID-GAP` | Hueco o ID repetido: algo se borró en vez de descartarse |
| `E-BACKLOG-REQUIREMENT` | Objetivo o candidata redactado como requisito («DEBERÁ») |
| `E-QUESTION-OPEN-GOAL` | Pregunta abierta que afecta a un objetivo |
| `E-PRODUCT-TEMPLATE` | Huecos de plantilla sin rellenar |
| `W-FEATURE-NO-GOAL` | Candidata que no persigue ningún objetivo |
| `W-FEATURE-NO-OUTCOME` | Candidata sin resultado observable |
| `W-QUESTION-OPEN` | Preguntas abiertas que no afectan a ningún objetivo |
| `W-PRODUCT-NOT-APPROVED` | Brief o backlog sin aprobar, o cambiados tras aprobarse |

Los códigos son contrato público: añadir es aditivo; renombrar, quitar o
cambiar la forma de un campo exige `discovery.check/v2`. Una sección cuenta como
cubierta si se cita ella, una que la contiene o una contenida en ella, desde el
Origen de un objetivo o de una candidata viva, o desde los descartes.

## Aprobación

`/discovery:approve` sella `brief.md` y `backlog.md` con
`| Estado | Approved · <huella> |`, solo si `check` no da errores. La skill
ejecuta el script por inyección `` !`…` ``, fuera de la herramienta Bash.

- Un hook `PreToolUse` sobre `Write|Edit|Bash` deniega cualquier escritura que
  apruebe el brief o el backlog, y cualquier comando que llame a
  `discovery.py approve`. Nunca devuelve `allow`.
- Un hook `PostToolUse` sobre Bash restaura el Estado si un comando opaco lo
  cambió.
- Si el brief o el backlog cambian después de aprobarse, dejan de estar
  aprobados (`W-PRODUCT-NOT-APPROVED`). Reformatear no cuenta como cambio.
- Sin `product/`, los hooks no hacen nada. Escape: `DISCOVERY_BYPASS=1`.

Límites conocidos:

- El guard deniega cualquier comando que **mencione** `discovery.py approve`,
  también un `grep` que lo busque. Es el mismo criterio que usa `sdd`; el
  mensaje documenta el escape.
- Si `product/` no existe todavía, un comando que lo cree con el brief ya
  aprobado no pasa por la auditoría: los hooks no actúan sin `product/`.
- Una edición múltiple (`MultiEdit`) no se analiza; solo `Write`, `Edit` y Bash.

## Relación con los demás plugins

- No lee ni escribe `specs/`: se une a `sdd` solo por archivos.
- Los invariantes del brief son propuestas para la constitución, que solo cambia
  el usuario con `/sdd:constitution`.
- El paso de una candidata a `sdd` (handoff) es una feature aparte.

## Pruebas

```bash
python3 plugins/discovery/tests/selftest.py
```

Cada prueba es `test_F001_Rxxx_*` y cita el requisito de la feature
`specs/001-discovery-documento-producto-backlog-features` al que sirve. El
selftest falla si un código de hallazgo declarado no se prueba.
