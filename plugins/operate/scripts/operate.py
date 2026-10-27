#!/usr/bin/env python3
"""
operate.py - utilidades deterministas del plugin operate.

Todo lo que no requiere criterio vive aqui: identificadores de incidentes y
acciones, borradores, la comprobacion, el sellado y los guardrails. Las
skills solo redactan.

El plugin lee releases/ (lo deja release), architecture/ (architecture) y
specs/ (sdd), y solo escribe en operations/. No importa codigo de otros
plugins: lo que lee de ellos lo copia, documentado, operate_sources.py.

Subcomandos:
  prepare vX.Y.Z      Escribe operations/vX.Y.Z.md, la preparacion de una
                      version publicada de releases/, con sus features y los
                      huecos de puesta en marcha, senales y vuelta atras. Si
                      ya existe, no la toca.
  incident "<titulo>"  Registra el siguiente incidente (I001, I002…) en
                      operations/incidents.md, que solo crece, y escribe
                      operations/incidents/INNN-slug.md con sus huecos.
  next-action I001     Siguiente accion libre del postmortem de I001
                      (I001-A3): el maximo de las suyas, mas 1. Las acciones
                      no se renumeran nunca.
  approve <vX.Y.Z|I001> [--skill]
                      Aprueba la preparacion o el postmortem si no tienen
                      errores ni huecos: los sella con 'Approved · <huella>' y,
                      en una preparacion, guarda la huella de su version. Solo
                      lo lanza el usuario, con /operate:approve.
  guard               Hook PreToolUse: impide que el modelo apruebe.
  audit               Hook PostToolUse sobre Bash: revierte una aprobacion
                      escrita por un comando.
  check [vX.Y.Z|I001] [--json] [--check]
                      Comprueba esa preparacion o ese incidente, o todo
                      operations/. --json emite operate.check/v1; --check
                      sale con 1 si hay errores (para CI).
"""

import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import operate_sources as src  # noqa: E402

OPS_DIR = "operations"
INCIDENTS_DIR = "incidents"
REGISTRY = "incidents.md"


# --------------------------------------------------------------------------
# Raiz del proyecto. Copia de project_root y find_upwards de
# plugins/release/scripts/release.py (y de architecture.py, sdd.py y
# discovery.py): los plugins no comparten codigo.
# --------------------------------------------------------------------------

def project_root(payload=None):
    """
    CLAUDE_PROJECT_DIR se usa tal cual. Sin ella (la inyeccion de comandos de
    una skill no la recibe), se sube desde el cwd hasta operations/ y, si no
    lo hay, hasta releases/, sin salir del repositorio.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    start = Path((payload or {}).get("cwd") or os.getcwd()).resolve()
    return (find_upwards(start, (OPS_DIR,)) or find_upwards(start, (src.RELEASES_DIR,))
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


def plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT")
                or Path(__file__).resolve().parent.parent)


def template_text(name):
    """La plantilla del plugin, o None si no se encuentra."""
    for base in (plugin_root(), Path(__file__).resolve().parent.parent):
        text = src.read_text(base / "templates" / name)
        if text:
            return text
    return None


def fill(template, values):
    """Sustituye {{CLAVES}} en una sola pasada."""
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), m.group(0)), template)


STOPWORDS = {
    "a", "al", "ante", "con", "de", "del", "e", "el", "en", "la", "las", "lo",
    "los", "o", "para", "por", "que", "se", "sin", "sobre", "su", "sus", "un",
    "una", "unos", "unas", "y",
}


def slugify(text, max_words=5):
    """Adaptada de slugify de plugins/sdd/scripts/sdd.py (la de
    plugins/discovery/scripts/discovery.py es otra variante): solo las
    palabras vacias en español, y los acentos con norm de operate_sources."""
    text = src.norm(text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    words = [w for w in re.split(r"[\s-]+", text) if w]
    kept = [w for w in words if w not in STOPWORDS] or words
    return "-".join(kept[:max_words]) or "incidente"


# --------------------------------------------------------------------------
# Huecos de plantilla (R009): texto en cursiva sin sustituir. Copia de holes
# de plugins/release/scripts/release.py; la misma regla esta en
# check_templates de plugins/architecture/scripts/architecture.py.
# --------------------------------------------------------------------------

PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9_*])_[^_\n]+_(?![A-Za-z0-9_*])")
TEMPLATE_VAR = re.compile(r"\{\{[A-Z_]+\}\}")


def holes(text, generated=(), subheadings=False):
    """Huecos que siguen sin rellenar. No cuentan las notas en blockquote, el
    codigo en linea, las secciones generated, que escribe el script, ni los
    encabezados; con subheadings, si cuentan los ### (el nombre de una senal
    de la preparacion)."""
    out, skip = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            skip = src.norm(m.group(1)).strip() in generated
        if skip or line.lstrip().startswith(">"):
            continue
        if line.lstrip().startswith("#") and not (subheadings and line.startswith("### ")):
            continue
        plain = re.sub(r"`[^`]*`", " ", line)
        out += [h.group(0) for h in PLACEHOLDER.finditer(plain)]
        out += TEMPLATE_VAR.findall(plain)
    return out


def first_hole(found):
    return found[0] if len(found[0]) <= 70 else found[0][:69] + "…"


# --------------------------------------------------------------------------
# Incidentes (D2, D6): registro que solo crece y un archivo por incidente
# --------------------------------------------------------------------------

INCIDENT_ID = re.compile(r"^I(\d{3,})$")
INCIDENT_FILE = re.compile(r"^(I\d{3,})(?:-[^/]*)?\.md$")
REGISTRY_ROW = re.compile(r"^\|\s*(I\d{3,})\s*\|", re.M)
UNKNOWN_VERSION = {"desconocida", "desconocido", "—", "-"}


def incident_files(root):
    """{I001: Path} de operations/incidents/. Si dos archivos tienen el mismo
    ID (I001-a.md e I001-b.md), cuenta el primero por orden de nombre."""
    try:
        paths = sorted((Path(root) / OPS_DIR / INCIDENTS_DIR).iterdir())
    except OSError:
        return {}
    out = {}
    for path in paths:
        m = INCIDENT_FILE.match(path.name)
        if m and path.is_file():
            out.setdefault(m.group(1), path)
    return out


def registered_ids(root):
    """IDs del registro operations/incidents.md, aunque su archivo no exista."""
    return REGISTRY_ROW.findall(src.read_text(Path(root) / OPS_DIR / REGISTRY) or "")


def next_incident(root):
    """Siguiente incidente libre: maximo del registro y de los archivos, mas 1.
    Un incidente borrado sigue en el registro: su numero no se recicla."""
    used = [int(i[1:]) for i in registered_ids(root) + list(incident_files(root))]
    return f"I{(max(used) if used else 0) + 1:03d}"


REGISTRY_HEAD = """# Registro de incidentes

