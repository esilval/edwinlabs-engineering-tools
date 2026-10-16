#!/usr/bin/env python3
"""
sdd_product.py - lectura del producto que deja el plugin discovery.

`sdd.py new B03` crea una feature desde una candidata del backlog de
discovery. Para eso lee product/brief.md, product/backlog.md y
product/sources/, y comprueba que el producto esta aprobado y no cambio
despues de aprobarse.

Los plugins no comparten codigo: lo que aqui se lee del formato de discovery,
y su huella de aprobacion, es una copia de plugins/discovery/scripts/discovery.py.
Un cambio en una copia se replica en la otra; la prueba de contrato del
selftest de sdd las compara con el discovery real cuando esta en el repo.
"""

import hashlib
import re
from pathlib import Path

PRODUCT_DIR = "product"
BRIEF = "brief.md"
BACKLOG = "backlog.md"


# --------------------------------------------------------------------------
# Huella y Estado. Copia de discovery.py: norm, _squash, text_digest,
# STATUS_ROW, _header_end, doc_status, approval_digest, content_digest.
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
    """Minusculas sin acentos, para comparar etiquetas."""
    return text.lower().translate(ACCENTS)


def _squash(line):
    line = re.sub(r"\s*\|\s*", "|", line.strip())
    return re.sub(r"\s+", " ", line)


def text_digest(text):
    """Huella que ignora espacios sobrantes y lineas en blanco."""
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
    """Huella de todo menos la fila Estado de la cabecera."""
    end = _header_end(text)
    return text_digest(STATUS_ROW.sub("", text[:end], count=1) + text[end:])


# --------------------------------------------------------------------------
# Aprobacion del producto
# --------------------------------------------------------------------------

def artifact_state(text):
    """
    'missing' | 'draft' | 'approved' | 'stale'. Aprobado es
    'Approved · <huella>' con la huella del contenido actual; un 'Approved'
    sin huella no cuenta, como en discovery.
    """
    if text is None:
        return "missing"
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    stamp = approval_digest(text)
    if not (words and words[0].strip("`*_") in APPROVED and stamp):
        return "draft"
    return "approved" if stamp == content_digest(text) else "stale"


def read_product(root, name):
    path = Path(root) / PRODUCT_DIR / name
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def product_approval(root):
    """{"brief.md": estado, "backlog.md": estado}, con los estados de artifact_state."""
    return {name: artifact_state(read_product(root, name)) for name in (BRIEF, BACKLOG)}


APPROVAL_PROBLEM = {
    "missing": "no existe: lo crea /discovery:decompose",
    "draft": "no está aprobado: lo aprueba el usuario con /discovery:approve",
    "stale": "cambió después de aprobarse: el usuario lo revisa y lo aprueba de "
             "nuevo con /discovery:approve",
}


# --------------------------------------------------------------------------
# Objetivos, candidatas y fuentes. Copia de discovery.py: section,
# ITEM_HEAD, ITEM_FIELD, parse_items, las expresiones de citas y el formato
# de product/sources/Dn-slug.md con secciones '## 4 Titulo'.
# --------------------------------------------------------------------------

SOURCES_DIR = "sources"
SOURCE_FILE = re.compile(r"^D(\d+)-[a-z0-9-]+\.md$")
ITEM_HEAD = re.compile(r"^#{2,5}\s*(?=([GB]\d+)\b)", re.M)
ITEM_FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$", re.M)
DOC_REF = re.compile(r"(?<![A-Za-z0-9])D(\d+)§(\d+(?:\.\d+)*)")
GOAL_REF = re.compile(r"(?<![A-Za-z0-9])G(\d+)(?![0-9])")
CAND_REF = re.compile(r"(?<![A-Za-z0-9])B(\d{2,})(?![0-9])")


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
    """Items '### G1 — titulo' o '### B03 — titulo' con campos '- **Campo:** valor'."""
    items = []
    blocks = ITEM_HEAD.split(text or "")
    for i in range(1, len(blocks) - 1, 2):
        iid, block = blocks[i], blocks[i + 1]
        if not iid.startswith(prefix):
            continue
        head, _, rest = block.partition("\n")
        title = re.sub(rf"^{iid}\s*[—–:-]?\s*", "", head).strip()
        rest = re.split(r"^#{1,6}\s", rest, maxsplit=1, flags=re.M)[0]
        fields = {norm(k): v.strip() for k, v in ITEM_FIELD.findall(rest)}
        items.append({"id": iid, "title": title, "fields": fields})
    return items


