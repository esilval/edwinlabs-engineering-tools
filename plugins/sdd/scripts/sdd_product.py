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


def approval_problems(root):
    """
    Lista de frases con lo que impide usar el producto, vacia si brief y
    backlog estan aprobados y sin cambios.
    """
    return [f"product/{name} {APPROVAL_PROBLEM[state]}"
            for name, state in product_approval(root).items() if state != "approved"]
