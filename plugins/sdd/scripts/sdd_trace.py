#!/usr/bin/env python3
"""
sdd_trace.py - matriz de trazabilidad requisito -> tarea -> prueba.

Convierte los IDs de requisito en algo con consecuencias: sin este modulo,
R001 es un adorno tipografico. Se ejecuta en dos sitios con la misma logica:
como skill local (/sdd:trace) y como paso de CI (`trace --check --json`).

Codigos de hallazgo: ver FINDINGS. Los que empiezan por E- hacen fallar --check.
"""

import json
import os
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Catalogo de hallazgos. Es contrato publico: no renombrar codigos existentes.
# --------------------------------------------------------------------------

FINDINGS = {
    "E-REQ-NO-TASK":       "Requisito MUST sin ninguna tarea que lo implemente",
    "E-REQ-NO-TEST":       "Requisito MUST sin ninguna prueba que lo referencie",
    "E-REQ-NO-CRITERIA":   "Requisito MUST sin criterios de aceptacion",
    "E-REQ-DUPLICATE":     "ID de requisito duplicado",
    "E-TASK-UNKNOWN-REQ":  "Tarea que referencia un requisito inexistente",
    "E-TASK-UNKNOWN-DEP":  "Tarea que depende de una tarea inexistente",
    "E-TASK-DEP-CYCLE":    "Ciclo de dependencias entre tareas",
    "E-DONE-NO-TEST":      "Tarea cerrada cuyos requisitos no tienen prueba",
    "E-SPEC-OPEN-MUST-QUESTION": "Pregunta abierta que afecta a un requisito MUST",
    "E-PLAN-REQ-MISSING":  "Requisito MUST que plan.md no menciona",
    "E-PLAN-UNKNOWN-REQ":  "plan.md cita un requisito que no existe en spec.md",
    "E-PLAN-TEMPLATE":     "plan.md conserva marcadores de plantilla sin rellenar",
    "E-SPEC-TEMPLATE":     "spec.md conserva marcadores de plantilla sin rellenar",
    "E-TASK-TEMPLATE":     "tasks.md conserva marcadores de plantilla sin rellenar",
    "W-REQ-NO-TASK":       "Requisito SHOULD/COULD sin tarea",
    "W-REQ-NO-EARS":       "Requisito que no usa la forma EARS (falta DEBERA)",
    "W-REQ-VAGUE":         "Requisito con adjetivo sin umbral verificable",
    "W-TASK-NO-REQ":       "Tarea que no referencia ningun requisito",
    "W-DONE-OPEN-DEPS":    "Tarea cerrada con dependencias sin cerrar",
    "W-SPEC-OPEN-QUESTIONS": "La spec tiene preguntas abiertas sin resolver",
    "W-SPEC-NO-UNWANTED":  "La spec no tiene requisitos de comportamiento no deseado",
    "W-PLAN-NO-CONSTITUTION-CHECK": "plan.md no contrasta sus decisiones con la constitucion",
    "E-PLAN-ADR-UNKNOWN":  "plan.md cita una decision de arquitectura que no existe",
    "E-PLAN-ADR-NOT-APPROVED": "plan.md cita una decision de arquitectura no aprobada",
    "W-PLAN-NO-ARCHITECTURE-CHECK": "plan.md no contrasta sus decisiones con la arquitectura",
    "W-PLAN-ADR-SUPERSEDED": "plan.md aprobado cita una decision sustituida despues",
    "E-PLAN-DIAGRAM-UNKNOWN": "plan.md dibuja en un diagrama un componente que no existe",
    "E-PLAN-DIAGRAM-VIOLATION": ("plan.md dibuja una llamada que un estandar prohibe o "
                                 "declara en sentido contrario"),
    "W-PLAN-NO-DIAGRAMS":  "plan.md no tiene diagramas ni declara que no aplican",
    "W-TASK-NO-DONE-WHEN": "Tarea sin condicion de terminado",
    "W-TEST-EMPTY":        "Prueba vacia que cita el requisito: no cuenta como evidencia",
    "W-TEST-NO-ASSERT":    "Prueba que cita el requisito sin ninguna asercion reconocible",
    "W-TASK-OBSOLETE-REQ": "Tarea abierta que sirve a un requisito obsoleto",
    "W-TEST-UNSCOPED":     "Prueba que cita el requisito sin el prefijo de la feature",
}

VAGUE = [
    "rapido", "rapida", "intuitivo", "intuitiva", "robusto", "robusta",
    "escalable", "eficiente", "facil", "sencillo", "amigable", "moderno",
    "optimo", "optima", "flexible", "potente", "fluido", "adecuado",
    "razonable", "apropiado", "user-friendly", "seamless", "fast", "intuitive",
    "robust", "scalable", "efficient", "easy", "simple", "modern", "flexible",
]

TEST_GLOBS = [
    "test_*.py", "*_test.py", "*_test.go", "*_test.rb", "*_spec.rb",
    "*.test.ts", "*.test.tsx", "*.test.js", "*.test.jsx",
    "*.spec.ts", "*.spec.tsx", "*.spec.js", "*.spec.jsx",
    "*Test.java", "*Tests.cs", "*_test.rs",
]
TEST_DIRS = {"test", "tests", "spec", "specs__", "__tests__", "testing"}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", ".next", ".tox", "vendor", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "coverage", ".terraform",
}

TEST_DECL = re.compile(
    r"(?:def\s+(test\w*)|func\s+(Test\w*)|"
    r"(?:it|test|describe)\s*\(\s*[\"'`](.+?)[\"'`])"
)

