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
  diagram             Crea architecture/diagrams.md con el esqueleto de las
                      vistas C4 (contexto, contenedores, componentes) si no
                      existe. Lo completa /architecture:diagram.
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
# Artefactos de architecture/ (D1)
# --------------------------------------------------------------------------

# Cualquier .md que empiece por cuatro digitos cuenta como decision, aunque su
# nombre no siga NNNN-slug.md: un numero ocupado no se vuelve a dar nunca.
ADR_FILE = re.compile(r"^(\d{4})(?:[-_.].*)?\.md$")
ADR_REF = re.compile(r"(?<![A-Za-z0-9])ADR-(\d{4})(?![0-9])")
QUESTION = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.*)$")


def read_arch(root, name):
    return read_text(Path(root) / ARCH_DIR / name)


def header_fields(text):
    """{campo: valor} de la tabla de cabecera (antes del primer ##)."""
    head = (text or "")[:_header_end(text or "")]
    rows = re.findall(r"^\|\s*([^|\n]+?)\s*\|\s*([^|\n]*?)\s*\|\s*$", head, re.M)
    return {norm(k): v for k, v in rows if not set(k) <= set("-: ")}


def quality(root):
    """Atributos Q de quality.md, con sus campos (escenario, motivo)."""
    return parse_items(section(read_arch(root, "quality.md"), "atributos"), "Q")


def components(root):
    """Componentes C de components.md, con sus campos (responsabilidad, candidatas)."""
    return parse_items(section(read_arch(root, "components.md"), "componentes"), "C")


def standards(root):
    """Estandares S de standards.md, con sus campos (tipo, detalle, decision)."""
    return parse_items(section(read_arch(root, "standards.md"), "estandares"), "S")


def questions(root):
    """
    Preguntas de questions.md: [{open, text, adrs, items}] en orden. Las citas
    salen solo del parentesis inicial (`- [ ] (ADR-0002; Q1) ¿…?`): «¿S3 o
    disco?» en el texto no es una cita al estandar S3.
    """
    out = []
    for line in section(read_arch(root, "questions.md"), "preguntas").splitlines():
        m = QUESTION.match(line)
        if not m:
            continue
        text = m.group(2).strip()
        cites = re.match(r"^\(([^)]*)\)", text)
        cited = cites.group(1) if cites else ""
        out.append({
            "open": m.group(1) == " ",
            "text": text,
            "adrs": [f"ADR-{n}" for n in ADR_REF.findall(cited)],
            "items": re.findall(r"(?<![A-Za-z0-9-])([QCS]\d+)(?![0-9])", cited),
        })
    return out


ADR_SECTIONS = {
    "contexto": ("contexto", "context"),
    "decision": ("decision",),
    "alternativas": ("alternativas descartadas", "alternativas"),
    "consecuencias": ("consecuencias", "consequences"),
}


def adr_state(text):
    """
    'draft' | 'proposed' | 'approved' | 'stale' | 'rejected' | 'superseded'.
    Aprobado, como el resto, exige la huella del contenido actual.
    """
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


def adrs(root):
    """
    Decisiones de architecture/adr/NNNN-slug.md, ordenadas por numero:
    [{id, number, file, title, state, status, motivo, sustituye,
      superseded_by, sections: {clave: tiene contenido}}].
    """
    base = Path(root) / ARCH_DIR / ADR_DIR
    try:
        files = sorted(p for p in base.iterdir() if ADR_FILE.match(p.name))
    except OSError:
        return []
    out = []
    for path in files:
        text = read_text(path) or ""
        number = ADR_FILE.match(path.name).group(1)
        head = re.search(r"^#\s+(.*)$", text, re.M)
        title = re.sub(r"^ADR-\d{4}\s*[—–:-]?\s*", "", head.group(1)).strip() if head else ""
        fields = header_fields(text)
        status = doc_status(text) or ""
        sup = ADR_REF.search(status) if adr_state(text) == "superseded" else None
        out.append({
            "id": f"ADR-{number}", "number": int(number),
            "file": f"{ARCH_DIR}/{ADR_DIR}/{path.name}", "title": title,
            "state": adr_state(text), "status": status,
            "motivo": fields.get("motivo", ""), "sustituye": fields.get("sustituye", ""),
            "superseded_by": f"ADR-{sup.group(1)}" if sup else None,
            "sections": {key: bool(re.sub(r"\s+", "", section(text, *titles)))
                         for key, titles in ADR_SECTIONS.items()},
        })
    return out


def next_id(root, kind):
    """Siguiente ID libre de Q, C, S o ADR: maximo + 1, sin reciclar nunca."""
    kind = kind.upper()
    if kind == "ADR":
        used = [a["number"] for a in adrs(root)]
        return f"ADR-{(max(used) if used else 0) + 1:04d}"
    readers = {"Q": quality, "C": components, "S": standards}
    if kind not in readers:
        raise ValueError(f"tipo desconocido: {kind} (Q, C, S o ADR)")
    used = [int(i["id"][1:]) for i in readers[kind](root)]
    return f"{kind}{(max(used) if used else 0) + 1}"


def cmd_next_id(args):
    if len(args) != 1 or args[0].upper() not in ("Q", "C", "S", "ADR"):
        print("Uso: architecture.py next-id Q|C|S|ADR", file=sys.stderr)
        return 2
    print(next_id(project_root(), args[0]))
    return 0


# --------------------------------------------------------------------------
# Comprobacion de coherencia (D3)
# --------------------------------------------------------------------------

