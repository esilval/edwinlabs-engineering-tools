# Plan: discovery: de documento de producto a backlog de features

| Campo  | Valor              |
| ------ | ------------------ |
| Spec   | `spec.md`          |
| Fecha  | 2026-10-15         |
| Estado | Approved · ab35ab9b5f63              |

> Este documento describe **cómo**. Si aquí aparece un requisito nuevo que no
> está en `spec.md`, el sitio correcto es `spec.md`, no aquí.
>
> Sustituye todo texto en cursiva; si una sección no aplica, escribe
> «No aplica.». Solo el usuario cambia el Estado, con `/sdd:approve`.

## Resumen

Un plugin nuevo, `plugins/discovery/`, con la misma anatomía que `sdd`: cinco
skills que hacen el trabajo de criterio y un script, `discovery.py`, que hace
todo lo determinista (identificadores, numeración de secciones, huellas,
comprobación y aprobación). La decisión clave es que la estructura del producto
viva en Markdown con campos parseables, como `tasks.md`, para que la misma
fuente sirva a la persona que lee y al script que comprueba.

## Comprobación de constitución

| Regla | ¿Se cumple? | Cómo, o excepción justificada |
| ----- | ----------- | ----------------------------- |
| Lo determinista en un script | sí | IDs, numeración, huellas, comprobación y aprobación en `discovery.py`; las skills solo redactan y preguntan (D2) |
| Plugins unidos solo por archivos | sí | No importa código de `sdd`; duplica a propósito los ~40 líneas de huella y estado (D7) |
| Cada plugin funciona sin los demás | sí | Ningún comando lee `specs/` ni requiere `sdd` instalado |
| Guardrail que falla abierto y con escape | sí | Los hooks dejan pasar ante cualquier error; escape `DISCOVERY_BYPASS=1` (D6) |
| Ningún hook devuelve `allow` | sí | El guard solo deniega o calla; el selftest lo comprueba |
| Solo el usuario aprueba | sí | `/discovery:approve` con `disable-model-invocation` e inyección `` !`…` ``, más guard y auditoría como en `sdd` (D6) |
| Python 3.8, solo biblioteca estándar | sí, con un límite | Word se convierte con `zipfile` y `xml`; PDF no tiene conversión fiable sin dependencias, así que lo convierte el modelo (D4) |
| Selftest por plugin en CI | sí | `plugins/discovery/tests/selftest.py`; el workflow pasa a recorrer `plugins/*/tests/selftest.py` |
| Todo código de hallazgo alcanzable | sí | El selftest compara los declarados con los probados, como en `sdd` |
| Prefijos de hallazgo reservados antes de usarlos | sí | Se reservan en `plugins/sdd/docs/standards-roadmap.md` §7 (D8) |
| Hooks en forma exec con `timeout` | sí | Igual que `sdd` |
| Español en docs y commits con prefijo | sí | Commits `discovery: …` |

## Decisiones

### D1 — Un plugin con la anatomía de `sdd`

- **Contexto:** la constitución fija la estructura de un plugin y pide que sea
  independiente.
- **Decisión:** `plugins/discovery/` con `.claude-plugin/plugin.json`, cinco
  skills (`ingest`, `clarify`, `decompose`, `check`, `approve`), `hooks/`,
  `scripts/discovery.py`, `templates/`, `tests/selftest.py`, `README.md`.
  Entrada nueva en `marketplace.json`. Todas las skills llevan
  `disable-model-invocation: true`: o producen artefactos o abren una
  aprobación.
- **Alternativas descartadas:** fases nuevas dentro de `sdd` (descartado por el
  usuario, D5 del diseño); una sola skill con subcomandos, porque mezcla en un
  prompt fases con criterios distintos.
- **Consecuencias:** cinco descripciones de skill más en el contexto de cada
  sesión.

### D2 — Reparto entre skills y script

- **Contexto:** la spec mezcla trabajo de criterio (detectar huecos, proponer
  candidatas) con reglas verificables (IDs, referencias, ciclos).
- **Decisión:**

  | Comando | Lo hace el script | Lo hace el modelo |
  | ------- | ----------------- | ----------------- |
  | `ingest` | formato admitido, duplicado, ID `Dn`, numeración, huella, cabecera | convertir PDF a Markdown (D4) |
  | `clarify` | listar preguntas abiertas y validar sus citas | encontrar huecos, preguntar, registrar respuestas |
  | `decompose` | `next-id G` y `next-id B` | redactar objetivos, glosario, candidatas |
  | `check` | todo | nada |
  | `approve` | todo, lanzado por el usuario | mostrar el resultado |