> Lo mantiene `operate.py incident`: una fila por incidente, que no se borra
> nunca, aunque se borre su archivo. Así ningún número se recicla.

| ID | Fecha | Título | Archivo |
| -- | ----- | ------ | ------- |
"""


def cmd_incident(args):
    """0 y el ID nuevo; 1 sin titulo (Contratos)."""
    # Una sola linea: el titulo va en el encabezado y en una fila del registro.
    title = " ".join(" ".join(args).split())
    if not title:
        print('error: falta el título del incidente. Uso: operate.py incident "<título>"',
              file=sys.stderr)
        return 1
    template = template_text("incident.md")
    if template is None:
        print("error: no se encuentra templates/incident.md del plugin operate. "
              "No se ha registrado nada.", file=sys.stderr)
        return 1
    root = project_root()
    iid = next_incident(root)
    rel = f"{OPS_DIR}/{INCIDENTS_DIR}/{iid}-{slugify(title)}.md"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fill(template, {"ID": iid, "TITLE": title}), encoding="utf-8")
    registry = root / OPS_DIR / REGISTRY
    text = src.read_text(registry) or REGISTRY_HEAD
    clean = title.replace("|", "/")
    row = (f"| {iid} | {datetime.date.today().isoformat()} | {clean} | "
           f"{INCIDENTS_DIR}/{path.name} |\n")
    registry.write_text(text.rstrip("\n") + "\n" + row, encoding="utf-8")
    print(json.dumps({"incident": iid, "file": rel}, ensure_ascii=False))
    return 0


# Acciones del postmortem (D2, D6): '### I001-A1 — titulo' en ## Acciones.
ACTION_ID = re.compile(r"^(I\d{3,})-A(\d+)$")


def actions(text):
    """[(id, titulo)] de los encabezados ### de la seccion Acciones, en orden.
    Un encabezado sin ID de accion devuelve ('', encabezado)."""
    out = []
    for line in src.section(text, "acciones").splitlines():
        m = re.match(r"^###\s+(.*?)\s*$", line)
        if not m:
            continue
        # El ID se corta en su ultimo digito: '### I001-A1: titulo' y
        # '### I001-A1—titulo' tambien lo traen.
        head = re.match(r"^([Ii]\d{3,}-[Aa]\d+)(?![0-9])\s*[—–:-]?\s*(.*)$", m.group(1))
        if head:
            out.append((head.group(1).upper(), head.group(2)))
        else:
            out.append(("", m.group(1)))
    return out


def next_action(text, iid):
    """Siguiente accion libre del incidente iid: el maximo de las suyas, mas 1."""
    used = [int(ACTION_ID.match(a).group(2)) for a, _t in actions(text)
            if a and ACTION_ID.match(a).group(1) == iid]
    return f"{iid}-A{(max(used) if used else 0) + 1}"


def cmd_next_action(args):
    """0 y I001-A<n>; 1 si el incidente no existe (Contratos)."""
    iid = (args[0] if len(args) == 1 else "").strip().upper()
    path = incident_files(project_root()).get(iid) if INCIDENT_ID.match(iid) else None
    if path is None:
        print(f"error: no existe el incidente {iid or '(ninguno)'} en "
              f"{OPS_DIR}/{INCIDENTS_DIR}/. Uso: operate.py next-action I001", file=sys.stderr)
        return 1
    print(next_action(src.read_text(path) or "", iid))
    return 0


def incidents(root):
    """[{id, rel, text, state, version, fields}] de operations/incidents/."""
    out = []
    for iid, path in incident_files(root).items():
        text = src.read_text(path) or ""
        out.append({"id": iid, "rel": f"{OPS_DIR}/{INCIDENTS_DIR}/{path.name}",
                    "text": text, "state": src.artifact_state(text),
                    "version": src.header_row(text, "Versión afectada")
                    or src.header_row(text, "Version afectada") or ""})
    return out


# --------------------------------------------------------------------------
# Preparaciones (D2, D6): operations/vX.Y.Z.md de una version publicada
# --------------------------------------------------------------------------

PREPARATION_FILE = re.compile(r"^v(\d+\.\d+\.\d+)\.md$")
# Seccion que escribe el script: sus lineas no son huecos.
PREP_GENERATED = ("features",)

SIGNAL_HOLE = """### SG1 — _nombre de la señal_

