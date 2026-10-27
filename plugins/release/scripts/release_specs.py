"""
release_specs.py - lectura de specs/ para el plugin release (feature 010, D3).

Copia documentada del formato de sdd: los plugins no comparten codigo, se unen
por archivos. Los originales estan en plugins/sdd/scripts/sdd_trace.py (norm,
section, STATUS_ROW, _header_end, doc_status, is_approved, TASK_STATE_LINE,
content_digest, is_stale, los requisitos de parse_spec, el estado de
parse_tasks y ADR_REF) y en plugins/sdd/scripts/sdd.py (FEATURE_RE,
feature_dirs y phase_approval). plugins/operate/scripts/operate_sources.py
copia de aqui features, resolve y la cabecera. Un cambio de formato en sdd se
replica aqui; la prueba test_F010_R002_contrato_con_sdd del selftest de
release lo contrasta con el sdd.py real.

Solo lee: nunca escribe en specs/.
"""

import hashlib
import re
from pathlib import Path

SPECS_DIR = "specs"
PHASES = (("spec.md", "spec"), ("plan.md", "plan"), ("tasks.md", "tasks"))

# sdd.py: FEATURE_RE
FEATURE_RE = re.compile(r"^(\d{3,})-[a-z0-9]+(?:-[a-z0-9]+)*$")

# sdd_trace.py: ACCENTS y norm
ACCENTS = str.maketrans(
    "áàäâéèëê"
    "íìïîóòöô"
    "úùüûñç",
    "aaaaeeeeiiiioooouuuunc",
)


def norm(text):
    return text.lower().translate(ACCENTS)


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


# --------------------------------------------------------------------------
# Features de specs/ (sdd.py: feature_dirs)
# --------------------------------------------------------------------------

def feature_dirs(root):
    base = Path(root) / SPECS_DIR
    try:
        out = [p for p in base.iterdir() if p.is_dir() and FEATURE_RE.match(p.name)]
    except OSError:
        return []
    return sorted(out, key=lambda p: p.name)


def resolve(root, name):
    """Los directorios de feature que nombra name ('008' o '008-slug'). Mas
    de uno solo si dos features comparten numero. Copia de named_features de
    sdd.py, la regla de sdd.py trace --feature."""
    name = (name or "").strip().rstrip("/").split("/")[-1]
    exact = [p for p in feature_dirs(root) if p.name == name]
    return exact or [p for p in feature_dirs(root) if p.name.split("-", 1)[0] == name]


def number(feature):
    """'008-diagramas' -> '008'."""
    return Path(feature).name.split("-", 1)[0]


# --------------------------------------------------------------------------
# Cabecera, Estado y huella (sdd_trace.py)
# --------------------------------------------------------------------------

STATUS_ROW = re.compile(
    r"^(\|\s*(?:Estado|Status)\s*\|\s*)([^|\n]*?)(\s*\|)", re.I | re.M
)
APPROVED = {"approved", "aprobado", "aprobada"}
TASK_STATE_LINE = re.compile(r"^\s*[-*]\s*\*\*\s*(?:Estado|Status)\s*:?\s*\*\*", re.I)
DIGEST = re.compile(r"\b([0-9a-f]{12})\b")


def _header_end(text):
    m = re.search(r"^##\s", text, re.M)
    return m.start() if m else len(text)


def _squash(line):
    line = re.sub(r"\s*\|\s*", "|", line.strip())
    return re.sub(r"\s+", " ", line)


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


def is_approved(text):
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    return bool(words) and words[0].strip("`*_") in APPROVED


def content_digest(text, fname):
    """Huella del contenido: sin la fila Estado y, en tasks.md, sin las lineas
    de estado de las tareas. Ignora espacios y lineas en blanco."""
    end = _header_end(text)
    head = STATUS_ROW.sub("", text[:end], count=1)
    lines = []
    for raw in (head + text[end:]).splitlines():
        if fname == "tasks.md" and TASK_STATE_LINE.match(raw):
            continue
        line = _squash(raw)
        if line:
            lines.append(line)
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()[:12]


def approval_digest(text):
    m = DIGEST.search(doc_status(text) or "")
    return m.group(1) if m else None


def phase_state(text, fname):
    """'missing' | 'draft' | 'stale' (cambio tras aprobarse) | 'approved',
    como phase_approval de sdd.py."""
    if text is None:
        return "missing"
    if not is_approved(text):
        return "draft"
    stamp = approval_digest(text)
    return "stale" if (stamp and stamp != content_digest(text, fname)) else "approved"


# --------------------------------------------------------------------------
# Contenido de spec, plan y tasks (sdd_trace.py: parse_spec, parse_tasks,
# parse_plan)
# --------------------------------------------------------------------------

REQ_ROW = re.compile(
    r"^\|\s*(R\d{2,})\s*\|\s*(MUST|SHOULD|COULD|DEBE|DEBERIA|PODRIA|"
    r"OBSOLETE|OBSOLETO|OBSOLETA|DEPRECATED)\s*\|\s*(.+?)\s*\|\s*$",
    re.I | re.M,
)
PRIORITY = {"DEBE": "MUST", "DEBERIA": "SHOULD", "PODRIA": "COULD",
            "OBSOLETO": "OBSOLETE", "OBSOLETA": "OBSOLETE", "DEPRECATED": "OBSOLETE"}
