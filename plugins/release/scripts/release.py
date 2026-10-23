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
                      con 1 si hay errores (para CI).
"""

import hashlib
import json
import os
import re
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
    "W-RELEASE-NOT-APPROVED": "Versión sin aprobar o cambiada después de aprobarse",
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
