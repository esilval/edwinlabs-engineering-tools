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
  check [vX.Y.Z] [--json] [--check]
                      Comprueba la version indicada, o todas las de
                      releases/. --json emite release.check/v1; --check sale
                      con 1 si hay errores (para CI). La trazabilidad de
                      cada feature la da sdd.py trace --feature, que se busca
                      en SDD_SCRIPT, junto al plugin o en la cache de plugins.
"""

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
    last = last_published(all_releases, exclude=release)
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


def check_release(root, release, all_releases):
    rel = release["rel"]
    if release["state"] == "stale":
        return [_finding("W-RELEASE-NOT-APPROVED",
                         f"{rel} cambió después de aprobarse: ya no cuenta como aprobada, "
                         "pero sigue publicada (sus features y su número siguen contando). "
                         "El usuario la revisa y la aprueba de nuevo con /release:approve.",
                         rel)]
    if release["state"] == "approved":
        return []
    out = [_finding("W-RELEASE-NOT-APPROVED",
                    f"{rel} no está aprobada. La aprueba el usuario con "
                    "/release:approve.", rel)]
    if not release["features"]:
        out.append(_finding("E-RELEASE-NO-FEATURES",
                            f"{rel} no incluye ninguna feature: elígelas con "
                            "/release:new.", rel))
    out += check_version(release, all_releases)
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


COMMANDS = {
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
