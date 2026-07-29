#!/usr/bin/env python3
"""
sdd_quality.py - hook PostToolUse: control de calidad determinista.

Tras cada Write/Edit corre formateador y linter sobre EL ARCHIVO EDITADO, no
sobre el repositorio entero. Es el bucle de calidad mas barato que existe:
feedback inmediato sin gastar tokens en que el modelo se acuerde de comprobarlo.

Contrato con Claude Code:
  - exit 0  -> todo bien, silencio.
  - exit 2  -> stderr se muestra al modelo. En PostToolUse no deshace nada,
               solo informa; el modelo lee el error y corrige.
Los formateadores que reescriben el archivo no se consideran fallo.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# fmt: off
# Cada entrada: (binario, argumentos, tipo, binario_que_lo_hace_redundante)
TOOLCHAINS = {
    ".py": [
        ("ruff",       ["format", "{file}"],                "format", None),
        ("ruff",       ["check", "--fix", "{file}"],        "lint",   None),
        ("black",      ["-q", "{file}"],                     "format", "ruff"),
        ("flake8",     ["{file}"],                           "lint",   "ruff"),
    ],
    ".ts":  [("prettier", ["--write", "{file}"], "format", None),
             ("eslint",   ["--fix", "{file}"],   "lint",   None)],
    ".tf":  [("terraform", ["fmt", "{file}"],    "format", None)],
    ".go":  [("gofmt",  ["-w", "{file}"],        "format", None)],
    ".rs":  [("rustfmt", ["{file}"],             "format", None)],
    ".rb":  [("rubocop", ["-a", "{file}"],       "lint",   None)],
    ".sh":  [("shellcheck", ["{file}"],          "lint",   None)],
}
# fmt: on

for _ext in (".tsx", ".js", ".jsx", ".mjs", ".cjs"):
    TOOLCHAINS[_ext] = TOOLCHAINS[".ts"]
TOOLCHAINS[".bash"] = TOOLCHAINS[".sh"]
TOOLCHAINS[".tfvars"] = TOOLCHAINS[".tf"]

PER_COMMAND_TIMEOUT = 30


def resolve_bin(name, root):
    """Prefiere el binario local del proyecto antes que el global."""
    local = root / "node_modules" / ".bin" / name
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return shutil.which(name)


def build_plan(path, root, config):
    """Devuelve [(etiqueta, argv, tipo)] para el archivo dado."""
    ext = path.suffix.lower()
    override = (config.get("quality") or {}).get("commands", {}).get(ext)
    if override:
        plan = []
        for raw in override:
            parts = [p.replace("{file}", str(path)) for p in raw.split()]
            if parts and (shutil.which(parts[0]) or Path(parts[0]).is_file()):
                plan.append((parts[0], parts, "lint"))
        return plan

    plan, available = [], set()
    for name, args, kind, redundant_if in TOOLCHAINS.get(ext, []):
        if resolve_bin(name, root):
            available.add(name)
    for name, args, kind, redundant_if in TOOLCHAINS.get(ext, []):
        if redundant_if and redundant_if in available:
            continue
        binary = resolve_bin(name, root)
        if not binary:
            continue
        plan.append((name, [binary] + [a.replace("{file}", str(path)) for a in args], kind))
    return plan


def run(payload, root, config, is_exempt):
    qcfg = config.get("quality") or {}
    if not qcfg.get("enabled", True) or os.environ.get("SDD_NO_QUALITY") == "1":
        return 0

    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return 0

    try:
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        rel = path.relative_to(root)
    except (ValueError, OSError):
        return 0

    if not path.is_file() or is_exempt(rel):
        return 0

    plan = build_plan(path, root, config)
    if not plan:
        return 0

    before = path.read_bytes()
    failures, reformatted = [], False

    for name, argv, kind in plan:
        try:
            res = subprocess.run(
                argv, capture_output=True, text=True,
                timeout=qcfg.get("timeout", PER_COMMAND_TIMEOUT), cwd=str(root),
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if res.returncode != 0 and kind == "lint":
            detail = ((res.stdout or "") + (res.stderr or "")).strip()
            failures.append((name, detail[:1500]))

    if path.read_bytes() != before:
        reformatted = True

    if not failures:
        return 0

    lines = [f"Control de calidad SDD sobre {rel.as_posix()}:", ""]
    for name, detail in failures:
        lines.append(f"--- {name} ---")
        lines.append(detail or "(sin salida)")
        lines.append("")
    if reformatted:
        lines.append("Nota: un formateador reescribio el archivo. Vuelve a leerlo "
                     "antes de editarlo de nuevo.")
        lines.append("")
    lines.append("Corrige estos problemas y continua con la tarea. No es una "
                 "denegacion de permiso ni una peticion del usuario: es una "
                 "comprobacion automatica. No te detengas ni preguntes.")

    sys.stderr.write("\n".join(lines) + "\n")
    return 2