# Sin \b: el guion bajo es caracter de palabra, asi que \bR001\b NO casa
# dentro de test_R001_algo, que es justo la convencion que pedimos.
REQ_ID = re.compile(r"(?<![A-Za-z0-9])R(\d{2,})(?![0-9])")
# Referencia con alcance de feature: F002_R001 o F002-R001. Los IDs R001 se
# reinician en cada feature, asi que solo esta forma identifica un requisito
# de manera univoca en un repositorio con varias features.
SCOPED_REQ_ID = re.compile(r"(?<![A-Za-z0-9])F(\d{3,})[_-]R(\d{2,})(?![0-9])")
TASK_ID = re.compile(r"(?<![A-Za-z0-9])T(\d{2,})(?![0-9])")


ACCENTS = str.maketrans(
    "\u00e1\u00e0\u00e4\u00e2\u00e9\u00e8\u00eb\u00ea"
    "\u00ed\u00ec\u00ef\u00ee\u00f3\u00f2\u00f6\u00f4"
    "\u00fa\u00f9\u00fc\u00fb\u00f1\u00e7",
    "aaaaeeeeiiiioooouuuunc",
)


def norm(text):
    """Minusculas sin acentos, para comparar etiquetas y buscar palabras."""
    return text.lower().translate(ACCENTS)


def section(text, *titles):
    """Extrae el cuerpo de una seccion markdown por su titulo (sin acentos)."""
    lines = text.splitlines()
    wanted = {norm(t) for t in titles}
    out, level, capturing = [], None, False
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            depth, title = len(m.group(1)), norm(m.group(2)).strip()
            if capturing and depth <= level:
                break
            if not capturing and any(w in title for w in wanted):
                capturing, level = True, depth
                continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def feature_number(feature):
    """'002-exportar-csv' -> 2. None si el nombre no empieza por numero."""
    m = re.match(r"^(\d+)-", feature.name)
    return int(m.group(1)) if m else None


def scoped_ref(feature, rid):
    """Forma canonica de citar un requisito en una prueba: F002_R001."""
    num = feature_number(feature)
    return f"F{num:03d}_{rid}" if num is not None else rid


# --------------------------------------------------------------------------
# Marcadores de plantilla y estado del documento
# --------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Un texto en cursiva con guion bajo (_..._) en la plantilla es un hueco que
# hay que sustituir. Las notas que se pueden conservar van en blockquote.
ITALIC_EDGE = re.compile(
    r"(?:^|[\s|*(>\[])_(?=[^\s_])|(?<=[^\s_])_(?=$|[\s|.,;:)*\]])"
)
INLINE_PLACEHOLDER = re.compile(
    r"(?<![A-Za-z0-9])_[^_\n]*(?:\.\.\.|\\<)[^_\n]*_(?![A-Za-z0-9])"
)
TEMPLATE_VAR = re.compile(r"\{\{[A-Z_]+\}\}")
_TEMPLATE_CACHE = {}


def _squash(line):
    """Normaliza espacios y relleno de tablas para comparar lineas."""
    line = re.sub(r"\s*\|\s*", "|", line.strip())
    return re.sub(r"\s+", " ", line)


def template_lines(name):
    """Lineas de la plantilla que son huecos por rellenar."""
    if name not in _TEMPLATE_CACHE:
        lines = set()
        path = TEMPLATES_DIR / name
        if path.is_file():
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if line and not TEMPLATE_VAR.search(line) and ITALIC_EDGE.search(line):
                    lines.add(_squash(line))
        _TEMPLATE_CACHE[name] = lines
    return _TEMPLATE_CACHE[name]


def find_placeholders(text, template_name):
    """[(numero_de_linea, linea)] con huecos de plantilla sin rellenar."""
    known = template_lines(template_name)
    out = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if (TEMPLATE_VAR.search(line) or _squash(line) in known
                or INLINE_PLACEHOLDER.search(line)):
            out.append((i, line))
    return out


STATUS_ROW = re.compile(
    r"^(\|\s*(?:Estado|Status)\s*\|\s*)([^|\n]*?)(\s*\|)", re.I | re.M
)
APPROVED = {"approved", "aprobado", "aprobada"}


def _header_end(text):
    """Fin de la cabecera: el primer encabezado de nivel 2. Asi una fila
    «| Estado | MIENTRAS ... |» de la tabla de patrones EARS no se confunde
    con el estado del documento."""
    m = re.search(r"^##\s", text, re.M)
    return m.start() if m else len(text)


def doc_status(text):
    """Valor del campo Estado de la cabecera, o None si no existe."""
    text = text or ""
    m = STATUS_ROW.search(text, 0, _header_end(text))
    return m.group(2).strip() if m else None


def is_approved(text):
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    return bool(words) and words[0].strip("`*_") in APPROVED


TASK_STATE_LINE = re.compile(r"^\s*[-*]\s*\*\*\s*(?:Estado|Status)\s*:?\s*\*\*", re.I)
DIGEST = re.compile(r"\b([0-9a-f]{12})\b")


def content_digest(text, fname):
    """
    Huella del contenido revisable de un artefacto. Excluye la fila Estado de
    la cabecera (donde se guarda la propia huella) y, en tasks.md, las lineas
    de estado de cada tarea, que /sdd:implement cambia sin alterar el plan de
    trabajo. Ignora espacios y lineas en blanco: reformatear no es cambiar.
    """
    end = _header_end(text)
    head = STATUS_ROW.sub("", text[:end], count=1)
    lines = []
    for raw in (head + text[end:]).splitlines():
        if fname == "tasks.md" and TASK_STATE_LINE.match(raw):
            continue
        line = _squash(raw)
        if line:
            lines.append(line)
    import hashlib
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()[:12]