def _finding(code, message, artifact):
    # Los codigos son contrato publico: emitir uno sin declararlo es un fallo
    # del plugin, no un hallazgo.
    if code not in FINDINGS:
        raise ValueError(f"codigo de hallazgo no declarado: {code}")
    return {"code": code, "severity": "error" if code.startswith("E-") else "warning",
            "message": message, "artifact": artifact}


def cited_motive(root, motive):
    """
    Lo que un Motivo cita y existe: objetivos Gn del brief y secciones Dn§x
    que citan sus restricciones (D3). Lista vacia si no cita nada valido.
    """
    goals = product_goals(root)
    restrictions = product_restriction_sections(root)
    valid = [f"G{g}" for g in GOAL_REF.findall(motive or "") if f"G{g}" in goals]
    valid += [f"D{d}§{s}" for d, s in DOC_REF.findall(motive or "")
              if f"D{d}§{s}" in restrictions]
    return valid


# Citas que no son una medida: su numero no cuenta como cifra del escenario.
CITATION = re.compile(r"(?<![A-Za-z0-9])(?:ADR-\d+|D\d+§[\d.]+|[GBQCS]\d+)(?![0-9])")


def check_quality(root):
    out = []
    for q in quality(root):
        f = q["fields"]
        if not re.search(r"\d", CITATION.sub(" ", f.get("escenario", ""))):
            out.append(_finding(
                "E-QUALITY-NOT-MEASURABLE",
                f"{q['id']} ({q['title']}): el escenario no tiene ninguna cifra. Escríbelo "
                "con estímulo, respuesta y medida («p95 < 300 ms con 500 peticiones/s»).",
                f"{ARCH_DIR}/quality.md"))
        if not cited_motive(root, f.get("motivo", "")):
            out.append(_finding(
                "E-QUALITY-NO-MOTIVE",
                f"{q['id']} ({q['title']}): el motivo no cita un objetivo del brief (G1) ni "
                "la sección de una de sus restricciones (D1§5).",
                f"{ARCH_DIR}/quality.md"))
    return out


def check_components(root):
    out = []
    placed = set()
    for c in components(root):
        f = c["fields"]
        if not re.sub(r"[\s—–-]", "", f.get("responsabilidad", "")):
            out.append(_finding(
                "E-COMPONENT-NO-RESPONSIBILITY",
                f"{c['id']} ({c['title']}) no dice qué hace: falta la responsabilidad.",
                f"{ARCH_DIR}/components.md"))
        placed |= {f"B{b}" for b in CAND_REF.findall(f.get("candidatas", ""))}
    for cid, cand in product_candidates(root).items():
        if cand["state"] == "descartada" or cid in placed:
            continue
        out.append(_finding(
            "E-COMPONENT-CANDIDATE-UNPLACED",
            f"{cid} ({cand['title']}) no vive en ningún componente: añádela a las "
            "candidatas del componente que la implementa.",
            f"{ARCH_DIR}/components.md"))
    return out


# Decisiones que ya no rigen: se conservan como historia y no se les exige
# forma, motivo ni citas vigentes (podrian citar algo que ya no existe).
HISTORY = ("rejected", "superseded")


def check_adrs(root):
    out = []
    known_q = {q["id"] for q in quality(root)}
    goals = product_goals(root)
    restrictions = product_restriction_sections(root)
    by_number = {}
    for a in adrs(root):
        by_number.setdefault(a["number"], []).append(a["file"])
        if a["state"] in HISTORY:
            continue  # rechazada o sustituida: queda como historia
        missing = [titles[0] for key, titles in ADR_SECTIONS.items() if not a["sections"][key]]
        if missing:
            out.append(_finding(
                "E-ADR-INCOMPLETE",
                f"{a['id']} ({a['title']}) no tiene contenido en: {', '.join(missing)}.",
                a["file"]))
        motive = a["motivo"]
        valid = ([f"Q{n}" for n in re.findall(r"(?<![A-Za-z0-9])Q(\d+)(?![0-9])", motive)
                  if f"Q{n}" in known_q]
                 + [f"G{g}" for g in GOAL_REF.findall(motive) if f"G{g}" in goals]
                 + [f"D{d}§{s}" for d, s in DOC_REF.findall(motive)
                    if f"D{d}§{s}" in restrictions])
        if not valid:
            out.append(_finding(
                "E-ADR-NO-MOTIVE",
                f"{a['id']} ({a['title']}): el motivo no cita un atributo de calidad (Q1), "
                "un objetivo del brief (G1) ni la sección de una restricción (D1§5).",
                a["file"]))
    for number, files in sorted(by_number.items()):
        if len(files) > 1:
            out.append(_finding(
                "E-ADR-ID-DUPLICATE",
                f"ADR-{number:04d} está en {len(files)} archivos: {', '.join(files)}. "
                "Renumera uno con el siguiente libre (next-id ADR).",
                files[0]))
    return out


def check_standards(root):
    out = []
    for s in standards(root):
        if not ADR_REF.search(s["fields"].get("decision", "")):
            out.append(_finding(
                "E-STANDARD-NO-ADR",
                f"{s['id']} ({s['title']}) no cita la decisión de la que se deriva (ADR-0001).",
                f"{ARCH_DIR}/standards.md"))
    return out


