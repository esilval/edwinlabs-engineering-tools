#!/usr/bin/env python3
"""
release.py - utilidades deterministas del plugin release.

Todo lo que no requiere criterio vive aqui: el borrador de una version, la
comprobacion de sus features, el numero de version, el sellado y los
guardrails. Las skills solo redactan las notas y los cambios tecnicos.

El plugin lee specs/ (lo deja sdd) y solo escribe en releases/. No importa
codigo de otros plugins: es una etapa independiente, unida a las demas por
archivos.

Subcomandos:
  new <features...> [--version X.Y.Z]
                      Escribe releases/vX.Y.Z.md en borrador con las features
                      elegidas (008 o 008-slug), el numero propuesto o el
                      fijado, la comprobacion del momento y los huecos de las
                      notas para usuarios y los cambios tecnicos. Si el
                      archivo ya existe, no lo toca.
  approve [vX.Y.Z] [--skill]
                      Aprueba la version si la comprobacion no da errores ni
                      quedan huecos: reescribe su Comprobacion, la sella con
                      'Approved · <huella>' y muestra el git tag que ejecuta
                      el usuario. Solo lo lanza el usuario, con
                      /release:approve.
  check [vX.Y.Z] [--json] [--check]
                      Comprueba la version indicada, o todas las de
                      releases/. --json emite release.check/v1; --check sale
                      con 1 si hay errores (para CI). La trazabilidad de
                      cada feature la da sdd.py trace --feature, que se busca
                      en SDD_SCRIPT, junto al plugin o en la cache de plugins.
"""

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_specs as specs  # noqa: E402

RELEASES_DIR = "releases"
SPECS_DIR = "specs"
PHASE_FILES = {"spec": "spec.md", "plan": "plan.md", "tasks": "tasks.md"}


# --------------------------------------------------------------------------
# Raiz del proyecto. Copia de project_root y find_upwards de
# plugins/architecture/scripts/architecture.py (y de sdd.py y discovery.py):
# los plugins no comparten codigo.
# --------------------------------------------------------------------------