def approval_digest(text):
    """Huella guardada al aprobar ('Approved · 3f9a2c...'), o None."""
    m = DIGEST.search(doc_status(text) or "")
    return m.group(1) if m else None


def is_stale(text, fname):
    """True si el artefacto cambio despues de aprobarse."""
    stamp = approval_digest(text)
    return bool(is_approved(text) and stamp and stamp != content_digest(text, fname))


def set_status(text, value):
    """Devuelve (texto_nuevo, cambiado?)."""
    end = _header_end(text)
    head, n = STATUS_ROW.subn(lambda m: m.group(1) + value + m.group(3),
                              text[:end], count=1)
    return head + text[end:], bool(n)


# --------------------------------------------------------------------------
# Parseo de spec.md
# --------------------------------------------------------------------------

def parse_spec(path):
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    reqs, order, duplicates = {}, [], []

    row = re.compile(
        r"^\|\s*(R\d{2,})\s*\|\s*(MUST|SHOULD|COULD|DEBE|DEBERIA|PODRIA|"
        r"OBSOLETE|OBSOLETO|OBSOLETA|DEPRECATED)\s*\|\s*(.+?)\s*\|\s*$",
        re.I | re.M,
    )
    for rid, prio, body in row.findall(text):
        rid = rid.upper()
        prio = {"DEBE": "MUST", "DEBERIA": "SHOULD", "PODRIA": "COULD",
                "OBSOLETO": "OBSOLETE", "OBSOLETA": "OBSOLETE",
                "DEPRECATED": "OBSOLETE"}.get(prio.upper(), prio.upper())
        if rid in reqs:
            duplicates.append(rid)
            continue
        reqs[rid] = {"id": rid, "priority": prio, "text": body.strip()}
        order.append(rid)

    # Fallback: requisitos declarados como encabezado en vez de tabla.
    for m in re.finditer(r"^#{2,5}\s*(R\d{2,})\b[^\n]*\n(.*?)(?=^#{1,5}\s|\Z)",
                         text, re.M | re.S):
        rid = m.group(1).upper()
        if rid in reqs:
            continue
        body = " ".join(m.group(2).split())[:400]
        prio = "MUST"
        for p in ("MUST", "SHOULD", "COULD"):
            if p in m.group(0).upper():
                prio = p
                break
        reqs[rid] = {"id": rid, "priority": prio, "text": body}
        order.append(rid)

    # Criterios de aceptacion: subsecciones por requisito.
    criteria = {rid: 0 for rid in reqs}
    body = section(text, "criterios de aceptacion", "acceptance criteria")
    current = None
    for line in body.splitlines():
        h = re.match(r"^#{2,6}\s*(R\d{2,})\b", line)
        if h:
            current = h.group(1).upper()
            continue
        if current and re.match(r"^\s*[-*]\s+\S", line):
            criteria[current] = criteria.get(current, 0) + 1

    # Preguntas abiertas sin marcar, con los requisitos que citan:
    #   - [ ] (R002) ¿Cuanto dura la sesion?
    questions = [
        {"text": m.group(1).strip(),
         "requirements": sorted({"R" + n for n in REQ_ID.findall(m.group(1))})}
        for m in re.finditer(r"^\s*[-*]\s*\[ \]\s*(.*)$",
                             section(text, "preguntas abiertas", "open questions"), re.M)
    ]

    return {
        "path": path.name,
        "exists": path.is_file(),
        "status": doc_status(text),
        "placeholders": find_placeholders(text, "spec.md"),
        "requirements": [dict(reqs[r], criteria=criteria.get(r, 0)) for r in order],
        "duplicates": duplicates,
        "open_questions": len(questions),
        "questions": questions,
    }


# --------------------------------------------------------------------------
# Parseo de tasks.md
# --------------------------------------------------------------------------

FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$", re.M)


def parse_tasks(path):
    if not path.is_file():
        return {"path": path.name, "exists": False, "status": None,
                "placeholders": [], "tasks": []}
    text = path.read_text(encoding="utf-8", errors="replace")

    tasks, seen = [], set()
    blocks = re.split(r"^#{2,5}\s*(?=T\d{2,}\b)", text, flags=re.M)
    for block in blocks[1:]:
        head, _, rest = block.partition("\n")
        tid_match = TASK_ID.search(head)
        if not tid_match:
            continue
        tid = "T" + tid_match.group(1)
        if tid in seen:
            continue
        seen.add(tid)

        title = re.sub(r"^T\d{2,}\s*[\u2014\u2013:-]?\s*", "", head).strip()
        fields = {norm(k): v.strip() for k, v in FIELD.findall(rest)}

        state_raw = fields.get("estado", fields.get("status", ""))
        if "[x]" in state_raw.lower():
            state = "done"
        elif "[~]" in state_raw:
            state = "wip"
        else:
            state = "todo"

        req_field = fields.get("requisitos", fields.get("requirements", ""))
        dep_field = fields.get("depende de", fields.get("depends on",
                              fields.get("dependencias", "")))

        tasks.append({
            "id": tid,
            "title": title,
            "state": state,
            "requirements": sorted({"R" + n for n in REQ_ID.findall(req_field)}),
            "depends_on": sorted({"T" + n for n in TASK_ID.findall(dep_field)}),
            "done_when": fields.get("hecho cuando", fields.get("done when", "")),
        })
    return {"path": path.name, "exists": True, "status": doc_status(text),
            "placeholders": find_placeholders(text, "tasks.md"), "tasks": tasks}


# --------------------------------------------------------------------------
# Parseo de plan.md
# --------------------------------------------------------------------------