def check_references(root):
    """Citas a decisiones, atributos, componentes, objetivos o candidatas que no existen."""
    known = {
        "ADR": {a["id"] for a in adrs(root)},
        "Q": {q["id"] for q in quality(root)},
        "C": {c["id"] for c in components(root)},
        "S": {s["id"] for s in standards(root)},
        "G": set(product_goals(root)),
        "B": set(product_candidates(root)),
    }
    sources = []  # (artefacto, texto, tipos que se comprueban)
    for q in quality(root):
        sources.append((f"{ARCH_DIR}/quality.md", q["fields"].get("motivo", ""), "G"))
    for c in components(root):
        sources.append((f"{ARCH_DIR}/components.md", c["fields"].get("candidatas", ""), "B"))
    for s in standards(root):
        f = s["fields"]
        sources.append((f"{ARCH_DIR}/standards.md", f.get("decision", ""), "ADR"))
        sources.append((f"{ARCH_DIR}/standards.md", f.get("detalle", ""), "C"))
    for a in adrs(root):
        if a["state"] in HISTORY:
            continue
        sources.append((a["file"], a["motivo"], "QG"))
        sources.append((a["file"], a["sustituye"], "ADR"))
        # En el cuerpo solo se buscan ADR-NNNN: una «S3» o una «C2» en prosa
        # pueden no ser citas, un ADR-0042 si lo es.
        body = (read_text(Path(root) / a["file"]) or "")
        sources.append((a["file"], body[_header_end(body):], "ADR"))
    for q in questions(root):
        cited = ", ".join(q["adrs"] + q["items"])
        sources.append((f"{ARCH_DIR}/questions.md", cited, "ADR QCS"))

    out, seen = [], set()
    for artifact, text, kinds in sources:
        refs = []
        if "ADR" in kinds:
            refs += [("ADR", f"ADR-{n}") for n in ADR_REF.findall(text)]
        for kind in "QCSGB":
            if kind in kinds.replace("ADR", ""):
                width = r"\d{2,}" if kind == "B" else r"\d+"
                refs += [(kind, f"{kind}{n}") for n in
                         re.findall(rf"(?<![A-Za-z0-9-]){kind}({width})(?![0-9])", text)]
        for kind, ref in refs:
            if ref not in known[kind] and (artifact, ref) not in seen:
                seen.add((artifact, ref))
                out.append(_finding("E-ARCH-REF-UNKNOWN",
                                    f"{artifact} cita {ref}, que no existe.", artifact))
    return out


def check_questions(root):
    out = []
    for q in questions(root):
        blocking = q["adrs"] + [i for i in q["items"] if i.startswith("Q")]
        if q["open"] and blocking:
            out.append(_finding(
                "E-ARCH-OPEN-QUESTION",
                f"Pregunta abierta sobre {', '.join(blocking)}: «{q['text']}». Impide "
                "aprobar: respóndela y conviértela en decisión o atributo.",
                f"{ARCH_DIR}/questions.md"))
    return out


PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9_*])_[^_\n]+_(?![A-Za-z0-9_*])")


def check_templates(root):
    """Huecos de plantilla (texto en cursiva) que siguen sin rellenar."""
    out = []
    files = [f"{ARCH_DIR}/{name}" for name in SET_FILES] + [a["file"] for a in adrs(root)]
    for rel in files:
        text = read_text(Path(root) / rel)
        if text is None:
            continue
        # Las instrucciones de las plantillas van en blockquote, y el codigo en
        # linea (`_cache_`) no es cursiva: ninguno de los dos es un hueco.
        holes = [m.group(0) for line in text.splitlines()
                 if not line.lstrip().startswith(">")
                 for m in PLACEHOLDER.finditer(re.sub(r"`[^`]*`", " ", line))]
        if holes:
            out.append(_finding(
                "E-ARCH-TEMPLATE",
                f"{rel} conserva {len(holes)} hueco(s) de plantilla, como {holes[0]}.", rel))
    return out


PRODUCT_ROW = re.compile(r"^\|\s*Producto\s*\|\s*([^|\n]*?)\s*\|\s*$", re.M)


def recorded_product(root):
    """{'brief': huella, 'backlog': huella} de la fila Producto de
    components.md, o None si la arquitectura nunca se aprobo."""
    text = read_arch(root, "components.md") or ""
    m = PRODUCT_ROW.search(text, 0, _header_end(text))
    if not m:
        return None
    pairs = re.findall(r"(brief|backlog)\s+([0-9a-f]{12})", m.group(1))
    return dict(pairs) if pairs else None


def check_approval(root):
    """W-ARCH-NOT-APPROVED por artefacto sin aprobar o cambiado (R011), y
    W-ARCH-PRODUCT-CHANGED si el producto cambio desde la aprobacion (R014)."""
    out = []
    targets = [(f"{ARCH_DIR}/{n}", artifact_state(read_arch(root, n))) for n in SET_FILES]
    targets += [(a["file"], a["state"]) for a in adrs(root) if a["state"] in ("draft", "stale")]
    for rel, state in targets:
        if state == "draft":
            out.append(_finding("W-ARCH-NOT-APPROVED",
                                f"{rel} no está aprobado. Lo aprueba el usuario con "
                                "/architecture:approve.", rel))
        elif state == "stale":
            out.append(_finding("W-ARCH-NOT-APPROVED",
                                f"{rel} cambió después de aprobarse: ya no cuenta como "
                                "aprobado. El usuario lo revisa y aprueba de nuevo con "
                                "/architecture:approve.", rel))
    recorded = recorded_product(root)
    if recorded:
        current = product_digests(root)
        changed = [k for k in ("brief", "backlog") if recorded.get(k) != current.get(k)]
        if changed:
            out.append(_finding(
                "W-ARCH-PRODUCT-CHANGED",
                f"El producto cambió desde que se aprobó la arquitectura "
                f"({', '.join(f'product/{k}.md' for k in changed)}): revisa si la "
                "arquitectura sigue valiendo y apruébala de nuevo.",
                f"{ARCH_DIR}/components.md"))
    return out


SCHEMA = "architecture.check/v1"


