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
  approve [fase]      Marca spec|plan|tasks como aprobado si esta listo.
  trace [--json] [--check]   Matriz requisito -> tarea -> prueba.
  quality             Hook PostToolUse: formateador y linter del archivo.
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
    # Si es true, cada fase exige ademas "Estado: Approved", que solo pone el
    # usuario con /sdd:approve. El modelo no puede escribirlo.
    "approval": True,
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


# --------------------------------------------------------------------------
# Readiness: una fase cuenta solo si su artefacto esta relleno y aprobado
# --------------------------------------------------------------------------

def _trace():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sdd_trace
    return sdd_trace


def _musts(spec):
    return [r["id"] for r in spec["requirements"] if r["priority"] == "MUST"]


def phase_problems(feature, phase):
    """
    Problemas de contenido que impiden dar la fase por lista (sin contar la
    aprobacion). None si el artefacto no existe; [] si esta listo.
    """
    t = _trace()
    fname = dict((p, f) for f, _s, p in PHASES)[phase]
    path = feature / fname
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    problems = []

    holes = t.find_placeholders(text, fname)
    if holes:
        line, sample = holes[0]
        problems.append(f"{fname} conserva {len(holes)} hueco(s) de plantilla sin "
                        f"rellenar (linea {line}: {sample[:70]})")

    spec = t.parse_spec(feature / "spec.md")
    musts = _musts(spec)

    if phase == "spec":
        if not musts:
            problems.append("spec.md no declara ningun requisito MUST")
        if spec["duplicates"]:
            problems.append("IDs de requisito duplicados: "
                            + ", ".join(sorted(set(spec["duplicates"]))))
        sin = [r["id"] for r in spec["requirements"]
               if r["priority"] == "MUST" and not r["criteria"]]
        if sin:
            problems.append("requisitos MUST sin criterios de aceptacion: "
                            + ", ".join(sin))

    elif phase == "plan":
        cited = {"R" + n for n in t.REQ_ID.findall(text)}
        missing = [rid for rid in musts if rid not in cited]
        if missing:
            problems.append("plan.md no menciona estos requisitos MUST: "
                            + ", ".join(missing))

    elif phase == "tasks":
        tasks = t.parse_tasks(path)["tasks"]
        req_ids = {r["id"] for r in spec["requirements"]}
        task_ids = {x["id"] for x in tasks}
        if not tasks:
            problems.append("tasks.md no declara ninguna tarea")
        unknown = sorted({rid for x in tasks for rid in x["requirements"]} - req_ids)
        if unknown:
            problems.append("tareas que citan requisitos inexistentes: "
                            + ", ".join(unknown))
        bad_deps = sorted({d for x in tasks for d in x["depends_on"]} - task_ids)
        if bad_deps:
            problems.append("dependencias a tareas inexistentes: " + ", ".join(bad_deps))
        for cycle in t.find_cycles(tasks):
            problems.append("ciclo de dependencias: " + " -> ".join(cycle))
        covered = {rid for x in tasks for rid in x["requirements"]}
        orphan = [rid for rid in musts if rid not in covered]
        if orphan:
            problems.append("requisitos MUST sin tarea: " + ", ".join(orphan))

    return problems


def phase_approved(feature, phase):
    fname = dict((p, f) for f, _s, p in PHASES)[phase]
    path = feature / fname
    return path.is_file() and _trace().is_approved(
        path.read_text(encoding="utf-8", errors="replace"))


def phase_state(feature, cfg=None):
    """
    [(archivo, skill, fase, estado, problemas), ...] en orden.
    estado: "missing" | "incomplete" | "draft" (falta aprobar) | "ready".
    """
    need_approval = (cfg or DEFAULT_CONFIG).get("approval", True)
    out = []
    for fname, skill, phase in PHASES:
        problems = phase_problems(feature, phase)
        if problems is None:
            state = "missing"
        elif problems:
            state = "incomplete"
        elif need_approval and not phase_approved(feature, phase):
            state = "draft"
        else:
            state = "ready"
        out.append((fname, skill, phase, state, problems or []))
    return out


