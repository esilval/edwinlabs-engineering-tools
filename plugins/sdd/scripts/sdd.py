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
  audit               Hook PostToolUse sobre Bash: detecta lo que guard no vio.
  approve [fase]      Marca spec|plan|tasks como aprobado si esta listo.
  next-req            Imprime el siguiente ID de requisito libre (R00N).
  trace [--json] [--check]   Matriz requisito -> tarea -> prueba.
  quality             Hook PostToolUse: formateador y linter del archivo.
  arch-context [--json]
                      Con architecture/: componentes de la candidata de la
                      feature activa, decisiones vigentes y propuestas, y
                      estandares, para planificar.
  propose-adr "<titulo>"
                      Escribe la siguiente decision en architecture/adr/ como
                      propuesta, desde el plan de la feature activa. La decide
                      el usuario con /architecture:review.
  diagram             Con architecture/: escribe en plan.md el esqueleto del
                      diagrama de secuencia con los componentes de la
                      candidata, si el plan aun no tiene diagramas.
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
    """
    Raiz del proyecto. CLAUDE_PROJECT_DIR es la fuente autoritativa y se usa
    tal cual. Sin ella (la inyeccion de comandos de una skill no la recibe),
    se sube desde el cwd hasta los datos de sdd: un /sdd:approve lanzado con la
    sesion dentro de specs/<feature>/ debe encontrar el proyecto.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    start = Path((payload or {}).get("cwd") or os.getcwd()).resolve()
    return find_upwards(start, (".sdd",)) or find_upwards(start, ("specs",)) or start


def find_upwards(start, markers):
    """
    El directorio mas cercano, desde start hacia arriba, que contiene alguno de
    los directorios markers, o None. Se detiene en el primer directorio con
    .git (carpeta, o archivo en un worktree) despues de examinarlo: la busqueda
    no sale del repositorio. Un directorio que no se puede leer cuenta como
    vacio.

    Hay una copia en plugins/discovery/scripts/discovery.py: los plugins no
    comparten codigo.
    """
    for directory in (start, *start.parents):
        try:
            if any((directory / m).is_dir() for m in markers):
                return directory
            if (directory / ".git").exists():
                return None
        except OSError:
            continue
    return None


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
        must_ids = set(musts)
        blocking = sorted({rid for q in spec["questions"] for rid in q["requirements"]
                           if rid in must_ids})
        if blocking:
            problems.append("preguntas abiertas sobre requisitos MUST: "
                            + ", ".join(blocking) + " (se cierran con /sdd:clarify)")

    elif phase == "plan":
        cited = {"R" + n for n in t.REQ_ID.findall(text)}
        missing = [rid for rid in musts if rid not in cited]
        if missing:
            problems.append("plan.md no menciona estos requisitos MUST: "
                            + ", ".join(missing))
        unknown = sorted(cited - {r["id"] for r in spec["requirements"]})
        if unknown:
            problems.append("plan.md cita requisitos que no estan en spec.md: "
                            + ", ".join(unknown) + " (un requisito nuevo va a la spec)")

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


def phase_approval(feature, phase):
    """'approved' | 'stale' (cambio tras aprobarse) | 'draft'."""
    fname = dict((p, f) for f, _s, p in PHASES)[phase]
    path = feature / fname
    if not path.is_file():
        return "draft"
    t = _trace()
    text = path.read_text(encoding="utf-8", errors="replace")
    if not t.is_approved(text):
        return "draft"
    return "stale" if t.is_stale(text, fname) else "approved"


def phase_state(feature, cfg=None):
    """
    [(archivo, skill, fase, estado, problemas), ...] en orden.
    estado: "missing" | "incomplete" | "draft" (falta aprobar) |
            "stale" (cambio despues de aprobarse) | "ready".
    """
    need_approval = (cfg or DEFAULT_CONFIG).get("approval", True)
    out = []
    for fname, skill, phase in PHASES:
        problems = phase_problems(feature, phase)
        approval = phase_approval(feature, phase) if need_approval else "approved"
        if problems is None:
            state = "missing"
        elif problems:
            state = "incomplete"
        elif approval != "approved":
            state = approval
        else:
            state = "ready"
        out.append((fname, skill, phase, state, problems or []))
    return out


def next_step(feature, cfg=None):
    """(archivo, comando, fase, estado) de la primera fase no lista, o None."""
    for fname, skill, phase, state, _p in phase_state(feature, cfg):
        if state in ("draft", "stale"):
            return fname, "/sdd:approve", phase, state
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


def _product():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sdd_product
    return sdd_product


# Un ID de candidata del backlog de discovery: B03, b12.
CANDIDATE_ARG = re.compile(r"^[Bb]\d+$")


def prepare_handoff(root, cid):
    """
    Lee la candidata cid del producto de discovery. Devuelve (handoff, None)
    o (None, motivo) si no se puede crear la feature: producto sin aprobar o
    cambiado, candidata inexistente o descartada. No escribe nada.
    """
    p = _product()
    cid = cid.upper()
    problems = p.approval_problems(root)
    if problems:
        return None, (f"No se crea la feature desde {cid}: el producto de discovery no "
                      "está aprobado.\n" + "".join(f"  - {x}\n" for x in problems))
    cand = p.candidate(root, cid)
    if cand is None:
        return None, f"No se crea la feature: {cid} no existe en product/backlog.md."
    if cand["state"] == "descartada":
        motivo = re.sub(r"^\S+\s*", "", cand["fields"].get("estado", "")).strip(" ()")
        return None, (f"No se crea la feature: {cid} está descartada en product/backlog.md"
                      + (f" ({motivo})." if motivo else "."))
    taken = features_by_origin(root)
    if cid in taken:
        return None, (f"No se crea la feature: {cid} ya tiene una, {taken[cid]} "
                      f"(fila Origen de specs/{taken[cid]}/spec.md).")
    # Con architecture/ (feature 007, D5): la arquitectura tiene que estar
    # aprobada y alojar la candidata en algun componente.
    sa = _architecture()
    hosts = None
    if sa.exists(root):
        arch_problems = sa.approval_problems(root)
        if arch_problems:
            return None, (f"No se crea la feature desde {cid}: la arquitectura no está "
                          "aprobada.\n" + "".join(f"  - {x}\n" for x in arch_problems))
        hosts = [c["id"] for c in sa.components(root) if cid in c["candidates"]]
        if not hosts:
            return None, (f"No se crea la feature: {cid} no vive en ningún componente de "
                          "architecture/components.md. Se corrige en architecture "
                          "(/architecture:init) y se aprueba con /architecture:approve.")
    fields = cand["fields"]
    goal_ids = p.refs(fields.get("objetivos"))["goals"]
    all_goals = p.goals(root)
    handoff = {
        "candidate": cand,
        "goals": [all_goals.get(g, {"id": g, "title": None, "description": ""})
                  for g in goal_ids],
        "sections": [p.source_section(root, s)
                     for s in p.refs(fields.get("origen"))["sections"]],
    }
    if hosts is not None:
        handoff["components"] = hosts  # solo con arquitectura: Origen de 4 grupos
    # Avisos que no impiden crear la feature: dependencias sin feature (R009)
    # y secciones de origen que ya no se pueden leer como contexto (R006).
    warnings = []
    all_candidates = p.candidates(root)
    for dep in p.refs(fields.get("depende de"))["candidates"]:
        if dep in taken or all_candidates.get(dep, {}).get("state") == "descartada":
            continue
        warnings.append(f"{cid} depende de {dep}, que aún no tiene feature: "
                        f"conviene especificarla antes (/sdd:specify {dep}).")
    for s in handoff["sections"]:
        if s["file"] is None:
            warnings.append(f"{s['ref']}: el documento no está en product/sources/; "
                            "esa sección no se puede leer como contexto.")
    handoff["warnings"] = warnings
    return handoff, None


ORIGIN_ROW = re.compile(r"^\|\s*Origen\s*\|\s*([^|\n]*?)\s*\|", re.M)


def features_by_origin(root):
    """{candidata: feature} leyendo la fila Origen de la cabecera de cada spec (D4)."""
    t = _trace()
    out = {}
    for feature in feature_dirs(root):
        try:
            text = (feature / "spec.md").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = ORIGIN_ROW.search(text, 0, t._header_end(text))
        if m:
            first = m.group(1).split("·")[0].strip().upper()
            if first:
                out.setdefault(first, feature.name)
    return out


def handoff_json(handoff):
    """Campos que el traspaso añade a la salida de new (D5)."""
    out = {
        "origin": {"candidate": handoff["candidate"]["id"],
                   "goals": [g["id"] for g in handoff["goals"]],
                   "sections": [s["ref"] for s in handoff["sections"]]},
        "context": {"brief": "product/brief.md",
                    "goals": handoff["goals"], "sources": handoff["sections"]},
        "warnings": handoff["warnings"],
    }
    if "components" in handoff:  # feature 007: con arquitectura
        out["origin"]["components"] = handoff["components"]
        out["context"]["components"] = handoff["components"]
    return out


def origin_value(handoff):
    """
    'B03 · G2 · D2§4.2': candidata, objetivos y secciones, siempre en ese orden
    y separados por ' · '. Un grupo vacio se escribe '—' para no mover los demas.
    Con arquitectura, un cuarto grupo con los componentes: 'B03 · G2 · D2§4.2 · C2'.
    """
    parts = [handoff["candidate"]["id"],
             ", ".join(g["id"] for g in handoff["goals"]),
             ", ".join(s["ref"] for s in handoff["sections"])]
    if "components" in handoff:
        parts.append(", ".join(handoff["components"]))
    return " · ".join(x or "—" for x in parts)


def _replace_section(text, title, body):
    """Sustituye el cuerpo de '## title' hasta el siguiente encabezado de nivel 2."""
    pattern = re.compile(rf"(^## {re.escape(title)}[^\n]*\n)(.*?)(?=^## |\Z)", re.M | re.S)
    return pattern.sub(lambda m: m.group(1) + "\n" + body.strip() + "\n\n", text, count=1)


def fill_from_candidate(text, handoff):
    """Problema, Contexto, Alcance y la fila Origen de la spec, desde la candidata (D3)."""
    cand = handoff["candidate"]
    f = cand["fields"]
    missing = "No consta en la candidata."
    text = _replace_section(text, "Problema", f.get("problema") or missing)

    lines = [f"Feature creada desde la candidata {cand['id']} «{cand['title']}» de "
             "`product/backlog.md`, con el producto de discovery aprobado.", ""]
    for g in handoff["goals"]:
        if g["title"] is None:
            lines.append(f"- **{g['id']}:** no está en `product/brief.md`.")
        else:
            lines.append(f"- **{g['id']} — {g['title']}:** {g['description']}")
    for s in handoff["sections"]:
        where = f"`{s['file']}`" if s["file"] else "documento no encontrado en product/sources/"
        title = f" «{s['title']}»" if s["title"] else ""
        lines.append(f"- **Origen {s['ref']}**{title}: {where}")
    text = _replace_section(text, "Contexto", "\n".join(lines))

    inside = [x for x in (f.get("resultado observable"), f.get("dentro")) if x and x != "—"]
    outside = [x for x in (f.get("fuera"),) if x and x != "—"]
    text = _replace_section(
        text, "Alcance",
        "### Dentro\n\n" + "".join(f"- {x}\n" for x in (inside or [missing]))
        + "\n### Fuera (non-goals)\n\n" + "".join(f"- {x}\n" for x in (outside or [missing])))

    row = f"| Origen | {origin_value(handoff)} |\n"
    issue = re.compile(r"^\|\s*Issue\s*\|[^\n]*\n", re.M)
    if issue.search(text):
        return issue.sub(lambda m: m.group(0) + row, text, count=1)
    return re.sub(r"^(\|\s*Estado\s*\|[^\n]*\n)", lambda m: m.group(1) + row, text,
                  count=1, flags=re.M)


def cmd_new(args):
    description = " ".join(args).strip()
    if not description:
        print("error: falta la descripcion de la feature", file=sys.stderr)
        return 1

    root = project_root()
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent)
    )

    # Traspaso desde discovery (D1): solo con un ID de candidata y un backlog.
    # Cualquier otra descripcion sigue el camino de siempre.
    handoff = None
    if (CANDIDATE_ARG.match(description)
            and (root / "product" / "backlog.md").is_file()):
        handoff, refusal = prepare_handoff(root, description)
        if refusal:
            print(refusal.rstrip(), file=sys.stderr)
            return 1
        description = handoff["candidate"]["title"] or handoff["candidate"]["id"]

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
    spec_text = render_template("spec.md", mapping, plugin_root)
    if handoff:
        spec_text = fill_from_candidate(spec_text, handoff)
    (feature / "spec.md").write_text(spec_text, encoding="utf-8")

    sdd = root / ".sdd"
    sdd.mkdir(exist_ok=True)
    (sdd / "current").write_text(slug + "\n", encoding="utf-8")

    out = {
        "feature": slug,
        "dir": str(feature.relative_to(root)),
        "spec": str((feature / "spec.md").relative_to(root)),
        "next": "/sdd:clarify",
    }
    if handoff:
        out.update(handoff_json(handoff))
    print(json.dumps(out, indent=2))
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
    marks = {"missing": " ", "incomplete": "~", "draft": "a", "stale": "!",
             "ready": "x"}
    labels = {"missing": "falta", "incomplete": "incompleto",
              "draft": "sin aprobar", "stale": "cambio tras aprobar",
              "ready": "listo"}
    for fname, skill, phase, state, problems in phase_state(feature, cfg):
        hint = {"missing": f"-> {skill}", "incomplete": f"-> {skill}",
                "draft": "-> /sdd:approve", "stale": "-> revisar y /sdd:approve",
                "ready": ""}[state]
        print(f"  [{marks[state]}] {fname:<9} {labels[state]:<12} {hint}".rstrip())
        for prob in problems:
            print(f"        - {prob}")

    nxt = next_step(feature, cfg)
    print(f"\nSiguiente: {nxt[1] if nxt else 'listo para /sdd:implement'}")
    print("Leyenda:   [x] listo · [!] cambio tras aprobar · [a] sin aprobar · "
          "[~] incompleto · [ ] falta")
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
    if nxt and nxt[3] == "stale":
        line += (f" {nxt[0]} cambio despues de aprobarse y la aprobacion ya no "
                 f"vale; el usuario debe revisarlo y aprobarlo de nuevo ({nxt[1]}).")
    elif nxt and nxt[3] == "draft":
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

    if payload.get("tool_name") == "Bash":
        return guard_bash(payload, root, cfg)

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not raw_path:
        return passthrough()

    located = locate(root, raw_path)
    if located is None:
        # Fuera del proyecto: no es asunto nuestro.
        return passthrough()
    target, rel = located

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

    reason = gate_reason(root, cfg, rel.as_posix())
    return deny(reason) if reason else passthrough()


ESCAPE = "Escape puntual: SDD_BYPASS=1, o \"gate\": \"off\" en .sdd/config.json."


def locate(root, raw_path, base=None):
    """(ruta_absoluta, ruta_relativa_a_root), o None si cae fuera del proyecto."""
    try:
        target = Path(os.path.expanduser(raw_path))
        if not target.is_absolute():
            target = Path(base or root) / target
        target = target.resolve()
        return target, target.relative_to(root)
    except (ValueError, OSError):
        return None


def is_phase_artifact(rel):
    parts = rel.parts
    return (len(parts) == 3 and parts[0] == "specs" and bool(FEATURE_RE.match(parts[1]))
            and parts[2] in {f for f, _s, _p in PHASES})


def gate_reason(root, cfg, what):
    """
    Motivo por el que la compuerta impide escribir codigo ahora mismo, o None
    si lo permite. `what` describe el destino en el mensaje.
    """
    feature = resolve_feature(root)
    if feature is None:
        return (
            "Guardrail SDD: no hay una feature activa, asi que no hay especificacion "
            f"que respalde escribir en {what}.\n\n"
            "Detente y dile al usuario que ejecute /sdd:specify para describir el "
            "cambio antes de tocar codigo. No intentes crear los artefactos a mano "
            "ni reintentar la escritura.\n\n" + ESCAPE
        )

    gate = cfg.get("gate", "tasks")
    required = [p for _f, _s, p in PHASES]
    limit = required.index(gate) if gate in required else len(required) - 1

    for fname, skill, phase, state, problems in phase_state(feature, cfg):
        if required.index(phase) > limit:
            break
        if state == "missing":
            return (
                f"Guardrail SDD: la feature {feature.name} todavia no tiene {fname}, "
                f"asi que no se puede escribir en {what}.\n\n"
                f"Detente y dile al usuario que ejecute {skill}. No crees {fname} "
                "a mano para saltarte la compuerta: la fase existe para que el "
                "usuario revise antes de que se escriba codigo.\n\n" + ESCAPE
            )
        if state == "incomplete":
            return (
                f"Guardrail SDD: {fname} de la feature {feature.name} existe pero "
                f"no esta listo, asi que no se puede escribir en {what}:\n"
                + "".join(f"  - {p}\n" for p in problems)
                + f"\nDetente y dile al usuario que hay que completarlo con {skill}. "
                "No rellenes huecos con suposiciones para pasar la compuerta.\n\n"
                + ESCAPE
            )
        if state == "stale":
            return (
                f"Guardrail SDD: {fname} de la feature {feature.name} cambio despues "
                f"de que el usuario lo aprobara, asi que no se puede escribir en "
                f"{what}. La aprobacion era sobre otra version.\n\n"
                "Detente y dile al usuario que hay cambios sin revisar en "
                f"{fname}. Si el cambio es de requisitos, el camino es /sdd:amend; "
                "en cualquier caso, el usuario revisa y ejecuta /sdd:approve. "
                "No cambies tu el campo Estado.\n\n" + ESCAPE
            )
        if state == "draft":
            return (
                f"Guardrail SDD: {fname} de la feature {feature.name} esta completo "
                f"pero no aprobado, asi que no se puede escribir en {what}."
                f"\n\nDetente y pidele al usuario que lo revise y ejecute "
                "/sdd:approve. No cambies tu el campo Estado.\n\n" + ESCAPE
            )
    return None


# --------------------------------------------------------------------------
# La compuerta sobre Bash (ver sdd_bash.py)
# --------------------------------------------------------------------------

def _bash():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sdd_bash
    return sdd_bash


BASH_NOTE = ("\n\nEsto aplica igual a Bash: escribir el archivo con una redireccion, "
             "sed -i, tee, cp o un script es la misma escritura que un Write.")


def guard_bash(payload, root, cfg):
    b = _bash()
    command = (payload.get("tool_input") or {}).get("command") or ""
    approval = cfg.get("approval", True)
    exempt = cfg.get("exempt", DEFAULT_CONFIG["exempt"])

    if approval and b.invokes_approve(command):
        return deny(
            "Guardrail SDD: aprobar una fase es decision del usuario. Solo se hace "
            "con la skill /sdd:approve, que lanza el propio usuario; no ejecutes "
            "`sdd.py approve` ni cambies el campo Estado tu mismo.\n\n"
            "Pidele al usuario que revise el artefacto y ejecute /sdd:approve."
        )

    base = payload.get("cwd") or str(root)
    reason = None
    for raw in b.write_targets(command):
        located = locate(root, raw, base)
        if located is None:
            continue
        _target, rel = located
        if approval and is_phase_artifact(rel) and b.mentions_approval(command):
            return deny(
                f"Guardrail SDD: este comando parece marcar {rel.as_posix()} como "
                "aprobado. La aprobacion es del usuario: pidele que lo revise y "
                "ejecute /sdd:approve."
            )
        if is_exempt(rel, exempt):
            continue
        try:
            reason = gate_reason(root, cfg, rel.as_posix())
        except OSError:
            continue  # artefacto ilegible: falla abierto y sigue a la instantanea
        if reason:
            return deny(reason + BASH_NOTE)

    # Lo que el analizador no ve lo recoge la auditoria de PostToolUse.
    try:
        gate = gate_reason(root, cfg, "codigo del proyecto")
    except OSError:
        # Un artefacto ilegible: la compuerta falla abierta, pero la
        # instantanea de aprobaciones se guarda igual para no dejar de
        # proteger los demas artefactos.
        gate = None
    snapshot = {
        "approved": all_approvals(root) if approval else {},
        "gate": gate,
    }
    if snapshot["gate"]:
        snapshot["files"] = b.dirty_files(root)
    b.save_snapshot(root, payload, snapshot)
    return passthrough()


def all_approvals(root):
    """
    {"NNN-slug/archivo": valor del campo Estado} de los artefactos de fase de
    todas las features. No solo la activa: un comando puede aprobar otra
    feature, o cambiar el puntero, aprobar y dejarlo como estaba. Un artefacto
    que no se puede leer se omite: la auditoria no bloquea por eso.
    """
    t = _trace()
    out = {}
    for feature in feature_dirs(root):
        for fname, _s, _p in PHASES:
            path = feature / fname
            try:
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    out[f"{feature.name}/{fname}"] = t.doc_status(text)
            except OSError:
                continue
    return out


def cmd_audit(_args):
    """
    Hook PostToolUse sobre Bash. Compara con la instantanea de guard_bash:
      - una fase que paso a aprobada se devuelve a su Estado anterior;
      - archivos de codigo cambiados con la compuerta cerrada se reportan.
    exit 2 hace que Claude lea stderr. PostToolUse no puede deshacer el comando.
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    root = project_root(payload)
    b = _bash()
    snap = b.pop_snapshot(root, payload)
    if not snap or os.environ.get("SDD_BYPASS") == "1" or not adopted(root):
        return 0
    cfg = load_config(root)
    t = _trace()
    messages = []

    # Se compara por "NNN-slug/archivo", sin resolver la feature activa: el
    # comando pudo cambiarla. Una instantanea de una version anterior (claves
    # sin "/") no se puede ubicar y se ignora. Solo se aceptan claves de la
    # forma feature/artefacto: la instantanea vive en un directorio temporal y
    # no debe poder dirigir una escritura fuera de specs/.
    phase_files = {fname for fname, _s, _p in PHASES}
    before = snap.get("approved") or {}
    if cfg.get("approval", True):
        for key, old in before.items():
            slug, _sep, fname = str(key).partition("/")
            if not (FEATURE_RE.fullmatch(slug) and fname in phase_files):
                continue
            path = specs_dir(root) / key
            try:
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if t.is_approved(text) and t.doc_status(text) != old:
                restored, ok = t.set_status(text, old or "Draft")
                if ok:
                    try:
                        path.write_text(restored, encoding="utf-8")
                    except OSError:
                        continue
                    messages.append(
                        f"El comando cambio el campo Estado de {key} "
                        f"hacia una aprobacion. Se ha devuelto a '{old or 'Draft'}': "
                        "la aprobacion es del usuario, con /sdd:approve."
                    )
        if messages:
            # La auditoria no distingue una aprobacion fabricada de una que trae
            # git (checkout, pull, rebase): en ambos casos, decide el usuario.
            messages.append(
                "Detente y dile al usuario lo que paso, en vez de seguir. Si el "
                "cambio venia de git (checkout, pull, rebase), que lance el "
                "comando el mismo con ! o con SDD_BYPASS=1."
            )

    if snap.get("gate") and snap.get("files") is not None:
        after = b.dirty_files(root)
        if after is not None:
            exempt = cfg.get("exempt", DEFAULT_CONFIG["exempt"])
            changed = [rel for rel in b.changed_since(snap["files"], after)
                       if not is_exempt(Path(rel), exempt)]
            if changed:
                listed = "".join(f"  - {rel}\n" for rel in changed[:15])
                more = f"  (y {len(changed) - 15} mas)\n" if len(changed) > 15 else ""
                messages.append(
                    "Este comando cambio archivos de codigo con la compuerta SDD "
                    "cerrada:\n" + listed + more + "\nMotivo de la compuerta: "
                    + snap["gate"] + "\n\nDeshaz esos cambios (por ejemplo con "
                    "git checkout o borrando los archivos nuevos) y detente: dile "
                    "al usuario lo que paso en vez de seguir implementando."
                )

    if not messages:
        return 0
    sys.stderr.write("Guardrail SDD (auditoria de Bash):\n\n"
                     + "\n\n".join(messages) + "\n")
    return 2