def parse_plan(path):
    if not path.is_file():
        return {"path": path.name, "exists": False, "status": None,
                "placeholders": [], "cited": [], "constitution_check": False,
                "adrs": [], "architecture_check": False, "approved": False,
                "diagrams": ""}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": path.name,
        "exists": True,
        "status": doc_status(text),
        "placeholders": find_placeholders(text, "plan.md"),
        "cited": sorted({"R" + n for n in REQ_ID.findall(text)}),
        "constitution_check": bool(section(text, "constitucion", "constitution").strip()),
        # Decisiones de arquitectura que cita el plan y su seccion de contraste
        # (feature 007); solo se comprueban si el proyecto tiene architecture/.
        "adrs": sorted({"ADR-" + n for n in ADR_REF.findall(text)}),
        "architecture_check": bool(section(text, "comprobacion de arquitectura",
                                           "architecture check").strip()),
        "approved": is_approved(text),
        # Seccion ## Diagramas (feature 009), sin las notas en blockquote.
        "diagrams": "\n".join(x for x in section(text, "diagramas", "diagrams").splitlines()
                              if not x.lstrip().startswith(">")),
    }


ADR_REF = re.compile(r"(?<![A-Za-z0-9])ADR-(\d{4})(?![0-9])")


def check_plan_architecture(root, plan, add):
    """
    Con architecture/ en el proyecto: el plan se contrasta con la arquitectura
    y solo cita decisiones aprobadas (R003, R004). Un plan aprobado que cita
    una decision sustituida despues recibe un aviso y no un error (R005).
    """
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import sdd_architecture
    if not sdd_architecture.exists(root):
        return
    if not plan["architecture_check"]:
        add("W-PLAN-NO-ARCHITECTURE-CHECK",
            "El proyecto tiene architecture/ y plan.md no tiene la seccion "
            "'Comprobacion de arquitectura': contrasta el plan con los componentes, "
            "las decisiones y los estandares (sdd.py arch-context).")
    by_id = {a["id"]: a for a in sdd_architecture.adrs(root)}
    for ref in plan["adrs"]:
        adr = by_id.get(ref)
        if adr is None:
            add("E-PLAN-ADR-UNKNOWN",
                f"plan.md cita {ref}, que no existe en architecture/adr/.")
        elif adr["state"] == "approved":
            continue
        elif adr["state"] == "superseded" and plan["approved"]:
            add("W-PLAN-ADR-SUPERSEDED",
                f"plan.md (aprobado) cita {ref}, sustituida despues por "
                f"{adr['superseded_by'] or 'otra decision'}: revisa si el plan sigue valiendo.")
        elif adr["state"] == "proposed":
            add("E-PLAN-ADR-NOT-APPROVED",
                f"plan.md cita {ref}, que esta propuesta y sin decidir: el usuario la "
                "acepta o la rechaza con /architecture:review antes de aprobar el plan.")
        else:
            estado = {"draft": "en borrador", "stale": "cambiada despues de aprobarse",
                      "rejected": "rechazada", "superseded": "sustituida"}[adr["state"]]
            add("E-PLAN-ADR-NOT-APPROVED",
                f"plan.md cita {ref}, que esta {estado}: un plan solo se apoya en "
                "decisiones aprobadas.")


# Diagramas del plan (feature 009, D5): solo los sequenceDiagram se contrastan
# con la arquitectura; el modelo de datos y las clases no tienen con que.
MERMAID_BLOCK = re.compile(r"^```mermaid[ \t]*\n(.*?)^```", re.M | re.S)
SEQ_PARTICIPANT = re.compile(r"^\s*(?:create\s+)?(?:participant|actor)\s+([A-Za-z_]\w*)")
# A->>B:, A-->>B:, A->B:, A-xB:, A-)B:, A<<->>B: ... El texto tras ':' no cuenta.
SEQ_MESSAGE = re.compile(
    r"^\s*([A-Za-z_]\w*)\s*(<<-{1,2}>>|-{1,2}(?:>>|>|x|\)))\s*[+-]?\s*([A-Za-z_]\w*)\s*:")
COMPONENT_ID = re.compile(r"^C\d+$")


def diagram_kind(block):
    """Primera palabra del bloque mermaid, tras el frontmatter (---) y las
    directivas o comentarios (%%) que pueden precederla."""
    body = re.sub(r"\A\s*---\n.*?\n---[ \t]*\n", "", block, flags=re.S)
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("%%"):
            return line.split()[0]
    return ""


def sequence_graph(block):
    """(participantes, llamadas) de un sequenceDiagram. Una llamada es una
    flecha continua (->>, ->, -x, -)): el que llama depende del llamado. Las
    discontinuas (-->>) son respuestas y no cuentan (D2)."""
    names, calls = set(), []
    for raw in block.splitlines():
        line = raw.split("%%", 1)[0]
        m = SEQ_PARTICIPANT.match(line)
        if m:
            names.add(m.group(1))
            continue
        m = SEQ_MESSAGE.match(line)
        if not m:
            continue
        a, arrow, b = m.groups()
        names.update((a, b))
        if arrow.startswith("<<"):
            if arrow == "<<->>":
                calls += [(a, b), (b, a)]
        elif not arrow.startswith("--"):
            calls.append((a, b))
    return names, calls


