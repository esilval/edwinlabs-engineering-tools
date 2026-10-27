"""
operate_sources.py - lectura de los otros plugins para operate (feature 011, D3).

Los plugins no comparten codigo, se unen por archivos. Lo que aqui se lee del
formato de otro plugin es una copia documentada de su original:

- releases/ de release: la cabecera, el estado, la huella y la regla de version
  publicada son copia de plugins/release/scripts/release.py (content_digest,
  release_state, feature_list, releases, published).
- architecture/ de architecture: la aprobacion del conjunto, los atributos de
  calidad y el Motivo de los ADR son copia de plugins/architecture/scripts/
  architecture.py (header_fields, parse_items, artifact_state, adr_state,
  quality, adrs), como la de plugins/sdd/scripts/sdd_architecture.py.
- specs/ de sdd: features, la fila Origen y las citas ADR-NNNN del plan son
  copia de plugins/release/scripts/release_specs.py, a su vez copia de
  plugins/sdd/scripts/sdd_trace.py y sdd.py (feature_dirs, resolve,
  header_row, features_by_origin).

La huella es la misma en los tres: todo menos la fila Estado, sin espacios ni
lineas en blanco. Su original es plugins/discovery/scripts/discovery.py, y la
copian plugins/sdd/scripts/sdd_product.py (que usa sdd_architecture.py),
plugins/architecture/scripts/architecture.py y plugins/release/scripts/
release.py. Es tambien la de los artefactos propios de operate.

Un cambio de formato en un original se replica aqui; la prueba
test_F011_R003_contrato_con_los_demas del selftest de operate lo contrasta con
los release.py, architecture.py, discovery.py y sdd.py reales.

Solo lee: nunca escribe fuera de operations/.
"""

import hashlib
import re
from pathlib import Path

RELEASES_DIR = "releases"
ARCH_DIR = "architecture"
ADR_DIR = "adr"
SPECS_DIR = "specs"
# Artefactos del conjunto de architecture que tienen que estar aprobados.
SET_FILES = ("quality.md", "components.md", "standards.md", "questions.md")


# --------------------------------------------------------------------------
# Texto, Estado y huella (comun a release, architecture, sdd y operate)
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


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _squash(line):
    line = re.sub(r"\s*\|\s*", "|", line.strip())
    return re.sub(r"\s+", " ", line)


def _header_end(text):
    m = re.search(r"^##\s", text or "", re.M)
    return m.start() if m else len(text or "")


def doc_status(text):
    text = text or ""
    m = STATUS_ROW.search(text, 0, _header_end(text))
    return m.group(2).strip() if m else None


def header_row(text, name):
    """Valor de la fila '| name | valor |' de la cabecera, o None."""
    text = text or ""
    m = re.compile(rf"^\|\s*{re.escape(name)}\s*\|\s*([^|\n]*?)\s*\|", re.I | re.M).search(
        text, 0, _header_end(text))
    return m.group(1).strip() if m else None


def header_fields(text):
    """{campo: valor} de la tabla de cabecera (antes del primer ##)."""
    head = (text or "")[:_header_end(text or "")]
    rows = re.findall(r"^\|\s*([^|\n]+?)\s*\|\s*([^|\n]*?)\s*\|\s*$", head, re.M)
    return {norm(k): v for k, v in rows if not set(k) <= set("-: ")}


