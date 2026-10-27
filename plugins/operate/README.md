# operate — de versión publicada a operación

Prepara la puesta en marcha de cada versión publicada y recoge lo que pasa
después: incidentes con su postmortem, cuyas acciones vuelven a `sdd` como
features de corrección. La aprobación es tuya.

Es la última etapa de la serie `discovery` → `architecture` → `sdd` →
`release` → `operate`. Cubre la **preparación y el aprendizaje**: no despliega,
no ejecuta procedimientos ni vueltas atrás, no lee métricas y no se conecta a
ningún sistema de monitorización.

## Uso

```
/operate:prepare v0.4.0        # preparación de una versión publicada
/operate:incident Caída del resumen diario
/operate:postmortem I001       # cronología, causas y acciones
/operate:check                 # comprobación; también en CI
/operate:approve v0.4.0        # tú apruebas la preparación…
/operate:approve I001          # …o el postmortem
/sdd:specify I001-A2           # cada acción, una feature de corrección
```

`prepare`, `incident`, `postmortem` y `approve` los lanza el usuario
(`disable-model-invocation`). `check` lo puede lanzar también el modelo, porque
solo lee. Por debajo usan `scripts/operate.py`, que también se puede llamar a
mano:

| Subcomando | Qué hace | Salida |
| ---------- | -------- | ------ |
| `prepare vX.Y.Z` | Escribe `operations/vX.Y.Z.md` en borrador; no sobrescribe | 0 si la escribe o ya existía; 1 si la versión no existe o no está publicada; 2 sin versión |
| `incident "<título>"` | Registra el siguiente incidente y escribe su archivo | 0 y el ID nuevo (JSON); 1 sin título |
| `next-action I001` | Siguiente acción libre del postmortem | 0 y `I001-A<n>`; 1 si el incidente no existe |
| `check [vX.Y.Z\|I001] [--json] [--check]` | Comprueba eso, o todo `operations/` | 0; 1 con `--check` y errores; 2 con un argumento desconocido o un objetivo que no existe |
| `approve <vX.Y.Z\|I001> [--skill]` | Aprueba la preparación o el postmortem | 0, o 1 si se niega; con `--skill`, siempre 0 |
| `guard`, `audit` | Hooks que protegen la aprobación (leen JSON por stdin) | — |

El 2 de los usos incorrectos, como en `release`, no está en los contratos del
plan: separa en CI una errata del comando de una comprobación que falla.

## Los artefactos

```
operations/
├── v0.4.0.md            preparación de la versión 0.4.0
├── incidents.md         registro de incidentes: solo crece
└── incidents/
    └── I001-slug.md     un incidente con su postmortem
```

**Preparación, `operations/vX.Y.Z.md`:**

- **Cabecera:** `Estado`, `Versión` (`0.4.0 · <huella de releases/v0.4.0.md>`),
  `Fecha` y `Features`.
- **Features:** las de la versión, con su título. La escribe el script.
- **Puesta en marcha:** los pasos y cómo verificar que funciona.
- **Señales:** una subsección `### SG1 — <nombre>` por señal, con `Atributo`
  (`Q1` o `—`), `Escenario`, `Umbral` y `Cómo se mide`.
- **Vuelta atrás:** los campos `Pasos` y `Disparador`.

**Incidente, `operations/incidents/I001-slug.md`:**

- **Cabecera:** `Estado`, `ID`, `Fecha`, `Versión afectada` (`0.4.0` o
  `desconocida`) y `Severidad`.
- Secciones **Qué pasó**, **Impacto**, **Cronología**, **Causas** y
  **Acciones**. Cada acción es `### I001-A1 — <título>` con el campo `Qué`.
- Aprobar el archivo es aprobar el postmortem.

**Registro, `operations/incidents.md`:** una fila por incidente que no se borra
nunca, aunque se borre su archivo. El siguiente incidente es el mayor del
registro y de los archivos, más 1: un número no se recicla.

Las líneas en cursiva son huecos: mientras quede alguno, `E-PREP-TEMPLATE` o
`E-INCIDENT-TEMPLATE` impiden aprobar. No cuentan las notas en blockquote, el
código en línea, los encabezados ni la sección «Features». En una preparación
sí cuentan los `###`, para que el nombre de una señal no quede sin poner.

Un incidente en investigación tiene huecos, así que da error en CI hasta que
su postmortem se completa, como una spec o una versión a medio redactar.

## Señales desde la arquitectura

Con `architecture/` aprobada, `prepare` propone una señal por cada atributo de
calidad (`Qn`) relacionado con alguna feature de la versión. Un atributo se
relaciona con una feature si:

- su `Motivo` cita un objetivo (`Gn`) del segundo grupo de la fila `Origen` de
  la feature; o
- lo cita el `Motivo` de un ADR **aprobado** que cita el plan de la feature.

Cada señal propuesta trae el atributo y su escenario; el umbral y cómo se mide
los completa `/operate:prepare`. Sin `architecture/`, con la arquitectura sin
aprobar o sin atributos relacionados, la sección trae una sola señal con
huecos y una nota que dice por qué. Lo que la relación no ve se añade a mano.

## Acciones

Cada acción del postmortem lleva un ID `I001-A<n>` que da `next-action`: el
mayor de las del incidente, más 1. Una acción no se renumera al editarla ni al
borrar otra. Si se borra la de mayor número, ese número queda libre dentro de
su incidente.

`E-INCIDENT-ACTION-ID` señala una acción sin ID, con el ID de otro incidente o
repetida.

## Comprobación

Un borrador se comprueba entero. Una preparación aprobada solo se mira por si
cambió ella o su versión; un postmortem aprobado, por si cambió y por sus
acciones sin feature.