- **Atributo:** —
- **Escenario:** _qué se observa_
- **Umbral:** _a partir de qué cifra preocupa_
- **Cómo se mide:** _con qué herramienta o consulta_"""


def preparations(root):
    """[{version, rel, text, state}] de operations/vX.Y.Z.md, por nombre."""
    try:
        paths = sorted(p for p in (Path(root) / OPS_DIR).iterdir()
                       if p.is_file() and PREPARATION_FILE.match(p.name))
    except OSError:
        return []
    out = []
    for path in paths:
        text = src.read_text(path) or ""
        out.append({"version": PREPARATION_FILE.match(path.name).group(1),
                    "rel": f"{OPS_DIR}/{path.name}", "text": text,
                    "state": src.artifact_state(text)})
    return out


def feature_lines(root, names):
    """'- 008 — titulo' por cada feature de la version; tal cual si no se
    resuelve en specs/."""
    lines = []
    for name in names:
        found = src.resolve(root, name)
        if len(found) == 1:
            f = src.feature(found[0])
            lines.append(f"- {found[0].name.split('-', 1)[0]} — {f['title']}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines) or "Ninguna."


def related_attributes(root, names):
    """Atributos de calidad relacionados con las features names (D4): su
    Motivo cita un objetivo del Origen de alguna feature, o lo cita el Motivo
    de un ADR aprobado que cita su plan. En el orden de quality.md."""
    goals, cited = set(), set()
    for name in names:
        found = src.resolve(root, name)
        if len(found) == 1:
            f = src.feature(found[0])
            goals.update(f["goals"])
            cited.update(f["adrs"])
    via_adr = set()
    for a in src.adrs(root):
        if a["id"] in cited and a["state"] == "approved":
            via_adr.update("Q" + n for n in src.QUALITY_REF.findall(a["motive"]))
    return [q for q in src.quality(root)
            if q["id"] in via_adr
            or goals & {"G" + n for n in src.GOAL_REF.findall(q["motive"])}]


def signals(root, release):
    """Seccion de senales del borrador (D4): una SG<n> por atributo
    relacionado; si no hay ninguno, una senal con huecos y una nota que dice
    por que."""
    if not src.architecture_exists(root):
        why = "El proyecto no tiene architecture/"
    elif src.architecture_problems(root):
        why = "La arquitectura no está aprobada"
    else:
        related = related_attributes(root, release["features"])
        if related:
            return "\n\n".join(
                f"### SG{n} — {q['title']}\n\n- **Atributo:** {q['id']}\n"
                f"- **Escenario:** {q['scenario'] or '_qué se observa_'}\n"
                "- **Umbral:** _a partir de qué cifra preocupa_\n"
                "- **Cómo se mide:** _con qué herramienta o consulta_"
                for n, q in enumerate(related, 1))
        why = "Ningún atributo de calidad de la arquitectura se relaciona con estas features"
    return (f"> {why}: no se proponen señales desde sus atributos de calidad. Añade "
            "las que\n> haga falta vigilar.\n\n" + SIGNAL_HOLE)


def release_refusal(version, rel):
    """Motivo por el que no se prepara la version, o None (R002)."""
    if rel is None:
        return (f"No existe {src.RELEASES_DIR}/v{version}.md: solo se prepara una "
                "versión publicada.")
    if not src.published(rel):
        return (f"La versión {version} no está publicada ({rel['rel']} está en borrador): "
                "la publica el usuario con /release:approve.")
    return None


def cmd_prepare(args):
    """0 si la escribe o ya existia; 1 si la version no existe o no esta
    publicada (Contratos); 2 sin una version."""
    version = version_arg(args[0]) if len(args) == 1 else None
    if version is None:
        print("error: indica la versión. Uso: operate.py prepare vX.Y.Z", file=sys.stderr)
        return 2
    root = project_root()
    rel = src.release(root, version)
    refusal = release_refusal(version, rel)
    if refusal:
        print(refusal + " No se ha creado nada.", file=sys.stderr)
        return 1
    target = f"{OPS_DIR}/v{version}.md"
    path = root / target
    if path.exists():
        print(f"{target} ya existe: no se toca. Compruébala con /operate:check.")
        return 0
    template = template_text("preparation.md")
    if template is None:
        print("error: no se encuentra templates/preparation.md del plugin operate. "
              "No se ha creado nada.", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fill(template, {
        "VERSION": version, "RELEASE_DIGEST": rel["digest"],
        "DATE": datetime.date.today().isoformat(),
        "FEATURES": ", ".join(rel["features"]) or "—",
        "FEATURE_LIST": feature_lines(root, rel["features"]),
        "SIGNALS": signals(root, rel),
    }), encoding="utf-8")
    print(f"{target} escrito en borrador, para la versión publicada {version}.")
    return 0


# Toda subseccion ### de Senales es una senal; el ID SG<n> es opcional, para
# que una escrita a mano sin el tambien se compruebe.
SIGNAL_HEAD = re.compile(r"^###\s+(?:(SG\d+)\b\s*[—–:-]?\s*)?(.*?)\s*$")
FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$")


def prep_signals(text):
    """[{id, name, fields}] de las subsecciones ### SG<n> de Señales."""
    out = []
    for line in src.section(text, "señales").splitlines():
        m = SIGNAL_HEAD.match(line)
        if m:
            out.append({"id": m.group(1) or "", "name": m.group(2), "fields": {}})
            continue
        f = FIELD.match(line)
        if f and out:
            out[-1]["fields"][src.norm(f.group(1))] = f.group(2).strip()
    return out


