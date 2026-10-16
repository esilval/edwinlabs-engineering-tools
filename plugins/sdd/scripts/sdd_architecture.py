#!/usr/bin/env python3
"""
sdd_architecture.py - lectura de la arquitectura que deja el plugin architecture.

Con architecture/ en el proyecto, sdd planifica sobre ella: da al plan los
componentes, las decisiones vigentes y los estandares (arch-context), comprueba
las decisiones que cita el plan (trace), propone decisiones nuevas
(propose-adr) y aloja la candidata del traspaso en sus componentes. Sin
architecture/, nada de esto se activa.

Los plugins no comparten codigo: lo que aqui se lee del formato de architecture
(componentes, ADR y su estado, estandares, aprobacion del conjunto) es una
copia de plugins/architecture/scripts/architecture.py. La huella es la de
sdd_product.py, a su vez copia de la de discovery, igual que la de
architecture. La prueba de contrato del selftest de sdd compara esta lectura
con el architecture.py real cuando esta en el repositorio.
"""

import re
from pathlib import Path

import sdd_product as product

ARCH_DIR = "architecture"
ADR_DIR = "adr"
SET_FILES = ("quality.md", "components.md", "standards.md", "questions.md")

# Copia de architecture.py: cualquier .md que empiece por cuatro digitos es una
# decision, aunque su nombre no siga NNNN-slug.md.
ADR_FILE = re.compile(r"^(\d{4})(?:[-_.].*)?\.md$")
ADR_REF = re.compile(r"(?<![A-Za-z0-9])ADR-(\d{4})(?![0-9])")
# Items de cualquier prefijo (C1, S1); parse_items filtra por el exacto.
ITEM_HEAD = re.compile(r"^#{2,5}\s*(?=([A-Z]\d+)\b)", re.M)


def exists(root):
    """El proyecto tiene arquitectura si existe architecture/ en su raiz."""
    return (Path(root) / ARCH_DIR).is_dir()


def read_arch(root, name):
    try:
        return (Path(root) / ARCH_DIR / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def parse_items(text, prefix):
    """Items '### C1 — titulo' con campos '- **Campo:** valor', en orden."""
    items = []
    blocks = ITEM_HEAD.split(text or "")
    for i in range(1, len(blocks) - 1, 2):
        iid, block = blocks[i], blocks[i + 1]
        if not re.match(rf"^{prefix}\d+$", iid):
            continue
        head, _, rest = block.partition("\n")
        title = re.sub(rf"^{iid}\s*[—–:-]?\s*", "", head).strip()
        rest = re.split(r"^#{1,6}\s", rest, maxsplit=1, flags=re.M)[0]
        fields = {product.norm(k): v.strip() for k, v in product.ITEM_FIELD.findall(rest)}
        items.append({"id": iid, "title": title, "fields": fields})
    return items


def header_fields(text):
    """{campo: valor} de la tabla de cabecera (antes del primer ##)."""
    head = (text or "")[:product._header_end(text or "")]
    rows = re.findall(r"^\|\s*([^|\n]+?)\s*\|\s*([^|\n]*?)\s*\|\s*$", head, re.M)
    return {product.norm(k): v for k, v in rows if not set(k) <= set("-: ")}


def components(root):
    """[{id, title, responsibility, candidates: [B01, …]}] de components.md."""
    out = []
    for c in parse_items(product.section(read_arch(root, "components.md"), "componentes"), "C"):
        f = c["fields"]
        out.append({"id": c["id"], "title": c["title"],
                    "responsibility": f.get("responsabilidad", ""),
                    "candidates": [f"B{b}" for b in product.CAND_REF.findall(
                        f.get("candidatas", ""))]})
    return out


def standards(root):
    """[{id, title, kind, detail, adr}] de standards.md."""
    out = []
    for s in parse_items(product.section(read_arch(root, "standards.md"), "estandares"), "S"):
        f = s["fields"]
        out.append({"id": s["id"], "title": s["title"], "kind": f.get("tipo", ""),
                    "detail": f.get("detalle", ""), "adr": f.get("decision", "")})
    return out


def adr_state(text):
    """'draft' | 'proposed' | 'approved' | 'stale' | 'rejected' | 'superseded',
    con la regla de architecture.py."""
    status = product.norm(product.doc_status(text) or "").strip("`*_ ")
    first = (status.split() or ["draft"])[0]
    if first in ("proposed", "propuesta", "propuesto"):
        return "proposed"
    if first in ("rejected", "rechazada", "rechazado"):
        return "rejected"
    if first in ("superseded", "sustituida", "sustituido"):
        return "superseded"
    state = product.artifact_state(text)
    return state if state in ("approved", "stale") else "draft"


def adrs(root):
    """Decisiones ordenadas por numero: [{id, number, file, title, state,
    superseded_by, motive}]."""
    base = Path(root) / ARCH_DIR / ADR_DIR
    try:
        files = sorted(p for p in base.iterdir() if ADR_FILE.match(p.name))
    except OSError:
        return []
    out = []
    for path in files:
        # Como en architecture.py: un ADR que no se puede leer cuenta como
        # borrador y ocupa su numero (si no, next_adr lo reciclaria).
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        number = ADR_FILE.match(path.name).group(1)
        head = re.search(r"^#\s+(.*)$", text, re.M)
        title = re.sub(r"^ADR-\d{4}\s*[—–:-]?\s*", "", head.group(1)).strip() if head else ""
        state = adr_state(text)
        sup = ADR_REF.search(product.doc_status(text) or "") if state == "superseded" else None
        out.append({"id": f"ADR-{number}", "number": int(number),
                    "file": f"{ARCH_DIR}/{ADR_DIR}/{path.name}", "title": title,
                    "state": state, "superseded_by": f"ADR-{sup.group(1)}" if sup else None,
                    "motive": header_fields(text).get("motivo", "")})
    return out


def next_adr(root):
    """Siguiente ADR libre: maximo + 1 sobre todos los archivos, nunca reciclado."""
    used = [a["number"] for a in adrs(root)]
    return f"ADR-{(max(used) if used else 0) + 1:04d}"


def approval_problems(root):
    """
    Frases con lo que impide dar la arquitectura por aprobada, vacia si los
    cuatro artefactos y los ADR vigentes estan aprobados y sin cambios. Los
    ADR propuestos, rechazados o sustituidos no cuentan: se deciden aparte.
    """
    problem = {
        "missing": "no existe: lo crea /architecture:init",
        "draft": "no está aprobado: lo aprueba el usuario con /architecture:approve",
        "stale": "cambió después de aprobarse: el usuario lo revisa y lo aprueba de "
                 "nuevo con /architecture:approve",
    }
    out = []
    for name in SET_FILES:
        state = product.artifact_state(read_arch(root, name))
        if state != "approved":
            out.append(f"{ARCH_DIR}/{name} {problem[state]}")
    for a in adrs(root):
        if a["state"] in ("draft", "stale"):
            out.append(f"{a['file']} {problem[a['state']]}")
    return out
