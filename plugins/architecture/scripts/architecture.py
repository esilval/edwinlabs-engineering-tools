#!/usr/bin/env python3
"""
architecture.py - utilidades deterministas del plugin architecture.

Todo lo que no requiere criterio vive aqui: identificadores, comprobacion de
coherencia, huellas, aprobacion, revision de decisiones y guardrails. Las
skills solo redactan y preguntan.

El plugin lee product/ (lo deja discovery) y solo escribe en architecture/.
No importa codigo de otros plugins: es una etapa independiente, unida a las
demas por archivos.

Subcomandos:
  init                Crea architecture/ desde las plantillas, si el producto
                      de discovery esta aprobado.
  next-id Q|C|S|ADR   Siguiente atributo (Q3), componente (C2), estandar (S4)
                      o decision (ADR-0005) libre. Nunca se recicla.
  check [--json] [--check]
                      Coherencia de la arquitectura. --json emite
                      architecture.check/v1; --check sale con 1 si hay
                      errores (para CI).
  approve [--skill]   Aprueba el conjunto si check no da errores. Solo lo
                      lanza el usuario, con /architecture:approve.
  review ADR-NNNN aceptar|rechazar [--skill]
                      Decide una decision propuesta. Solo lo lanza el
                      usuario, con /architecture:review.
  guard               Hook PreToolUse: impide que el modelo apruebe.
  audit               Hook PostToolUse sobre Bash: revierte una aprobacion
                      escrita por un comando.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

PRODUCT_DIR = "product"
BRIEF = "brief.md"
BACKLOG = "backlog.md"
ARCH_DIR = "architecture"
ADR_DIR = "adr"
# Artefactos del conjunto, en el orden en que se crean y se informan.
SET_FILES = ("quality.md", "components.md", "standards.md", "questions.md")


# --------------------------------------------------------------------------
# Raiz del proyecto. Copia de find_upwards de plugins/sdd/scripts/sdd.py y
# plugins/discovery/scripts/discovery.py: los plugins no comparten codigo.
# --------------------------------------------------------------------------

def project_root(payload=None):
    """
    CLAUDE_PROJECT_DIR se usa tal cual. Sin ella (la inyeccion de comandos de
    una skill no la recibe), se sube desde el cwd hasta architecture/ y, si no
    lo hay, hasta product/, sin salir del repositorio.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    start = Path((payload or {}).get("cwd") or os.getcwd()).resolve()
    return (find_upwards(start, (ARCH_DIR,)) or find_upwards(start, (PRODUCT_DIR,))
            or start)


def find_upwards(start, markers):
    """El directorio mas cercano hacia arriba que contiene alguno de markers,
    sin pasar del primer .git; un directorio ilegible cuenta como vacio."""
    for directory in (start, *start.parents):
        try:
            if any((directory / m).is_dir() for m in markers):
                return directory
            if (directory / ".git").exists():
                return None
        except OSError:
            continue
    return None


# --------------------------------------------------------------------------
# Huella y Estado. Copia de discovery.py (norm, _squash, text_digest,
# STATUS_ROW, _header_end, doc_status, approval_digest, content_digest), igual
# que la de plugins/sdd/scripts/sdd_product.py. Un cambio en una se replica en
# las otras; la prueba de contrato del selftest lo comprueba contra discovery.
# --------------------------------------------------------------------------

ACCENTS = str.maketrans(
    "áàäâéèëê"
    "íìïîóòöô"
    "úùüûñç",
    "aaaaeeeeiiiioooouuuunc",
)
STATUS_ROW = re.compile(
    r"^(\|\s*(?:Estado|Status)\s*\|\s*)([^|\n]*?)(\s*\|)", re.I | re.M
)
APPROVED = {"approved", "aprobado", "aprobada"}
DIGEST = re.compile(r"\b([0-9a-f]{12})\b")


def norm(text):
    return text.lower().translate(ACCENTS)


def _squash(line):
    line = re.sub(r"\s*\|\s*", "|", line.strip())
    return re.sub(r"\s+", " ", line)