def section_fields(text, title):
    """{campo: valor} de las lineas '- **Campo:** valor' de una seccion."""
    out = {}
    for line in src.section(text, title).splitlines():
        f = FIELD.match(line)
        if f:
            out[src.norm(f.group(1))] = f.group(2).strip()
    return out


def check_signals(prep):
    """E-PREP-SIGNAL-THRESHOLD (R004): una senal sin umbral con cifra. Un
    umbral que sigue siendo hueco ya lo cuenta E-PREP-TEMPLATE."""
    out = []
    for s in prep_signals(prep["text"]):
        value = s["fields"].get("umbral", "")
        if holes(value):
            continue
        if not re.search(r"\d", value):
            name = " — ".join(x for x in (s["id"], s["name"]) if x)
            out.append(_finding("E-PREP-SIGNAL-THRESHOLD",
                                f"{prep['rel']}: la señal {name} no tiene un umbral con "
                                f"cifra («{value or 'sin umbral'}»).", prep["rel"]))
    return out


def check_rollback(prep):
    """E-PREP-ROLLBACK-TRIGGER (R005): la vuelta atras sin disparador."""
    value = section_fields(prep["text"], "vuelta atras").get("disparador", "")
    if holes(value) or value.strip("`*_—- "):
        return []
    return [_finding("E-PREP-ROLLBACK-TRIGGER",
                     f"{prep['rel']}: la vuelta atrás no dice qué señal o condición la "
                     "dispara (campo Disparador).", prep["rel"])]


def recorded_release(text):
    """La huella de la version guardada en la fila Versión ('0.4.0 · <huella>'),
    o None."""
    value = src.header_row(text, "Versión") or src.header_row(text, "Version") or ""
    m = src.DIGEST.search(value)
    return m.group(1) if m else None


def check_preparation(root, prep):
    """Hallazgos de una preparacion. En borrador, la comprobacion entera; una
    aprobada solo se mira por si cambio ella (R011) o su version."""
    rel = prep["rel"]
    if prep["state"] == "approved":
        current = src.release(root, prep["version"])
        if current and current["digest"] == recorded_release(prep["text"]):
            return []
        return [_finding("W-PREP-RELEASE-CHANGED",
                         f"{rel} se aprobó para la versión {prep['version']} con otra huella: "
                         "la versión cambió (o ya no existe). Revisa la preparación frente a "
                         "ella y apruébala de nuevo con /operate:approve.", rel)]
    if prep["state"] == "stale":
        return [_finding("W-PREP-NOT-APPROVED",
                         f"{rel} cambió después de aprobarse: ya no cuenta como aprobada. El "
                         "usuario la revisa y la aprueba de nuevo con /operate:approve.", rel)]
    return [_finding("W-PREP-NOT-APPROVED",
                     f"{rel} no está aprobada. La aprueba el usuario con /operate:approve.",
                     rel)] + prep_errors(root, prep)