- **Alternativas descartadas:** que el modelo asigne IDs al redactar; es justo
  donde estos flujos se degradan (principio 1 de la constitución).
- **Consecuencias:** `decompose` es la fase menos determinista; `check` es la
  red que la valida.

### D3 — Artefactos del producto

- **Contexto:** R001, R005–R007 piden documentos citables, un brief y un
  backlog.
- **Decisión:**

  ```
  product/
  ├── sources/D1-vision.md, D2-pagos.md…   un archivo por documento ingerido
  ├── brief.md                             objetivos, usuarios, glosario, restricciones,
  │                                         invariantes propuestos, preguntas, descartes
  └── backlog.md                           candidatas B01…
  ```

  - Cada `sources/Dn-slug.md` lleva cabecera con `Documento: Dn`, `Original:`
    (nombre del archivo), `Ingesta:` (fecha), `Huella original:` y
    `Huella:` (del Markdown almacenado).
  - Ingest **reescribe los encabezados con su número** (`## 4.2 Pagos
    recurrentes`), así la cita `D2§4.2` es visible al leer. Si el documento
    tiene un único H1, es el título y no se numera; sin encabezados, todo el
    cuerpo es `§1` (supuesto de la spec).
  - Formato de campos parseables, como `tasks.md`: `### G1 — título` y
    `### B03 — título` con viñetas `- **Origen:** D1§4.2, D2§7`.
  - Preguntas en el brief: `- [ ] (D1§2; G2) ¿…?`, con
    `- **Respuesta:** …` debajo; al responder, `[x]`.
  - Secciones descartadas en el brief: `- D1§7 — motivo`.
- **Alternativas descartadas:** numerar al leer, sin reescribir el documento
  (las citas no se ven al leerlo); YAML o JSON para brief y backlog (peor para
  revisar en un PR, y rompe la simetría con `sdd`).
- **Consecuencias:** el Markdown almacenado ya no es idéntico al original; por
  eso hay dos huellas (D5).

### D4 — PDF y Word (R003, R004)

- **Contexto:** la constitución prohíbe dependencias externas.
- **Decisión:** `ingest` acepta `.md`, `.markdown`, `.docx` y `.pdf`; rechaza
  cualquier otra extensión sin tocar el producto. Word se convierte con la
  biblioteca estándar (el `.docx` es un zip con XML; los estilos de título dan
  los encabezados). PDF lo convierte el modelo: lee el PDF, escribe el
  Markdown en un archivo temporal y llama a
  `discovery.py ingest <md> --original <pdf>`; el script registra el nombre y la
  huella del PDF. El original no se versiona (propuesta de la pregunta abierta
  de R004; si el usuario decide lo contrario, solo cambia este punto).
- **Alternativas descartadas:** una librería de PDF (viola la constitución);
  rechazar PDF (contradice la decisión del usuario).
- **Consecuencias:** la conversión de PDF no es reproducible byte a byte. Es
  aceptable porque R004 es SHOULD y lo que se revisa y aprueba es el Markdown.

### D5 — Huellas: duplicados, edición y aprobación (R002, R011, R016)

- **Contexto:** tres requisitos dependen de saber si un contenido cambió.
- **Decisión:** huella = SHA-1 truncada del contenido normalizado (sin espacios
  sobrantes ni líneas en blanco), la misma regla que `sdd`.
  - **R002:** `Huella original` se compara con las de todos los documentos.
  - **R011:** `Huella` del Markdown almacenado, recalculada en cada `check`.
  - **R016:** al aprobar, `| Estado | Approved · <huella> |` en la cabecera de
    `brief.md` y de `backlog.md`; si la huella deja de coincidir, el producto
    figura como no aprobado.
- **Alternativas descartadas:** comparar fechas de modificación (cambian con un
  `git checkout`); guardar las huellas en un archivo aparte (otro artefacto que
  mantener sincronizado).
- **Consecuencias:** reformatear no invalida nada; cualquier cambio de palabras
  sí.

### D6 — Aprobación solo por el usuario (R014, R015)

- **Contexto:** mismo problema que resolvió `sdd`, con la misma solución
  probada en una sesión real.
- **Decisión:** `/discovery:approve` ejecuta
  `discovery.py approve --skill` por inyección `` !`…` ``, fuera de la
  herramienta Bash. Un hook `PreToolUse` sobre `Write|Edit|Bash` deniega
  cualquier escritura que deje `brief.md` o `backlog.md` aprobados con un Estado
  distinto, y cualquier comando que llame a `discovery.py approve`. Un hook
  `PostToolUse` sobre Bash restaura el Estado si un comando opaco lo cambió.
  Escape: `DISCOVERY_BYPASS=1`. Sin `product/`, los hooks no hacen nada.