def project_root(payload=None):
    """
    CLAUDE_PROJECT_DIR se usa tal cual. Sin ella (la inyeccion de comandos de
    una skill no la recibe), se sube desde el cwd hasta releases/ y, si no lo
    hay, hasta specs/, sin salir del repositorio.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    start = Path((payload or {}).get("cwd") or os.getcwd()).resolve()
    return (find_upwards(start, (RELEASES_DIR,)) or find_upwards(start, (SPECS_DIR,))
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
# El artefacto releases/vX.Y.Z.md (D2): cabecera, Estado y huella
# --------------------------------------------------------------------------

STATUS_ROW = specs.STATUS_ROW
APPROVED = specs.APPROVED
RELEASE_FILE = re.compile(r"^v(\d+\.\d+\.\d+)\.md$")


def text_digest(text):
    lines = [specs._squash(raw) for raw in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def content_digest(text):
    """Huella de la version: todo menos la fila Estado, donde se guarda."""
    end = specs._header_end(text)
    return text_digest(STATUS_ROW.sub("", text[:end], count=1) + text[end:])


def release_state(text):
    """'draft' | 'approved' | 'stale' (cambio tras aprobarse)."""
    if not specs.is_approved(text):
        return "draft"
    stamp = specs.approval_digest(text)
    if not stamp:
        return "draft"
    return "approved" if stamp == content_digest(text) else "stale"


def feature_list(value):
    """'008, 009' -> ['008', '009']; '—' o vacio -> []."""
    return [x for x in re.split(r"[,\s]+", (value or "").strip("`*_ ")) if x and x not in "—-"]


def releases(root):
    """[{file, rel, version, header_version, features, state, text}] de
    releases/, ordenadas por nombre de archivo."""
    out = []
    base = Path(root) / RELEASES_DIR
    try:
        paths = sorted(p for p in base.iterdir() if p.is_file() and p.suffix == ".md")
    except OSError:
        return []
    for path in paths:
        m = RELEASE_FILE.match(path.name)
        if not m:
            continue
        text = specs.read_text(path) or ""
        out.append({
            "file": path.name,
            "rel": f"{RELEASES_DIR}/{path.name}",
            "version": m.group(1),
            "header_version": (specs.header_row(text, "Versión")
                               or specs.header_row(text, "Version") or "").strip("`*_ "),
            "features": feature_list(specs.header_row(text, "Features")),
            "state": release_state(text),
            "text": text,
        })
    return out


def published(release):
    """Publicada: aprobada alguna vez, aunque cambiara despues (D6)."""
    return release["state"] in ("approved", "stale")


# --------------------------------------------------------------------------
# Numero de version (D6): MAYOR.MENOR.PARCHE, enteros sin ceros a la izquierda
# --------------------------------------------------------------------------

SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def parse_version(text):
    """'0.4.0' -> (0, 4, 0); None si no es MAYOR.MENOR.PARCHE."""
    m = SEMVER.fullmatch((text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def show(version):
    return ".".join(str(x) for x in version)


def last_published(all_releases, exclude=None):
    """La mayor version publicada (D6), sin contar exclude; None si no hay."""
    found = [parse_version(r["version"]) for r in all_releases
             if published(r) and r is not exclude]
    found = [v for v in found if v]
    return max(found) if found else None


def propose(last, features):
    """Numero propuesto (R007) tras last, para features de release_specs:
    sin version previa, 0.1.0; con un requisito OBSOLETO, la mayor (en 0.x,
    la menor); con alguna funcionalidad, la menor; solo correcciones, el
    parche."""
    if last is None:
        return (0, 1, 0)
    major, minor, patch = last
    retired = any(r["priority"] == "OBSOLETE" for f in features for r in f["requirements"])
    if retired:
        return (0, minor + 1, 0) if major == 0 else (major + 1, 0, 0)
    # Prudente: un Tipo no valido (E-RELEASE-FEATURE-TYPE) cuenta como
    # funcionalidad, y sin ninguna feature valida tampoco se propone un parche.
    if not features or any(f["type"] != "corrección" for f in features):
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def proposed_version(root, names):
    """Numero propuesto para una version con las features names, tras la
    ultima publicada de releases/. Las features que no existen no cuentan:
    las informa check."""
    found = [specs.resolve(root, n) for n in names]
    features = [specs.feature(f[0]) for f in found if len(f) == 1]
    return show(propose(last_published(releases(root)), features))


def check_version(release, all_releases):
    """E-RELEASE-VERSION (R008) de una version en borrador."""
    rel, out = release["rel"], []
    header, name = release["header_version"], release["version"]
    current = parse_version(header)
    if current is None:
        return [_finding("E-RELEASE-VERSION",
                         f"{rel}: la versión «{header}» no es MAYOR.MENOR.PARCHE "
                         "(enteros sin ceros a la izquierda).", rel)]
    if parse_version(name) is None:
        return [_finding("E-RELEASE-VERSION",
                         f"{rel}: el archivo v{name} no es MAYOR.MENOR.PARCHE "
                         "(enteros sin ceros a la izquierda).", rel)]
    if current != parse_version(name):
        out.append(_finding("E-RELEASE-VERSION",
                            f"{rel}: la cabecera dice {header} y el archivo es v{name}: "
                            "tienen que coincidir.", rel))
    for other in all_releases:
        if other is not release and current in (parse_version(other["version"]),
                                                parse_version(other["header_version"])):
            out.append(_finding("E-RELEASE-VERSION",
                                f"{rel}: la versión {header} ya existe en {other['rel']}.",
                                rel))
    # Una version ya publicada que se vuelve a sellar tiene su numero contado
    # (D6): no tiene que ser mayor que las que se publicaron despues.
    last = None if published(release) else last_published(all_releases, exclude=release)
    if last and current <= last:
        out.append(_finding("E-RELEASE-VERSION",
                            f"{rel}: la versión {header} no es mayor que la última "
                            f"publicada, {show(last)}.", rel))
    return out


# --------------------------------------------------------------------------
# Comprobacion (D7)
# --------------------------------------------------------------------------

def _finding(code, message, artifact):
    # Los codigos son contrato publico: emitir uno sin declararlo es un fallo
    # del plugin, no un hallazgo.
    if code not in FINDINGS:
        raise ValueError(f"codigo de hallazgo no declarado: {code}")
    return {"code": code, "severity": "error" if code.startswith("E-") else "warning",
            "message": message, "artifact": artifact}


PHASE_WORDS = {"draft": "sin aprobar", "stale": "cambió después de aprobarse",
               "missing": "no existe"}


def check_feature(root, release, name, others):
    """Hallazgos de una feature incluida en una version en borrador."""
    rel = release["rel"]
    found = specs.resolve(root, name)
    if not found:
        return [_finding("E-RELEASE-FEATURE-UNKNOWN",
                         f"La feature {name} no existe en specs/.", rel)]
    if len(found) > 1:
        return [_finding("E-RELEASE-FEATURE-UNKNOWN",
                         f"La feature {name} es ambigua: "
                         f"{', '.join(p.name for p in found)}. Usa el nombre completo.", rel)]
    f = specs.feature(found[0])
    out = []
    for other in others:
        if any(specs.resolve(root, n) == found for n in other["features"]):
            out.append(_finding("E-RELEASE-FEATURE-RELEASED",
                                f"La feature {f['slug']} ya está en la versión publicada "
                                f"v{other['version']} ({other['rel']}).", rel))
    for phase, state in f["phases"].items():
        if state != "approved":
            out.append(_finding("E-RELEASE-FEATURE-NOT-APPROVED",
                                f"La feature {f['slug']}: {PHASE_FILES[phase]} "
                                f"{PHASE_WORDS[state]}. Se aprueba en sdd con /sdd:approve.",
                                rel))
    open_tasks = [t["id"] for t in f["tasks"] if t["state"] != "done"]
    if open_tasks:
        out.append(_finding("E-RELEASE-FEATURE-OPEN-TASKS",
                            f"La feature {f['slug']} tiene tareas sin cerrar: "
                            f"{', '.join(open_tasks)}.", rel))
    if f["type"] is None:
        out.append(_finding("E-RELEASE-FEATURE-TYPE",
                            f"La feature {f['slug']} tiene Tipo «{f['type_raw']}»: "
                            "solo vale funcionalidad o corrección.", rel))
    return out + check_trace(root, f, rel)


# --------------------------------------------------------------------------
# Trazabilidad de sdd (D4): sdd.py trace --feature NNN --json, como comando
# externo; se lee su contrato publico sdd.trace/v1, no su codigo.
# --------------------------------------------------------------------------

TRACE_TIMEOUT = 60
ADR_CODES = {"E-PLAN-ADR-UNKNOWN", "E-PLAN-ADR-NOT-APPROVED"}


def plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT")
                or Path(__file__).resolve().parent.parent)


def sdd_script():
    """El sdd.py que se usa para trazar, o None. Orden de D4: SDD_SCRIPT; el
    plugin hermano (repositorio o enlace de desarrollo); la cache de plugins
    del marketplace, la version mas reciente. Los directorios de la cache se
    nombran por huella, no por numero: la mas reciente es la de sdd.py
    modificado por ultima vez, que es la ultima instalada."""
    env = os.environ.get("SDD_SCRIPT")
    if env and Path(env).is_file():
        return Path(env)
    here = plugin_root()
    sibling = here.parent / "sdd" / "scripts" / "sdd.py"
    if sibling.is_file():
        return sibling
    try:
        cached = [p for p in (here.parent.parent / "sdd").glob("*/scripts/sdd.py")
                  if p.is_file()]
    except OSError:
        cached = []
    return max(cached, key=lambda p: p.stat().st_mtime) if cached else None


def trace(root, slug):
    """(sdd.trace/v1, None) de la feature, o (None, motivo) si no se pudo."""
    script = sdd_script()
    if script is None:
        return None, "no se encuentra sdd.py (instala sdd o fija SDD_SCRIPT)"
    # CLAUDE_PLUGIN_ROOT es el de sdd, no el de release: sdd.py lee de ahi
    # sus plantillas para reconocer los huecos.
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root),
               CLAUDE_PLUGIN_ROOT=str(script.parent.parent))
    try:
        r = subprocess.run([sys.executable, str(script), "trace", "--feature", slug, "--json"],
                           capture_output=True, text=True, cwd=str(root), env=env,
                           timeout=TRACE_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"sdd.py trace no se pudo ejecutar ({exc.__class__.__name__})"
    if r.returncode != 0:
        why = (r.stderr.strip().splitlines() or [f"salió con {r.returncode}"])[-1]
        return None, f"sdd.py trace falló: {why}"
    try:
        data = json.loads(r.stdout)
        if data.get("schema") != "sdd.trace/v1" or not isinstance(data.get("findings"), list):
            raise ValueError
    except (ValueError, AttributeError):
        return None, "la salida de sdd.py trace no es sdd.trace/v1"
    return data, None


def check_trace(root, f, rel):
    """E-RELEASE-FEATURE-ADR (R005), E-RELEASE-FEATURE-TRACE (R004) o
    W-RELEASE-NO-TRACE (R016)."""
    data, why = trace(root, f["slug"])
    if data is None:
        return [_finding("W-RELEASE-NO-TRACE",
                         f"No se pudo obtener la trazabilidad de la feature {f['slug']}: "
                         f"{why}. No se comprueban su trazabilidad ni sus decisiones de "
                         "arquitectura; el resto de comprobaciones sí.", rel)]
    errors = [x for x in data["findings"]
              if isinstance(x, dict) and x.get("severity") == "error"]
    out = [_finding("E-RELEASE-FEATURE-ADR",
                    f"La feature {f['slug']}: {x.get('message', x['code'])}", rel)
           for x in errors if x.get("code") in ADR_CODES]
    rest = [x for x in errors if x.get("code") not in ADR_CODES]
    if rest:
        out.append(_finding("E-RELEASE-FEATURE-TRACE",
                            f"La trazabilidad de la feature {f['slug']} da {len(rest)} "
                            f"error(es), el primero [{rest[0].get('code')}] "
                            f"{rest[0].get('message', '')}. Se corrige en sdd (/sdd:trace).",
                            rel))
    return out


# --------------------------------------------------------------------------
# Huecos de plantilla (R010): texto en cursiva sin sustituir
# --------------------------------------------------------------------------

PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9_*])_[^_\n]+_(?![A-Za-z0-9_*])")
TEMPLATE_VAR = re.compile(r"\{\{[A-Z_]+\}\}")
GENERATED = {"contenido", "comprobacion"}


def holes(text):
    """Huecos que siguen sin rellenar. No cuentan las notas en blockquote, el
    codigo en linea, los encabezados ni las secciones Contenido y
    Comprobacion, que escribe el script con datos de specs/ (un titulo de
    spec con _x_ no es un hueco)."""
    out, generated = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            generated = specs.norm(m.group(1)).strip() in GENERATED
        if generated or line.lstrip().startswith((">", "#")):
            continue
        plain = re.sub(r"`[^`]*`", " ", line)
        out += [h.group(0) for h in PLACEHOLDER.finditer(plain)]
        out += TEMPLATE_VAR.findall(plain)
    return out


def check_template(release):
    found = holes(release["text"])
    if not found:
        return []
    first = found[0] if len(found[0]) <= 70 else found[0][:69] + "…"
    return [_finding("E-RELEASE-TEMPLATE",
                     f"{release['rel']} conserva {len(found)} hueco(s) sin completar, como "
                     f"«{first}». Los completa /release:new.", release["rel"])]


def check_release(root, release, all_releases, full=False):
    """Hallazgos de una version. Una publicada solo se mira por si cambio
    tras aprobarse (D7); full=True la comprueba entera, como un borrador,
    que es lo que hace approve antes de sellar."""
    rel = release["rel"]
    if release["state"] == "stale" and not full:
        return [_finding("W-RELEASE-NOT-APPROVED",
                         f"{rel} cambió después de aprobarse: ya no cuenta como aprobada, "
                         "pero sigue publicada (sus features y su número siguen contando). "
                         "El usuario la revisa y la aprueba de nuevo con /release:approve.",
                         rel)]
    if release["state"] == "approved" and not full:
        return []
    out = [_finding("W-RELEASE-NOT-APPROVED",
                    f"{rel} no está aprobada. La aprueba el usuario con "
                    "/release:approve.", rel)]
    if not release["features"]:
        out.append(_finding("E-RELEASE-NO-FEATURES",
                            f"{rel} no incluye ninguna feature: elígelas con "
                            "/release:new.", rel))
    out += check_template(release) + check_version(release, all_releases)
    others = [r for r in all_releases if r is not release and published(r)]
    for name in release["features"]:
        out += check_feature(root, release, name, others)
    return out


SCHEMA = "release.check/v1"


def analyze(root, version=None):
    """
    Hallazgos de las versiones de releases/ (o solo de vX.Y.Z), con el schema
    release.check/v1: {schema, ok, counts, findings: [{code, severity,
    message, artifact}]}.
    """
    all_releases = releases(root)
    targets = [r for r in all_releases if version in (None, r["version"])]
    findings = []
    for release in targets:
        findings += check_release(root, release, all_releases)
    errors = sum(1 for f in findings if f["severity"] == "error")
    return {
        "schema": SCHEMA,
        "ok": errors == 0,
        "counts": {"releases": len(targets),
                   "published": sum(1 for r in targets if published(r)),
                   "errors": errors, "warnings": len(findings) - errors},
        "findings": findings,
    }


def report(data):
    c = data["counts"]
    out = [f"Versiones: {c['releases']} ({c['published']} publicada(s))"]
    for sev, label in (("error", "ERRORES"), ("warning", "AVISOS")):
        items = [f for f in data["findings"] if f["severity"] == sev]
        if items:
            out.append(f"\n  {label} ({len(items)})")
            out += [f"    [{f['code']}] {f['message']}" for f in items]
    out.append("\n  OK: sin errores." if data["ok"]
               else f"\n  FALLA: {c['errors']} error(es).")
    return "\n".join(out)


def version_arg(value):
    """'v0.4.0', '0.4.0' o 'releases/v0.4.0.md' -> '0.4.0'; None si no lo es."""
    m = re.fullmatch(r"(?:.*/)?v?(\d+\.\d+\.\d+)(?:\.md)?", value.strip())
    return m.group(1) if m else None


def cmd_check(args):
    """
    Informe legible (siempre exit 0), --json (release.check/v1) o --check
    (exit 1 si hay errores): lo mismo en local y en CI (R014).
    """
    flags = [a for a in args if a in ("--json", "--check")]
    rest = [a for a in args if a not in flags]
    version = version_arg(rest[0]) if len(rest) == 1 else None
    if len(rest) > 1 or (rest and not version):
        # En CI, una errata como --chek no debe convertirse en un exit 0.
        print(f"error: argumento desconocido {' '.join(rest)}. "
              "Uso: release.py check [vX.Y.Z] [--json] [--check]", file=sys.stderr)
        return 2
    root = project_root()
    if version and not (root / RELEASES_DIR / f"v{version}.md").is_file():
        print(f"error: no existe {RELEASES_DIR}/v{version}.md.", file=sys.stderr)
        return 2
    data = analyze(root, version)
    if "--json" in flags:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(report(data))
    return 1 if ("--check" in flags and not data["ok"]) else 0


# --------------------------------------------------------------------------
# new (D2, D8): el borrador de una version
# --------------------------------------------------------------------------

CAND_REF = re.compile(r"(?<![A-Za-z0-9])B\d{2,}(?![0-9])")
GOAL_REF = re.compile(r"(?<![A-Za-z0-9])G\d+(?![0-9])")


def template_text():
    """La plantilla del artefacto, o None si no se encuentra."""
    for base in (plugin_root(), Path(__file__).resolve().parent.parent):
        text = specs.read_text(base / "templates" / "release.md")
        if text:
            return text
    return None


def replace_section(text, title, body):
    """Sustituye el cuerpo de '## title' hasta el siguiente encabezado de
    nivel 2, conservando las notas en blockquote del principio."""
    pattern = re.compile(rf"(^## {re.escape(title)}[^\n]*\n)(.*?)(?=^## |\Z)", re.M | re.S)

    def sub(m):
        notes = re.match(r"\s*((?:>[^\n]*\n)+)", m.group(2))
        keep = ("\n" + notes.group(1)) if notes else ""
        return m.group(1) + keep + "\n" + body.strip() + "\n\n"
    return pattern.sub(sub, text, count=1)


# Lo que la seccion Comprobacion no cuenta como resultado de las features: los
# huecos que el propio borrador trae para redactar (van en una linea aparte) y
# el aviso de que la version esta sin aprobar, que es su estado al escribirla.
NOT_FEATURE_CHECK = {"E-RELEASE-TEMPLATE", "W-RELEASE-NOT-APPROVED"}


def feature_check(data):
    """(hallazgos de la comprobacion, hallazgos de huecos) de analyze."""
    shown = [f for f in data["findings"] if f["code"] not in NOT_FEATURE_CHECK]
    pending = [f for f in data["findings"] if f["code"] == "E-RELEASE-TEMPLATE"]
    return shown, pending


def check_section(data):
    """Cuerpo de la seccion Comprobacion: el resultado de check sobre las
    features y el numero, y aparte lo que queda por redactar."""
    shown, pending = feature_check(data)
    errors = sum(1 for f in shown if f["severity"] == "error")
    today = datetime.date.today().isoformat()
    lines = [f"Resultado de `release.py check` el {today}: {errors} error(es) y "
             f"{len(shown) - errors} aviso(s)."]
    if shown:
        lines.append("")
        lines += [f"- `{f['code']}`: {f['message']}" for f in shown]
    if pending:
        lines += ["", "Pendiente: completar las notas para usuarios y los cambios técnicos "
                      "(`E-RELEASE-TEMPLATE` hasta que no quede ningún hueco)."]
    return "\n".join(lines)


def current_requirements(f):
    return [r["id"] for r in f["requirements"] if r["priority"] != "OBSOLETE"]


def content_block(f):
    reqs = current_requirements(f)
    return (f"### {f['id']} — {f['title']}\n\n"
            f"- **Tipo:** {f['type'] or f['type_raw']}\n"
            f"- **Origen:** {f['origin'] or '—'}\n"
            f"- **Requisitos:** {', '.join(reqs) or '—'}")


def notes_block(f):
    cands = CAND_REF.findall(f["origin"] or "")
    goals = GOAL_REF.findall(f["origin"] or "")
    cite = ""
    if cands or goals:
        parts = ([f"la candidata {', '.join(cands)}"] if cands else []) + (
            [f"el objetivo {', '.join(goals)}"] if goals else [])
        cite = f", a partir de {' y '.join(parts)} del producto"
    return (f"### {f['id']} — {f['title']}\n\n"
            f"_Redacta qué cambia para el usuario con esta feature{cite}._")


def changes_block(f):
    plan = f"specs/{f['slug']}/plan.md"
    retired = [r["id"] for r in f["requirements"] if r["priority"] == "OBSOLETE"]
    lines = [f"### {f['id']} — {f['title']}", "",
             f"- **Requisitos:** {', '.join(current_requirements(f)) or '—'}"]
    if retired:
        lines.append(f"- **Requisitos retirados:** {', '.join(retired)}")
    lines += [f"- **Decisiones de arquitectura:** {', '.join(f['adrs']) or 'ninguna'}",
              f"- **Contratos:** {'sí, en «Contratos» de ' + plan if f['contracts'] else 'no'}",
              f"- **Modelo de datos:** "
              f"{'sí, en «Modelo de datos» de ' + plan if f['data_model'] else 'no'}",
              "",
              "_Resume para el equipo técnico qué cambia con esta feature, a partir de "
              "estos datos._"]
    return "\n".join(lines)


def draft(root, number, names):
    """Texto del borrador (D2), sin la seccion Comprobacion rellena."""
    resolved = [(n, specs.resolve(root, n)) for n in names]
    features = [specs.feature(found[0]) for _n, found in resolved if len(found) == 1]
    header = ", ".join(specs.number(found[0]) if len(found) == 1 else n
                       for n, found in resolved)
    last = last_published(releases(root))
    values = {
        "VERSION": number,
        "DATE": datetime.date.today().isoformat(),
        "PREVIOUS": show(last) if last else "—",
        "FEATURES": header,
        "CONTENT": "\n\n".join(content_block(f) for f in features) or "Ninguna.",
        "CHECK": "Pendiente.",
        "NOTES": "\n\n".join(notes_block(f) for f in features) or "Ninguna.",
        "CHANGES": "\n\n".join(changes_block(f) for f in features) or "Ninguno.",
    }
    # En una sola pasada: un titulo de spec con {{NOTES}} no se sustituye.
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), m.group(0)),
                  template_text())


def cmd_new(args):
    """
    0 si escribe el borrador o ya existia; 1 sin features o con un numero mal
    formado (Contratos del plan).
    """
    args, number = list(args), None
    for i, a in enumerate(args):
        if a == "--version" or a.startswith("--version="):
            number = a.split("=", 1)[1] if "=" in a else (
                args[i + 1] if i + 1 < len(args) else "")
            del args[i:i + (1 if "=" in a else 2)]
            break
    unknown = [a for a in args if a.startswith("-")]
    if unknown:
        print(f"error: argumento desconocido {' '.join(unknown)}. "
              "Uso: release.py new <features...> [--version X.Y.Z]", file=sys.stderr)
        return 2
    if not args:
        print("No hay features que incluir: indica cuáles, por su número o su nombre "
              "en specs/ (release.py new 008 009). No se ha creado nada.", file=sys.stderr)
        return 1
    if number is not None:
        number = number.strip().lstrip("v")
        if parse_version(number) is None:
            print(f"error: la versión «{number}» no es MAYOR.MENOR.PARCHE (enteros sin "
                  "ceros a la izquierda). No se ha creado nada.", file=sys.stderr)
            return 1
    root = project_root()
    number = number or proposed_version(root, args)
    rel = f"{RELEASES_DIR}/v{number}.md"
    path = root / rel
    if path.exists():
        existing = feature_list(specs.header_row(specs.read_text(path), "Features"))
        print(f"{rel} ya existe, con las features {', '.join(existing) or 'ninguna'}: no se "
              "toca. Compruébala con /release:check, o fija otro número con --version.")
        return 0
    if template_text() is None:
        print("error: no se encuentra templates/release.md del plugin release. "
              "No se ha creado nada.", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(draft(root, number, args), encoding="utf-8")
    try:
        data = analyze(root, number)
    except Exception:
        path.unlink()  # sin la comprobacion, el borrador no se deja a medias
        raise
    path.write_text(replace_section(path.read_text(encoding="utf-8"), "Comprobación",
                                    check_section(data)), encoding="utf-8")
    shown, pending = feature_check(data)
    print(f"{rel} escrito en borrador, versión {number}.")
    print(report(dict(data, findings=shown, ok=not any(f["severity"] == "error" for f in shown),
                      counts=dict(data["counts"],
                                  errors=sum(f["severity"] == "error" for f in shown)))))
    if pending:
        print(f"\n  Pendiente: {len(holes(path.read_text(encoding='utf-8')))} hueco(s) en las "
              "notas para usuarios y los cambios técnicos (E-RELEASE-TEMPLATE hasta "
              "completarlos con /release:new).")
    return 0


# --------------------------------------------------------------------------
# approve (D8, R010-R012). Solo la lanza el usuario, con /release:approve;
# los hooks impiden que el modelo la escriba.
# --------------------------------------------------------------------------

def set_status(text, value):
    """Devuelve (texto_nuevo, cambiado?). Copia de set_status de
    plugins/architecture/scripts/architecture.py, que copia la de
    plugins/discovery/scripts/discovery.py; la de plugins/sdd/scripts/
    sdd_trace.py es la misma."""
    end = specs._header_end(text)
    head, n = STATUS_ROW.subn(lambda m: m.group(1) + value + m.group(3), text[:end], count=1)
    return head + text[end:], bool(n)


def approval_findings(root, release, all_releases):
    """Lo que impide aprobar (D8): la comprobacion entera, tambien al volver a
    sellar una version publicada que cambio, porque el cambio puede tocar sus
    features o su numero. El aviso de que esta sin aprobar no cuenta: es lo
    que approve resuelve."""
    return [f for f in check_release(root, release, all_releases, full=True)
            if f["code"] != "W-RELEASE-NOT-APPROVED"]


def approve(root, version=None):
    """(ok, lineas_de_mensaje). No toca nada si se niega (R010)."""
    all_releases = releases(root)
    if version:
        targets = [r for r in all_releases if r["version"] == version]
        if not targets:
            return False, [f"No existe {RELEASES_DIR}/v{version}.md."]
    else:
        # D8: la unica en borrador. Una publicada que cambio se nombra.
        targets = [r for r in all_releases if r["state"] == "draft"]
        if not targets:
            changed = [f"v{r['version']}" for r in all_releases if r["state"] == "stale"]
            return False, ["No hay ninguna versión en borrador en releases/. Se crea con "
                           "/release:new." + (f" Para volver a aprobar una que cambió tras "
                                              f"aprobarse, nómbrala: {', '.join(changed)}."
                                              if changed else "")]
        if len(targets) > 1:
            return False, ["Hay varias versiones en borrador: "
                           + ", ".join(f"v{r['version']}" for r in targets)
                           + f". Indica cuál: /release:approve v{targets[0]['version']}."]
    release = targets[0]
    rel = release["rel"]
    if release["state"] == "approved":
        return True, [f"{rel} ya estaba aprobada."]
    findings = approval_findings(root, release, all_releases)
    errors = [f for f in findings if f["severity"] == "error"]
    if errors:
        return False, ([f"No se puede aprobar {rel}: la comprobación da errores."]
                       + [f"  [{f['code']}] {f['message']}" for f in errors])

    # La evidencia sellada es la comprobacion del momento de aprobar.
    text = replace_section(release["text"], "Comprobación",
                           check_section({"findings": findings}))
    stamp = f"Approved · {content_digest(text)}"
    text, changed = set_status(text, stamp)
    if not changed:
        return False, [f"{rel} no tiene la fila '| Estado | ... |' en la cabecera. "
                       "Añádela y vuelve a aprobar."]
    (Path(root) / rel).write_text(text, encoding="utf-8")
    tag = f"v{release['version']}"
    features = ", ".join(release["features"])
    return True, [f"{rel} aprobada ({stamp}).",
                  "",
                  "El plugin no etiqueta ni publica. Para etiquetar la versión, ejecuta tú:",
                  f'  git tag -a {tag} -m "Versión {release["version"]}: features {features}"',
                  f"  git push origin {tag}"]


def cmd_approve(args):
    """
    Con --skill (lo usa /release:approve) todo va a stdout y sale siempre con
    0: el resultado lo lee el modelo como texto, no como codigo de salida.
    """
    rest = [a for a in args if a != "--skill"]
    version = version_arg(rest[0]) if len(rest) == 1 else None
    try:
        if len(rest) > 1 or (rest and not version):
            ok, lines = False, [f"Argumento desconocido {' '.join(rest)}. "
                                "Uso: release.py approve [vX.Y.Z]"]
        else:
            ok, lines = approve(project_root(), version)
    except Exception as exc:  # noqa: BLE001
        if "--skill" not in args:
            raise
        ok, lines = False, [f"No se pudo aprobar: error inesperado ({exc})."]
    stream = sys.stdout if (ok or "--skill" in args) else sys.stderr
    print("\n".join(lines), file=stream)
    return 0 if (ok or "--skill" in args) else 1


COMMANDS = {
    "new": cmd_new,
    "approve": cmd_approve,
    "check": cmd_check,
}

# Codigos de hallazgo declarados: el selftest exige probar cada uno. Son
# contrato publico (prefijo *-RELEASE-* reservado en el registro comun).
FINDINGS = {
    "E-RELEASE-NO-FEATURES": "La versión no incluye ninguna feature",
    "E-RELEASE-FEATURE-UNKNOWN": "Una feature incluida no existe en specs/",
    "E-RELEASE-FEATURE-RELEASED": "La feature ya está en otra versión publicada",
    "E-RELEASE-FEATURE-NOT-APPROVED": ("Una fase de la feature sin aprobar o cambiada "
                                       "tras aprobarse"),
    "E-RELEASE-FEATURE-OPEN-TASKS": "La feature tiene tareas sin cerrar",
    "E-RELEASE-FEATURE-TYPE": "El Tipo de la spec no es funcionalidad ni corrección",
    "E-RELEASE-FEATURE-TRACE": "La trazabilidad de la feature tiene errores",
    "E-RELEASE-FEATURE-ADR": "El plan cita una decisión de arquitectura no aprobada",
    "E-RELEASE-VERSION": ("Número de versión mal formado, no mayor que la última "
                          "publicada, repetido o distinto del archivo"),
    "E-RELEASE-TEMPLATE": "Quedan huecos de plantilla sin completar",
    "W-RELEASE-NOT-APPROVED": "Versión sin aprobar o cambiada después de aprobarse",
    "W-RELEASE-NO-TRACE": "La trazabilidad de una feature no se pudo obtener",
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