def analyze(root):
    """
    Todos los hallazgos de la arquitectura, con el schema architecture.check/v1:
    {schema, ok, counts, findings: [{code, severity, message, artifact}]}.
    """
    findings = (check_templates(root) + check_quality(root) + check_components(root)
                + check_adrs(root) + check_standards(root) + check_references(root)
                + check_questions(root) + check_approval(root))
    errors = sum(1 for f in findings if f["severity"] == "error")
    return {
        "schema": SCHEMA,
        "ok": errors == 0,
        "counts": {
            "quality": len(quality(root)), "components": len(components(root)),
            "adrs": len(adrs(root)), "standards": len(standards(root)),
            "questions_open": sum(1 for q in questions(root) if q["open"]),
            "errors": errors, "warnings": len(findings) - errors,
        },
        "findings": findings,
    }


def report(data):
    c = data["counts"]
    out = [f"Arquitectura: {c['quality']} atributo(s), {c['components']} componente(s), "
           f"{c['adrs']} decisión(es), {c['standards']} estándar(es), "
           f"{c['questions_open']} pregunta(s) abierta(s)"]
    for sev, label in (("error", "ERRORES"), ("warning", "AVISOS")):
        items = [f for f in data["findings"] if f["severity"] == sev]
        if items:
            out.append(f"\n  {label} ({len(items)})")
            out += [f"    [{f['code']}] {f['message']}" for f in items]
    out.append("\n  OK: sin errores." if data["ok"] else f"\n  FALLA: {c['errors']} error(es).")
    return "\n".join(out)


def cmd_check(args):
    """
    Informe legible (siempre exit 0), --json (architecture.check/v1) o
    --check (exit 1 si hay errores): lo mismo en local y en CI (R008).
    """
    unknown = [a for a in args if a not in ("--json", "--check")]
    if unknown:
        # En CI, una errata como --chek no debe convertirse en un exit 0.
        print(f"error: argumento desconocido {' '.join(unknown)}. "
              "Uso: architecture.py check [--json] [--check]", file=sys.stderr)
        return 2
    data = analyze(project_root())
    if "--json" in args:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(report(data))
    return 1 if ("--check" in args and not data["ok"]) else 0


# --------------------------------------------------------------------------
# Aprobacion del conjunto (D4). Solo la lanza el usuario, con
# /architecture:approve; los hooks impiden que el modelo la escriba.
# --------------------------------------------------------------------------

def set_status(text, value):
    """Devuelve (texto_nuevo, cambiado?). Copia de discovery.py."""
    end = _header_end(text)
    head, n = STATUS_ROW.subn(lambda m: m.group(1) + value + m.group(3), text[:end], count=1)
    return head + text[end:], bool(n)


def with_product_row(text, digests):
    """components.md con la fila Producto actualizada (o añadida tras Estado)."""
    value = f"brief {digests['brief']} · backlog {digests['backlog']}"
    end = _header_end(text)
    head, rest = text[:end], text[end:]
    if PRODUCT_ROW.search(head):
        # Por posicion: con la fila vacia, replace('') pondria el valor al
        # principio de la linea.
        head = PRODUCT_ROW.sub(lambda m: (m.string[m.start(0):m.start(1)] + value
                                          + m.string[m.end(1):m.end(0)]), head, count=1)
    else:
        lines = head.split("\n")
        for i, line in enumerate(lines):
            if STATUS_ROW.match(line):
                lines.insert(i + 1, f"| Producto | {value} |")
                break
        head = "\n".join(lines)
    return head + rest


def approve(root):
    """
    Sella el conjunto con 'Approved · <huella>' si el producto esta aprobado y
    la comprobacion no da errores. Sella quality, components, standards,
    questions y los ADR en Draft (o cambiados tras aprobarse); los Proposed,
    Rejected y Superseded no se tocan: se deciden con review. Devuelve
    (ok, lineas_de_mensaje).
    """
    problems = product_problems(root)
    if problems:
        return False, (["No se puede aprobar la arquitectura: el producto de discovery "
                        "no está aprobado."] + [f"  - {p}" for p in problems])
    missing = [n for n in SET_FILES if read_arch(root, n) is None]
    if missing:
        return False, [f"No se puede aprobar: falta architecture/{' y architecture/'.join(missing)}."
                       " Lo crea /architecture:init."]
    data = analyze(root)
    errors = [f for f in data["findings"] if f["severity"] == "error"]
    if errors:
        return False, (["No se puede aprobar la arquitectura: la comprobación da errores."]
                       + [f"  [{f['code']}] {f['message']}" for f in errors])

    texts = {f"{ARCH_DIR}/{n}": read_arch(root, n) for n in SET_FILES}
    comp = f"{ARCH_DIR}/components.md"
    texts[comp] = with_product_row(texts[comp], product_digests(root))
    for a in adrs(root):
        if a["state"] in ("draft", "stale", "approved"):
            texts[a["file"]] = read_text(Path(root) / a["file"])

    sealed, already = {}, True
    for rel, text in texts.items():
        stamp = f"Approved · {content_digest(text)}"
        if doc_status(text) == stamp:
            continue
        already = False
        new, changed = set_status(text, stamp)
        if not changed:
            return False, [f"{rel} no tiene la fila '| Estado | ... |' en la cabecera. "
                           "Añádela y vuelve a aprobar."]
        sealed[rel] = (new, stamp)
    if already:
        return True, ["La arquitectura ya estaba aprobada."]
    for rel, (new, _stamp) in sealed.items():
        (Path(root) / rel).write_text(new, encoding="utf-8")
    skipped = [a["id"] for a in adrs(root) if a["state"] == "proposed"]
    lines = [f"{rel} aprobado ({stamp})." for rel, (_n, stamp) in sealed.items()]
    if skipped:
        lines.append(f"Sin tocar, pendientes de /architecture:review: {', '.join(skipped)}.")
    return True, lines