def prep_errors(root, prep):
    """Lo que impide aprobar una preparacion (R002, R004, R005, R009)."""
    rel = prep["rel"]
    out = []
    refusal = release_refusal(prep["version"], src.release(root, prep["version"]))
    if refusal:
        out.append(_finding("E-PREP-RELEASE", f"{rel}: {refusal}", rel))
    found = holes(prep["text"], PREP_GENERATED, subheadings=True)
    if found:
        out.append(_finding("E-PREP-TEMPLATE",
                            f"{rel} conserva {len(found)} hueco(s) sin completar, como "
                            f"«{first_hole(found)}». Los completa /operate:prepare.", rel))
    return out + check_signals(prep) + check_rollback(prep)


# --------------------------------------------------------------------------
# Comprobacion (D5)
# --------------------------------------------------------------------------

def _finding(code, message, artifact):
    # Los codigos son contrato publico: emitir uno sin declararlo es un fallo
    # del plugin, no un hallazgo.
    if code not in FINDINGS:
        raise ValueError(f"codigo de hallazgo no declarado: {code}")
    return {"code": code, "severity": "error" if code.startswith("E-") else "warning",
            "message": message, "artifact": artifact}


def version_arg(value):
    """'v0.4.0', '0.4.0' o 'operations/v0.4.0.md' -> '0.4.0'; None si no lo es."""
    m = re.fullmatch(r"(?:.*/)?v?(\d+\.\d+\.\d+)(?:\.md)?", (value or "").strip())
    return m.group(1) if m else None


def check_incident_version(root, inc):
    """E-INCIDENT-RELEASE (R007): una versión afectada que no existe en
    releases/. 'desconocida' vale (R017); un hueco lo cuenta la plantilla."""
    value = inc["version"].strip("`*_ ")
    if not value or src.norm(value) in UNKNOWN_VERSION or holes(inc["version"]):
        return []
    number = version_arg(value)
    if number and src.release(root, number):
        return []
    return [_finding("E-INCIDENT-RELEASE",
                     f"El incidente {inc['id']} cita la versión afectada «{value}», que no "
                     f"existe en releases/. Corrígela, o escribe «desconocida».", inc["rel"])]


def check_incident(root, inc):
    """Hallazgos de un incidente. En borrador, la comprobacion entera; uno
    aprobado, sus acciones sin feature (R015); uno cambiado, el aviso (R011)."""
    rel = inc["rel"]
    if inc["state"] == "approved":
        return check_action_features(root, inc)
    if inc["state"] == "stale":
        return [_finding("W-INCIDENT-NOT-APPROVED",
                         f"El postmortem de {inc['id']} cambió después de aprobarse: ya no "
                         "cuenta como aprobado. El usuario lo revisa y lo aprueba de nuevo "
                         "con /operate:approve.", rel)]
    return [_finding("W-INCIDENT-NOT-APPROVED",
                     f"El postmortem de {inc['id']} no está aprobado. Se completa con "
                     "/operate:postmortem y lo aprueba el usuario con /operate:approve.",
                     rel)] + incident_errors(root, inc)


def incident_errors(root, inc):
    """Lo que impide aprobar un incidente y su postmortem (R007, R008, R009)."""
    rel = inc["rel"]
    out = []
    found = holes(inc["text"])
    if found:
        out.append(_finding("E-INCIDENT-TEMPLATE",
                            f"{rel} conserva {len(found)} hueco(s) sin completar, como "
                            f"«{first_hole(found)}».", rel))
    return out + check_incident_version(root, inc) + check_action_ids(inc)


def check_action_ids(inc):
    """E-INCIDENT-ACTION-ID (R008): una accion sin ID, con el de otro
    incidente o repetido."""
    out, seen = [], set()
    for aid, title in actions(inc["text"]):
        if not aid:
            problem = (f"la acción «{title}» no tiene ID: dale el de "
                       f"`operate.py next-action {inc['id']}`")
        elif ACTION_ID.match(aid).group(1) != inc["id"]:
            problem = f"la acción {aid} es de otro incidente; las suyas son {inc['id']}-A<n>"
        elif aid in seen:
            problem = f"la acción {aid} está repetida"
        else:
            seen.add(aid)
            continue
        out.append(_finding("E-INCIDENT-ACTION-ID", f"{inc['id']}: {problem}.", inc["rel"]))
    return out


def check_action_features(root, inc):
    """W-INCIDENT-ACTION-NO-FEATURE (R015): de un postmortem aprobado, las
    acciones que ninguna spec cita como primer elemento de su Origen."""
    taken = src.features_by_origin(root)
    return [_finding("W-INCIDENT-ACTION-NO-FEATURE",
                     f"La acción {aid} del postmortem de {inc['id']} no tiene feature: se "
                     f"crea con /sdd:specify {aid}.", inc["rel"])
            for aid, _t in actions(inc["text"]) if aid and aid not in taken]


SCHEMA = "operate.check/v1"


