# Hoja de ruta de estándares

Documento de diseño del plugin, no plantilla para proyectos. Describe qué
estándares puede llegar a hacer cumplir el plugin, en qué orden conviene
adoptarlos y con qué criterio de entrada.

Nada de lo que hay aquí está implementado salvo lo marcado como **Hecho**.

---

## 1. Cómo usar este documento

La tabla de fases de la sección 5 es el estado real. Cuando adoptes un escalón,
cambia su estado y anota la fecha. Cuando decidas no adoptarlo, anótalo también
con el motivo: un «no» razonado ahorra la discusión dentro de seis meses.

La regla de oro para decidir si un escalón toca ya: **¿el proyecto ya cumple
este estándar de facto?** Si sí, codificarlo es gratis y evita la regresión. Si
no, codificarlo crea una deuda visible que hay que planificar. Ver sección 4.

---

## 2. Los tres niveles de estándar

Confundirlos es el error que hace que una guía de estilo no sirva para nada.

| Nivel | Ejemplo | Dónde se hace cumplir | Fiabilidad |
| ----- | ------- | --------------------- | ---------- |
| **Mecánico** | formato, dirección de dependencias, cobertura, secretos | hook o CI | 100% |
| **Revisable** | ¿es correcta esta abstracción?, ¿respeta el límite? | agente que lee el diff | alta |
| **Juicio** | ¿es esta la arquitectura adecuada? | persona | — |

Un estándar mecánico escrito en prosa dentro de `constitution.md` se cumple
más o menos. El mismo estándar en un linter se cumple siempre. **Todo lo
determinista debe salir del prompt y entrar en un script.**

Consecuencia de coste: la prosa dentro de una skill se paga en tokens en cada
sesión. Un YAML que lee un script cuesta cero. Cuando un estándar sube del
nivel prosa al nivel mecánico, el plugin se abarata.

---

## 3. Mapa de artefactos

Dónde vive cada tipo de estándar. Las dos últimas filas no existen todavía.

| Artefacto | Contenido | Audiencia | Estado |
| --------- | --------- | --------- | ------ |
| `specs/constitution.md` | el **porqué**: principios, contexto, razonamiento | Claude y personas | Hecho |
| `specs/{NNN}/spec.md` | qué y por qué de una feature | Claude y personas | Hecho |
| `specs/{NNN}/plan.md` | cómo, incluidas decisiones con alternativas | Claude y personas | Hecho |
| `.sdd/config.json` | configuración del plugin (compuerta, exentos, calidad) | scripts | Hecho |
| `specs/standards.yaml` | el **qué** mecánico, en forma consumible por máquina | scripts, hooks, CI, `/sdd:plan` | Fase 2 |
| `specs/adr/{NNNN}-*.md` | decisiones transversales, fuera del plan de una feature | personas | Fase 5 |
| `specs/{NNN}/contracts/` | contratos de API como artefacto versionado | personas y herramientas | Fase 4 |

La separación `constitution.md` / `standards.yaml` es la decisión estructural
principal de esta hoja de ruta. Un solo `standards.yaml` alimenta cuatro
consumidores —el hook de calidad decide qué comandos ejecutar, `sdd.py trace`
añade hallazgos, CI corre lo mismo, y `/sdd:plan` lo lee como restricción— sin
duplicar la definición en ningún sitio. Es el mismo principio que ya sostiene
el JSON de trazabilidad: una definición, varios puntos de aplicación.

---

## 4. El principio del ratchet

**No codifiques un estándar que hoy no cumples.**

Si declaras 90% de cobertura y el repositorio está en 40%, pasa una de dos
cosas: el build queda rojo de forma permanente, o desactivas la comprobación.
En ambos casos **todas las demás comprobaciones pierden credibilidad**, que es
peor que no haber empezado.

El mecanismo correcto registra el valor actual como suelo y solo permite que
suba:

```yaml
coverage:
  floor: current      # se mide al adoptar y se persiste
  # floor: 72.4       # tras el primer registro
```

Aplica igual a número de violaciones de arquitectura, de avisos de linter o de
requisitos sin prueba: el suelo es lo que hay hoy, y el build falla solo si
empeora. Es la única forma que conozco de adoptar estándares sobre código
existente sin generar un bloqueo que acabe desactivándose.

Los estándares **binarios** son la excepción y no necesitan ratchet: un secreto
filtrado o un ciclo de dependencias no admiten «un poco».

---

## 5. Fases

