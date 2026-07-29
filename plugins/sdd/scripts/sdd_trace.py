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
    "W-REQ-NO-TASK":       "Requisito SHOULD/COULD sin tarea",
    "W-REQ-NO-EARS":       "Requisito que no usa la forma EARS (falta DEBERA)",
    "W-REQ-VAGUE":         "Requisito con adjetivo sin umbral verificable",
    "W-TASK-NO-REQ":       "Tarea que no referencia ningun requisito",
    "W-DONE-OPEN-DEPS":    "Tarea cerrada con dependencias sin cerrar",
    "W-SPEC-OPEN-QUESTIONS": "La spec tiene preguntas abiertas sin resolver",
    "W-SPEC-NO-UNWANTED":  "La spec no tiene requisitos de comportamiento no deseado",
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


# --------------------------------------------------------------------------
# Parseo de spec.md
# --------------------------------------------------------------------------

def parse_spec(path):
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    reqs, order, duplicates = {}, [], []

    row = re.compile(
        r"^\|\s*(R\d{2,})\s*\|\s*(MUST|SHOULD|COULD|DEBE|DEBERIA|PODRIA)\s*\|\s*(.+?)\s*\|\s*$",
        re.I | re.M,
    )
    for rid, prio, body in row.findall(text):
        rid = rid.upper()
        prio = {"DEBE": "MUST", "DEBERIA": "SHOULD", "PODRIA": "COULD"}.get(
            prio.upper(), prio.upper()
        )
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

    # Preguntas abiertas sin marcar.
    questions = len(re.findall(
        r"^\s*[-*]\s*\[ \]", section(text, "preguntas abiertas", "open questions"), re.M
    ))

    return {
        "path": path.name,
        "exists": path.is_file(),
        "requirements": [dict(reqs[r], criteria=criteria.get(r, 0)) for r in order],
        "duplicates": duplicates,
        "open_questions": questions,
    }


# --------------------------------------------------------------------------
# Parseo de tasks.md
# --------------------------------------------------------------------------

FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$", re.M)


def parse_tasks(path):
    if not path.is_file():
        return {"path": path.name, "exists": False, "tasks": []}
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
    return {"path": path.name, "exists": True, "tasks": tasks}


# --------------------------------------------------------------------------
# Barrido de pruebas
# --------------------------------------------------------------------------

def is_test_file(path):
    from fnmatch import fnmatch
    if any(fnmatch(path.name, g) for g in TEST_GLOBS):
        return True
    return any(norm(part) in TEST_DIRS for part in path.parts[:-1])


def scan_tests(root, extra_globs=None):
    """Devuelve {req_id: [ "ruta::nombre", ... ]}."""
    from fnmatch import fnmatch
    evidence = {}
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
            for i, line in enumerate(lines):
                for num in REQ_ID.findall(line):
                    rid = "R" + num
                    label = None
                    for j in range(i, max(-1, i - 25), -1):
                        d = TEST_DECL.search(lines[j])
                        if d:
                            label = next(g for g in d.groups() if g)
                            break
                    ref = f"{rel.as_posix()}::{label}" if label else rel.as_posix()
                    evidence.setdefault(rid, set()).add(ref)
    return {k: sorted(v) for k, v in evidence.items()}


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
    tasks_doc = parse_tasks(feature / "tasks.md")
    evidence = scan_tests(root, (config.get("tests") or {}).get("globs"))

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

    for cycle in find_cycles(tasks):
        add("E-TASK-DEP-CYCLE",
            "Ciclo de dependencias: " + " -> ".join(cycle))

    rows = []
    for r in reqs:
        rid = r["id"]
        r_tasks = sorted(set(by_req_tasks.get(rid, [])))
        r_tests = evidence.get(rid, [])
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
                f"(por ejemplo test_{rid}_...) o menciona {rid} en un comentario.",
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
            "issues": issues,
        })

    tests_by_req = {r["id"]: r["tests"] for r in rows}
    for t in tasks:
        if t["state"] != "done":
            continue
        sin_test = [rid for rid in t["requirements"] if not tests_by_req.get(rid)]
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

    if spec["open_questions"]:
        add("W-SPEC-OPEN-QUESTIONS",
            f"Quedan {spec['open_questions']} preguntas abiertas en spec.md.")
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
