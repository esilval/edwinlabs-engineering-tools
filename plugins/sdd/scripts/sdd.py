#!/usr/bin/env python3
"""
sdd.py - utilidades deterministas del plugin SDD.

Todo lo que no requiere criterio vive aqui: numeracion de features, resolucion
de la feature activa, y la compuerta (gate) que decide si se puede escribir
codigo. El LLM no deberia tener que "acordarse" de nada de esto.

Subcomandos:
  new <descripcion>   Crea specs/NNN-slug/ y lo marca como feature activa.
  current             Imprime el slug de la feature activa (vacio si no hay).
  status              Reporte legible del estado del proyecto.
  context             Linea breve para inyectar en SessionStart.
  guard               Hook PreToolUse: lee JSON por stdin, decide sobre stdout.
"""

import datetime
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

FEATURE_RE = re.compile(r"^(\d{3,})-[a-z0-9]+(?:-[a-z0-9]+)*$")

# Orden de fases. (archivo, skill que lo produce, nombre de la fase)
PHASES = [
    ("spec.md", "/sdd:specify", "spec"),
    ("plan.md", "/sdd:plan", "plan"),
    ("tasks.md", "/sdd:tasks", "tasks"),
]

DEFAULT_CONFIG = {
    "enabled": True,
    # Fase que debe estar completa antes de permitir escribir codigo.
    # Valores: "spec" | "plan" | "tasks" | "off"
    "gate": "tasks",
    # Rutas relativas a la raiz del proyecto que la compuerta nunca bloquea.
    "exempt": [
        "specs/**",
        ".sdd/**",
        ".claude/**",
        ".git/**",
        "*.md",
        ".gitignore",
        ".env.example",
    ],
}


# --------------------------------------------------------------------------
# Localizacion del proyecto y config
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


def load_config(root):
    cfg = dict(DEFAULT_CONFIG)
    path = root / ".sdd" / "config.json"
    if path.is_file():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                cfg.update(user)
        except (json.JSONDecodeError, OSError):
            # Config corrupta no debe romper la sesion. Se usa el default.
            pass
    return cfg


def specs_dir(root):
    return root / "specs"


def adopted(root):
    """El plugin solo actua en repos que ya adoptaron SDD."""
    return specs_dir(root).is_dir()


# --------------------------------------------------------------------------
# Resolucion de la feature activa
# --------------------------------------------------------------------------

def feature_dirs(root):
    base = specs_dir(root)
    if not base.is_dir():
        return []
    out = [p for p in base.iterdir() if p.is_dir() and FEATURE_RE.match(p.name)]
    return sorted(out, key=lambda p: p.name)


def git_branch(root):
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def resolve_feature(root):
    """
    Devuelve el Path de la feature activa, o None.

    Prioridad:
      1. .sdd/current (lo escribe `sdd.py new`)
      2. rama git, si su nombre coincide con un directorio de feature
      3. si existe exactamente una feature, esa
    """
    pointer = root / ".sdd" / "current"
    if pointer.is_file():
        slug = pointer.read_text(encoding="utf-8").strip()
        candidate = specs_dir(root) / slug
        if slug and candidate.is_dir():
            return candidate

    branch = git_branch(root)
    if branch:
        candidate = specs_dir(root) / branch
        if candidate.is_dir():
            return candidate

    dirs = feature_dirs(root)
    if len(dirs) == 1:
        return dirs[0]
    return None


def phase_state(feature):
    """[(archivo, skill, fase, existe?), ...] en orden."""
    return [
        (fname, skill, phase, (feature / fname).is_file())
        for fname, skill, phase in PHASES
    ]


def next_missing(feature):
    """Primera fase incompleta, o None si estan todas."""
    for fname, skill, phase, ok in phase_state(feature):
        if not ok:
            return fname, skill, phase
    return None


# --------------------------------------------------------------------------
# Subcomando: new
# --------------------------------------------------------------------------

STOPWORDS = {
    "a", "al", "ante", "con", "de", "del", "e", "el", "en", "la", "las", "lo",
    "los", "o", "para", "por", "que", "se", "sin", "sobre", "su", "sus", "un",
    "una", "unos", "unas", "y",
    "an", "and", "at", "by", "for", "from", "in", "of", "on", "or", "the",
    "to", "with",
}