def review(root, adr_id, decision):
    """
    Decide una decision propuesta (D4, R013). Aceptar exige que el ADR no tenga
    errores propios; lo sella y marca como sustituidos los ADR que cita en
    Sustituye, que tienen que estar aprobados. Rechazar lo deja en Rejected,
    con su numero. Devuelve (ok, lineas_de_mensaje).
    """
    adr_id = adr_id.upper()
    by_id = {a["id"]: a for a in adrs(root)}
    target = by_id.get(adr_id)
    if target is None:
        return False, [f"No se puede revisar: {adr_id} no existe en {ARCH_DIR}/{ADR_DIR}/."]
    if target["state"] != "proposed":
        return False, [f"No se puede revisar {adr_id}: solo se revisan decisiones propuestas "
                       f"(Proposed), y está en «{target['status'] or 'Draft'}». Una en borrador "
                       "se aprueba con el conjunto, con /architecture:approve."]
    path = Path(root) / target["file"]
    text = read_text(path)

    if decision == "rechazar":
        new, _ = set_status(text, "Rejected")
        path.write_text(new, encoding="utf-8")
        return True, [f"{adr_id} rechazada. Conserva su número y queda como historia."]

    own = [f for f in analyze(root)["findings"]
           if f["severity"] == "error" and f["artifact"] == target["file"]]
    if own:
        return False, ([f"No se puede aceptar {adr_id}: tiene errores propios."]
                       + [f"  [{f['code']}] {f['message']}" for f in own])
    replaced = [f"ADR-{n}" for n in ADR_REF.findall(target["sustituye"])]
    def why_not(r):
        if r not in by_id:
            return f"{r} no existe"
        if by_id[r]["state"] == "stale":
            return (f"{r} cambió después de aprobarse: reapruébala antes con "
                    "/architecture:approve")
        return f"{r} no está aprobada ({by_id[r]['status'] or 'Draft'})"

    bad = [r for r in replaced if by_id.get(r, {}).get("state") != "approved"]
    if bad:
        return False, [f"No se puede aceptar {adr_id}: solo sustituye a decisiones "
                       f"aprobadas, y {'; '.join(why_not(r) for r in bad)}."]

    writes = {path: set_status(text, f"Approved · {content_digest(text)}")[0]}
    for r in replaced:
        old = Path(root) / by_id[r]["file"]
        writes[old] = set_status(read_text(old), f"Superseded by {adr_id}")[0]
    for p, new in writes.items():
        p.write_text(new, encoding="utf-8")
    lines = [f"{adr_id} aceptada y aprobada."]
    if replaced:
        lines.append(f"{', '.join(replaced)} queda(n) sustituida(s) por {adr_id}.")
    return True, lines


REVIEW_DECISIONS = {"aceptar": "aceptar", "accept": "aceptar",
                    "rechazar": "rechazar", "reject": "rechazar"}


def cmd_review(args):
    """
    review ADR-NNNN aceptar|rechazar [--skill]. Con --skill (lo usa
    /architecture:review) todo va a stdout y sale siempre con 0.
    """
    skill = "--skill" in args
    rest = [a for a in args if a != "--skill"]
    if len(rest) != 2 or not ADR_REF.fullmatch(rest[0].upper()) \
            or rest[1].lower() not in REVIEW_DECISIONS:
        msg = "Uso: architecture.py review ADR-NNNN aceptar|rechazar [--skill]"
        print(msg, file=sys.stdout if skill else sys.stderr)
        return 0 if skill else 2
    try:
        ok, lines = review(project_root(), rest[0], REVIEW_DECISIONS[rest[1].lower()])
    except Exception as exc:  # noqa: BLE001
        if not skill:
            raise
        ok, lines = False, [f"No se pudo revisar: error inesperado ({exc})."]
    stream = sys.stdout if (ok or skill) else sys.stderr
    print("\n".join(lines), file=stream)
    return 0 if (ok or skill) else 1


# --------------------------------------------------------------------------
# Guardrails (D6, R012): el modelo no puede escribir un estado que decide el
# usuario (Approved, Rejected, Superseded) ni ejecutar approve o review.
# --------------------------------------------------------------------------

BYPASS = "ARCHITECTURE_BYPASS"
USER_STATES = {"approved", "aprobado", "aprobada", "rejected", "rechazada", "rechazado",
               "superseded", "sustituida", "sustituido"}
GUARDED_COMMANDS = {"approve", "review"}
APPROVE_TEXT = re.compile(r"architecture\.py['\"]?\s+(?:approve|review)\b")

GUARD_REASON = (
    "Guardrail architecture: aprobar, rechazar o sustituir una decisión es del "
    "usuario, no tuya. Es la prueba de que una persona revisó la arquitectura.\n\n"
    "No cambies el campo Estado a Approved, Rejected ni Superseded, ni ejecutes "
    "`architecture.py approve` o `review`: pídele al usuario que lo revise y ejecute "
    "/architecture:approve o /architecture:review. Puedes dejar una decisión en "
    "Draft o en Proposed.\n\nEscape puntual: ARCHITECTURE_BYPASS=1."
)


def claims_user_state(text):
    """True si el Estado de la cabecera es uno que solo decide el usuario."""
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    return bool(words) and words[0].strip("`*_") in USER_STATES


def guarded_files(root):
    """Rutas relativas de los artefactos de architecture/ que se protegen."""
    rels = [f"{ARCH_DIR}/{n}" for n in SET_FILES]
    try:
        rels += sorted(f"{ARCH_DIR}/{ADR_DIR}/{p.name}"
                       for p in (Path(root) / ARCH_DIR / ADR_DIR).iterdir()
                       if p.suffix.lower() == ".md")
    except OSError:
        pass
    return rels