def check_plan_diagrams(root, plan, add):
    """W-PLAN-NO-DIAGRAMS siempre (R006); con architecture/, los componentes y
    las llamadas de los diagramas de secuencia frente a la arquitectura (R004,
    R005). Sin architecture/ no se contrasta nada (R007)."""
    if not plan["diagrams"].strip():
        add("W-PLAN-NO-DIAGRAMS",
            "plan.md no tiene la seccion 'Diagramas' (secuencia, modelo de datos y "
            "clases, o 'No aplica.' en cada uno): anadela desde la plantilla, o con "
            "sdd.py diagram si hay architecture/.")
        return
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import sdd_architecture
    if not sdd_architecture.exists(root):
        return
    names, calls = set(), []
    for block in MERMAID_BLOCK.findall(plan["diagrams"]):
        if diagram_kind(block) == "sequenceDiagram":
            n, c = sequence_graph(block)
            names |= n
            calls += c
    known = {c["id"] for c in sdd_architecture.components(root)}
    for name in sorted((n for n in names if COMPONENT_ID.match(n) and n not in known),
                       key=lambda x: int(x[1:])):
        add("E-PLAN-DIAGRAM-UNKNOWN",
            f"Un diagrama de plan.md nombra {name}, que no es un componente de "
            "architecture/components.md.")
    deps = sdd_architecture.standard_pairs(root, "dependencia")
    banned = sdd_architecture.standard_pairs(root, "prohibida")
    seen = set()
    for a, b in calls:
        for x, y, sid in deps:
            if (a, b) == (y, x) and (a, b, sid) not in seen:
                seen.add((a, b, sid))
                add("E-PLAN-DIAGRAM-VIOLATION",
                    f"El diagrama de secuencia de plan.md dibuja una llamada de {a} a {b}, "
                    f"pero {sid} declara {x} -> {y}.")
        for x, y, sid in banned:
            if (a, b) == (x, y) and (a, b, sid) not in seen:
                seen.add((a, b, sid))
                add("E-PLAN-DIAGRAM-VIOLATION",
                    f"El diagrama de secuencia de plan.md dibuja una llamada de {a} a {b}, "
                    f"una dependencia que {sid} prohibe.")


# --------------------------------------------------------------------------
# Barrido de pruebas
# --------------------------------------------------------------------------

def is_test_file(path):
    from fnmatch import fnmatch
    if any(fnmatch(path.name, g) for g in TEST_GLOBS):
        return True
    return any(norm(part) in TEST_DIRS for part in path.parts[:-1])


def code_view(content, suffix):
    """
    Lineas del archivo con el contenido de los textos literales en blanco,
    mismas lineas y columnas. Las citas y las declaraciones de prueba se buscan
    aqui: una cadena "def test_F001_R001_x()" escrita como dato en un test no
    es una prueba (R010 de la feature 002). Nombres y comentarios se conservan.

    Python se tokeniza, que conoce las cadenas de varias lineas; si no se puede
    tokenizar, se devuelve el texto tal cual. En los demas lenguajes la vista es
    el texto tal cual: un analizador hecho a mano perdia citas reales en formas
    habituales de nombrar o comentar pruebas (R010 de la feature 002).
    """
    lines = content.splitlines()
    if suffix != ".py":
        return lines
    import tokenize
    string_types = {tokenize.STRING}
    for name in ("FSTRING_MIDDLE", "TSTRING_MIDDLE"):  # f-strings 3.12+, t-strings 3.14+
        if hasattr(tokenize, name):
            string_types.add(getattr(tokenize, name))
    chars = [list(line) for line in lines]
    # Se tokenizan las mismas lineas que devuelve splitlines(): asi las filas de
    # los tokens coinciden aunque el archivo tenga saltos de pagina (\x0c) u
    # otros separadores que splitlines() corta y tokenize no.
    feed = iter([line + "\n" for line in lines])
    try:
        for tok in tokenize.generate_tokens(lambda: next(feed, "")):
            if tok.type not in string_types:
                continue
            (srow, scol), (erow, ecol) = tok.start, tok.end
            for row in range(srow, erow + 1):
                if row - 1 >= len(chars):
                    break
                line = chars[row - 1]
                start = scol if row == srow else 0
                end = ecol if row == erow else len(line)
                for c in range(start, min(end, len(line))):
                    line[c] = " "
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
        return lines
    return ["".join(line) for line in chars]