- **Alternativas descartadas:** confiar en la instrucción de la skill (es lo que
  `sdd` tuvo que cerrar en la mejora D).
- **Consecuencias:** los hooks de los dos plugins corren en cada llamada; los
  de `discovery` salen enseguida si no hay `product/`.

### D7 — No compartir código con `sdd`

- **Contexto:** huella, campo Estado y análisis de comandos Bash ya existen en
  `sdd`.
- **Decisión:** se copian las piezas mínimas (huella, Estado, detección de
  `approve` en un comando) a `discovery.py`.
- **Alternativas descartadas:** una librería común en el marketplace (acopla
  versiones de dos plugins que se instalan por separado; la constitución pide
  unión solo por archivos).
- **Consecuencias:** ~40 líneas duplicadas; un arreglo en una copia no llega a
  la otra.

### D8 — Comprobación y códigos de hallazgo (R008–R014)

- **Contexto:** R011–R013 piden errores, avisos y salida para CI; R008 y R010
  necesitan una forma mecánica de hacerse cumplir.
- **Decisión:** `discovery.py check [--json] [--check]`, schema
  `discovery.check/v1`, mismo contrato que `sdd.py trace`.

  | Código | Requisito | Detecta |
  | ------ | --------- | ------- |
  | `E-GOAL-NO-FEATURE` | R011 | objetivo sin candidata |
  | `E-SOURCE-UNCOVERED` | R011 | sección sin objetivo, candidata ni descarte |
  | `E-REF-UNKNOWN` | R011 | cita a un documento, sección, objetivo o candidata inexistentes |
  | `E-BACKLOG-DEP-CYCLE` | R011 | dependencias circulares entre candidatas |
  | `E-SOURCE-MODIFIED` | R011 | documento editado tras ingerirse |
  | `E-BACKLOG-ID-GAP` | R008 | hueco en B01…Bn, G1…Gn o D1…Dn: algo se borró en vez de descartarse |
  | `E-BACKLOG-REQUIREMENT` | R010 | una candidata u objetivo redactado como requisito («DEBERÁ») |
  | `E-QUESTION-OPEN-GOAL` | R014 | pregunta abierta que cita un objetivo |
  | `E-PRODUCT-TEMPLATE` | R014 | brief o backlog con huecos de plantilla |
  | `W-FEATURE-NO-GOAL` | R012 | candidata sin objetivo |
  | `W-FEATURE-NO-OUTCOME` | R012 | candidata sin resultado observable |
  | `W-QUESTION-OPEN` | R005 | preguntas abiertas que no citan objetivo |
  | `W-PRODUCT-NOT-APPROVED` | R016 | brief o backlog sin aprobar o cambiados tras aprobarse |

  `approve` aprueba solo si `check` no da errores (R014). Los prefijos
  `*-GOAL-*`, `*-SOURCE-*`, `*-REF-*`, `*-BACKLOG-*`, `*-FEATURE-*`,
  `*-QUESTION-*` y `*-PRODUCT-*` se reservan en el registro común.
- **Alternativas descartadas:** un registro de IDs emitidos aparte para R008
  (otro archivo que sincronizar); la regla «se descarta, no se borra» más el
  error de hueco cubre el caso común.
- **Consecuencias:** borrar la última candidata y reutilizar su ID no se
  detecta si el backlog no estaba aprobado; si lo estaba, la huella lo delata.

## Componentes afectados

| Componente | Cambio | Requisitos que cubre |
| ---------- | ------ | -------------------- |
| `plugins/discovery/scripts/discovery.py` | nuevo: `ingest`, `next-id`, `questions`, `check`, `approve`, `guard`, `audit` | R001, R002, R003, R004, R008, R010, R011, R012, R013, R014, R015, R016 |
| `plugins/discovery/skills/ingest/SKILL.md` | nuevo | R001, R003, R004 |
| `plugins/discovery/skills/clarify/SKILL.md` | nuevo | R005, R009 |
| `plugins/discovery/skills/decompose/SKILL.md` | nuevo | R006, R007, R008, R009, R010 |
| `plugins/discovery/skills/check/SKILL.md` | nuevo | R011, R012, R013 |
| `plugins/discovery/skills/approve/SKILL.md` | nuevo | R014, R015 |
| `plugins/discovery/templates/brief.md`, `backlog.md` | nuevo | R006, R007 |
| `plugins/discovery/hooks/hooks.json` | nuevo: guard y auditoría de la aprobación | R015 |
| `plugins/discovery/tests/selftest.py` | nuevo | todos |
| `plugins/discovery/.claude-plugin/plugin.json`, `README.md` | nuevo | — |
| `.claude-plugin/marketplace.json`, `README.md` raíz | entrada del plugin | — |
| `.github/workflows/validate.yml` | recorre `plugins/*/tests/selftest.py` | — |
| `plugins/sdd/docs/standards-roadmap.md` §7 | reserva de prefijos | — |