def _guarded_target(root, raw_path):
    """Ruta relativa del artefacto protegido al que apunta raw_path, o None."""
    try:
        target = Path(raw_path)
        if not target.is_absolute():
            target = Path(root) / target
        rel = target.resolve().relative_to((Path(root) / ARCH_DIR).resolve())
    except (OSError, ValueError):
        return None
    parts = rel.parts
    # Sin distinguir mayusculas: en macOS y Windows QUALITY.md es quality.md.
    if len(parts) == 1 and parts[0].casefold() in SET_FILES:
        return f"{ARCH_DIR}/{parts[0].casefold()}"
    if len(parts) == 2 and parts[0].casefold() == ADR_DIR and parts[1].lower().endswith(".md"):
        return f"{ARCH_DIR}/{ADR_DIR}/{parts[1]}"
    return None


# Analisis de comandos: ejecutar approve o review frente a mencionarlos.
#
# Copia adaptada del analizador de plugins/discovery/scripts/discovery.py, que a
# su vez copia el de plugins/sdd/scripts/sdd_bash.py: los plugins no comparten
# codigo. Un arreglo en una copia se replica en las otras, y los selftests usan
# listas de casos equivalentes.

_WRAPPERS = {"sudo", "env", "command", "nohup", "time", "nice", "builtin", "exec"}
_SEPARATORS = {";", "&&", "||", "|", "|&", "&", "(", ")", ";;"}
_REDIRECTS = {">", ">>", ">|", "&>", "&>>", "<", "<<", "<<<", "<<-", "<>", ">&", "<&"}
_HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)",
    re.S,
)


def _strip_heredocs(command):
    """Quita el cuerpo de los heredocs: es texto, no comandos."""
    return _HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], command)


def _command_segments(command):
    """Palabras de cada comando simple, sin redirecciones ni su destino."""
    import shlex
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)  # ValueError si las comillas no cierran
    segments, seg, i = [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _SEPARATORS:
            segments.append(seg)
            seg = []
        elif tok in _REDIRECTS:
            i += 1
        else:
            seg.append(tok)
        i += 1
    segments.append(seg)
    return segments


def _command_words(seg):
    """Quita asignaciones VAR=x y envoltorios como sudo o env."""
    words = list(seg)
    while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])
                     or os.path.basename(words[0]) in _WRAPPERS):
        words.pop(0)
    return words


def _substitutions(command):
    """Contenido de las sustituciones `…` y $(…) que bash ejecutaria,
    respetando las comillas simples y los escapes."""
    found, i, n, single = [], 0, len(command), False
    while i < n:
        ch = command[i]
        if single:
            if ch == "'":
                single = False
            i += 1
            continue
        if ch == "\\":
            i += 2
            continue
        if ch == "'":
            if command.count('"', 0, i) % 2 == 0:
                single = True
            i += 1
            continue
        if ch == "`":
            j = i + 1
            while j < n and command[j] != "`":
                j += 2 if command[j] == "\\" else 1
            if j >= n:
                break
            found.append(command[i + 1:j])
            i = j + 1
            continue
        if command.startswith("$(", i) and not command.startswith("$((", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if command[j] == "\\":
                    j += 2
                    continue
                if command[j] == "(":
                    depth += 1
                elif command[j] == ")":
                    depth -= 1
                j += 1
            if depth:
                break
            found.append(command[i + 2:j - 1])
            i = j
            continue
        i += 1
    return found


def invokes_approve(command):
    """
    True si el comando **ejecuta** architecture.py approve o review: en algun
    segmento, una palabra cuyo nombre de archivo es architecture.py seguida de
    una de esas ordenes, tambien dentro de una sustitucion que se ejecuta. Una
    mencion (mensaje de commit, PR, heredoc) no cuenta. Lo que no se puede
    analizar se evalua por su texto; lo que no se ve lo revierte la auditoria.
    """
    command = _strip_heredocs(command or "")
    if any(invokes_approve(inner) for inner in _substitutions(command)):
        return True
    try:
        segments = _command_segments(command)
    except ValueError:
        return bool(APPROVE_TEXT.search(command))
    for seg in segments:
        words = _command_words(seg)
        for word, nxt in zip(words, words[1:]):
            if os.path.basename(word) == "architecture.py" and nxt in GUARDED_COMMANDS:
                return True
    return False


def deny(reason):
    """Bloquea. El JSON solo se procesa con exit 0: nunca combinar con exit 2."""
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}, sys.stdout)
    sys.stdout.write("\n")
    return 0


SNAPSHOT_TTL = 24 * 3600


def _snapshot_path(root, payload):
    import tempfile
    key = payload.get("tool_use_id") or payload.get("session_id") or "nosession"
    digest = hashlib.sha1(f"{root}|{key}".encode("utf-8")).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / "architecture-audit" / f"{digest}.json"


def _prune(directory):
    """Si un comando falla o se rechaza, PostToolUse no llega y la instantanea
    queda huerfana. Se barren las de mas de un dia."""
    import time
    limit = time.time() - SNAPSHOT_TTL
    try:
        for old in directory.glob("*.json"):
            if old.stat().st_mtime < limit:
                old.unlink()
    except OSError:
        pass


def _statuses(root):
    out = {}
    for rel in guarded_files(root):
        text = read_text(Path(root) / rel)
        if text is not None:
            out[rel] = doc_status(text)
    return out