def candidates(root):
    """{id: candidata} del backlog. 'state' es la primera palabra del campo Estado."""
    out = {}
    for c in parse_items(section(read_product(root, BACKLOG) or "", "candidatas",
                                 "candidates"), "B"):
        raw = norm(c["fields"].get("estado", "")).replace("`", "").replace("_", "")
        c["state"] = (raw.split() or ["candidata"])[0]
        out.setdefault(c["id"], c)  # un ID repetido: vale el primero, como en discovery
    return out


def candidate(root, cid):
    """La candidata con ese ID (sin distinguir mayusculas), o None."""
    return candidates(root).get(cid.upper())


def goals(root):
    """{id: {id, title, description}} de los objetivos del brief."""
    out = {}
    for g in parse_items(section(read_product(root, BRIEF) or "", "objetivos", "goals"), "G"):
        out.setdefault(g["id"], {"id": g["id"], "title": g["title"],
                                 "description": g["fields"].get("descripcion", "")})
    return out


def refs(text):
    """
    Citas de un campo: secciones Dn§x, objetivos y candidatas, en orden de
    aparicion. No es una copia de refs() de discovery: usa sus expresiones,
    pero conserva el orden (la fila Origen lo respeta) y no lista documentos.
    """
    def ordered(found):
        seen = []
        for item in found:
            if item not in seen:
                seen.append(item)
        return seen
    text = text or ""
    return {
        "sections": ordered(f"D{d}§{s}" for d, s in DOC_REF.findall(text)),
        "goals": ordered(f"G{g}" for g in GOAL_REF.findall(text)),
        "candidates": ordered(f"B{b}" for b in CAND_REF.findall(text)),
    }


def source_section(root, ref):
    """
    {"ref", "file", "section", "title"} de una cita D2§4.2. "file" es la ruta
    relativa del documento ingerido, o None si ya no existe; "title" es el de
    la seccion ('## 4.2 Titulo'), o None si no se encuentra.
    """
    did, _, number = ref.partition("§")
    out = {"ref": ref, "file": None, "section": number, "title": None}
    base = Path(root) / PRODUCT_DIR / SOURCES_DIR
    try:
        files = sorted(p for p in base.iterdir()
                       if SOURCE_FILE.match(p.name) and p.name.startswith(did + "-"))
    except OSError:
        return out
    if not files:
        return out
    out["file"] = f"{PRODUCT_DIR}/{SOURCES_DIR}/{files[0].name}"
    try:
        text = files[0].read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    # Solo el contenido ingerido, y fuera de bloques de codigo: discovery no
    # numera un encabezado que esta dentro de ``` (su _outside_fences).
    _head, marker, body = text.partition("<!-- discovery:contenido -->")
    heading = re.compile(rf"^#{{1,6}}\s+{re.escape(number)}\.?\s+(.+?)\s*$")
    fence = None
    for line in (body if marker else text).splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            mark = stripped[:3]
            fence = None if fence == mark else (fence or mark)
            continue
        if fence:
            continue
        m = heading.match(line)
        if m:
            out["title"] = m.group(1)
            break
    return out


def approval_problems(root):
    """
    Lista de frases con lo que impide usar el producto, vacia si brief y
    backlog estan aprobados y sin cambios.
    """
    return [f"product/{name} {APPROVAL_PROBLEM[state]}"
            for name, state in product_approval(root).items() if state != "approved"]