| # | Escalón | Criterio de entrada | Coste | Estado |
| - | ------- | ------------------- | ----- | ------ |
| 0 | Compuerta SDD, trazabilidad, calidad de archivo | — | — | **Hecho** |
| 0b | Compuerta por readiness, aprobación del usuario, IDs con alcance de feature | — | bajo | **Hecho** (2026-10-14) |
| 0c | Compuerta sobre Bash: prevención por análisis del comando y auditoría por `git status` | — | bajo | **Hecho** (2026-10-14) |
| 0d | Preguntas ligadas a requisitos, `/sdd:analyze`, pruebas vacías, `implementation-reviewer` | — | bajo | **Hecho** (2026-10-14) |
| 0e | Deriva por huella de aprobación, `/sdd:amend`, requisitos obsoletos | — | bajo | **Hecho** (2026-10-14) |
| 1 | Detección de secretos | siempre; hazlo primero | bajo | Pendiente |
| 2 | `standards.yaml` + ratchet de cobertura | tras 2–3 features reales | medio | Pendiente |
| 3 | Dirección de dependencias | existe una separación de capas de facto | bajo | Pendiente |
| 4 | Contrato de API como artefacto | el producto expone o consume una API | medio | Pendiente |
| 5 | ADRs promovidos + dependencia exige ADR | hay decisiones que afectan a varias features | bajo | Pendiente |
| 6 | TDD estricto | decisión deliberada; rediseña el ciclo | **alto** | Pendiente |

Las fases 1 a 5 son aditivas: no rompen nada de lo que ya funciona. La 6 es una
refactorización del ciclo de tareas y del hook de calidad, y mezclarla con las
otras hace imposible saber qué se rompió.

### Fase 1 — Detección de secretos

La comprobación con mejor retorno de toda la lista: barata, determinista, y
previene el único error de esta lista que es **irreversible**. Un secreto
publicado en git hay que rotarlo, no revertirlo.

- Mecanismo: `PreToolUse` bloqueante sobre `Write|Edit`, más un paso en CI.
- Herramientas: `gitleaks`, `trufflehog`.
- Sin ratchet: es binario.
- No requiere `standards.yaml`; se puede añadir a `.sdd/config.json`.

### Fase 2 — `standards.yaml` y el ratchet

Es la pieza estructural de la que dependen las fases 3 a 5. Boceto:

```yaml
layers:                       # ver fase 3
  domain:      []
  application: [domain]
  adapters:    [application, domain]
  infra:       [adapters, application, domain]
  paths:
    domain:      "src/domain/**"
    application: "src/application/**"

testing:
  strategy: test-after        # test-first exige la fase 6
  naming: "test_{req_id}_*"
  coverage:
    floor: current
  mock_boundary: ports        # se dobla en el puerto, nunca en el adaptador

dependencies:
  requires_adr: true          # ver fase 5
  denied: []

api:
  contract: "specs/{feature}/contracts/openapi.yaml"
  breaking_changes: forbidden
```

Por qué esperar a tener dos o tres features: los valores que pongas antes de
eso son adivinanzas. Con tres features reales, el `floor: current` mide algo.

### Fase 3 — Dirección de dependencias

Lo único de Clean Architecture que es realmente automatizable, y por suerte lo
que más importa. Declaras el grafo de capas permitido y la violación rompe el
build.

- Herramientas: `import-linter` (Python), `dependency-cruiser` (TS/JS),
  `ArchUnit` (Java/Kotlin), `go-arch-lint` (Go).
- Va en el hook de calidad y en CI. **Nunca en un prompt.**
- Con ratchet sobre el número de violaciones si el código ya las tiene.

Lo que sí va en `constitution.md`: los nombres de las capas, qué tipo de código
vive en cada una, y el porqué de los bordes.

**La tensión con SDD, y cómo resolverla.** Los casos de uso mapean casi uno a
uno con los requisitos, y es tentador escribir «este requisito vive en la capa
de aplicación» en `spec.md`. No debe ir ahí: es una decisión de implementación
y su sitio es `plan.md`. La forma limpia de aprovechar el mapeo es enriquecer
la tabla de componentes del plan:

| Requisito | Caso de uso | Capa | Puerto |
| --------- | ----------- | ---- | ------ |
| R001 | AutenticarConGoogle | application | `OAuthProvider` |

Eso da una comprobación nueva y barata: todo requisito MUST debería tocar
exactamente una capa de aplicación. Un requisito que solo aparece en `infra`
casi seguro está mal escrito.

### Fase 4 — Contrato de API como artefacto

El punto importante: **el contrato es un artefacto de especificación, no
código**. En prosa dentro de `plan.md` deriva en la primera semana.

```
specs/003-consulta-saldo/
├── spec.md
├── plan.md
├── tasks.md
└── contracts/openapi.yaml
```

Extiende la trazabilidad con dos códigos nuevos, y es probablemente la
extensión con mejor relación valor/esfuerzo de la lista:

- `E-CONTRACT-NO-REQ` — endpoint que no sirve a ningún requisito.
- `E-REQ-NO-CONTRACT` — requisito que promete algo observable por API y no
  aparece en el contrato.

Comprobación mecánica: `spectral` para lint del esquema, `oasdiff` o `buf` para
detectar cambios rompientes.

Estándares que conviene fijar una vez y no volver a discutir, porque la
inconsistencia entre features en estos seis puntos es la más visible desde
fuera y la más cara de arreglar después: versionado, forma del sobre de error,
paginación, idempotencia, formato de fechas, formato de importes.

### Fase 5 — ADRs promovidos

La sección «Decisiones» de `templates/plan.md` —contexto, decisión,
alternativas descartadas, consecuencias— **ya es un ADR**. Falta una sola cosa:
promover las decisiones transversales fuera del plan de la feature, a
`specs/adr/`. Una decisión que afecta a todas las features no debe quedar
enterrada en el plan de la feature 007.

Regla que sí se puede hacer cumplir: un `PreToolUse` sobre edición de
`pyproject.toml`, `package.json` o `go.mod` que exija referencia a un ADR.
Añadir una dependencia es una decisión arquitectónica y hoy es el cambio menos
revisado de todos.

Higiene asociada, con verificación estándar: lockfiles versionados, `pip-audit`
o `npm audit` en CI, versiones de runtime declaradas en un solo sitio. Lo
último parece trivial y no lo es: el fallo de que CI corra 3.12 y tú 3.9
aparece siempre, y siempre tarde.

### Fase 6 — TDD estricto

**El plugin tal como está hoy es incompatible con TDD estricto**, en dos
puntos. Conviene tenerlos claros antes de decidir.

1. `E-DONE-NO-TEST` comprueba que exista una prueba, no que se escribiera
   *antes*. Nada fuerza el orden.
2. El hook de calidad corre el linter sobre el archivo recién escrito. En TDD,
   ese archivo es una prueba que **debe** fallar. El hook lo reportaría como
   problema. Hay que enseñarle a distinguir «falla porque está en rojo, como
   toca» de «falla porque está mal».

Lo que haría falta:

- **Compuerta test-first**: `PreToolUse` que bloquee escribir `src/foo.py` si
  no existe ya el test correspondiente referenciando el requisito. Es la misma
  forma que la compuerta actual con otra condición, así que la maquinaria ya
  está.
- **Cuatro estados de tarea** en vez de tres. Hoy hay `[ ] [~] [x]`; con TDD
  hacen falta pendiente, rojo, verde y refactorizado. Sin esto el agente
  escribe prueba e implementación en el mismo turno y el ciclo rojo-verde solo
  existe de nombre. **Es la pieza que decide si el TDD es real o decorativo.**
- **Verificación rojo-verde** vía git, corriendo la prueba en `HEAD~1` y en
  `HEAD`. Es la única evidencia dura de que la prueba fue primero. Caro: solo
  en CI, nunca en el bucle local.

Estándares a declarar: qué cuenta como unitaria frente a integración, umbral de
cobertura y si es por archivo o global, y **dónde se permite doblar**. Este
último es donde TDD y Clean Architecture se encuentran: se dobla en el puerto,
nunca en el adaptador. Una regla de una línea que ahorra años de discusión.

---

## 6. Estándares sin fase asignada

Reales e importantes, pero su momento depende del producto.

**Cumplimiento regulatorio.** Si hay exposición regulatoria, los requisitos de
cumplimiento merecen ser ciudadanos de primera: IDs propios (`C001`) trazados
exactamente igual que los funcionales, y una compuerta que exija revisión
cuando la spec toca autenticación, datos personales o dinero. Es la diferencia
entre afirmar que cumples y poder demostrarlo con un artefacto generado, y es
también lo que permite que un auditor externo lea el repositorio.

**Contrato de errores.** Qué excepciones cruzan qué límite. Toca a la vez la
fase 3 y la 4, y es la regla que más código feo previene. Parcialmente
mecánica: se puede prohibir que un tipo de excepción de `infra` aparezca en
`application`.

**Migraciones de datos.** Reversibilidad y despliegue sin interrupción. Lo que
más duele cuando falla y lo que menos gente escribe. Aunque el despliegue viva
fuera del plugin, **la reversibilidad de una migración es una decisión de
diseño, no de infraestructura**, y su sitio es `plan.md`.

**Observabilidad.** Logging estructurado, IDs de correlación, y sobre todo qué
**nunca** se registra. Parcialmente mecánica: una regla que prohíba `print` y
`console.log`, y otra que prohíba loguear campos marcados como sensibles.