def cmd_guard(_args):
    """Hook PreToolUse sobre Write|Edit|Bash. Nunca devuelve allow."""
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    root = project_root(payload)
    if os.environ.get(BYPASS) == "1" or not (root / ARCH_DIR).is_dir():
        return 0
    tool_input = payload.get("tool_input") or {}

    if payload.get("tool_name") == "Bash":
        if invokes_approve(tool_input.get("command") or ""):
            return deny(GUARD_REASON)
        # Lo que un comando opaco cambie lo revisa la auditoria de PostToolUse.
        path = _snapshot_path(root, payload)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_statuses(root)), encoding="utf-8")
        except OSError:
            return 0
        _prune(path.parent)
        return 0

    rel = _guarded_target(root, tool_input.get("file_path") or "")
    if not rel:
        return 0
    target = root / rel
    before = read_text(target) if target.is_file() else ""
    if "content" in tool_input:
        after = tool_input.get("content") or ""
    elif "new_string" in tool_input:
        old = tool_input.get("old_string") or ""
        if not old or old not in (before or ""):
            return 0
        count = -1 if tool_input.get("replace_all") else 1
        after = before.replace(old, tool_input.get("new_string") or "", count)
    else:
        return 0
    if claims_user_state(after) and doc_status(after) != doc_status(before or ""):
        return deny(GUARD_REASON)
    return 0


def cmd_audit(_args):
    """
    Hook PostToolUse sobre Bash: si un comando llevo el Estado de un artefacto
    a uno que decide el usuario, lo devuelve a su valor anterior. Exit 2 para
    que el modelo lea el aviso; PostToolUse no puede deshacer el comando.
    """
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    root = project_root(payload)
    path = _snapshot_path(root, payload)
    try:
        before = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except (OSError, ValueError):
        return 0
    if os.environ.get(BYPASS) == "1":
        return 0
    restored = []
    # Se recorren todos los artefactos de ahora, no solo los de antes: uno
    # creado o recreado ya aprobado tambien vuelve a Draft.
    for rel in guarded_files(root):
        text = read_text(root / rel)
        old = before.get(rel)
        if text is not None and claims_user_state(text) and doc_status(text) != old:
            (root / rel).write_text(set_status(text, old or "Draft")[0], encoding="utf-8")
            restored.append(f"{rel} (vuelve a '{old or 'Draft'}')")
    if not restored:
        return 0
    sys.stderr.write("Guardrail architecture: el comando cambió el Estado de "
                     + ", ".join(restored) + ". Aprobar, rechazar o sustituir es del "
                     "usuario, con /architecture:approve o /architecture:review. "
                     "Detente y dile al usuario lo que pasó.\n")
    return 2


def cmd_approve(args):
    """
    Con --skill (lo usa /architecture:approve) todo va a stdout y sale siempre
    con 0: el resultado lo lee el modelo como texto, no como codigo de salida.
    """
    try:
        ok, lines = approve(project_root())
    except Exception as exc:  # noqa: BLE001
        if "--skill" not in args:
            raise
        ok, lines = False, [f"No se pudo aprobar: error inesperado ({exc})."]
    stream = sys.stdout if (ok or "--skill" in args) else sys.stderr
    print("\n".join(lines), file=stream)
    return 0 if (ok or "--skill" in args) else 1


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------

def plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT")
                or Path(__file__).resolve().parent.parent)


# --------------------------------------------------------------------------
# Diagramas C4 (feature 008): architecture/diagrams.md, opcional
# --------------------------------------------------------------------------

DIAGRAMS = "diagrams.md"
# Vistas C4 y el encabezado de seccion que las identifica (D2).
DIAGRAM_VIEWS = (("contexto", "Contexto"), ("contenedores", "Contenedores"),
                 ("componentes", "Componentes"))
MERMAID_STYLES = (
    "  classDef persona fill:#08427b,stroke:#052e56,color:#fff\n"
    "  classDef sistema fill:#1168bd,stroke:#0b4884,color:#fff\n"
    "  classDef contenedor fill:#438dd5,stroke:#2e6295,color:#fff\n"
    "  classDef externo fill:#999999,stroke:#6b6b6b,color:#fff\n"
)


def mermaid_label(*lines):
    """Etiqueta de nodo ["…"]: lineas unidas con <br/> y las comillas escapadas,
    que Mermaid no admite dentro de la etiqueta."""
    return "<br/>".join(str(x).replace('"', "#quot;").strip() for x in lines if x)


def product_users(root):
    """Tipos de usuario del brief: las viñetas de primer nivel de ## Usuarios, sin
    sus citas. En 'Gestor: lleva las cuentas' el tipo es lo anterior a ': '."""
    body = section(read_product(root, BRIEF), "usuarios", "users")
    out = []
    for line in body.splitlines():
        m = re.match(r"^[-*]\s+(.*)$", line)
        if not m:
            continue
        name = re.sub(r"\s*\([^)]*D\d+§[^)]*\)\s*$", "", m.group(1))
        name = name.split(": ")[0].strip(" *_:")
        if name:
            out.append(name)
    return out


def standard_dependencies(root):
    """[(desde, hacia, estandar, decision)] de los estandares de tipo dependencia
    con Detalle 'C2 → C1' (o 'C2 -> C1')."""
    out = []
    for s in standards(root):
        f = s["fields"]
        if norm(f.get("tipo", "")).strip(" _") != "dependencia":
            continue
        decision = ADR_REF.search(f.get("decision", ""))
        for a, b in re.findall(r"\b(C\d+)\s*(?:→|->)\s*(C\d+)\b", f.get("detalle", "")):
            out.append((a, b, s["id"], f"ADR-{decision.group(1)}" if decision else None))
    return out


