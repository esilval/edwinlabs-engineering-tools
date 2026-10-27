# EdwinLabs Engineering Tools

Marketplace de plugins de [Claude Code](https://code.claude.com/docs).

## Instalación

```bash
claude plugin marketplace add esilval/edwinlabs-engineering-tools
claude plugin install discovery --scope user
claude plugin install architecture --scope user
claude plugin install sdd --scope user
claude plugin install release --scope user
claude plugin install operate --scope user
```

Cada plugin funciona por su cuenta: instala solo los que vayas a usar.

En VS Code: escribe `/plugins`, pestaña **Marketplaces**, añade
`esilval/edwinlabs-engineering-tools`, y luego instala desde la pestaña
**Plugins**.

## Plugins

Los plugins forman una serie que cubre el ciclo de vida de un producto, una
etapa por plugin:

```
discovery  →  architecture  →  sdd  →  release  →  operate
producto      decisiones        features  versiones  operación
```

| Plugin | Qué hace | Deja en el proyecto |
| ------ | -------- | ------------------- |
| [`discovery`](plugins/discovery) | De documento de producto a backlog de features: brief (objetivos, restricciones), candidatas y trazabilidad documento → objetivo → candidata, aprobados por el usuario. | `product/` |
| [`architecture`](plugins/architecture) | De producto aprobado a arquitectura: atributos de calidad medibles, componentes con las candidatas que alojan, decisiones (ADR) y estándares comprobables, aprobados por el usuario. Solo para productos nuevos. | `architecture/` |
| [`sdd`](plugins/sdd) | Desarrollo orientado a especificaciones: spec → plan → tareas → implementación, con una compuerta que impide escribir código sin especificación aprobada y trazabilidad requisito → tarea → prueba. | `specs/`, `.sdd/` |
| [`release`](plugins/release) | De features terminadas a versión preparada: comprueba que las features elegidas están aprobadas, cerradas y trazadas, propone el número SemVer y deja notas para usuarios y cambios técnicos, aprobados por el usuario. No despliega ni etiqueta. | `releases/` |
| [`operate`](plugins/operate) | De versión publicada a operación: preparación de cada versión (puesta en marcha, señales con umbral desde los atributos de calidad y vuelta atrás) e incidentes con postmortems cuyas acciones vuelven a `sdd` como correcciones, aprobados por el usuario. No despliega ni lee métricas. | `operations/` |

Cómo encajan:

- `/sdd:specify B03` crea una feature desde una candidata del backlog aprobado,
  con su problema, contexto, alcance y origen ya rellenos.
- Si hay `architecture/`, `/sdd:plan` planifica sobre ella: cita las decisiones
  aprobadas en lugar de volver a decidir el stack. Si hace falta una nueva, la
  propone (`Proposed`) para que el usuario la decida con
  `/architecture:review`. `/sdd:trace` da error si un plan cita una decisión
  no aprobada.
- `/release:new 008 009` prepara una versión con features terminadas: lee
  `specs/`, ejecuta la trazabilidad de `sdd` sobre cada una y cita en las notas
  las candidatas y objetivos de su fila `Origen`.
- `/operate:prepare v0.4.0` prepara la puesta en marcha de una versión
  publicada, con una señal por cada atributo de calidad de la arquitectura que
  tocan sus features. Las acciones del postmortem de un incidente vuelven a
  `sdd`: `/sdd:specify I001-A2` crea la feature de corrección.
- Ningún plugin importa código de otro: se unen solo por esos archivos. Lo que
  uno lee del formato de otro lo lleva copiado y documentado, y una prueba de
  contrato lo contrasta con el plugin real en CI.
- En todos, aprobar es del usuario: las skills que aprueban solo las lanza
  él, y unos hooks impiden que el modelo escriba o ejecute una aprobación.

Un flujo completo, en un producto nuevo:

```
/discovery:ingest docs/vision.md      # documento de producto → D1
/discovery:decompose                  # brief y backlog de candidatas
/discovery:approve
/architecture:init                    # atributos de calidad y componentes
/architecture:decide                  # decisiones (ADR) y estándares
/architecture:approve
/sdd:specify B01                      # feature desde una candidata
/sdd:plan                             # sobre la arquitectura aprobada
/sdd:tasks
/sdd:implement
/release:new 001 002                  # versión con las features terminadas
/release:approve                      # y el git tag lo ejecutas tú
/operate:prepare v0.1.0               # puesta en marcha, señales y vuelta atrás
/operate:approve v0.1.0
/operate:incident Caída del resumen   # cuando algo falla en producción
/operate:postmortem I001
/operate:approve I001
/sdd:specify I001-A1                  # cada acción, una corrección
```

En un repositorio que ya existe, `sdd` funciona solo, sin los demás.

## Estructura del repositorio

```
.claude-plugin/marketplace.json   catálogo; debe estar en la raíz
plugins/<nombre>/                 un directorio por plugin
specs/                            el propio repositorio se desarrolla con sdd:
                                  constitución y una carpeta por feature
scripts/validate.py               validación estructural, la misma que corre CI
.github/workflows/validate.yml    CI: validate --strict y el selftest de cada plugin
```

Las reglas que todo cambio respeta (Python 3.8 sin dependencias, plugins unidos
solo por archivos, guardrails que fallan abiertos, aprobación solo del usuario,
selftest por plugin, registro común de prefijos de hallazgo) están en
[`specs/constitution.md`](specs/constitution.md).

El `marketplace.json` va en la raíz del repositorio, no dentro de un plugin.
Cada `source` es una ruta relativa a la raíz y debe empezar por `./`.

## Añadir un plugin

1. Crea `plugins/<nombre>/.claude-plugin/plugin.json` con al menos `name`.
2. Añade la entrada correspondiente a `.claude-plugin/marketplace.json`.
3. Añade `plugins/<nombre>/tests/selftest.py` (solo biblioteca estándar): CI lo
   ejecuta.
4. Reserva sus prefijos de hallazgo en el registro común
   (`plugins/sdd/docs/standards-roadmap.md`, sección 7).
5. `python3 scripts/validate.py --strict`
6. `claude plugin validate .` — comprueba cosas que el script no cubre.

## Versionado

Los plugins no fijan `version`, así que Claude Code usa el SHA del commit y
cada commit cuenta como una actualización disponible. Es lo adecuado mientras
se itera.

Cuando un plugin se estabilice, añade `"version"` a su `plugin.json` y etiqueta
la release:

```bash
claude plugin tag plugins/sdd --push
```

A partir de ese momento hay que subir el número en cada cambio que deba llegar a
los usuarios: publicar commits sin tocarlo no les entrega nada.

## Desarrollo

Para iterar sin reinstalar tras cada cambio, enlaza el plugin a tu directorio de
skills personal:

```bash
ln -s "$(pwd)/plugins/sdd" ~/.claude/skills/sdd
```

Se carga como `sdd@skills-dir`, descubierto en su sitio en vez de copiado al
caché. Los cambios en `SKILL.md` aplican al instante; los de `hooks/`,
`scripts/` y `plugin.json` necesitan `/reload-plugins`.

No uses el enlace y la instalación por marketplace a la vez.

## Licencia

MIT