TASK_ID = re.compile(r"(?<![A-Za-z0-9])T(\d{2,})(?![0-9])")
FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$", re.M)
ADR_REF = re.compile(r"(?<![A-Za-z0-9])ADR-(\d{4})(?![0-9])")
TYPES = {"funcionalidad": "funcionalidad", "correccion": "corrección"}


def title(spec_text):
    m = re.search(r"^#\s+(?:Spec:\s*)?(.+?)\s*$", spec_text or "", re.M)
    return m.group(1) if m else ""


def requirements(spec_text):
    """[{id, priority}] de la tabla de requisitos, sin duplicados. La
    prioridad se normaliza como en sdd (OBSOLETO -> OBSOLETE)."""
    out, seen = [], set()
    for rid, prio, _body in REQ_ROW.findall(spec_text or ""):
        rid = rid.upper()
        if rid in seen:
            continue
        seen.add(rid)
        out.append({"id": rid, "priority": PRIORITY.get(prio.upper(), prio.upper())})
    # Fallback de parse_spec: requisitos declarados como encabezado.
    for m in re.finditer(r"^#{2,5}\s*(R\d{2,})\b[^\n]*\n(.*?)(?=^#{1,5}\s|\Z)",
                         spec_text or "", re.M | re.S):
        rid = m.group(1).upper()
        if rid in seen:
            continue
        seen.add(rid)
        head = m.group(0).upper()
        prio = next((x for x in ("MUST", "SHOULD", "COULD") if x in head), "MUST")
        out.append({"id": rid, "priority": prio})
    return out


def tasks(tasks_text):
    """[{id, title, state}] con state 'todo' | 'wip' | 'done'."""
    out, seen = [], set()
    for block in re.split(r"^#{2,5}\s*(?=T\d{2,}\b)", tasks_text or "", flags=re.M)[1:]:
        head, _, rest = block.partition("\n")
        m = TASK_ID.search(head)
        if not m or "T" + m.group(1) in seen:
            continue
        tid = "T" + m.group(1)
        seen.add(tid)
        fields = {norm(k): v.strip() for k, v in FIELD.findall(rest)}
        raw = fields.get("estado", fields.get("status", ""))
        state = "done" if "[x]" in raw.lower() else "wip" if "[~]" in raw else "todo"
        name = re.sub(r"^T\d{2,}\s*[—–:-]?\s*", "", head).strip()
        out.append({"id": tid, "title": name, "state": state})
    return out


def top_section(text, title_norm):
    """Cuerpo de la seccion '## <titulo>' (solo nivel 2, a diferencia de
    section de sdd_trace: el plan tiene tambien '### Modelo de datos' dentro
    de Diagramas), sin las notas en blockquote."""
    out, capturing = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and len(m.group(1)) <= 2:
            if capturing:
                break
            capturing = len(m.group(1)) == 2 and norm(m.group(2)).strip() == title_norm
            continue
        if capturing and not line.lstrip().startswith(">"):
            out.append(line)
    return "\n".join(out).strip()


def has_content(body):
    return bool(body) and norm(body).strip(" .") not in ("no aplica", "")


def plan_info(plan_text):
    """{adrs, contracts, data_model}: decisiones citadas y si las secciones
    Contratos y Modelo de datos tienen contenido."""
    return {
        "adrs": sorted({"ADR-" + n for n in ADR_REF.findall(plan_text or "")}),
        "contracts": has_content(top_section(plan_text, "contratos")),
        "data_model": has_content(top_section(plan_text, "modelo de datos")),
    }


def feature_type(spec_text):
    """(tipo, valor_escrito): tipo es 'funcionalidad', 'corrección' o None si
    el valor no es ninguno de los dos, tambien si esta vacio. Sin la fila,
    'funcionalidad' (R017, D5)."""
    raw = header_row(spec_text, "Tipo")
    if raw is None:
        return "funcionalidad", raw
    return TYPES.get(norm(raw).strip("`*_ .")), raw


def feature(path):
    """Todo lo que release necesita de una feature de specs/."""
    path = Path(path)
    texts = {fname: read_text(path / fname) for fname, _p in PHASES}
    spec = texts["spec.md"] or ""
    kind, raw = feature_type(spec)
    origin = header_row(spec, "Origen")
    info = plan_info(texts["plan.md"])
    return {
        "id": number(path),
        "slug": path.name,
        "title": title(spec) or path.name,
        "phases": {phase: phase_state(texts[fname], fname) for fname, phase in PHASES},
        "type": kind,
        "type_raw": raw,
        "origin": origin if origin and origin.strip("—- ") else None,
        "requirements": requirements(spec),
        "tasks": tasks(texts["tasks.md"]),
        "adrs": info["adrs"],
        "contracts": info["contracts"],
        "data_model": info["data_model"],
    }