def text_digest(text):
    lines = [_squash(raw) for raw in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def content_digest(text):
    """Huella del contenido: todo menos la fila Estado, donde se guarda."""
    end = _header_end(text)
    return text_digest(STATUS_ROW.sub("", text[:end], count=1) + text[end:])


def is_approved(text):
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    return bool(words) and words[0].strip("`*_") in APPROVED


def approval_digest(text):
    m = DIGEST.search(doc_status(text) or "")
    return m.group(1) if m else None


def artifact_state(text):
    """'missing' | 'draft' | 'approved' | 'stale': aprobado es 'Approved ·
    <huella>' con la huella del contenido actual (architecture.py y
    release.py)."""
    if text is None:
        return "missing"
    stamp = approval_digest(text)
    if not (is_approved(text) and stamp):
        return "draft"
    return "approved" if stamp == content_digest(text) else "stale"


# --------------------------------------------------------------------------
# releases/ de release (release.py)
# --------------------------------------------------------------------------

RELEASE_FILE = re.compile(r"^v(\d+\.\d+\.\d+)\.md$")


def feature_list(value):
    """'008, 009' -> ['008', '009']; '—' o vacio -> []."""
    return [x for x in re.split(r"[,\s]+", (value or "").strip("`*_ ")) if x and x not in "—-"]


def releases(root):
    """[{version, rel, features, state, digest}] de releases/, por nombre."""
    out = []
    try:
        paths = sorted(p for p in (Path(root) / RELEASES_DIR).iterdir()
                       if p.is_file() and RELEASE_FILE.match(p.name))
    except OSError:
        return []
    for path in paths:
        text = read_text(path) or ""
        out.append({
            "version": RELEASE_FILE.match(path.name).group(1),
            "rel": f"{RELEASES_DIR}/{path.name}",
            "features": feature_list(header_row(text, "Features")),
            "state": artifact_state(text),
            "digest": content_digest(text),
        })
    return out


def release(root, version):
    """La version vX.Y.Z de releases/, o None si no existe."""
    return next((r for r in releases(root) if r["version"] == version), None)


def published(rel):
    """Publicada: aprobada alguna vez, aunque cambiara despues (D6 de 010)."""
    return rel is not None and rel["state"] in ("approved", "stale")


# --------------------------------------------------------------------------
# architecture/ de architecture (architecture.py)
# --------------------------------------------------------------------------

ITEM_HEAD = re.compile(r"^#{2,5}\s*(?=([A-Z]\d+)\b)", re.M)
ITEM_FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$", re.M)
ADR_FILE = re.compile(r"^(\d{4})(?:[-_.].*)?\.md$")
ADR_REF = re.compile(r"(?<![A-Za-z0-9])ADR-(\d{4})(?![0-9])")
GOAL_REF = re.compile(r"(?<![A-Za-z0-9])G(\d+)(?![0-9])")
QUALITY_REF = re.compile(r"(?<![A-Za-z0-9])Q(\d+)(?![0-9])")


def architecture_exists(root):
    return (Path(root) / ARCH_DIR).is_dir()


def read_arch(root, name):
    return read_text(Path(root) / ARCH_DIR / name)


def section(text, title):
    """Cuerpo de la seccion de nivel 2 cuyo titulo es title o empieza por el."""
    wanted = norm(title)
    out, capturing = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m and len(m.group(1)) <= 2:
            if capturing:
                break
            name = norm(m.group(2))
            capturing = len(m.group(1)) == 2 and (name == wanted
                                                  or name.startswith(wanted + " "))
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def parse_items(text, prefix):
    """Items '### Q1 — titulo' con campos '- **Campo:** valor', en orden."""
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


def adr_state(text):
    """'draft' | 'proposed' | 'approved' | 'stale' | 'rejected' | 'superseded'."""
    status = norm(doc_status(text) or "").strip("`*_ ")
    first = (status.split() or ["draft"])[0]
    if first in ("proposed", "propuesta", "propuesto"):
        return "proposed"
    if first in ("rejected", "rechazada", "rechazado"):
        return "rejected"
    if first in ("superseded", "sustituida", "sustituido"):
        return "superseded"
    state = artifact_state(text)
    return state if state in ("approved", "stale") else "draft"


def quality(root):
    """[{id, title, scenario, motive}] de los atributos de quality.md."""
    return [{"id": q["id"], "title": q["title"],
             "scenario": q["fields"].get("escenario", ""),
             "motive": q["fields"].get("motivo", "")}
            for q in parse_items(section(read_arch(root, "quality.md"), "atributos"), "Q")]


def adrs(root):
    """[{id, state, motive}] de architecture/adr/, por numero."""
    try:
        files = sorted(p for p in (Path(root) / ARCH_DIR / ADR_DIR).iterdir()
                       if ADR_FILE.match(p.name))
    except OSError:
        return []
    out = []
    for path in files:
        text = read_text(path) or ""
        out.append({"id": f"ADR-{ADR_FILE.match(path.name).group(1)}",
                    "state": adr_state(text),
                    "motive": header_fields(text).get("motivo", "")})
    return out


def architecture_problems(root):
    """Lo que impide dar la arquitectura por aprobada; vacio si lo esta. Los
    ADR propuestos, rechazados o sustituidos no cuentan (approval_problems de
    sdd_architecture.py)."""
    out = []
    for name in SET_FILES:
        state = artifact_state(read_arch(root, name))
        if state != "approved":
            out.append(f"{ARCH_DIR}/{name}: {state}")
    out += [f"{a['id']}: {a['state']}" for a in adrs(root) if a["state"] in ("draft", "stale")]
    return out


# --------------------------------------------------------------------------
# specs/ de sdd (release_specs.py, sdd.py)
# --------------------------------------------------------------------------

FEATURE_RE = re.compile(r"^(\d{3,})-[a-z0-9]+(?:-[a-z0-9]+)*$")


def feature_dirs(root):
    try:
        out = [p for p in (Path(root) / SPECS_DIR).iterdir()
               if p.is_dir() and FEATURE_RE.match(p.name)]
    except OSError:
        return []
    return sorted(out, key=lambda p: p.name)


def resolve(root, name):
    """Los directorios de feature que nombra name ('008' o '008-slug')."""
    name = (name or "").strip().rstrip("/").split("/")[-1]
    exact = [p for p in feature_dirs(root) if p.name == name]
    return exact or [p for p in feature_dirs(root) if p.name.split("-", 1)[0] == name]


# Como ORIGIN_ROW de sdd.py: 'Origen' tal cual, solo en la cabecera.
ORIGIN_ROW = re.compile(r"^\|\s*Origen\s*\|\s*([^|\n]*?)\s*\|", re.M)


def origin_groups(spec_text):
    """Grupos de la fila Origen ('B03 · G2 · D1§4'), o [] sin fila."""
    spec_text = spec_text or ""
    m = ORIGIN_ROW.search(spec_text, 0, _header_end(spec_text))
    return [g.strip() for g in m.group(1).split("·")] if m and m.group(1) else []


def feature(path):
    """{slug, title, goals, adrs} de una feature: los objetivos del segundo
    grupo de su Origen y las decisiones que cita su plan."""
    path = Path(path)
    spec = read_text(path / "spec.md") or ""
    head = re.search(r"^#\s+(?:Spec:\s*)?(.+?)\s*$", spec, re.M)
    groups = origin_groups(spec)
    goals = ["G" + n for n in GOAL_REF.findall(groups[1])] if len(groups) > 1 else []
    plan = read_text(path / "plan.md") or ""
    return {"slug": path.name, "title": head.group(1) if head else path.name,
            "goals": goals, "adrs": sorted({"ADR-" + n for n in ADR_REF.findall(plan)})}


def features_by_origin(root):
    """{primer elemento del Origen: feature}: la candidata o la accion que cada
    spec cita (features_by_origin de sdd.py)."""
    out = {}
    for path in feature_dirs(root):
        groups = origin_groups(read_text(path / "spec.md") or "")
        first = groups[0].upper() if groups else ""
        if first and first not in ("—", "-"):
            out.setdefault(first, path.name)
    return out