def text_digest(text):
    lines = [_squash(raw) for raw in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def _header_end(text):
    m = re.search(r"^##\s", text, re.M)
    return m.start() if m else len(text)


def doc_status(text):
    text = text or ""
    m = STATUS_ROW.search(text, 0, _header_end(text))
    return m.group(2).strip() if m else None


def approval_digest(text):
    m = DIGEST.search(doc_status(text) or "")
    return m.group(1) if m else None


def content_digest(text):
    end = _header_end(text)
    return text_digest(STATUS_ROW.sub("", text[:end], count=1) + text[end:])


def artifact_state(text):
    """'missing' | 'draft' | 'approved' | 'stale', con la regla de discovery:
    aprobado es 'Approved · <huella>' con la huella del contenido actual."""
    if text is None:
        return "missing"
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    stamp = approval_digest(text)
    if not (words and words[0].strip("`*_") in APPROVED and stamp):
        return "draft"
    return "approved" if stamp == content_digest(text) else "stale"


# --------------------------------------------------------------------------
# El producto de discovery. Copia de su formato (section, parse_items, citas);
# leerlo es el contrato entre plugins ya aprobado para sdd.
# --------------------------------------------------------------------------

# Diferencia con la copia de discovery ([GB]\d+): aqui la misma expresion lee
# tambien los items propios de architecture (Q1, C1, S1), y parse_items filtra
# por prefijo exacto. Para G y B el resultado es el mismo.
ITEM_HEAD = re.compile(r"^#{2,5}\s*(?=([A-Z]\d+)\b)", re.M)
ITEM_FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$", re.M)
DOC_REF = re.compile(r"(?<![A-Za-z0-9])D(\d+)§(\d+(?:\.\d+)*)")
GOAL_REF = re.compile(r"(?<![A-Za-z0-9])G(\d+)(?![0-9])")
CAND_REF = re.compile(r"(?<![A-Za-z0-9])B(\d{2,})(?![0-9])")


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_product(root, name):
    return read_text(Path(root) / PRODUCT_DIR / name)


def section(text, *titles):
    """Cuerpo de la seccion de nivel 2 cuyo titulo es uno de titles o empieza por el."""
    wanted = [norm(t) for t in titles]
    out, capturing = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m and len(m.group(1)) <= 2:
            if capturing:
                break
            title = norm(m.group(2))
            if len(m.group(1)) == 2 and any(title == w or title.startswith(w + " ")
                                            for w in wanted):
                capturing = True
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def parse_items(text, prefix):
    """Items '### X1 — titulo' con campos '- **Campo:** valor', en orden."""
    items = []
    blocks = ITEM_HEAD.split(text or "")
    for i in range(1, len(blocks) - 1, 2):
        iid, block = blocks[i], blocks[i + 1]
        if not re.match(rf"^{prefix}\d+$", iid):
            continue
        head, _, rest = block.partition("\n")
        title = re.sub(rf"^{iid}\s*[—–:-]?\s*", "", head).strip()
        rest = re.split(r"^#{1,6}\s", rest, maxsplit=1, flags=re.M)[0]
        fields = {norm(k): v.strip() for k, v in ITEM_FIELD.findall(rest)}
        items.append({"id": iid, "title": title, "fields": fields})
    return items


def product_problems(root):
    """
    Frases con lo que impide usar el producto, vacia si brief y backlog estan
    aprobados y sin cambios. Sin product/, una sola frase que lo dice.
    """
    if not (Path(root) / PRODUCT_DIR).is_dir():
        return ["no hay product/: la arquitectura parte del producto de discovery "
                "(/discovery:ingest, /discovery:decompose y /discovery:approve)"]
    problem = {
        "missing": "no existe: lo crea /discovery:decompose",
        "draft": "no está aprobado: lo aprueba el usuario con /discovery:approve",
        "stale": "cambió después de aprobarse: el usuario lo revisa y lo aprueba "
                 "de nuevo con /discovery:approve",
    }
    out = []
    for name in (BRIEF, BACKLOG):
        state = artifact_state(read_product(root, name))
        if state != "approved":
            out.append(f"product/{name} {problem[state]}")
    return out


def product_digests(root):
    """{'brief': huella, 'backlog': huella} del contenido actual del producto."""
    out = {}
    for key, name in (("brief", BRIEF), ("backlog", BACKLOG)):
        text = read_product(root, name)
        out[key] = content_digest(text) if text is not None else None
    return out


def product_goals(root):
    return {g["id"]: g for g in
            parse_items(section(read_product(root, BRIEF), "objetivos", "goals"), "G")}


def product_restriction_sections(root):
    """Secciones de documento (D1§5) que citan las viñetas de ## Restricciones
    (D3): una restriccion se cita por la seccion de la que sale."""
    body = section(read_product(root, BRIEF), "restricciones", "constraints")
    bullets = "\n".join(line for line in body.splitlines()
                        if re.match(r"^\s*[-*]\s+\S", line))
    return {f"D{d}§{s}" for d, s in DOC_REF.findall(bullets)}


def product_candidates(root):
    """{id: candidata} del backlog, con 'state' = primera palabra del Estado."""
    out = {}
    for c in parse_items(section(read_product(root, BACKLOG), "candidatas", "candidates"),
                         "B"):
        raw = norm(c["fields"].get("estado", "")).replace("`", "").replace("_", "")
        c["state"] = (raw.split() or ["candidata"])[0]
        out.setdefault(c["id"], c)
    return out


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------

def plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT")
                or Path(__file__).resolve().parent.parent)


def cmd_init(_args):
    """Copia las plantillas a architecture/ si el producto esta aprobado (R001).
    No sobrescribe: un artefacto que ya existe se deja como esta."""
    root = project_root()
    problems = product_problems(root)
    if problems:
        print("No se inicia la arquitectura: el producto de discovery no está listo.\n"
              + "".join(f"  - {p}\n" for p in problems), file=sys.stderr, end="")
        return 1
    arch = root / ARCH_DIR
    (arch / ADR_DIR).mkdir(parents=True, exist_ok=True)
    templates = plugin_root() / "templates"
    created, kept = [], []
    for name in SET_FILES:
        target = arch / name
        if target.exists():
            kept.append(name)
            continue
        target.write_text((templates / name).read_text(encoding="utf-8"), encoding="utf-8")
        created.append(name)
    print(json.dumps({"dir": ARCH_DIR, "created": created, "kept": kept,
                      "next": "/architecture:init redacta atributos y componentes"},
                     indent=2))
    return 0


COMMANDS = {
    "init": cmd_init,
}

# Un hook que revienta nunca debe bloquear al usuario: falla abierto.
HOOKS = {"guard", "audit"}

# Codigos de hallazgo declarados: el selftest exige probar cada uno.
FINDINGS = {}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[1]](argv[2:])
    except Exception as exc:  # noqa: BLE001
        if argv[1] in HOOKS:
            print(f"architecture.py {argv[1]}: {exc}", file=sys.stderr)
            return 0
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv))
