"""
sdd_operate.py - lectura de los incidentes que deja el plugin operate.

`sdd.py new I001-A2` crea una feature de correccion desde una accion del
postmortem de un incidente (feature 011, D7). Para eso lee
operations/incidents.md (el registro: si no existe, el traspaso no se activa)
y operations/incidents/I001-slug.md, y comprueba que el postmortem esta
aprobado y no cambio despues.

Los plugins no comparten codigo: lo que aqui se lee del formato de operate es
una copia de plugins/operate/scripts/operate.py (incident_files, actions, la
fila Versión afectada y las secciones del incidente). La huella es la de
sdd_product.py, copia de la de discovery, la misma que usa operate. La prueba
test_F011_R013_contrato_con_operate del selftest de sdd la contrasta con el
operate.py real cuando esta en el repositorio.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdd_product as product  # noqa: E402

OPS_DIR = "operations"
INCIDENTS_DIR = "incidents"
REGISTRY = "incidents.md"

# Un ID de accion de un postmortem: I001-A2 (sin distinguir mayusculas).
ACTION_ARG = re.compile(r"^[Ii](\d{3,})-[Aa](\d+)$")
INCIDENT_FILE = re.compile(r"^(I\d{3,})(?:-[^/]*)?\.md$")
ACTION_HEAD = re.compile(r"^###\s+([Ii]\d{3,}-[Aa]\d+)(?![0-9])\s*[—–:-]?\s*(.*)$")
FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$")


def has_registry(root):
    """El traspaso desde una accion solo existe con el registro de operate."""
    return (Path(root) / OPS_DIR / REGISTRY).is_file()


def section(text, title):
    """Cuerpo de la seccion de nivel 2 title, sin las notas en blockquote."""
    wanted = product.norm(title)
    out, capturing = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m and len(m.group(1)) <= 2:
            if capturing:
                break
            capturing = len(m.group(1)) == 2 and product.norm(m.group(2)) == wanted
            continue
        if capturing and not line.lstrip().startswith(">"):
            out.append(line)
    return "\n".join(out).strip()


def incident(root, iid):
    """{id, rel, text, state, version} del incidente iid, o None. Si dos
    archivos tienen el mismo ID, cuenta el primero por nombre (como operate)."""
    base = Path(root) / OPS_DIR / INCIDENTS_DIR
    try:
        paths = sorted(p for p in base.iterdir()
                       if p.is_file() and INCIDENT_FILE.match(p.name)
                       and INCIDENT_FILE.match(p.name).group(1) == iid)
    except OSError:
        return None
    if not paths:
        return None
    text = paths[0].read_text(encoding="utf-8", errors="replace")
    head = text[:product._header_end(text)]
    m = re.search(r"^\|\s*Versi[oó]n afectada\s*\|\s*([^|\n]*?)\s*\|", head, re.M)
    return {"id": iid, "rel": f"{OPS_DIR}/{INCIDENTS_DIR}/{paths[0].name}", "text": text,
            "state": product.artifact_state(text), "version": m.group(1) if m else ""}


def action(text, aid):
    """{id, title, what} de la accion aid de la seccion Acciones, o None."""
    current = None
    for line in section(text, "acciones").splitlines():
        m = ACTION_HEAD.match(line)
        if m:
            if current:
                break
            if m.group(1).upper() == aid:
                current = {"id": aid, "title": m.group(2).strip(), "what": ""}
            continue
        f = FIELD.match(line)
        if current and f and product.norm(f.group(1)) == "que":
            current["what"] = f.group(2).strip()
    return current