def self_approval(rel, target, tool_input):
    """
    True si la escritura deja el artefacto aprobado con un Estado distinto del
    que tenia: aprobarlo, o reescribir la huella de una aprobacion. Solo
    `sdd.py approve` (lanzado por el usuario) puede hacerlo.
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
    return t.is_approved(after) and t.doc_status(after) != t.doc_status(before)


# --------------------------------------------------------------------------
# Subcomando: approve
# --------------------------------------------------------------------------

def cmd_approve(args):
    """
    Con --skill (lo usa /sdd:approve) todo va a stdout y sale siempre con 0:
    el resultado lo lee el modelo como texto, no como codigo de salida.
    """
    if "--skill" in args:
        args = [a for a in args if a != "--skill"]
        real_stderr, sys.stderr = sys.stderr, sys.stdout
        try:
            _approve(args)
        finally:
            sys.stderr = real_stderr
        return 0
    return _approve(args)


def _approve(args):
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

    t = _trace()
    path = feature / fname
    current = path.read_text(encoding="utf-8")
    digest = t.content_digest(current, fname)
    text, changed = t.set_status(current, f"Approved · {digest}")
    if not changed:
        print(f"{fname} no tiene la fila '| Estado | ... |' en la cabecera. "
              "Anadela y vuelve a aprobar.", file=sys.stderr)
        return 1
    path.write_text(text, encoding="utf-8")

    # Las fases posteriores se aprobaron sobre la version anterior de esta:
    # vuelven a borrador para que se revisen contra la nueva.
    reopened = []
    for later in order[order.index(target) + 1:]:
        later_path = feature / dict((p, f) for f, _s, p in PHASES)[later]
        if later_path.is_file():
            later_text = later_path.read_text(encoding="utf-8")
            if t.is_approved(later_text):
                later_path.write_text(t.set_status(later_text, "Draft")[0], encoding="utf-8")
                reopened.append(later_path.name)

    nxt = next_step(feature)
    print(f"{feature.name}: {fname} aprobado (huella {digest}).")
    if reopened:
        print(f"Vuelven a borrador, porque se aprobaron sobre la version anterior: "
              f"{', '.join(reopened)}. Revisalos contra el cambio y apruebalos de nuevo.")
    print(f"Siguiente: {nxt[1] if nxt else '/sdd:implement'}")
    return 0


def cmd_next_req(_args):
    """
    Siguiente ID libre. Cuenta los obsoletos: un ID no se recicla nunca. Solo
    cuentan los requisitos declarados, los mismos que reconoce la
    trazabilidad: una mencion en el texto (un requisito de otra feature) no
    ocupa un ID.
    """
    root = project_root()
    feature = resolve_feature(root)
    if feature is None:
        print("No hay una feature activa.", file=sys.stderr)
        return 1
    reqs = _trace().parse_spec(feature / "spec.md")["requirements"]
    used = [int(r["id"][1:]) for r in reqs]
    print(f"R{(max(used) if used else 0) + 1:03d}")
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


# --------------------------------------------------------------------------
# Arquitectura (feature 007): contexto para el plan y propuestas de decision
# --------------------------------------------------------------------------

def _architecture():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sdd_architecture
    return sdd_architecture


def spec_candidate(feature):
    """La candidata de la fila Origen de la spec de feature, o None."""
    if feature is None:
        return None
    try:
        text = (feature / "spec.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = ORIGIN_ROW.search(text, 0, _trace()._header_end(text))
    first = m.group(1).split("·")[0].strip().upper() if m else ""
    return first if re.fullmatch(r"B\d+", first) else None


def arch_context(root):
    """
    Contexto de arquitectura para planificar la feature activa (D3): los
    componentes de su candidata (o todos, si no tiene), las decisiones vigentes,
    las propuestas y los estandares. {"architecture": False} sin architecture/.
    """
    sa = _architecture()
    if not sa.exists(root):
        return {"architecture": False}
    feature = resolve_feature(root)
    candidate = spec_candidate(feature)
    comps = sa.components(root)
    mine = [c for c in comps if candidate and candidate in c["candidates"]]
    all_adrs = sa.adrs(root)
    problems = sa.approval_problems(root)
    if candidate and not mine:
        problems = problems + [f"{candidate} no vive en ningún componente de "
                               "architecture/components.md (/architecture:init)"]

    def adr_view(a):
        return {"id": a["id"], "title": a["title"], "motive": a["motive"], "file": a["file"]}

    return {
        "architecture": True,
        "approved": not problems,
        "problems": problems,
        "feature": feature.name if feature else None,
        "candidate": candidate,
        "components_scope": "candidate" if candidate else "all",
        "components": mine if candidate else comps,
        "adrs": [adr_view(a) for a in all_adrs if a["state"] == "approved"],
        "proposed": [adr_view(a) for a in all_adrs if a["state"] == "proposed"],
        "standards": sa.standards(root),
    }


def cmd_arch_context(args):
    data = arch_context(project_root())
    if "--json" in args:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    if not data["architecture"]:
        print("Sin architecture/: el plan sigue el camino de siempre.")
        return 0
    out = [f"Arquitectura {'aprobada' if data['approved'] else 'SIN APROBAR'}"
           + (f" · feature {data['feature']}" if data["feature"] else "")]
    out += [f"  - {p}" for p in data["problems"]]
    scope = (f"que alojan {data['candidate']}" if data["components_scope"] == "candidate"
             else "todos (la feature no viene de una candidata)")
    out.append(f"\nComponentes {scope}:")
    out += [f"  {c['id']} — {c['title']}: {c['responsibility']}" for c in data["components"]]
    out.append("\nDecisiones vigentes:")
    out += [f"  {a['id']} — {a['title']} (motivo: {a['motive']})" for a in data["adrs"]]
    if data["proposed"]:
        out.append("\nPropuestas pendientes de /architecture:review (no se citan como vigentes):")
        out += [f"  {a['id']} — {a['title']}" for a in data["proposed"]]
    out.append("\nEstándares:")
    out += [f"  {s['id']} — {s['title']} ({s['kind']}; {s['detail']}; {s['adr']})"
            for s in data["standards"]]
    print("\n".join(out))
    return 0


def propose_adr(root, title, plugin_root):
    """
    Escribe la siguiente decision libre en architecture/adr/ como propuesta, con
    el plan de la feature activa como origen (D4). Devuelve (ok, datos o motivo).

    La plantilla templates/adr.md es una copia de la de plugins/architecture/
    templates/adr.md con Estado Proposed y la fila «Propuesto por»; la
    numeracion es la de sdd_architecture (copia de la de architecture.py).
    """
    sa = _architecture()
    if not sa.exists(root):
        return False, ("No hay architecture/: sin arquitectura no se proponen decisiones; "
                       "esta va al plan.md de la feature. Para crearla, /architecture:init.")
    feature = resolve_feature(root)
    if feature is None:
        return False, ("No hay una feature activa: una decisión se propone desde el plan "
                       "de una feature (/sdd:specify, /sdd:plan).")
    proposer = f"`specs/{feature.name}/plan.md`"
    adr_id = sa.next_adr(root)
    number = adr_id.split("-")[1]
    slug = slugify(title)
    if slug == "feature":  # slugify sin palabras utiles
        slug = "decision"
    path = root / sa.ARCH_DIR / sa.ADR_DIR / f"{number}-{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_template("adr.md", {"NUMBER": number, "TITLE": title,
                                      "DATE": datetime.date.today().isoformat(),
                                      "PROPOSER": proposer}, plugin_root)
    path.write_text(text, encoding="utf-8")
    return True, {"id": adr_id, "file": str(path.relative_to(root))}


def cmd_propose_adr(args):
    title = " ".join(args).strip()
    if not title:
        print('Uso: sdd.py propose-adr "<título de la decisión>"', file=sys.stderr)
        return 2
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
    ok, data = propose_adr(project_root(), title, plugin_root)
    if not ok:
        print(data, file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2))
    return 0


# --------------------------------------------------------------------------
# Diagramas del plan (feature 009)
# --------------------------------------------------------------------------

DIAGRAMS_TITLE = "Diagramas"
SEQUENCE_TITLE = "Secuencia"


def _plan_template_section(plugin_root):
    """La seccion ## Diagramas de templates/plan.md, sin el salto final."""
    text = (Path(plugin_root) / "templates" / "plan.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {DIAGRAMS_TITLE}\n.*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0).rstrip() + "\n" if m else ""


def _mermaid_text(text):
    """Texto de un participante: ';' separa sentencias en Mermaid."""
    return " ".join(str(text).split()).replace(";", "#59;")


def sequence_skeleton(data):
    """Bloque mermaid con un participante por componente de la candidata (D3).
    Sin candidata no hay participantes: el hueco lista entre cuales elegir.
    El hueco lleva '...' para que trace y la compuerta lo traten como tal, y
    no cita un ADR ni un requisito literal, que trace tomaria por citas."""
    mine = data["components"] if data["components_scope"] == "candidate" else []
    lines = ["```mermaid", "sequenceDiagram"]
    lines += [f"  participant {c['id']} as {_mermaid_text(c['title'])}" for c in mine]
    if mine:
        ask = "añade el usuario y los demás participantes"
    else:
        choices = ", ".join(f"{c['id']} ({c['title']})" for c in data["components"])
        ask = (f"elige los participantes entre los componentes {choices}, "
               "y añade el usuario").replace("_", " ")
    lines.append(f"  %% _Completa el flujo principal...: {ask}; cita en cada llamada "
                 "entre componentes la decisión del plan (Dn) o el ADR en que se apoya_")
    lines.append("```")
    return "\n".join(lines) + "\n"


def _subsection(text, title):
    """(inicio, fin) del cuerpo de '### title' dentro de text, o None."""
    m = re.search(rf"^### {re.escape(title)}[^\n]*\n", text, re.M)
    if not m:
        return None
    end = re.search(r"^#{2,3} ", text[m.end():], re.M)
    return m.end(), (m.end() + end.start() if end else len(text))


def plan_diagram(root, plugin_root):
    """
    Escribe el esqueleto de secuencia en el plan de la feature activa (D3).
    Devuelve (codigo_de_salida, lineas_de_mensaje).
    """
    sa = _architecture()
    if not sa.exists(root):
        return 0, ["Sin architecture/: el esqueleto solo se genera con arquitectura. "
                   "Dibuja los diagramas del plan desde cero en ## Diagramas."]
    feature = resolve_feature(root)
    plan = feature / "plan.md" if feature else None
    if plan is None or not plan.is_file():
        return 1, ["No hay plan.md en la feature activa: créalo con /sdd:plan."]
    data = arch_context(root)
    if not data["approved"]:
        return 1, (["La arquitectura no está aprobada, o la candidata no tiene "
                    "componente:"] + [f"  - {x}" for x in data["problems"]])
    text = plan.read_text(encoding="utf-8")
    t = _trace()
    hole = {t._squash(x) for x in t.template_lines("plan.md")}
    skeleton = sequence_skeleton(data)
    section = re.search(rf"^## {DIAGRAMS_TITLE}[^\n]*\n.*?(?=^## |\Z)", text, re.M | re.S)
    if section:
        span = _subsection(section.group(0), SEQUENCE_TITLE)
        if span is None:
            return 0, [f"plan.md tiene ## {DIAGRAMS_TITLE} sin ### {SEQUENCE_TITLE}: "
                       "no se toca. Añade el apartado desde la plantilla."]
        body = section.group(0)[span[0]:span[1]]
        content = [x for x in body.splitlines() if x.strip()]
        if any(t._squash(x) not in hole for x in content):
            return 0, ["plan.md ya tenía diagramas de secuencia (o «No aplica.»): "
                       "no se toca."]
        start = section.start() + span[0]
        new = (text[:start] + "\n" + skeleton + "\n"
               + text[section.start() + span[1]:].lstrip("\n"))
    else:
        block = _plan_template_section(plugin_root)
        span = _subsection(block, SEQUENCE_TITLE)
        if span is None:
            return 1, [f"La plantilla templates/plan.md no tiene ## {DIAGRAMS_TITLE} con "
                       f"### {SEQUENCE_TITLE}: reinstala el plugin sdd."]
        block = block[:span[0]] + "\n" + skeleton + "\n" + block[span[1]:].lstrip("\n")
        new = text.rstrip("\n") + "\n\n" + block
    was_approved = t.is_approved(text)
    plan.write_text(new, encoding="utf-8")
    rel = plan.relative_to(root)
    out = [f"{rel}: esqueleto de secuencia en ## {DIAGRAMS_TITLE} > ### {SEQUENCE_TITLE}"
           + (f" con {', '.join(c['id'] for c in data['components'])}."
              if data["components_scope"] == "candidate" else
              ", sin participantes: la feature no viene de una candidata."),
           "Complétalo, y también el modelo de datos y las clases (o «No aplica.»)."]
    if was_approved:
        out.append("plan.md estaba aprobado y ha cambiado: el usuario lo revisa y lo "
                   "vuelve a aprobar con /sdd:approve. Si tasks.md estaba aprobado, al "
                   "aprobar el plan de nuevo vuelve a Draft y también hay que aprobarlo.")
    return 0, out


def cmd_diagram(_args):
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
    code, lines = plan_diagram(project_root(), plugin_root)
    print("\n".join(lines), file=sys.stderr if code else sys.stdout)
    return code


COMMANDS = {
    "new": cmd_new,
    "arch-context": cmd_arch_context,
    "propose-adr": cmd_propose_adr,
    "diagram": cmd_diagram,
    "current": cmd_current,
    "status": cmd_status,
    "context": cmd_context,
    "guard": cmd_guard,
    "audit": cmd_audit,
    "approve": cmd_approve,
    "next-req": cmd_next_req,
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
        return 0 if argv[1] in ("guard", "context", "quality", "audit") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