| Código | Qué |
| ------ | --- |
| `E-PREP-RELEASE` | la preparación es de una versión que no existe o no está publicada |
| `E-PREP-SIGNAL-THRESHOLD` | una señal sin umbral con cifra (un dígito); la nombra |
| `E-PREP-ROLLBACK-TRIGGER` | la vuelta atrás no dice qué la dispara |
| `E-PREP-TEMPLATE` | huecos en la preparación |
| `W-PREP-NOT-APPROVED` | preparación sin aprobar, o cambiada tras aprobarse |
| `W-PREP-RELEASE-CHANGED` | la versión ya no tiene la huella con la que se aprobó la preparación, o ya no existe |
| `E-INCIDENT-RELEASE` | el incidente cita una versión afectada que no existe; nombra los dos |
| `E-INCIDENT-ACTION-ID` | una acción sin ID, con el de otro incidente o repetida |
| `E-INCIDENT-TEMPLATE` | huecos en el incidente o su postmortem |
| `W-INCIDENT-NOT-APPROVED` | postmortem sin aprobar, o cambiado tras aprobarse |
| `W-INCIDENT-ACTION-NO-FEATURE` | una acción de un postmortem aprobado sin feature; la nombra |

En CI:

```bash
python3 plugins/operate/scripts/operate.py check --check   # 1 si hay errores
python3 plugins/operate/scripts/operate.py check --json    # schema operate.check/v1
```

`operate.check/v1` es `{schema, ok, counts, findings: [{code, severity,
message, artifact}]}`. Añadir códigos es aditivo; renombrar o quitar uno exige
`v2`.

## Aprobación

`/operate:approve` se niega, sin cambiar nada, si hay errores o huecos. Si
aprueba, sella el archivo con `Approved · <huella>`. En una preparación,
además, guarda en la fila `Versión` la huella de la versión del momento: si la
versión cambia después, `check` da `W-PREP-RELEASE-CHANGED`, y si desaparece,
volver a aprobarla se niega. Al aprobar un postmortem, muestra los
`/sdd:specify I001-A1` que convierten cada acción en una corrección.

Volver a aprobar algo que cambió pasa por la comprobación entera.

## El traspaso a `sdd`

Con `operations/incidents.md` en el proyecto, `/sdd:specify I001-A2` crea una
feature desde esa acción de un postmortem aprobado. La spec nace con:

- `Tipo` en `corrección`, que `release` usa para el número de versión;
- el Problema (qué pasó, el impacto y la acción) y el Contexto (el incidente,
  la versión y las causas);
- la fila `| Origen | I001-A2 · 0.4.0 |`: la acción y la versión afectada (`—`
  si es desconocida).

No se crea nada si el postmortem no está aprobado o cambió, si la acción no
existe o si ya tiene feature. Una acción tiene feature cuando una spec la cita
como primer elemento de su `Origen`; desde ese momento `check` deja de avisar
de ella.

## Guardrails

Aprobar es del usuario:

- Un hook `PreToolUse` sobre Write, Edit y Bash deniega cualquier escritura
  que ponga `Approved` o una huella en el Estado de `operations/v*.md` o de
  `operations/incidents/*.md`, también al crearlos, y cualquier comando que
  **ejecute** `operate.py approve`: directamente, encadenado o dentro de una
  sustitución `$(…)` o con comillas invertidas. Mencionarlo (un commit, un PR,
  un heredoc) no bloquea. Nunca devuelve `allow`.
- Un hook `PostToolUse` sobre Bash devuelve a su Estado anterior, con un
  aviso, lo que un comando opaco (`bash -c`, un script) haya aprobado, aunque
  `operations/` no existiera antes.
- Un error inesperado de un hook deja pasar.

Escape para el usuario: `OPERATE_BYPASS=1` en el entorno desactiva los dos
hooks.

Límites conocidos: los mismos que los de `release`. Una mención sin comillas
(`echo python3 operate.py approve`) se bloquea aunque no se ejecute, y una
edición múltiple (`MultiEdit`) no se analiza.

## Relación con los demás plugins

`operate` no importa código de ningún plugin. Sin `architecture/` prepara sin
señales propuestas; sin `releases/` no hay preparaciones, pero sí incidentes,
con la versión afectada `desconocida`. Lo que lee de otros lo lleva copiado y
documentado en `scripts/operate_sources.py`:

- **De `release`:** la cabecera de `releases/vX.Y.Z.md`, su estado y huella, y
  la regla de versión publicada (aprobada alguna vez, aunque cambie).
- **De `architecture`:** la aprobación del conjunto, los atributos de calidad y
  el `Motivo` de las decisiones.
- **De `sdd`:** resolver una feature, su fila `Origen` y las decisiones que
  cita su plan, y qué spec cita cada acción.

Una prueba de contrato recorre los plugins reales: `discovery` aprueba un
producto, `architecture` su arquitectura, `sdd` crea y aprueba una feature
desde una candidata, y `release` crea y aprueba la versión. `operate` tiene que
leerlo todo igual.

En sentido contrario, `sdd` lee `operations/` con su propia copia
(`plugins/sdd/scripts/sdd_operate.py`), contrastada con el `operate.py` real
en el selftest de `sdd`.

El analizador de comandos de los guardrails es la quinta copia: de `release`,
que copia el de `architecture`, este el de `discovery` y este el de
`plugins/sdd/scripts/sdd_bash.py`. Las cinco se nombran entre sí, y sus
selftests usan la misma lista de casos.

## Pruebas

```bash
python3 plugins/operate/tests/selftest.py
```

Cada prueba cita el requisito de la feature de este repositorio que comprueba
(`test_F011_R0NN_…`). Los artefactos de los otros plugins se escriben a mano
en su formato; solo la prueba de contrato usa los reales. El selftest falla si
un código de hallazgo declarado no se prueba.