def analyze(root, target=None):
    """
    Hallazgos de operations/ (o solo de la preparacion vX.Y.Z o del incidente
    I001), con el schema operate.check/v1: {schema, ok, counts, findings:
    [{code, severity, message, artifact}]}.
    """
    all_preps = [p for p in preparations(root) if target in (None, p["version"])]
    all_incidents = [i for i in incidents(root) if target in (None, i["id"])]
    findings = []
    for prep in all_preps:
        findings += check_preparation(root, prep)
    for inc in all_incidents:
        findings += check_incident(root, inc)
    errors = sum(1 for f in findings if f["severity"] == "error")
    return {
        "schema": SCHEMA,
        "ok": errors == 0,
        "counts": {"preparations": len(all_preps), "incidents": len(all_incidents),
                   "errors": errors, "warnings": len(findings) - errors},
        "findings": findings,
    }


def report(data):
    c = data["counts"]
    out = [f"Operación: {c['preparations']} preparación(es), {c['incidents']} incidente(s)"]
    for sev, label in (("error", "ERRORES"), ("warning", "AVISOS")):
        items = [f for f in data["findings"] if f["severity"] == sev]
        if items:
            out.append(f"\n  {label} ({len(items)})")
            out += [f"    [{f['code']}] {f['message']}" for f in items]
    out.append("\n  OK: sin errores." if data["ok"]
               else f"\n  FALLA: {c['errors']} error(es).")
    return "\n".join(out)


def target_arg(value):
    """'I001' o 'v0.4.0' -> 'I001' o '0.4.0'; None si no es ninguno."""
    value = (value or "").strip()
    if INCIDENT_ID.match(value.upper()):
        return value.upper()
    return version_arg(value)


def cmd_check(args):
    """
    Informe legible (siempre exit 0), --json (operate.check/v1) o --check
    (exit 1 si hay errores): lo mismo en local y en CI (R016).
    """
    flags = [a for a in args if a in ("--json", "--check")]
    rest = [a for a in args if a not in flags]
    target = target_arg(rest[0]) if len(rest) == 1 else None
    if len(rest) > 1 or (rest and not target):
        # En CI, una errata como --chek no debe convertirse en un exit 0.
        print(f"error: argumento desconocido {' '.join(rest)}. "
              "Uso: operate.py check [vX.Y.Z|I001] [--json] [--check]", file=sys.stderr)
        return 2
    root = project_root()
    if target and target.startswith("I") and target not in incident_files(root):
        print(f"error: no existe el incidente {target} en {OPS_DIR}/{INCIDENTS_DIR}/.",
              file=sys.stderr)
        return 2
    prep = root / OPS_DIR / f"v{target}.md"
    if target and not target.startswith("I") and not prep.is_file():
        print(f"error: no existe la preparación {OPS_DIR}/v{target}.md.", file=sys.stderr)
        return 2
    data = analyze(root, target)
    if "--json" in flags:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(report(data))
    return 1 if ("--check" in flags and not data["ok"]) else 0


# --------------------------------------------------------------------------
# approve (D8, R009-R011). Solo la lanza el usuario, con /operate:approve;
# los hooks impiden que el modelo la escriba.
# --------------------------------------------------------------------------

def set_status(text, value):
    """Devuelve (texto_nuevo, cambiado?). Copia de set_status de
    plugins/release/scripts/release.py, que copia la de architecture.py, y
    esta la de discovery.py."""
    end = src._header_end(text)
    head, n = src.STATUS_ROW.subn(lambda m: m.group(1) + value + m.group(3), text[:end],
                                  count=1)
    return head + text[end:], bool(n)


def with_release_digest(text, version, digest):
    """(texto, cambiado?): la fila Versión con la huella de la version del
    momento de aprobar."""
    end = src._header_end(text)
    row = re.compile(r"^(\|\s*Versi[oó]n\s*\|\s*)([^|\n]*?)(\s*\|)", re.M)
    head, n = row.subn(lambda m: m.group(1) + f"{version} · {digest}" + m.group(3),
                       text[:end], count=1)
    return head + text[end:], bool(n)


