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
  incident "<titulo>"  Registra el siguiente incidente (I001, I002…) en
                      operations/incidents.md, que solo crece, y escribe
                      operations/incidents/INNN-slug.md con sus huecos.
  check [vX.Y.Z|I001] [--json] [--check]
                      Comprueba esa preparacion o ese incidente, o todo
                      operations/. --json emite operate.check/v1; --check
                      sale con 1 si hay errores (para CI).
"""

import datetime
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


def holes(text, generated=()):
    """Huecos que siguen sin rellenar. No cuentan las notas en blockquote, el
    codigo en linea, los encabezados ni las secciones generated, que escribe
    el script."""
    out, skip = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            skip = src.norm(m.group(1)).strip() in generated
        if skip or line.lstrip().startswith((">", "#")):
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
    rel = inc["rel"]
    if inc["state"] != "draft":
        return []
    out = [_finding("W-INCIDENT-NOT-APPROVED",
                    f"El postmortem de {inc['id']} no está aprobado. Se completa con "
                    "/operate:postmortem y lo aprueba el usuario con /operate:approve.", rel)]
    found = holes(inc["text"])
    if found:
        out.append(_finding("E-INCIDENT-TEMPLATE",
                            f"{rel} conserva {len(found)} hueco(s) sin completar, como "
                            f"«{first_hole(found)}».", rel))
    return out + check_incident_version(root, inc)


SCHEMA = "operate.check/v1"


def analyze(root, target=None):
    """
    Hallazgos de operations/ (o solo de la preparacion vX.Y.Z o del incidente
    I001), con el schema operate.check/v1: {schema, ok, counts, findings:
    [{code, severity, message, artifact}]}.
    """
    all_incidents = [i for i in incidents(root) if target in (None, i["id"])]
    findings = []
    for inc in all_incidents:
        findings += check_incident(root, inc)
    errors = sum(1 for f in findings if f["severity"] == "error")
    return {
        "schema": SCHEMA,
        "ok": errors == 0,
        "counts": {"preparations": 0, "incidents": len(all_incidents),
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
    data = analyze(root, target)
    if "--json" in flags:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(report(data))
    return 1 if ("--check" in flags and not data["ok"]) else 0


COMMANDS = {
    "incident": cmd_incident,
    "check": cmd_check,
}

# Codigos de hallazgo declarados: el selftest exige probar cada uno. Son
# contrato publico (prefijos *-PREP-* e *-INCIDENT-* reservados en el
# registro comun).
FINDINGS = {
    "E-INCIDENT-RELEASE": "El incidente cita una versión afectada que no existe",
    "E-INCIDENT-TEMPLATE": "Huecos sin completar en el incidente o su postmortem",
    "W-INCIDENT-NOT-APPROVED": "Postmortem sin aprobar o cambiado después de aprobarse",
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