def diagram_skeleton(root):
    """Texto de diagrams.md generado solo desde los archivos (D3)."""
    users = product_users(root)
    comps = components(root)
    deps = standard_dependencies(root)
    pending = ("  %% _Completa: nombre del sistema, sistemas externos (XNombre) y la "
               "tecnología de cada contenedor, citando su ADR_\n")
    system = mermaid_label("_nombre del sistema_", "[Sistema]")

    def users_block(target):
        lines = [f'  U{i}["{mermaid_label(u, "[Persona]")}"]:::persona\n'
                 for i, u in enumerate(users, 1)]
        lines += [f"  U{i} -->|usa| {target}\n" for i in range(1, len(users) + 1)]
        return "".join(lines)

    def comp_nodes(kind, indent):
        return "".join(
            f'{indent}{c["id"]}["{mermaid_label(c["title"], f"[{kind}]", c["fields"].get("responsabilidad", ""))}"]:::contenedor\n'
            for c in comps)

    context = ("flowchart LR\n" + users_block("SYS")
               + f'  SYS["{system}"]:::sistema\n' + pending + MERMAID_STYLES)
    containers = ("flowchart LR\n" + users_block("SYS")
                  + f'  subgraph SYS["{system}"]\n' + comp_nodes("Contenedor", "    ")
                  + "  end\n" + pending + MERMAID_STYLES)
    # Sin decision citada (ya es E-STANDARD-NO-ADR), un hueco que la pida.
    edges = "".join(f"  {a} -->|usa · {adr or '_decisión_'}| {b}\n"
                    for a, b, _s, adr in deps)
    componentes = ("flowchart LR\n" + f'  subgraph SYS["{system}"]\n'
                   + comp_nodes("Componente", "    ") + "  end\n" + edges + pending
                   + MERMAID_STYLES)
    blocks = {"contexto": context, "contenedores": containers, "componentes": componentes}
    intro = {
        "contexto": "Quién usa el sistema y con qué sistemas externos habla.",
        "contenedores": "Las piezas desplegables o almacenes del sistema y quién las usa.",
        "componentes": "Las partes del sistema y sus dependencias, cada una con la "
                       "decisión (ADR) de la que sale.",
    }
    out = ("# Diagramas de arquitectura\n\n| Campo  | Valor |\n| ------ | ----- |\n"
           "| Estado | Draft |\n\n"
           "> Vistas C4 de contexto, contenedores y componentes, en Mermaid. Los nodos\n"
           "> de componente se llaman por su ID (C1) y la comprobación los contrasta con\n"
           "> components.md y standards.md. Solo el usuario cambia el Estado, con\n"
           "> /architecture:approve.\n")
    for key, title in DIAGRAM_VIEWS:
        out += f"\n## {title}\n\n{intro[key]}\n\n```mermaid\n{blocks[key]}```\n"
    return out


def cmd_diagram(_args):
    """Crea architecture/diagrams.md con el esqueleto si no existe (R004)."""
    root = project_root()
    target = root / ARCH_DIR / DIAGRAMS
    if target.exists():
        print(f"{ARCH_DIR}/{DIAGRAMS} ya existe: no se toca. Para rehacer el esqueleto, "
              "bórralo y vuelve a ejecutar diagram (se pierde lo completado).")
        return 0
    if not components(root):
        print("No hay componentes en architecture/components.md: los redacta "
              "/architecture:init.", file=sys.stderr)
        return 1
    target.write_text(diagram_skeleton(root), encoding="utf-8")
    print(json.dumps({"file": f"{ARCH_DIR}/{DIAGRAMS}",
                      "views": [k for k, _t in DIAGRAM_VIEWS],
                      "next": "/architecture:diagram completa sistemas externos y tecnologías"},
                     indent=2))
    return 0


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
    "diagram": cmd_diagram,
    "next-id": cmd_next_id,
    "check": cmd_check,
    "approve": cmd_approve,
    "review": cmd_review,
    "guard": cmd_guard,
    "audit": cmd_audit,
}

# Un hook que revienta nunca debe bloquear al usuario: falla abierto.
HOOKS = {"guard", "audit"}

# Codigos de hallazgo declarados: el selftest exige probar cada uno. Son
# contrato publico (prefijos reservados en el registro comun de la serie).
FINDINGS = {
    "E-QUALITY-NOT-MEASURABLE": "Atributo de calidad sin cifra en su escenario",
    "E-QUALITY-NO-MOTIVE": "Atributo de calidad sin objetivo ni restricción que lo motive",
    "E-COMPONENT-NO-RESPONSIBILITY": "Componente sin responsabilidad",
    "E-COMPONENT-CANDIDATE-UNPLACED": "Candidata vigente del backlog sin componente",
    "E-ADR-INCOMPLETE": "Decisión sin contexto, decisión, alternativas o consecuencias",
    "E-ADR-NO-MOTIVE": "Decisión sin atributo, objetivo ni restricción que la motive",
    "E-ADR-ID-DUPLICATE": "Dos archivos de decisión con el mismo número",
    "E-STANDARD-NO-ADR": "Estándar sin la decisión de la que se deriva",
    "E-ARCH-REF-UNKNOWN": ("Cita a una decisión, atributo, componente, objetivo o "
                           "candidata inexistente"),
    "E-ARCH-OPEN-QUESTION": "Pregunta abierta sobre una decisión o un atributo",
    "E-ARCH-TEMPLATE": "Hueco de plantilla sin rellenar",
    "W-ARCH-NOT-APPROVED": "Artefacto sin aprobar o cambiado después de aprobarse",
    "W-ARCH-PRODUCT-CHANGED": "El producto cambió desde la aprobación de la arquitectura",
}


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