def approve(root, target):
    """(ok, lineas). Aprueba la preparacion vX.Y.Z o el postmortem I001; no
    toca nada si se niega (R009)."""
    if target is None:
        return False, ["Indica qué aprobar: una preparación (v0.4.0) o un incidente (I001). "
                       "Uso: /operate:approve v0.4.0"]
    if target.startswith("I"):
        art = next((i for i in incidents(root) if i["id"] == target), None)
        if art is None:
            return False, [f"No existe el incidente {target} en {OPS_DIR}/{INCIDENTS_DIR}/."]
        what, errors = f"El postmortem de {target} ya estaba aprobado", incident_errors(root, art)
    else:
        art = next((p for p in preparations(root) if p["version"] == target), None)
        if art is None:
            return False, [f"No existe la preparación {OPS_DIR}/v{target}.md. Se crea con "
                           "/operate:prepare."]
        what = f"La preparación de la versión {target} ya estaba aprobada"
        errors = prep_errors(root, art)
    rel = art["rel"]
    text = art["text"]
    current = None if target.startswith("I") else src.release(root, target)
    # Una preparacion aprobada cuya version cambio o desaparecio se vuelve a
    # comprobar entera, como en check (W-PREP-RELEASE-CHANGED).
    if art["state"] == "approved" and (
            target.startswith("I")
            or (current is not None and current["digest"] == recorded_release(text))):
        return True, [f"{what} ({rel})."]
    if errors:
        return False, ([f"No se puede aprobar {rel}: la comprobación da errores."]
                       + [f"  [{f['code']}] {f['message']}" for f in errors])
    if current is not None:
        # R011: se sella con la version del momento; si cambia, check lo avisa.
        text, changed = with_release_digest(text, target, current["digest"])
        if not changed:
            return False, [f"{rel} no tiene la fila '| Versión | ... |' en la cabecera, donde "
                           "se guarda la huella de la versión. Añádela y vuelve a aprobar."]
    stamp = f"Approved · {src.content_digest(text)}"
    text, changed = set_status(text, stamp)
    if not changed:
        return False, [f"{rel} no tiene la fila '| Estado | ... |' en la cabecera. "
                       "Añádela y vuelve a aprobar."]
    (Path(root) / rel).write_text(text, encoding="utf-8")
    lines = [f"{rel} aprobado ({stamp})."]
    if target.startswith("I"):
        ids = [aid for aid, _t in actions(text) if aid]
        if ids:
            lines.append("Cada acción se convierte en una feature de corrección con "
                         + ", ".join(f"/sdd:specify {a}" for a in ids) + ".")
    return True, lines


def cmd_approve(args):
    """
    Con --skill (lo usa /operate:approve) todo va a stdout y sale siempre con
    0: el resultado lo lee el modelo como texto, no como codigo de salida.
    """
    rest = [a for a in args if a != "--skill" and a.strip()]
    target = target_arg(rest[0]) if len(rest) == 1 else None
    try:
        if len(rest) > 1 or (rest and not target):
            ok, lines = False, [f"Argumento desconocido {' '.join(rest)}. "
                                "Uso: operate.py approve <vX.Y.Z|I001>"]
        else:
            ok, lines = approve(project_root(), target)
    except Exception as exc:  # noqa: BLE001
        if "--skill" not in args:
            raise
        ok, lines = False, [f"No se pudo aprobar: error inesperado ({exc})."]
    stream = sys.stdout if (ok or "--skill" in args) else sys.stderr
    print("\n".join(lines), file=stream)
    return 0 if (ok or "--skill" in args) else 1


# --------------------------------------------------------------------------
# Guardrails (D8, R012): el modelo no puede aprobar una preparacion ni un
# postmortem, ni escribiendo el Estado ni ejecutando operate.py approve.
# --------------------------------------------------------------------------

BYPASS = "OPERATE_BYPASS"
APPROVE_TEXT = re.compile(r"operate\.py['\"]?\s+approve\b")

GUARD_REASON = (
    "Guardrail operate: aprobar una preparación o un postmortem es del usuario, no "
    "tuyo. Es la prueba de que una persona revisó cómo se pone en marcha la versión o "
    "qué se aprende de un incidente.\n\n"
    "No pongas Approved ni una huella en el campo Estado de operations/v*.md ni de "
    "operations/incidents/*.md, ni ejecutes `operate.py approve`: pídele al usuario que "
    "lo revise y ejecute /operate:approve. Puedes dejarlo en Draft.\n\n"
    "Escape puntual: OPERATE_BYPASS=1."
)


def claims_approval(text):
    """True si el Estado de la cabecera dice Approved o lleva una huella."""
    status = src.doc_status(text) or ""
    words = src.norm(status).strip("`*_ ").split()
    return (bool(words and words[0].strip("`*_") in src.APPROVED)
            or bool(src.DIGEST.search(status)))


def guarded_files(root):
    """Rutas relativas de las preparaciones y los incidentes que se protegen."""
    out = []
    for sub, pattern in (("", PREPARATION_FILE), (INCIDENTS_DIR, INCIDENT_FILE)):
        base = Path(root) / OPS_DIR / sub
        try:
            out += sorted(f"{OPS_DIR}/{sub + '/' if sub else ''}{p.name}"
                          for p in base.iterdir() if p.is_file() and pattern.match(p.name))
        except OSError:
            pass
    return out


def _guarded_target(root, raw_path):
    """Ruta relativa de la preparacion o el incidente al que apunta raw_path,
    o None. Con el mismo criterio que guarded_files, que usa la auditoria: un
    artefacto es vX.Y.Z.md o INNN-slug.md, con .md en minusculas, como los
    reconocen check y approve."""
    try:
        target = Path(raw_path)
        if not target.is_absolute():
            target = Path(root) / target
        rel = target.resolve().relative_to((Path(root) / OPS_DIR).resolve())
    except (OSError, ValueError, TypeError):
        return None
    parts = rel.parts
    if len(parts) == 1 and PREPARATION_FILE.match(parts[0]):
        return f"{OPS_DIR}/{parts[0]}"
    if len(parts) == 2 and parts[0] == INCIDENTS_DIR and INCIDENT_FILE.match(parts[1]):
        return f"{OPS_DIR}/{INCIDENTS_DIR}/{parts[1]}"
    return None