**Definición de terminado.** El meta-estándar que ata todo lo anterior, y
debería ser una lista legible por máquina. `sdd.py trace` ya cubre buena parte.

---

## 7. Reserva de códigos de hallazgo

Los códigos de `sdd_trace.py` y de los demás plugins de la serie son contrato
público. Para que no colisionen, este es el reparto de prefijos, común a todos
los plugins del marketplace:

| Prefijo | Dominio | Estado |
| ------- | ------- | ------ |
| `*-REQ-*` | requisitos de `spec.md` | en uso |
| `*-TASK-*` | tareas de `tasks.md` | en uso |
| `*-DONE-*` | coherencia de tareas cerradas | en uso |
| `*-SPEC-*` | el documento de spec en conjunto | en uso |
| `*-PLAN-*` | `plan.md` frente a la spec y la constitución | en uso |
| `*-TEST-*` | evidencia de prueba (forma de citar requisitos) | en uso |
| `*-ARCH-*` | la arquitectura en conjunto: citas, preguntas, aprobación, capas y dirección de dependencias (plugin `architecture`; antes reservado para la fase 3) | en uso |
| `*-CONTRACT-*` | contratos de API | fase 4 |
| `*-DEP-*` | dependencias y ADRs | fase 5 |
| `*-TDD-*` | orden rojo-verde | fase 6 |
| `*-SEC-*` | secretos y cumplimiento | fases 1 y 6+ |
| `*-GOAL-*` | objetivos del brief (plugin `discovery`) | en uso |
| `*-SOURCE-*` | documentos de producto (plugin `discovery`) | en uso |
| `*-REF-*` | citas entre artefactos de producto (plugin `discovery`) | en uso |
| `*-BACKLOG-*` | backlog de candidatas (plugin `discovery`) | en uso |
| `*-FEATURE-*` | candidatas individuales (plugin `discovery`) | en uso |
| `*-QUESTION-*` | preguntas del brief (plugin `discovery`) | en uso |
| `*-PRODUCT-*` | el producto en conjunto (plugin `discovery`) | en uso |
| `*-ADR-*` | decisiones de arquitectura (plugin `architecture`) | en uso |
| `*-QUALITY-*` | atributos de calidad (plugin `architecture`) | en uso |
| `*-COMPONENT-*` | componentes y candidatas que alojan (plugin `architecture`) | en uso |
| `*-STANDARD-*` | estándares comprobables (plugin `architecture`) | en uso |

**Política de compatibilidad del schema `sdd.trace/v1`:** añadir códigos nuevos
es aditivo y no rompe a un consumidor que filtre por `severity`. Renombrar o
eliminar un código, o cambiar la forma de un campo existente, exige subir a
`v2`. Un consumidor que enumere códigos explícitamente debe fijar la versión.

---

## 8. Decisiones abiertas

1. **¿`standards.yaml` en `specs/` o en `.sdd/`?** A favor de `specs/`: es un
   artefacto de especificación, se revisa en el PR y lo leen personas. A favor
   de `.sdd/`: es configuración de herramienta. Inclinación actual: `specs/`,
   porque el grafo de capas es una decisión arquitectónica, no un ajuste.
2. **¿Un `standards.yaml` por repositorio o por feature?** Por repositorio,
   casi seguro. Una feature que necesita reglas propias es señal de que sobra
   una capa o falta un servicio.
3. **¿El ratchet de cobertura se persiste en el repo o se calcula contra la
   rama base?** Persistirlo es simple pero genera commits de ruido; calcularlo
   contra base es más limpio pero ata la comprobación a CI y deja de funcionar
   en local.
4. **¿Vendorizar el plugin en el repo de producto?** Con un solo repo de
   producto, sí: desaparece el problema de versiones desincronizadas entre tu
   máquina y CI, que es exactamente el fallo que estos estándares pretenden
   evitar.

---

## 9. Fuera de alcance a propósito

Estimaciones, planificación de sprints, matrices RACI, aprobaciones multi-rol.
Es ceremonia diseñada para coordinar equipos grandes; en un plugin de una
persona lo único que consigue es que dejes de usarlo. Es la crítica más común a
las implementaciones existentes de SDD y conviene no repetirla.

Despliegue e infraestructura: se aíslan deliberadamente en GitHub Actions y
Terraform. El plugin llega hasta el artefacto verificado, y ahí termina su
responsabilidad.

**Aviso de coste, que aplica a cada fase.** Cada skill y cada agente añade su
descripción al contexto de **todas** las sesiones. Mide con
`claude plugin details sdd` antes y después de cada escalón. Si el coste
always-on duele, la salida es fusionar componentes o mover prosa a
`standards.yaml`, nunca acortar descripciones: la descripción es el mecanismo
de activación.