## Modelo de datos

No hay base de datos. El modelo es el de los archivos de D3: documentos `Dn`
con secciones `Dn§x.y`, objetivos `Gn`, candidatas `Bnn`, preguntas y
descartes en el brief. Las relaciones son citas por ID dentro de los campos
`**Origen:**`, `**Objetivos:**` y `**Depende de:**`.

## Contratos

- **CLI:** `discovery.py ingest <archivo> [--original <archivo>]`,
  `next-id G|B`, `questions`, `check [--json] [--check]`,
  `approve [--skill]`, `guard`, `audit`.
- **JSON de `check`:** `{"schema": "discovery.check/v1", "ok", "counts",
  "documents", "goals", "candidates", "questions", "findings"}`; cada hallazgo
  con `code`, `severity`, `title`, `message`. Mismo contrato de compatibilidad
  que `sdd.trace/v1`.
- **Formato de `backlog.md`:** es el contrato que leerá la feature de handoff;
  cambiarlo después es un cambio entre plugins (constitución, Límites).

## Estrategia de pruebas

Selftest con funciones `test_F001_Rxxx_*` y un ayudante `expect(...)`, para
que `sdd trace` las reconozca como pruebas con aserción.

| Requisito | Tipo de prueba | Dónde vive |
| --------- | -------------- | ---------- |
| R001 | integración: ingesta, IDs correlativos, numeración anidada, H1 único, sin encabezados | `plugins/discovery/tests/selftest.py` |
| R002 | integración: mismo contenido con otro nombre se rechaza; producto intacto | ídem |
| R003 | integración: `.xlsx` y `.png` rechazados; producto intacto | ídem |
| R004 | integración: `.docx` fabricado en la prueba se convierte; `--original` registra nombre y fecha | ídem |
| R005 | integración: `questions` lista abiertas y rechaza citas inexistentes | ídem |
| R006 | integración: `next-id G` y cobertura de objetivo por `check` | ídem |
| R007 | integración: candidata con todos los campos pasa `check`; sin campos, aviso | ídem |
| R008 | integración: `next-id B` = máximo + 1, con descartadas; hueco → `E-BACKLOG-ID-GAP` | ídem |
| R009 | integración: pregunta que cita dos documentos válida en `questions` | ídem |
| R010 | integración: ningún comando escribe fuera de `product/`; «DEBERÁ» → `E-BACKLOG-REQUIREMENT` | ídem |
| R011 | integración: un caso por error | ídem |
| R012 | integración: los dos avisos | ídem |
| R013 | integración: `--json` con schema y `--check` con exit 1 | ídem |
| R014 | integración: approve rechazado con errores o pregunta sobre objetivo; aceptado sin ellos | ídem |
| R015 | integración: guard deniega Edit/Write/Bash que aprueban; auditoría restaura | ídem |
| R016 | integración: cambio de palabras invalida; reformateo no | ídem |

## Riesgos técnicos

| Riesgo | Impacto | Mitigación |
| ------ | ------- | ---------- |
| `decompose` trocea por secciones del documento, no por valor | backlog con capas técnicas | criterio de la skill + `W-FEATURE-NO-OUTCOME` |
| Conversión de PDF por el modelo pierde estructura | citas a secciones mal numeradas | el usuario revisa el Markdown antes de descomponer; R004 es SHOULD |
| Falsa evidencia de prueba: el selftest de `sdd` contiene cadenas `test_F001_R001_…` de ejemplo que `trace` atribuye a esta feature | un requisito sin prueba real figura como probado | revisar a mano R001 y R002 en el cierre; arreglarlo en `sdd` como feature aparte |
| Dos plugins con hooks en cada llamada | latencia | los de `discovery` salen sin trabajo si no hay `product/` |

## Trazabilidad

Los trece requisitos MUST (R001–R003, R005–R011, R014–R016) aparecen en la
tabla de componentes y en la de pruebas. Los SHOULD (R004, R012, R013) también.
Ningún requisito queda sin cobertura.