def next_step(feature, cfg=None):
    """(archivo, comando, fase, estado) de la primera fase no lista, o None."""
    for fname, skill, phase, state, _p in phase_state(feature, cfg):
        if state == "draft":
            return fname, f"/sdd:approve {phase}", phase, state
        if state != "ready":
            return fname, skill, phase, state
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
    marks = {"missing": " ", "incomplete": "~", "draft": "a", "ready": "x"}
    labels = {"missing": "falta", "incomplete": "incompleto",
              "draft": "sin aprobar", "ready": "listo"}
    for fname, skill, phase, state, problems in phase_state(feature, cfg):
        hint = {"missing": f"-> {skill}", "incomplete": f"-> {skill}",
                "draft": f"-> /sdd:approve {phase}", "ready": ""}[state]
        print(f"  [{marks[state]}] {fname:<9} {labels[state]:<12} {hint}".rstrip())
        for prob in problems:
            print(f"        - {prob}")

    nxt = next_step(feature, cfg)
    print(f"\nSiguiente: {nxt[1] if nxt else 'listo para /sdd:implement'}")
    print("Leyenda:   [x] listo · [a] sin aprobar · [~] incompleto · [ ] falta")
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
    cfg = load_config(root)
    nxt = next_step(feature, cfg)
    done = [f for f, _s, _p, st, _x in phase_state(feature, cfg) if st == "ready"]
    line = (f"[SDD] Este proyecto usa desarrollo orientado a especificaciones. "
            f"La feature activa es {feature.name} y tiene estos artefactos listos: "
            f"{', '.join(done) or 'ninguno'}.")
    if nxt and nxt[3] == "draft":
        line += (f" {nxt[0]} esta pendiente de aprobacion por el usuario "
                 f"({nxt[1]}); el campo Estado solo lo cambia el usuario.")
    elif nxt and nxt[3] == "incomplete":
        line += f" {nxt[0]} existe pero esta incompleto; lo completa la skill {nxt[1]}."
    elif nxt:
        line += f" La compuerta exige {nxt[0]}, que produce la skill {nxt[1]}."
    else:
        line += " Los tres artefactos estan listos, asi que la compuerta permite escribir codigo."
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

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not raw_path:
        return passthrough()

    try:
        target = Path(raw_path)
        if not target.is_absolute():
            target = (root / target).resolve()
        target = target.resolve()
        rel = target.relative_to(root)
    except (ValueError, OSError):
        # Fuera del proyecto: no es asunto nuestro.
        return passthrough()

    if cfg.get("approval", True) and self_approval(rel, target, tool_input):
        return deny(
            f"Guardrail SDD: esta escritura marca {rel.as_posix()} como aprobado. "
            "La aprobacion es del usuario, no tuya: es la unica prueba de que "
            "alguien reviso el artefacto antes de escribir codigo.\n\n"
            "Deja el campo Estado como esta, termina la edicion sin tocarlo, y "
            f"pidele al usuario que lo revise y ejecute /sdd:approve."
        )

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

    escape = "Escape puntual: SDD_BYPASS=1, o \"gate\": \"off\" en .sdd/config.json."
    for fname, skill, phase, state, problems in phase_state(feature, cfg):
        if required.index(phase) > limit:
            break
        if state == "missing":
            return deny(
                f"Guardrail SDD: la feature {feature.name} todavia no tiene {fname}, "
                f"asi que no se puede escribir en {rel.as_posix()}.\n\n"
                f"Detente y dile al usuario que ejecute {skill}. No crees {fname} "
                "a mano para saltarte la compuerta: la fase existe para que el "
                "usuario revise antes de que se escriba codigo.\n\n" + escape
            )
        if state == "incomplete":
            return deny(
                f"Guardrail SDD: {fname} de la feature {feature.name} existe pero "
                f"no esta listo, asi que no se puede escribir en {rel.as_posix()}:\n"
                + "".join(f"  - {p}\n" for p in problems)
                + f"\nDetente y dile al usuario que hay que completarlo con {skill}. "
                "No rellenes huecos con suposiciones para pasar la compuerta.\n\n"
                + escape
            )
        if state == "draft":
            return deny(
                f"Guardrail SDD: {fname} de la feature {feature.name} esta completo "
                f"pero no aprobado, asi que no se puede escribir en {rel.as_posix()}."
                f"\n\nDetente y pidele al usuario que lo revise y ejecute "
                f"/sdd:approve {phase}. No cambies tu el campo Estado.\n\n" + escape
            )

    return passthrough()


