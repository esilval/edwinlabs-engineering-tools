# release — de features terminadas a versión preparada

Prepara una versión con las features que eliges: comprueba que están
aprobadas, cerradas y trazadas, propone el número de versión, y deja las notas
para quien usa el producto y el registro de cambios para el equipo. La
aprobación es tuya.

Es la etapa que sigue a `sdd` en la serie `discovery` → `architecture` →
`sdd` → `release` → … Cubre la **preparación y la decisión**: no despliega, no
etiqueta y no publica nada. Al aprobar, te muestra el comando `git tag` para
que lo ejecutes tú.

## Uso

```
/release:new 008 009           # borrador con esas features, número propuesto
/release:new 008 --version 1.0.0
/release:check                 # comprobación; también en CI
/release:approve               # tú apruebas la versión en borrador
/release:approve v0.4.0        # o la que nombres
```

`new` y `approve` los lanza el usuario (`disable-model-invocation`). `check` lo
puede lanzar también el modelo, porque solo lee. Por debajo usan
`scripts/release.py`, que también se puede llamar a mano:

| Subcomando | Qué hace | Salida |
| ---------- | -------- | ------ |
| `new <features…> [--version X.Y.Z]` | Escribe `releases/vX.Y.Z.md` en borrador; no sobrescribe | 0 si lo escribe o ya existía; 1 sin features o con un número mal formado; 2 con un argumento desconocido |
| `check [vX.Y.Z] [--json] [--check]` | Comprueba esa versión, o todas | 0; 1 con `--check` y errores; 2 con un argumento desconocido o una versión que no existe |
| `approve [vX.Y.Z] [--skill]` | Aprueba la versión | 0, o 1 si se niega; con `--skill`, siempre 0 |
| `guard`, `audit` | Hooks que protegen la aprobación (leen JSON por stdin) | — |

Las features se nombran por su número (`008`) o por su directorio de `specs/`
(`008-exportar-ventas`). El 2 de los usos incorrectos no está en los contratos
del plan, que solo fijan 0 y 1: separa en CI una errata del comando de una
comprobación que falla.

## El artefacto

Una versión es un archivo `releases/vX.Y.Z.md`:

- **Cabecera:** `Estado`, `Versión`, `Fecha`, `Anterior` (la última versión
  publicada al crearla, o `—`) y `Features` (`008, 009`).
- **Contenido:** por feature, su `Tipo`, su `Origen` y sus requisitos
  vigentes.
- **Comprobación:** el resultado de la comprobación de las features y del
  número al escribir el borrador. Lo que falta por redactar va aparte, en una
  línea «Pendiente». `approve` la reescribe con el resultado del momento de
  aprobar, que queda sellado como evidencia. Lo que manda en cada momento es
  `check`.
- **Notas para usuarios:** por feature, una línea en cursiva que pide redactar
  qué cambia para el usuario. Si la spec tiene `Origen`, cita su candidata y
  sus objetivos de `discovery`.
- **Cambios técnicos:** por feature, los datos que genera el script
  (requisitos vigentes y retirados, decisiones `ADR-NNNN` que cita su plan, y
  si su plan tiene contenido en «Contratos» y «Modelo de datos»), y una línea
  en cursiva que pide resumirlos.

Las líneas en cursiva son huecos: mientras quede alguno, `E-RELEASE-TEMPLATE`
impide aprobar. Los redacta `/release:new`. No cuentan las notas en
blockquote, los encabezados ni las secciones que escribe el script.

## El número de versión

`MAYOR.MENOR.PARCHE`, enteros sin ceros a la izquierda. Una versión está
**publicada** si se aprobó alguna vez, aunque haya cambiado después: sus
features ya no pueden entrar en otra versión y su número sigue contando. La
última publicada es la mayor.

| Caso | Propuesta |
| ---- | --------- |
| No hay ninguna publicada | 0.1.0 |
| Alguna feature tiene un requisito `OBSOLETO` | la mayor; en la serie 0.x, la menor |
| Alguna feature es `funcionalidad` | la menor |
| Todas son `corrección` | el parche |

El tipo sale de la fila `| Tipo | funcionalidad |` o `| Tipo | corrección |`
de la cabecera de cada spec, que pone `sdd`. Se aceptan sin tilde y en
mayúsculas. Sin la fila, cuenta como funcionalidad. Un `Tipo` no válido, o sin
ninguna feature válida, también cuenta como funcionalidad.

La propuesta es prudente: un `OBSOLETO` de una enmienda durante el desarrollo,
que no retira nada publicado, sube la mayor igual. Fija otro número con
`--version`.

## Comprobación

`check` comprueba cada versión en borrador entera. De una versión publicada
solo mira si cambió tras aprobarse: no se vuelve a juzgar por cómo
evolucionan sus features.

