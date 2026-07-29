#!/usr/bin/env python3
"""
Valida la estructura del marketplace y de cada plugin que contiene.

Replica las comprobaciones de `claude plugin validate` que no necesitan la CLI,
para poder correr en CI sin instalar ni autenticar Claude Code. No sustituye a
`claude plugin validate .`, que conviene ejecutar en local antes de publicar.

Uso:  python3 scripts/validate.py [--strict]
      --strict trata los avisos como errores.
"""

import json
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_FIELDS = {
    "name", "description", "disable-model-invocation", "user-invocable",
    "argument-hint", "allowed-tools", "model", "context", "agent", "hooks",
    "paths", "arguments", "license", "compatibility", "metadata", "effort",
}

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def check_marketplace():
    path = ROOT / ".claude-plugin" / "marketplace.json"
    if not path.is_file():
        err("Falta .claude-plugin/marketplace.json en la raiz del repo.")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(f"marketplace.json no parsea: {exc}")
        return []

    if not data.get("name"):
        err("marketplace.json: falta 'name'.")
    elif not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", data["name"]):
        err(f"marketplace.json: 'name' debe ser kebab-case, no {data['name']!r}.")

    entries = data.get("plugins")
    if not isinstance(entries, list) or not entries:
        err("marketplace.json: 'plugins' debe ser una lista no vacia.")
        return []

    seen, resolved = set(), []
    for i, entry in enumerate(entries):
        tag = f"plugins[{i}]"
        name = entry.get("name")
        if not name:
            err(f"{tag}: falta 'name'.")
            continue
        if name in seen:
            err(f"{tag}: nombre duplicado {name!r}.")
        seen.add(name)

        source = entry.get("source")
        if not isinstance(source, str):
            err(f"{tag} ({name}): 'source' debe ser una cadena.")
            continue
        if not source.startswith("./"):
            err(f"{tag} ({name}): 'source' debe empezar por './', no {source!r}.")
            continue
        if ".." in Path(source).parts:
            err(f"{tag} ({name}): 'source' sale del repo ({source}).")
            continue

        target = ROOT / source[2:]
        if not target.is_dir():
            err(f"{tag} ({name}): 'source' no existe: {source}")
            continue
        if not entry.get("description"):
            warn(f"{tag} ({name}): sin 'description'; no se vera nada en /plugins.")
        resolved.append((name, target, entry))
    return resolved


def check_plugin(entry_name, root, entry):
    tag = f"[{entry_name}]"
    manifest = root / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        err(f"{tag} falta .claude-plugin/plugin.json")
        return
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(f"{tag} plugin.json no parsea: {exc}")
        return

    if data.get("name") != entry_name:
        warn(f"{tag} plugin.json name={data.get('name')!r} difiere de la entrada "
             f"{entry_name!r}. Manda la entrada, asi que las skills seran "
             f"/{entry_name}:*")
    if "version" in data and "version" in entry and data["version"] != entry["version"]:
        err(f"{tag} 'version' distinta en plugin.json y en la entrada.")

    # Solo plugin.json vive en .claude-plugin/
    intrusos = [p.name for p in (root / ".claude-plugin").iterdir()
                if p.name != "plugin.json"]
    if intrusos:
        err(f"{tag} .claude-plugin/ solo admite plugin.json; sobra: {intrusos}")

    for componente in ("skills", "agents", "hooks", "commands"):
        if (root / ".claude-plugin" / componente).exists():
            err(f"{tag} {componente}/ esta dentro de .claude-plugin/; "
                "va en la raiz del plugin.")

    # Skills
    skills = sorted((root / "skills").glob("*/SKILL.md"))
    if not skills and not (root / "SKILL.md").is_file():
        warn(f"{tag} sin skills.")
    for skill in skills:
        carpeta = skill.parent.name
        texto = skill.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
        if not m:
            err(f"{tag} {carpeta}/SKILL.md sin frontmatter YAML.")
            continue
        campos = {}
        for linea in m.group(1).splitlines():
            if ":" in linea and not linea.startswith((" ", "\t", "-")):
                k, _, v = linea.partition(":")
                campos[k.strip()] = v.strip()
        desconocidos = set(campos) - SKILL_FIELDS
        if desconocidos:
            warn(f"{tag} {carpeta}: campos no reconocidos {sorted(desconocidos)}")
        if not campos.get("description"):
            err(f"{tag} {carpeta}: falta 'description', que es el mecanismo "
                "de activacion.")
        if campos.get("name") and campos["name"] != carpeta:
            warn(f"{tag} {carpeta}: name={campos['name']!r} no coincide con la carpeta.")

    # Hooks
    hooks = root / "hooks" / "hooks.json"
    if hooks.is_file():
        try:
            conf = json.loads(hooks.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            err(f"{tag} hooks.json no parsea: {exc}")
        else:
            for evento, grupos in (conf.get("hooks") or {}).items():
                for grupo in grupos:
                    for h in grupo.get("hooks", []):
                        if h.get("type") not in {"command", "http", "mcp_tool",
                                                 "prompt", "agent"}:
                            err(f"{tag} hooks.json {evento}: type "
                                f"{h.get('type')!r} no valido.")
                        if h.get("type") == "command" and "timeout" not in h:
                            warn(f"{tag} hooks.json {evento}: sin 'timeout'; "
                                 "el defecto son 600s.")

    # Scripts en Python
    for script in sorted(root.rglob("*.py")):
        if "__pycache__" in script.parts:
            continue
        try:
            py_compile.compile(str(script), doraise=True, cfile="/tmp/_c.pyc")
        except py_compile.PyCompileError as exc:
            err(f"{tag} {script.relative_to(root)} no compila: {exc}")


def main():
    strict = "--strict" in sys.argv
    plugins = check_marketplace()
    for name, root, entry in plugins:
        check_plugin(name, root, entry)

    for w in warnings:
        print(f"AVISO  {w}")
    for e in errors:
        print(f"ERROR  {e}")

    total = f"{len(plugins)} plugin(s), {len(errors)} error(es), {len(warnings)} aviso(s)"
    if errors or (strict and warnings):
        print(f"FALLA: {total}")
        return 1
    print(f"OK: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