def python_test_spans(lines):
    """
    [(primera_linea, ultima_linea, nombre)] de cada funcion cuyo nombre empieza
    por test, tambien metodos de clase y funciones anidadas. Lineas 1-based,
    desde el `def` (no el decorador) hasta el final del cuerpo.

    Se analizan las mismas lineas que devuelve splitlines(), como en code_view,
    para que la numeracion coincida. None si el archivo no se puede analizar
    (sintaxis invalida o de una version mas nueva): entonces se usa la
    atribucion de siempre.
    """
    import ast
    try:
        tree = ast.parse("\n".join(lines) + "\n")
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return None
    return [(node.lineno, node.end_lineno, node.name)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")]


def scan_tests(root, extra_globs=None):
    """
    Devuelve (scoped, bare):
      scoped: {(numero_feature, req_id): {"ruta::nombre": tipo}}  (F002_R001)
              tipo: 'ok' | 'no-assert' | 'empty' (ver test_body_kind)
      bare:   {req_id: [...]}  (R001 sin prefijo: ambiguo, no cuenta)
    """
    from fnmatch import fnmatch
    scoped, bare = {}, {}
    extra = extra_globs or []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(root)
            if rel.parts and rel.parts[0] == "specs":
                continue
            if not (is_test_file(rel) or any(fnmatch(rel.as_posix(), g) for g in extra)):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "R" not in content:
                continue
            lines = content.splitlines()
            suffix = path.suffix.lower()
            view = code_view(content, suffix)
            spans = python_test_spans(lines) if suffix == ".py" else None
            for i, line in enumerate(view):
                hits = [((int(f), "R" + r), scoped)
                        for f, r in SCOPED_REQ_ID.findall(line)]
                hits += [("R" + r, bare)
                         for r in REQ_ID.findall(SCOPED_REQ_ID.sub(" ", line))]
                if not hits:
                    continue
                label, kind = None, "ok"
                if spans is not None:
                    # Python: la cita es de la funcion de prueba que la contiene,
                    # la mas interior; fuera de toda prueba no cuenta (main(),
                    # ayudantes, nivel de modulo).
                    inside = [s for s in spans if s[0] <= i + 1 <= s[1]]
                    if not inside:
                        continue
                    start, _end, label = max(inside, key=lambda s: s[0])
                    kind = test_body_kind(lines, start - 1, suffix)
                else:
                    for j in range(i, max(-1, i - 25), -1):
                        d = TEST_DECL.search(view[j])
                        if d:
                            label = next(g for g in d.groups() if g)
                            kind = test_body_kind(lines, j, suffix)
                            break
                ref = f"{rel.as_posix()}::{label}" if label else rel.as_posix()
                for key, bucket in hits:
                    if bucket is scoped:
                        bucket.setdefault(key, {})[ref] = kind
                    else:
                        bucket.setdefault(key, set()).add(ref)
    return (scoped, {k: sorted(v) for k, v in bare.items()})


# --------------------------------------------------------------------------
# Cuerpo de una prueba: vacia, sin asercion, o con asercion
# --------------------------------------------------------------------------

ASSERTION = re.compile(
    r"\bassert\w*|\bexpect\s*\(|\.should\b|\bt\.(?:Error|Fatal|Fail)\w*"
    r"|\brequire\.\w+|\bpytest\.(?:raises|fail|warns)|\bself\.assert\w+"
    r"|\bAssert\.\w+|\bassertThat\b|\bverify\s*\(|\bpanic!|\bfail\s*\("
    r"|\braise\b|\bthrow\b|\bmust\.\w+|\bshould\.\w+"
)
BRACE_LANGS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".java",
               ".kt", ".rs", ".cs", ".swift", ".scala", ".php"}