def slugify(text, max_words=5):
    text = text.lower()
    # Normalizacion basica de acentos, para no depender de unicodedata.
    for src, dst in (("áàä", "a"), ("éèë", "e"), ("íìï", "i"),
                     ("óòö", "o"), ("úùü", "u"), ("ñ", "n")):
        for ch in src:
            text = text.replace(ch, dst)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    words = [w for w in re.split(r"[\s-]+", text) if w]
    kept = [w for w in words if w not in STOPWORDS] or words
    slug = "-".join(kept[:max_words])
    return slug or "feature"


def next_number(root):
    n = 0
    for p in feature_dirs(root):
        m = FEATURE_RE.match(p.name)
        if m:
            n = max(n, int(m.group(1)))
    return f"{n + 1:03d}"


def render_template(name, mapping, plugin_root):
    path = Path(plugin_root) / "templates" / name
    text = path.read_text(encoding="utf-8")
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def cmd_new(args):
    description = " ".join(args).strip()
    if not description:
        print("error: falta la descripcion de la feature", file=sys.stderr)
        return 1

    root = project_root()
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent)
    )

    specs_dir(root).mkdir(parents=True, exist_ok=True)
    number = next_number(root)
    slug = f"{number}-{slugify(description)}"
    feature = specs_dir(root) / slug

    if feature.exists():
        print(f"error: {feature} ya existe", file=sys.stderr)
        return 1

    feature.mkdir(parents=True)
    mapping = {
        "ID": slug,
        "TITLE": description,
        "DATE": datetime.date.today().isoformat(),
    }
    (feature / "spec.md").write_text(
        render_template("spec.md", mapping, plugin_root), encoding="utf-8"
    )

    sdd = root / ".sdd"
    sdd.mkdir(exist_ok=True)
    (sdd / "current").write_text(slug + "\n", encoding="utf-8")

    print(json.dumps({
        "feature": slug,
        "dir": str(feature.relative_to(root)),
        "spec": str((feature / "spec.md").relative_to(root)),
        "next": "/sdd:clarify",
    }, indent=2))
    return 0


# --------------------------------------------------------------------------
# Subcomandos: current / status / context
# --------------------------------------------------------------------------

def cmd_current(_args):
    root = project_root()
    feature = resolve_feature(root)
    if feature:
        print(feature.name)
        return 0
    return 1


def cmd_status(_args):
    root = project_root()
    if not adopted(root):
        print("SDD no esta activo en este proyecto (no existe specs/).")
        print("Ejecuta /sdd:constitution o /sdd:specify para empezar.")
        return 0

    cfg = load_config(root)
    feature = resolve_feature(root)
    print(f"Raiz:      {root}")
    print(f"Gate:      {cfg['gate']}" + ("" if cfg["enabled"] else "  (deshabilitado)"))

    dirs = feature_dirs(root)
    print(f"Features:  {len(dirs)}")
    if not feature:
        if dirs:
            print("\nNinguna feature activa. Marca una escribiendo su slug en .sdd/current,")
            print("o crea una nueva con /sdd:specify.")
            for p in dirs:
                print(f"  - {p.name}")
        else:
            print("\nNo hay features. Empieza con /sdd:specify.")
        return 0

    print(f"Activa:    {feature.name}\n")
    for fname, skill, _phase, ok in phase_state(feature):
        print(f"  [{'x' if ok else ' '}] {fname:<9} {'' if ok else '-> ' + skill}")

    nxt = next_missing(feature)
    print(f"\nSiguiente: {nxt[1] if nxt else 'listo para /sdd:implement'}")
    return 0


def cmd_context(_args):
    """Salida breve. En SessionStart, stdout se inyecta como contexto."""
    root = project_root()
    if not adopted(root):
        return 0
    feature = resolve_feature(root)
    if not feature:
        print("[SDD] Este proyecto usa desarrollo orientado a especificaciones. "
              "No hay ninguna feature activa, y la compuerta bloquea la escritura "
              "de codigo mientras siga asi. La skill /sdd:specify crea una.")
        return 0
    nxt = next_missing(feature)
    done = [f for f, _s, _p, ok in phase_state(feature) if ok]
    line = (f"[SDD] Este proyecto usa desarrollo orientado a especificaciones. "
            f"La feature activa es {feature.name} y tiene estos artefactos: "
            f"{', '.join(done) or 'ninguno'}.")
    line += (f" La compuerta exige {nxt[0]}, que produce la skill {nxt[1]}."
             if nxt else " Estan los tres artefactos, asi que la compuerta permite escribir codigo.")
    print(line)
    return 0