# Analisis de comandos: ejecutar approve frente a mencionarlo.
#
# Copia adaptada del analizador de plugins/release/scripts/release.py, que
# copia el de plugins/architecture/scripts/architecture.py, este el de
# plugins/discovery/scripts/discovery.py y este el de
# plugins/sdd/scripts/sdd_bash.py: los plugins no comparten codigo. Es la
# quinta copia. Un arreglo en una se replica en las otras, y los selftests
# usan la misma lista de casos MENCIONES/EJECUCIONES.

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
    True si el comando **ejecuta** operate.py approve: en algun segmento, una
    palabra cuyo nombre de archivo es operate.py seguida de approve, tambien
    dentro de una sustitucion que se ejecuta. Una mencion (mensaje de commit,
    PR, heredoc) no cuenta. Lo que no se puede analizar se evalua por su
    texto; lo que no se ve lo revierte la auditoria.
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
            if os.path.basename(word) == "operate.py" and nxt == "approve":
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
    return Path(tempfile.gettempdir()) / "operate-audit" / f"{digest}.json"


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
        text = src.read_text(Path(root) / rel)
        if text is not None:
            out[rel] = src.doc_status(text)
    return out


def cmd_guard(_args):
    """Hook PreToolUse sobre Write|Edit|Bash. Nunca devuelve allow."""
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    root = project_root(payload)
    # Sin operations/ tambien se vigila: un Write puede crear la primera
    # preparacion ya aprobada, y un comando, crearla con approve.
    if os.environ.get(BYPASS) == "1":
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
    before = src.read_text(target) if target.is_file() else ""
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
    if claims_approval(after) and src.doc_status(after) != src.doc_status(before or ""):
        return deny(GUARD_REASON)
    return 0


def cmd_audit(_args):
    """
    Hook PostToolUse sobre Bash: si un comando aprobo una preparacion o un
    postmortem, devuelve su Estado al valor anterior. Exit 2 para que el
    modelo lea el aviso; PostToolUse no puede deshacer el comando.
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
    # Se recorre todo lo protegido de ahora, no solo lo de antes: lo creado
    # ya aprobado tambien vuelve a Draft.
    for rel in guarded_files(root):
        text = src.read_text(root / rel)
        old = before.get(rel)
        if text is not None and claims_approval(text) and src.doc_status(text) != old:
            (root / rel).write_text(set_status(text, old or "Draft")[0], encoding="utf-8")
            restored.append(f"{rel} (vuelve a '{old or 'Draft'}')")
    if not restored:
        return 0
    sys.stderr.write("Guardrail operate: el comando cambió el Estado de "
                     + ", ".join(restored) + ". Aprobar una preparación o un "
                     "postmortem es del usuario, con /operate:approve. Detente y dile "
                     "al usuario lo que pasó.\n")
    return 2


COMMANDS = {
    "prepare": cmd_prepare,
    "incident": cmd_incident,
    "next-action": cmd_next_action,
    "check": cmd_check,
    "approve": cmd_approve,
    "guard": cmd_guard,
    "audit": cmd_audit,
}

# Un hook que revienta nunca debe bloquear al usuario: falla abierto.
HOOKS = {"guard", "audit"}

# Codigos de hallazgo declarados: el selftest exige probar cada uno. Son
# contrato publico (prefijos *-PREP-* e *-INCIDENT-* reservados en el
# registro comun).
FINDINGS = {
    "E-PREP-RELEASE": ("La preparación es de una versión que no existe o no está "
                       "publicada"),
    "E-PREP-SIGNAL-THRESHOLD": "Una señal sin umbral con cifra",
    "E-PREP-ROLLBACK-TRIGGER": "La vuelta atrás no dice qué la dispara",
    "E-PREP-TEMPLATE": "Huecos sin completar en la preparación",
    "W-PREP-NOT-APPROVED": "Preparación sin aprobar o cambiada después de aprobarse",
    "W-PREP-RELEASE-CHANGED": "La versión cambió desde que se aprobó su preparación",
    "E-INCIDENT-RELEASE": "El incidente cita una versión afectada que no existe",
    "E-INCIDENT-TEMPLATE": "Huecos sin completar en el incidente o su postmortem",
    "E-INCIDENT-ACTION-ID": "Una acción sin ID, con el de otro incidente o repetido",
    "W-INCIDENT-ACTION-NO-FEATURE": "Una acción de un postmortem aprobado sin feature",
    "W-INCIDENT-NOT-APPROVED": "Postmortem sin aprobar o cambiado después de aprobarse",
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[1]](argv[2:])
    except Exception as exc:  # noqa: BLE001
        if argv[1] in HOOKS:
            print(f"operate.py {argv[1]}: {exc}", file=sys.stderr)
            return 0
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv))