def self_approval(rel, target, tool_input):
    """
    True si la escritura pasa un artefacto de fase de no aprobado a aprobado.
    Solo `sdd.py approve` (lanzado por el usuario) debe hacer esa transicion.
    """
    parts = rel.parts
    if (len(parts) != 3 or parts[0] != "specs" or not FEATURE_RE.match(parts[1])
            or parts[2] not in {f for f, _s, _p in PHASES}):
        return False
    t = _trace()
    before = (target.read_text(encoding="utf-8", errors="replace")
              if target.is_file() else "")
    if "content" in tool_input:
        after = tool_input.get("content") or ""
    elif "new_string" in tool_input:
        old = tool_input.get("old_string") or ""
        if not old or old not in before:
            return False
        count = -1 if tool_input.get("replace_all") else 1
        after = before.replace(old, tool_input.get("new_string") or "", count)
    else:
        return False
    return t.is_approved(after) and not t.is_approved(before)


# --------------------------------------------------------------------------
# Subcomando: approve
# --------------------------------------------------------------------------

def cmd_approve(args):
    root = project_root()
    feature = resolve_feature(root)
    if feature is None:
        print("No hay una feature activa. Ejecuta /sdd:specify primero.",
              file=sys.stderr)
        return 1

    order = [p for _f, _s, p in PHASES]
    states = {p: (f, sk, st, pr) for f, sk, p, st, pr in phase_state(feature)}
    target = args[0].strip().lower() if args else None
    if target and target not in order:
        print(f"error: fase desconocida '{target}'. Usa: {', '.join(order)}",
              file=sys.stderr)
        return 1
    if not target:
        target = next((p for p in order if states[p][2] != "ready"), None)
        if target is None:
            print(f"{feature.name}: spec, plan y tasks ya estan aprobados.")
            return 0

    for prev in order[:order.index(target)]:
        if states[prev][2] != "ready":
            print(f"No se puede aprobar {target}: antes hay que aprobar {prev} "
                  f"(estado: {states[prev][2]}).", file=sys.stderr)
            return 1

    fname, skill, state, problems = states[target]
    if state == "missing":
        print(f"No existe {fname}. Lo produce {skill}.", file=sys.stderr)
        return 1
    if state == "incomplete":
        print(f"{fname} no esta listo para aprobarse:", file=sys.stderr)
        for prob in problems:
            print(f"  - {prob}", file=sys.stderr)
        return 1
    if state == "ready":
        print(f"{fname} ya estaba aprobado.")
        return 0

    path = feature / fname
    text, changed = _trace().set_status(path.read_text(encoding="utf-8"), "Approved")
    if not changed:
        print(f"{fname} no tiene la fila '| Estado | ... |' en la cabecera. "
              "Anadela y vuelve a aprobar.", file=sys.stderr)
        return 1
    path.write_text(text, encoding="utf-8")

    nxt = next_step(feature)
    print(f"{feature.name}: {fname} aprobado.")
    print(f"Siguiente: {nxt[1] if nxt else '/sdd:implement'}")
    return 0


# --------------------------------------------------------------------------

def cmd_trace(args):
    sdd_trace = _trace()

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
    "approve": cmd_approve,
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
