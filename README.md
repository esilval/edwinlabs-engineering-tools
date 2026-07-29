# EdwinLabs Engineering Tools

Marketplace de plugins de [Claude Code](https://code.claude.com/docs).

## Instalación

```bash
claude plugin marketplace add esilval/edwinlabs-engineering-tools
claude plugin install sdd --scope user
```

En VS Code: escribe `/plugins`, pestaña **Marketplaces**, añade
`esilval/edwinlabs-engineering-tools`, y luego instala desde la pestaña
**Plugins**.

## Plugins

| Plugin | Qué hace |
| ------ | -------- |
| [`sdd`](plugins/sdd) | Desarrollo orientado a especificaciones, con una compuerta que impide escribir código sin especificación y trazabilidad requisito → tarea → prueba. |

## Estructura del repositorio

```
.claude-plugin/marketplace.json   catálogo; debe estar en la raíz
plugins/<nombre>/                 un directorio por plugin
scripts/validate.py               validación estructural, la misma que corre CI
.github/workflows/validate.yml    CI
```

El `marketplace.json` va en la raíz del repositorio, no dentro de un plugin.
Cada `source` es una ruta relativa a la raíz y debe empezar por `./`.

## Añadir un plugin

1. Crea `plugins/<nombre>/.claude-plugin/plugin.json` con al menos `name`.
2. Añade la entrada correspondiente a `.claude-plugin/marketplace.json`.
3. `python3 scripts/validate.py --strict`
4. `claude plugin validate .` — comprueba cosas que el script no cubre.

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