| Código | Qué |
| ------ | --- |
| `E-RELEASE-NO-FEATURES` | la versión no incluye ninguna feature |
| `E-RELEASE-FEATURE-UNKNOWN` | una feature no existe en `specs/`, o su número es ambiguo |
| `E-RELEASE-FEATURE-RELEASED` | la feature ya está en otra versión publicada, que se nombra |
| `E-RELEASE-FEATURE-NOT-APPROVED` | una fase sin aprobar o cambiada tras aprobarse; nombra feature y fase |
| `E-RELEASE-FEATURE-OPEN-TASKS` | tareas sin cerrar, nombradas |
| `E-RELEASE-FEATURE-TRACE` | la trazabilidad de la feature tiene errores; nombra el primero |
| `E-RELEASE-FEATURE-ADR` | el plan cita una decisión de arquitectura inexistente o no aprobada |
| `E-RELEASE-FEATURE-TYPE` | el `Tipo` de la spec no es `funcionalidad` ni `corrección` |
| `E-RELEASE-VERSION` | número mal formado, no mayor que la última publicada, repetido o distinto del archivo |
| `E-RELEASE-TEMPLATE` | quedan huecos sin completar |
| `W-RELEASE-NOT-APPROVED` | la versión no está aprobada, o cambió tras aprobarse (sigue publicada) |
| `W-RELEASE-NO-TRACE` | la trazabilidad de una feature no se pudo obtener |

En CI:

```bash
python3 plugins/release/scripts/release.py check --check   # 1 si hay errores
python3 plugins/release/scripts/release.py check --json    # schema release.check/v1
```

`release.check/v1` es `{schema, ok, counts, findings: [{code, severity,
message, artifact}]}`. Añadir códigos es aditivo; renombrar o quitar uno exige
`v2`.

## La trazabilidad

La trazabilidad de cada feature la da `sdd`: `release` ejecuta
`sdd.py trace --feature NNN --json` como comando y lee su contrato
`sdd.trace/v1`, sin importar su código. De ahí salen `E-RELEASE-FEATURE-TRACE`
y, para las decisiones de arquitectura, `E-RELEASE-FEATURE-ADR`: `release` no
lee `architecture/`.

`sdd.py` se busca en este orden:

1. la variable de entorno `SDD_SCRIPT`;
2. `plugins/sdd/scripts/sdd.py` junto a este plugin (el repositorio o un
   enlace de desarrollo);
3. la caché de plugins del marketplace: la versión instalada más reciente.

Si no se encuentra, falla, tarda más de 60 s o su salida no se puede leer, hay
un aviso `W-RELEASE-NO-TRACE` y el resto de comprobaciones se aplica. Sin
trazabilidad no se comprueban ni los errores de trazabilidad ni las decisiones
de arquitectura.

## Aprobación

`/release:approve` se niega, sin cambiar nada, si la comprobación da errores o
quedan huecos. Si aprueba:

1. reescribe «Comprobación» con el resultado del momento;
2. sella el archivo con `Approved · <huella>`;
3. te muestra `git tag -a vX.Y.Z -m "…"` y `git push origin vX.Y.Z`, que no
   ejecuta.

Sin argumento aprueba la única versión en borrador; si hay varias, pide cuál.
Una versión aprobada que cambia después da `W-RELEASE-NOT-APPROVED` en
`check`, pero sigue publicada. Se vuelve a aprobar nombrándola, con la
comprobación entera de un borrador: el cambio podría haber añadido una
feature. Su número no tiene que ser mayor que el de las publicadas después.

## Guardrails

Aprobar es del usuario:

- Un hook `PreToolUse` sobre Write, Edit y Bash deniega cualquier escritura
  que ponga `Approved` o una huella en el Estado de `releases/*.md`, también
  al crear una versión, y cualquier comando que **ejecute** `release.py
  approve`: directamente, encadenado o dentro de una sustitución `$(…)` o con
  comillas invertidas. Mencionarlo (un commit, un PR, un heredoc) no bloquea.
  Nunca devuelve `allow`.
- Un hook `PostToolUse` sobre Bash devuelve a su Estado anterior, con un
  aviso, la versión que un comando opaco (`bash -c`, un script) haya aprobado.
- Un error inesperado de un hook deja pasar.

Escape para el usuario: `RELEASE_BYPASS=1` en el entorno desactiva los dos
hooks.

Límites conocidos: los mismos que los de `architecture`. Una mención sin
comillas (`echo python3 release.py approve`) se bloquea aunque no se ejecute,
y una edición múltiple (`MultiEdit`) no se analiza.

## Relación con los demás plugins

`release` no importa código de ningún plugin y funciona sin `product/` ni
`architecture/`. Lo que necesita de otros lo lleva copiado y documentado:

- **El formato de `specs/` de `sdd`** (`scripts/release_specs.py`): fases y su
  huella, tareas, requisitos, `Tipo`, `Origen` y lo que cita el plan. Una
  prueba de contrato crea y aprueba una feature con el `sdd.py` real y
  comprueba que `release` la lee igual.
- **La trazabilidad de `sdd`**, como comando (ver arriba). La misma prueba de
  contrato lee el `trace --feature` real del repositorio.
- **El analizador de comandos de los guardrails**, cuarta copia: de
  `architecture`, que copia el de `discovery`, que copia el de
  `plugins/sdd/scripts/sdd_bash.py`. Las cuatro se nombran entre sí, y sus
  selftests usan la misma lista de casos.

## Pruebas

```bash
python3 plugins/release/tests/selftest.py
```

Cada prueba cita el requisito de la feature de este repositorio que comprueba
(`test_F010_R0NN_…`). Las features de prueba se escriben en el formato de
`sdd`, con un `sdd.py` falso (`SDD_SCRIPT`) para la trazabilidad; solo la
prueba de contrato usa el real. El selftest falla si un código de hallazgo
declarado no se prueba.
