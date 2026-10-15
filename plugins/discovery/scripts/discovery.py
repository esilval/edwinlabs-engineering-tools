#!/usr/bin/env python3
"""
discovery.py - utilidades deterministas del plugin discovery.

Todo lo que no requiere criterio vive aqui: identificadores de documentos,
objetivos y candidatas, numeracion de secciones, huellas, comprobacion de
coherencia y aprobacion. Las skills solo redactan y preguntan.

El plugin solo escribe dentro de product/. No lee ni escribe specs/: es una
etapa independiente, unida a las demas por archivos.

Subcomandos:
  (se anaden en cada tarea de la feature 001)
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

PRODUCT_DIR = "product"


# --------------------------------------------------------------------------
# Localizacion del proyecto y escritura confinada a product/
# --------------------------------------------------------------------------

def project_root(payload=None):
    """Raiz del proyecto. CLAUDE_PROJECT_DIR es la fuente autoritativa."""
    for candidate in (
        os.environ.get("CLAUDE_PROJECT_DIR"),
        (payload or {}).get("cwd"),
        os.getcwd(),
    ):
        if candidate:
            return Path(candidate).resolve()
    return Path.cwd().resolve()


def product_root(root):
    return root / PRODUCT_DIR


class OutsideProduct(ValueError):
    """Intento de escribir fuera de product/."""


def product_path(root, rel):
    """
    Ruta absoluta de `rel` dentro de product/. Lanza OutsideProduct si `rel`
    escapa del directorio (`..`, ruta absoluta, enlace): el plugin no toca
    nada fuera de su etapa.
    """
    base = product_root(root).resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        raise OutsideProduct(f"{rel} queda fuera de {PRODUCT_DIR}/")
    return target


def write_product(root, rel, text):
    """Unica via de escritura del plugin."""
    target = product_path(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# --------------------------------------------------------------------------
# Huellas y campo Estado
#
# Copia deliberada de la logica de sdd (sdd_trace.py): la constitucion pide
# que los plugins se unan solo por archivos, asi que no se importa codigo de
# otro plugin. Si cambia la regla de normalizacion aqui, cambiala alli.
# --------------------------------------------------------------------------

ACCENTS = str.maketrans(
    "áàäâéèëê"
    "íìïîóòöô"
    "úùüûñç",
    "aaaaeeeeiiiioooouuuunc",
)


def norm(text):
    """Minusculas sin acentos, para comparar etiquetas y buscar palabras."""
    return text.lower().translate(ACCENTS)


def _squash(line):
    """Normaliza espacios y relleno de tablas para comparar lineas."""
    line = re.sub(r"\s*\|\s*", "|", line.strip())
    return re.sub(r"\s+", " ", line)


def text_digest(text):
    """
    Huella de un texto: ignora espacios sobrantes y lineas en blanco, porque
    reformatear no es cambiar el contenido.
    """
    lines = [_squash(raw) for raw in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


STATUS_ROW = re.compile(
    r"^(\|\s*(?:Estado|Status)\s*\|\s*)([^|\n]*?)(\s*\|)", re.I | re.M
)
APPROVED = {"approved", "aprobado", "aprobada"}
DIGEST = re.compile(r"\b([0-9a-f]{12})\b")


def _header_end(text):
    """Fin de la cabecera: el primer encabezado de nivel 2."""
    m = re.search(r"^##\s", text, re.M)
    return m.start() if m else len(text)


def doc_status(text):
    """Valor del campo Estado de la cabecera, o None si no existe."""
    text = text or ""
    m = STATUS_ROW.search(text, 0, _header_end(text))
    return m.group(2).strip() if m else None


def is_approved(text):
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    return bool(words) and words[0].strip("`*_") in APPROVED


def set_status(text, value):
    """Devuelve (texto_nuevo, cambiado?)."""
    end = _header_end(text)
    head, n = STATUS_ROW.subn(lambda m: m.group(1) + value + m.group(3),
                              text[:end], count=1)
    return head + text[end:], bool(n)


def content_digest(text):
    """Huella del contenido revisable: todo menos la fila Estado de la
    cabecera, que es donde se guarda la propia huella."""
    end = _header_end(text)
    return text_digest(STATUS_ROW.sub("", text[:end], count=1) + text[end:])


def approval_digest(text):
    """Huella guardada al aprobar ('Approved · 3f9a2c1b0d4e'), o None."""
    m = DIGEST.search(doc_status(text) or "")
    return m.group(1) if m else None


def is_stale(text):
    """True si el artefacto cambio despues de aprobarse."""
    stamp = approval_digest(text)
    return bool(is_approved(text) and stamp and stamp != content_digest(text))


# --------------------------------------------------------------------------

COMMANDS = {}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