def _python_body(lines, decl):
    head = lines[decl]
    indent = len(head) - len(head.lstrip())
    # Cuerpo en la misma linea: def test_x(a: int) -> None: pass
    m = re.search(r"\)\s*(?:->[^:]*)?:(.*)$", head)
    body = [m.group(1) if m else ""]
    for line in lines[decl + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    text = "\n".join(body)
    text = re.sub(r'("""|\'\'\')[\s\S]*?\1', "", text)       # docstrings
    text = re.sub(r"#[^\n]*", "", text)                         # comentarios
    return text


def _brace_body(lines, decl):
    text = "\n".join(lines[decl:decl + 400])
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    text = re.sub(r"(?<![:\\])//[^\n]*", "", text)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    return None


def test_body_kind(lines, decl, suffix):
    """'empty' | 'no-assert' | 'ok'. Ante la duda, 'ok': un falso positivo aqui
    le quitaria a un requisito una prueba legitima."""
    if suffix == ".py":
        body = _python_body(lines, decl)
    elif suffix in BRACE_LANGS:
        body = _brace_body(lines, decl)
    else:
        return "ok"
    if body is None:
        return "ok"
    residue = re.sub(r"\b(?:pass|return)\b|\.\.\.|[;\s]", "", body)
    if not residue:
        return "empty"
    return "ok" if ASSERTION.search(body) else "no-assert"


# --------------------------------------------------------------------------
# Analisis
# --------------------------------------------------------------------------

def find_cycles(tasks):
    graph = {t["id"]: [d for d in t["depends_on"] if d in {x["id"] for x in tasks}]
             for t in tasks}
    state, cycles = {}, []

    def visit(node, stack):
        if state.get(node) == "done":
            return
        if state.get(node) == "open":
            cycles.append(stack[stack.index(node):] + [node])
            return
        state[node] = "open"
        for nxt in graph.get(node, []):
            visit(nxt, stack + [nxt])
        state[node] = "done"

    for node in graph:
        visit(node, [node])
    return cycles


def analyze(root, feature, config):
    spec = parse_spec(feature / "spec.md")
    plan = parse_plan(feature / "plan.md")
    tasks_doc = parse_tasks(feature / "tasks.md")
    scoped, bare = scan_tests(root, (config.get("tests") or {}).get("globs"))
    fnum = feature_number(feature)

    reqs = spec["requirements"]
    req_ids = {r["id"] for r in reqs}
    tasks = tasks_doc["tasks"]
    task_ids = {t["id"] for t in tasks}

    by_req_tasks = {r["id"]: [] for r in reqs}
    findings = []

    def add(code, message, **extra):
        findings.append({
            "code": code,
            "severity": "error" if code.startswith("E-") else "warning",
            "title": FINDINGS.get(code, code),
            "message": message,
            **extra,
        })

    for ph, code in ((spec["placeholders"], "E-SPEC-TEMPLATE"),
                     (plan["placeholders"], "E-PLAN-TEMPLATE"),
                     (tasks_doc["placeholders"], "E-TASK-TEMPLATE")):
        if ph:
            line, text = ph[0]
            add(code, f"Quedan {len(ph)} hueco(s) de plantilla sin rellenar; "
                      f"el primero en la linea {line}: {text[:80]}", count=len(ph))

    for rid in spec["duplicates"]:
        add("E-REQ-DUPLICATE", f"El requisito {rid} esta declarado mas de una vez.",
            requirement=rid)

    for t in tasks:
        for rid in t["requirements"]:
            if rid in by_req_tasks:
                by_req_tasks[rid].append(t["id"])
            else:
                add("E-TASK-UNKNOWN-REQ",
                    f"La tarea {t['id']} referencia {rid}, que no existe en spec.md.",
                    task=t["id"], requirement=rid)
        for dep in t["depends_on"]:
            if dep not in task_ids:
                add("E-TASK-UNKNOWN-DEP",
                    f"La tarea {t['id']} depende de {dep}, que no existe.",
                    task=t["id"])
        if not t["requirements"]:
            add("W-TASK-NO-REQ",
                f"La tarea {t['id']} no referencia ningun requisito. "
                "Si no sirve a un requisito, sobra o falta el requisito.",
                task=t["id"])

    if plan["exists"]:
        for rid in [r["id"] for r in reqs if r["priority"] == "MUST"]:
            if rid not in plan["cited"]:
                add("E-PLAN-REQ-MISSING",
                    f"{rid} es MUST y plan.md no lo menciona: o falta cobertura en el "
                    "plan o sobra el requisito.", requirement=rid)
        for rid in plan["cited"]:
            if rid not in req_ids:
                add("E-PLAN-UNKNOWN-REQ",
                    f"plan.md cita {rid}, que no existe en spec.md. Un requisito nuevo "
                    "se anade a la spec, no al plan.", requirement=rid)
        if (root / "specs" / "constitution.md").is_file() and not plan["constitution_check"]:
            add("W-PLAN-NO-CONSTITUTION-CHECK",
                "Existe specs/constitution.md y plan.md no tiene la seccion "
                "'Comprobacion de constitucion'.")
        check_plan_architecture(root, plan, add)
        check_plan_diagrams(root, plan, add)

    for t in tasks:
        if not t["done_when"].strip():
            add("W-TASK-NO-DONE-WHEN",
                f"La tarea {t['id']} no tiene 'Hecho cuando': no hay forma objetiva "
                "de cerrarla.", task=t["id"])

    for cycle in find_cycles(tasks):
        add("E-TASK-DEP-CYCLE",
            "Ciclo de dependencias: " + " -> ".join(cycle))

    obsolete = {r["id"] for r in reqs if r["priority"] == "OBSOLETE"}
    for t in tasks:
        stale = [rid for rid in t["requirements"] if rid in obsolete]
        if stale and t["state"] != "done":
            add("W-TASK-OBSOLETE-REQ",
                f"La tarea {t['id']} sigue abierta y sirve a {', '.join(stale)}, "
                "que es obsoleto. Retirala o reasignala al requisito que lo sustituye.",
                task=t["id"])

    rows = []
    for r in reqs:
        rid = r["id"]
        if rid in obsolete:
            rows.append({
                "id": rid, "priority": r["priority"], "text": r["text"],
                "criteria": r["criteria"], "tasks": sorted(set(by_req_tasks.get(rid, []))),
                "tests": [], "empty_tests": [], "unscoped_tests": [], "issues": [],
            })
            continue
        r_tasks = sorted(set(by_req_tasks.get(rid, [])))
        found = scoped.get((fnum, rid), {})
        r_tests = sorted(ref for ref, kind in found.items() if kind != "empty")
        r_empty = sorted(ref for ref, kind in found.items() if kind == "empty")
        r_noassert = sorted(ref for ref, kind in found.items() if kind == "no-assert")
        r_unscoped = [] if found else bare.get(rid, [])
        must = r["priority"] == "MUST"
        issues = []

        if not r_tasks:
            code = "E-REQ-NO-TASK" if must else "W-REQ-NO-TASK"
            issues.append(code)
            add(code, f"{rid} ({r['priority']}) no tiene ninguna tarea asociada.",
                requirement=rid)
        if must and not r_tests:
            issues.append("E-REQ-NO-TEST")
            add("E-REQ-NO-TEST",
                f"{rid} no aparece en ninguna prueba. Nombra un test con el ID "
                f"de la feature (por ejemplo test_{scoped_ref(feature, rid)}_...) "
                f"o menciona {scoped_ref(feature, rid)} en un comentario.",
                requirement=rid)
        if r_empty:
            issues.append("W-TEST-EMPTY")
            add("W-TEST-EMPTY",
                f"{rid}: {', '.join(r_empty[:3])} no tiene cuerpo (solo pass, ... o "
                "comentarios). No cuenta como prueba: una prueba vacia satisface "
                "al comprobador y no verifica nada.", requirement=rid)
        if r_noassert:
            issues.append("W-TEST-NO-ASSERT")
            add("W-TEST-NO-ASSERT",
                f"{rid}: {', '.join(r_noassert[:3])} no contiene ninguna asercion "
                "reconocible. Cuenta como prueba, pero revisa que verifique algo.",
                requirement=rid)
        if r_unscoped:
            issues.append("W-TEST-UNSCOPED")
            add("W-TEST-UNSCOPED",
                f"{rid} aparece sin prefijo de feature en {', '.join(r_unscoped[:3])}. "
                f"No cuenta: {rid} existe en cada feature. Si la prueba es de esta, "
                f"renombrala a test_{scoped_ref(feature, rid)}_...",
                requirement=rid)
        if must and not r["criteria"]:
            issues.append("E-REQ-NO-CRITERIA")
            add("E-REQ-NO-CRITERIA",
                f"{rid} no tiene criterios de aceptacion en spec.md.",
                requirement=rid)

        body = norm(r["text"])
        if "debera" not in body and "shall" not in body and "debe " not in body:
            issues.append("W-REQ-NO-EARS")
            add("W-REQ-NO-EARS",
                f"{rid} no usa la forma EARS. Reescribelo con DEBERA.",
                requirement=rid)
        hits = sorted({w for w in VAGUE if re.search(rf"\b{w}\b", body)})
        if hits:
            issues.append("W-REQ-VAGUE")
            add("W-REQ-VAGUE",
                f"{rid} usa {', '.join(hits)} sin umbral. Sustituyelo por un numero.",
                requirement=rid)

        rows.append({
            "id": rid, "priority": r["priority"], "text": r["text"],
            "criteria": r["criteria"], "tasks": r_tasks, "tests": r_tests,
            "empty_tests": r_empty, "unscoped_tests": r_unscoped, "issues": issues,
        })

    tests_by_req = {r["id"]: r["tests"] for r in rows}
    for t in tasks:
        if t["state"] != "done":
            continue
        # Un requisito obsoleto ya no se puede probar: citarlo en una tarea
        # cerrada es historia, no una tarea sin prueba.
        sin_test = [rid for rid in t["requirements"]
                    if rid not in obsolete and not tests_by_req.get(rid)]
        if sin_test:
            add("E-DONE-NO-TEST",
                f"La tarea {t['id']} esta cerrada pero "
                f"{', '.join(sin_test)} "
                + ("no tiene" if len(sin_test) == 1 else "no tienen")
                + " prueba.", task=t["id"])
        abiertas = [d for d in t["depends_on"]
                    if d in task_ids and next(x for x in tasks if x["id"] == d)["state"] != "done"]
        if abiertas:
            add("W-DONE-OPEN-DEPS",
                f"La tarea {t['id']} esta cerrada pero depende de {', '.join(abiertas)}, "
                "sin cerrar.", task=t["id"])

    must_ids = {r["id"] for r in reqs if r["priority"] == "MUST"}
    loose = 0
    for q in spec["questions"]:
        blocking = [rid for rid in q["requirements"] if rid in must_ids]
        if blocking:
            add("E-SPEC-OPEN-MUST-QUESTION",
                f"Pregunta abierta sobre {', '.join(blocking)}: {q['text'][:100]}. "
                "Ciérrala con /sdd:clarify antes de planificar sobre ella.",
                requirement=blocking[0])
        else:
            loose += 1
    if loose:
        add("W-SPEC-OPEN-QUESTIONS",
            f"Quedan {loose} pregunta(s) abierta(s) en spec.md que no citan ningun "
            "requisito MUST. Si afectan a uno, citalo: - [ ] (R002) ...")
    if reqs and not any(
        re.search(r"\bsi\b.*\bentonces\b", norm(r["text"])) or
        re.search(r"\bif\b.*\bthen\b", norm(r["text"])) for r in reqs
    ):
        add("W-SPEC-NO-UNWANTED",
            "Ningun requisito describe comportamiento no deseado (SI... ENTONCES). "
            "Es el patron que mas bugs previene y el que mas se olvida.")

    musts = [r for r in rows if r["priority"] == "MUST"]
    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warning"]

    return {
        "schema": "sdd.trace/v1",
        "feature": feature.name,
        "ok": not errors,
        "status": {"spec": spec["status"], "plan": plan["status"],
                   "tasks": tasks_doc["status"]},
        "counts": {
            "requirements": len(rows), "tasks": len(tasks),
            "errors": len(errors), "warnings": len(warnings),
        },
        "coverage": {
            "must_total": len(musts),
            "must_with_task": sum(1 for r in musts if r["tasks"]),
            "must_with_test": sum(1 for r in musts if r["tests"]),
            "must_with_criteria": sum(1 for r in musts if r["criteria"]),
            "tasks_done": sum(1 for t in tasks if t["state"] == "done"),
        },
        "requirements": rows,
        "tasks": tasks,
        "findings": findings,
    }


# --------------------------------------------------------------------------
# Reporte legible
# --------------------------------------------------------------------------

def report(data):
    out = []
    c, cov = data["counts"], data["coverage"]
    out.append(f"Trazabilidad de {data['feature']}")
    out.append("")

    if not data["requirements"]:
        out.append("  No se encontraron requisitos en spec.md.")
        out.append("  Comprueba que la tabla de requisitos usa el formato "
                   "| R001 | MUST | ... |")
        return "\n".join(out)

    out.append(f"  {'REQ':<6} {'PRIO':<7} {'CRIT':>4} {'TAREAS':<16} PRUEBAS")
    out.append("  " + "-" * 62)
    for r in data["requirements"]:
        mark = "!" if any(i.startswith("E-") for i in r["issues"]) else " "
        tasks = ",".join(r["tasks"]) or "-"
        tests = str(len(r["tests"])) if r["tests"] else "NINGUNA"
        out.append(f" {mark}{r['id']:<6} {r['priority']:<7} {r['criteria']:>4} "
                   f"{tasks:<16} {tests}")
    out.append("")
    out.append(f"  MUST cubiertos: tarea {cov['must_with_task']}/{cov['must_total']} · "
               f"prueba {cov['must_with_test']}/{cov['must_total']} · "
               f"criterios {cov['must_with_criteria']}/{cov['must_total']}")
    out.append(f"  Tareas cerradas: {cov['tasks_done']}/{c['tasks']}")

    for sev, label in (("error", "ERRORES"), ("warning", "AVISOS")):
        items = [f for f in data["findings"] if f["severity"] == sev]
        if not items:
            continue
        out.append("")
        out.append(f"  {label} ({len(items)})")
        for f in items:
            out.append(f"    [{f['code']}] {f['message']}")

    out.append("")
    out.append("  OK: sin errores." if data["ok"]
               else f"  FALLA: {c['errors']} error(es). En CI esto tumba el PR.")
    return "\n".join(out)


def run(args, root, feature, config):
    as_json = "--json" in args
    check = "--check" in args
    data = analyze(root, feature, config)

    if as_json:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(report(data))

    return 1 if (check and not data["ok"]) else 0