# --------------------------------------------------------------------------
# Subcomando: guard (hook PreToolUse)
# --------------------------------------------------------------------------

def is_exempt(rel_path, patterns):
    rel = rel_path.as_posix()
    base = rel_path.name
    for pat in patterns:
        if pat.endswith("/**"):
            if rel == pat[:-3] or rel.startswith(pat[:-2]):
                return True
        elif fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def deny(reason):
    """
    Bloquea. Ojo: el JSON solo se procesa con exit 0. Nunca combinar con exit 2.
    """
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.stdout.write("\n")
    return 0


def passthrough():
    """
    No opinar. Deliberadamente NO devolvemos permissionDecision "allow":
    eso saltaria la peticion de permiso normal y convertiria un guardrail
    en una escalada de privilegios silenciosa.
    """
    return 0


def cmd_guard(_args):
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return passthrough()

    if os.environ.get("SDD_BYPASS") == "1":
        return passthrough()

    root = project_root(payload)
    if not adopted(root):
        return passthrough()

    cfg = load_config(root)
    if not cfg.get("enabled", True) or cfg.get("gate") == "off":
        return passthrough()

    raw_path = (payload.get("tool_input") or {}).get("file_path")
    if not raw_path:
        return passthrough()

    try:
        target = Path(raw_path)
        if not target.is_absolute():
            target = (root / target).resolve()
        rel = target.resolve().relative_to(root)
    except (ValueError, OSError):
        # Fuera del proyecto: no es asunto nuestro.
        return passthrough()

    if is_exempt(rel, cfg.get("exempt", DEFAULT_CONFIG["exempt"])):
        return passthrough()

    feature = resolve_feature(root)
    if feature is None:
        return deny(
            "Guardrail SDD: no hay una feature activa, asi que no hay especificacion "
            f"que respalde escribir en {rel.as_posix()}.\n\n"
            "Detente y dile al usuario que ejecute /sdd:specify para describir el "
            "cambio antes de tocar codigo. No intentes crear los artefactos a mano "
            "ni reintentar la escritura.\n\n"
            "Escape puntual: SDD_BYPASS=1, o \"gate\": \"off\" en .sdd/config.json."
        )

    gate = cfg.get("gate", "tasks")
    required = [p for _f, _s, p in PHASES]
    limit = required.index(gate) if gate in required else len(required) - 1

    for fname, skill, phase, ok in phase_state(feature):
        if required.index(phase) > limit:
            break
        if not ok:
            return deny(
                f"Guardrail SDD: la feature {feature.name} todavia no tiene {fname}, "
                f"asi que no se puede escribir en {rel.as_posix()}.\n\n"
                f"Detente y dile al usuario que ejecute {skill}. No crees {fname} "
                "a mano para saltarte la compuerta: la fase existe para que el "
                "usuario revise antes de que se escriba codigo.\n\n"
                "Escape puntual: SDD_BYPASS=1, o \"gate\": \"off\" en .sdd/config.json."
            )

    return passthrough()


# --------------------------------------------------------------------------

def cmd_trace(args):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sdd_trace

    root = project_root()
    feature = resolve_feature(root)
    if feature is None:
        print("No hay una feature activa. Ejecuta /sdd:specify primero.",
              file=sys.stderr)
        return 1
    return sdd_trace.run(args, root, feature, load_config(root))


def cmd_quality(_args):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sdd_quality

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    root = project_root(payload)
    cfg = load_config(root)
    exempt = cfg.get("exempt", DEFAULT_CONFIG["exempt"])
    return sdd_quality.run(payload, root, cfg, lambda rel: is_exempt(rel, exempt))


COMMANDS = {
    "new": cmd_new,
    "current": cmd_current,
    "status": cmd_status,
    "context": cmd_context,
    "guard": cmd_guard,
    "trace": cmd_trace,
    "quality": cmd_quality,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[1]](argv[2:])
    except Exception as exc:  # noqa: BLE001
        # Un guardrail que revienta jamas debe bloquear al usuario.
        print(f"sdd.py: {exc}", file=sys.stderr)
        return 0 if argv[1] in ("guard", "context", "quality") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
