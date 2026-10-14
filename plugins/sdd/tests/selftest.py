#!/usr/bin/env python3
"""
Regresion del plugin sdd. Sin dependencias externas: solo stdlib.

Cubre la compuerta (existencia, readiness y aprobacion), sus escapes, los
modos de fallo, y que todos los codigos de hallazgo de la trazabilidad sean
alcanzables. Corre en CI y en local:

    python3 plugins/sdd/tests/selftest.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SDD = PLUGIN / "scripts" / "sdd.py"

fallos = []


def check(ok, nombre, detalle=""):
    print(f"  {'ok  ' if ok else 'FALLA'} {nombre}" + (f" :: {detalle}" if detalle and not ok else ""))
    if not ok:
        fallos.append(nombre)


def run(sub, args=(), stdin=None, cwd=None, env_extra=None):
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN), CLAUDE_PROJECT_DIR=str(cwd))
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(SDD), sub, *args],
        input=stdin, capture_output=True, text=True, cwd=str(cwd), env=env, timeout=60,
    )


def payload(path, cwd, tool="Write"):
    return json.dumps({"tool_name": tool, "cwd": str(cwd),
                       "tool_input": {"file_path": path}})


def bloquea(cwd, path="src/app.py", **kw):
    r = run("guard", stdin=payload(path, cwd), cwd=cwd, **kw)
    assert r.returncode == 0, f"guard debe salir 0 siempre, salio {r.returncode}"
    return bool(r.stdout.strip())


def razon(cwd, path="src/app.py"):
    out = run("guard", stdin=payload(path, cwd), cwd=cwd).stdout
    return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out.strip() else ""


def edita(cwd, path, old, new):
    """True si el guard deniega un Edit de old -> new sobre path."""
    stdin = json.dumps({"tool_name": "Edit", "cwd": str(cwd), "tool_input": {
        "file_path": str(path), "old_string": old, "new_string": new}})
    return bool(run("guard", stdin=stdin, cwd=cwd).stdout.strip())


SPEC_LISTA = """# Spec: x

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Requisitos

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO X, el sistema DEBERA Y. |
| R002 | MUST | SI Z, ENTONCES el sistema DEBERA W. |

## Criterios de aceptacion

### R001

- **Dado** a **cuando** b **entonces** c

### R002

- **Dado** d **cuando** e **entonces** f
"""

PLAN_LISTO = """# Plan: x

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Componentes afectados

| Componente | Cambio | Requisitos |
| ---------- | ------ | ---------- |
| src/app.py | nuevo  | R001, R002 |
"""

TASKS_LISTAS = """# Tasks: x

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

### T001 — a

- **Estado:** `[ ]`
- **Requisitos:** R001, R002
- **Depende de:** —
- **Hecho cuando:** pasan los tests
"""


# ---------------------------------------------------------------- compuerta

def test_compuerta(base):
    print("\nCompuerta")
    p = base / "gate"
    p.mkdir()
    check(not bloquea(p), "repo sin specs/: el plugin no opina")

    (p / "specs").mkdir()
    check(bloquea(p), "specs/ sin feature activa: bloquea")
    check(not bloquea(p, "specs/notas.md"), "rutas exentas pasan")
    check(not bloquea(p, "README.md"), "*.md en raiz pasa")

    run("new", ["autenticacion con OAuth de Google"], cwd=p)
    feat = next((p / "specs").iterdir())
    check(feat.name == "001-autenticacion-oauth-google", "slug sin palabras vacias", feat.name)
    check((feat / "spec.md").is_file(), "spec.md creado desde plantilla")

    print("\nReadiness: existir no basta")
    check("no esta listo" in razon(p), "spec.md recien creado desde plantilla: bloquea")
    r = run("approve", cwd=p)
    check(r.returncode == 1 and "hueco" in r.stderr, "approve rechaza una plantilla")
    (feat / "spec.md").write_text(SPEC_LISTA.replace(
        "SI Z, ENTONCES el sistema DEBERA W.", "_SI Z, ENTONCES el sistema DEBERA ..._"))
    check("hueco" in razon(p), "detecta '...' en cursiva aunque la linea no sea de la plantilla")
    (feat / "spec.md").write_text(SPEC_LISTA.replace("### R002\n\n- **Dado** d", "### R002\n\nnada"))
    check("sin criterios" in razon(p), "MUST sin criterios: incompleto")
    (feat / "spec.md").write_text(SPEC_LISTA + "\n## Preguntas abiertas\n\n- [ ] (R002) Cuanto?\n")
    check("preguntas abiertas sobre requisitos MUST: R002" in razon(p),
          "pregunta abierta sobre un MUST: incompleto")
    (feat / "spec.md").write_text(SPEC_LISTA + "\n## Preguntas abiertas\n\n- [ ] Algo general\n"
                                  "- [x] (R002) Ya resuelta\n")
    check("no aprobado" in razon(p), "pregunta sin MUST o ya marcada: no bloquea")
    (feat / "spec.md").write_text(SPEC_LISTA)
    check("no aprobado" in razon(p), "spec completa sin aprobar: bloquea")

    print("\nAprobacion")
    spec_path = feat / "spec.md"
    check(edita(p, spec_path, "| Estado | Draft |", "| Estado | Approved |"),
          "el modelo no puede autoaprobar con Edit")
    check(edita(p, f"specs/{feat.name}/spec.md", "| Estado | Draft |", "| Estado | Aprobado |"),
          "tampoco en espanol ni con ruta relativa")
    check(not edita(p, spec_path, "CUANDO X", "CUANDO X2"),
          "editar otra parte de la spec no se bloquea")
    check(run("approve", ["plan"], cwd=p).returncode == 1, "approve respeta el orden")
    r = run("approve", ["plan", "--skill"], cwd=p)
    check(r.returncode == 0 and "antes hay que aprobar spec" in r.stdout,
          "approve --skill: siempre exit 0 y todo por stdout")
    check(run("approve", cwd=p).returncode == 0, "approve sin argumento aprueba spec")
    check("Approved" in spec_path.read_text(), "approve escribe Estado: Approved")
    check("todavia no tiene plan.md" in razon(p), "spec aprobada, sin plan.md: bloquea")

    (feat / "plan.md").touch()
    check("no esta listo" in razon(p), "plan.md vacio: incompleto")
    (feat / "plan.md").write_text(PLAN_LISTO.replace("R001, R002", "R001"))
    check("R002" in razon(p), "plan que no menciona un MUST: incompleto")
    (feat / "plan.md").write_text(PLAN_LISTO)
    check(run("approve", ["plan"], cwd=p).returncode == 0, "approve plan")
    check(bloquea(p), "con plan aprobado pero sin tasks.md: bloquea")
    (feat / "tasks.md").write_text(TASKS_LISTAS.replace("R001, R002", "R001"))
    check("sin tarea" in razon(p), "MUST sin tarea: incompleto")
    (feat / "tasks.md").write_text(TASKS_LISTAS)
    check("no aprobado" in razon(p), "tasks sin aprobar: bloquea")
    check(run("approve", ["tasks"], cwd=p).returncode == 0, "approve tasks")
    check(not bloquea(p), "con los tres artefactos listos y aprobados: permite")
    check(not edita(p, feat / "tasks.md", "`[ ]`", "`[x]`"),
          "marcar tareas en tasks.md aprobado no se bloquea")

    sdd_dir = p / ".sdd"
    (sdd_dir / "config.json").write_text('{"approval": false}')
    (feat / "tasks.md").write_text(TASKS_LISTAS)
    check(not bloquea(p), 'approval:false no exige aprobacion')
    check(not edita(p, feat / "tasks.md", "| Estado | Draft |", "| Estado | Approved |"),
          "approval:false no protege el campo Estado")
    (sdd_dir / "config.json").unlink()

    (feat / "tasks.md").unlink()
    check(not bloquea(p, env_extra={"SDD_BYPASS": "1"}), "SDD_BYPASS=1 desactiva")
    (sdd_dir / "config.json").write_text('{"gate":"off"}')
    check(not bloquea(p), 'gate:"off" desactiva')
    (sdd_dir / "config.json").write_text('{"gate":"spec"}')
    check(not bloquea(p), 'gate:"spec" permite si spec.md esta lista y aprobada')

    print("\nModos de fallo: nada debe bloquear al usuario")
    (sdd_dir / "config.json").write_text("no soy json {{{")
    check(bloquea(p), "config corrupta cae al defecto en vez de reventar")
    (sdd_dir / "config.json").unlink()
    r = run("guard", stdin="no soy json", cwd=p)
    check(r.returncode == 0 and not r.stdout.strip(), "stdin no-JSON permite")
    r = run("guard", stdin=json.dumps({"tool_name": "Write", "cwd": str(p),
                                       "tool_input": {}}), cwd=p)
    check(r.returncode == 0 and not r.stdout.strip(), "sin file_path permite")
    check(not bloquea(p, "/etc/hosts"), "ruta fuera del proyecto permite")
    check(bloquea(p, str(p / "src/app.py")), "ruta absoluta interna bloquea")

    print("\nForma de la denegacion")
    d = json.loads(run("guard", stdin=payload("src/app.py", p), cwd=p).stdout)
    hso = d.get("hookSpecificOutput", {})
    check(hso.get("hookEventName") == "PreToolUse", "hookEventName correcto")
    check(hso.get("permissionDecision") == "deny", "permissionDecision=deny")
    check(bool(hso.get("permissionDecisionReason")), "lleva razon para el modelo")
    check("allow" not in json.dumps(d), "nunca devuelve allow: no escala privilegios")


# ------------------------------------------------------------ trazabilidad

FIXTURES = {
    "E-REQ-DUPLICATE": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                        "| R001 | MUST | CUANDO X el sistema DEBERA Y. |\n"
                        "| R001 | MUST | Otro texto. |\n", None),
    "W-REQ-NO-EARS": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                      "| R001 | MUST | El login guarda la sesion. |\n", None),
    "W-SPEC-NO-UNWANTED": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                           "| R001 | MUST | El sistema DEBERA guardar la sesion. |\n", None),
    "W-REQ-VAGUE": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                    "| R001 | MUST | El sistema DEBERA ser rapido e intuitivo. |\n", None),
    "W-SPEC-OPEN-QUESTIONS": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                              "| R001 | MUST | CUANDO X el sistema DEBERA Y. |\n"
                              "\n## Preguntas abiertas\n\n- [ ] Sin resolver.\n", None),
    "E-SPEC-OPEN-MUST-QUESTION": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                                  "| R001 | MUST | CUANDO X el sistema DEBERA Y. |\n"
                                  "\n## Preguntas abiertas\n\n- [ ] (R001) Cuanto?\n", None),
    "E-TASK-DEP-CYCLE": (None,
                         "### T001 — a\n- **Estado:** `[ ]`\n- **Requisitos:** R001\n"
                         "- **Depende de:** T002\n"
                         "### T002 — b\n- **Estado:** `[ ]`\n- **Requisitos:** R001\n"
                         "- **Depende de:** T001\n"),
    "E-TASK-UNKNOWN-REQ": (None, "### T001 — a\n- **Estado:** `[ ]`\n"
                                 "- **Requisitos:** R099\n- **Depende de:** —\n"),
    "E-TASK-UNKNOWN-DEP": (None, "### T001 — a\n- **Estado:** `[ ]`\n"
                                 "- **Requisitos:** R001\n- **Depende de:** T099\n"),
    "W-TASK-NO-REQ": (None, "### T001 — a\n- **Estado:** `[ ]`\n"
                            "- **Requisitos:**\n- **Depende de:** —\n"),
    "W-DONE-OPEN-DEPS": (None, "### T001 — a\n- **Estado:** `[ ]`\n"
                               "- **Requisitos:** R001\n- **Depende de:** —\n"
                               "### T002 — b\n- **Estado:** `[x]`\n"
                               "- **Requisitos:** R001\n- **Depende de:** T001\n"),
    "E-DONE-NO-TEST": (None, "### T001 — a\n- **Estado:** `[x]`\n"
                             "- **Requisitos:** R001\n- **Depende de:** —\n"),
    "E-SPEC-TEMPLATE": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                        "| R001 | MUST | _CUANDO ..., el sistema DEBERÁ ..._ |\n", None),
    "E-TASK-TEMPLATE": (None, "### T001 — _\\<título\\>_\n- **Estado:** `[ ]`\n"
                              "- **Requisitos:** R001\n- **Hecho cuando:** _..._\n"),
}

SPEC_BASE = ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
             "| R001 | MUST | CUANDO X, el sistema DEBERA Y. |\n"
             "| R002 | SHOULD | SI Z, ENTONCES el sistema DEBERA W. |\n"
             "\n## Criterios de aceptacion\n### R001\n- **Dado** a **cuando** b **entonces** c\n")


def codigos(cwd):
    r = run("trace", ["--json"], cwd=cwd)
    if r.returncode != 0 and not r.stdout:
        return set()
    return {f["code"] for f in json.loads(r.stdout)["findings"]}


def test_trazabilidad(base):
    print("\nTrazabilidad: cada codigo de hallazgo es alcanzable")
    for code, (spec, tasks) in FIXTURES.items():
        p = base / f"tr-{code.lower()}"
        (p / "specs" / "001-x").mkdir(parents=True)
        (p / ".sdd").mkdir()
        (p / ".sdd" / "current").write_text("001-x\n")
        (p / "specs" / "001-x" / "spec.md").write_text(spec or SPEC_BASE, encoding="utf-8")
        if tasks:
            (p / "specs" / "001-x" / "tasks.md").write_text(tasks, encoding="utf-8")
        check(code in codigos(p), code)

    # Los tres que dependen de ausencia total de cobertura
    p = base / "tr-desnudo"
    (p / "specs" / "001-x").mkdir(parents=True)
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("001-x\n")
    (p / "specs" / "001-x" / "spec.md").write_text(
        "| ID | Prioridad | Requisito |\n| - | - | - |\n"
        "| R001 | MUST | El sistema DEBERA hacer algo. |\n", encoding="utf-8")
    got = codigos(p)
    for code in ("E-REQ-NO-TASK", "E-REQ-NO-TEST", "E-REQ-NO-CRITERIA"):
        check(code in got, code)
    p2 = base / "tr-should"
    (p2 / "specs" / "001-x").mkdir(parents=True)
    (p2 / ".sdd").mkdir()
    (p2 / ".sdd" / "current").write_text("001-x\n")
    (p2 / "specs" / "001-x" / "spec.md").write_text(SPEC_BASE, encoding="utf-8")
    check("W-REQ-NO-TASK" in codigos(p2), "W-REQ-NO-TASK")

    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_trace
    declarados = set(sdd_trace.FINDINGS)
    probados = set(FIXTURES) | {"E-REQ-NO-TASK", "E-REQ-NO-TEST",
                                "E-REQ-NO-CRITERIA", "W-REQ-NO-TASK",
                                "W-TEST-UNSCOPED"}
    check(declarados == probados,
          f"los {len(declarados)} codigos declarados estan cubiertos",
          f"sin probar: {sorted(declarados - probados)}")


def test_deteccion_pruebas(base):
    print("\nDeteccion de evidencia de prueba")
    p = base / "tests-ok"
    (p / "specs" / "001-x").mkdir(parents=True)
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("001-x\n")
    (p / "specs" / "001-x" / "spec.md").write_text(SPEC_BASE, encoding="utf-8")
    (p / "specs" / "001-x" / "tasks.md").write_text(
        "### T001 — a\n- **Estado:** `[ ]`\n- **Requisitos:** R001\n"
        "- **Depende de:** —\n", encoding="utf-8")
    (p / "tests").mkdir()
    # El guion bajo es caracter de palabra: \bR001\b NO casa aqui. Regresion.
    (p / "tests" / "test_a.py").write_text(
        "def test_F001_R001_algo():\n    pass\n", encoding="utf-8")
    (p / "node_modules" / "x" / "tests").mkdir(parents=True)
    (p / "node_modules" / "x" / "tests" / "test_b.py").write_text(
        "def test_F001_R001_falso():\n    pass\n", encoding="utf-8")

    d = json.loads(run("trace", ["--json"], cwd=p).stdout)
    r001 = next(r for r in d["requirements"] if r["id"] == "R001")
    check(len(r001["tests"]) == 1, "encuentra el ID dentro de test_F001_R001_algo")
    check(not any("node_modules" in t for t in r001["tests"]),
          "ignora node_modules")
    check("E-REQ-NO-TEST" not in {f["code"] for f in d["findings"]},
          "no reporta falta de prueba cuando la hay")

    print("\nIDs con alcance de feature")
    (p / "tests" / "test_c.py").write_text(
        "def test_otro():\n    # F001-R002 en comentario\n    pass\n", encoding="utf-8")
    d = json.loads(run("trace", ["--json"], cwd=p).stdout)
    r002 = next(r for r in d["requirements"] if r["id"] == "R002")
    check(r002["tests"] == ["tests/test_c.py::test_otro"], "F001-R002 en comentario cuenta")

    (p / "specs" / "002-y").mkdir()
    (p / "specs" / "002-y" / "spec.md").write_text(SPEC_BASE, encoding="utf-8")
    (p / ".sdd" / "current").write_text("002-y\n")
    d = json.loads(run("trace", ["--json"], cwd=p).stdout)
    r001 = next(r for r in d["requirements"] if r["id"] == "R001")
    check(r001["tests"] == [], "la prueba de F001_R001 no cubre el R001 de la feature 002")
    check("E-REQ-NO-TEST" in {f["code"] for f in d["findings"]},
          "feature 002 sigue sin prueba para su R001")

    (p / "tests" / "test_d.py").write_text(
        "def test_R001_sin_prefijo():\n    pass\n", encoding="utf-8")
    d = json.loads(run("trace", ["--json"], cwd=p).stdout)
    codes = {f["code"] for f in d["findings"]}
    check("W-TEST-UNSCOPED" in codes and "E-REQ-NO-TEST" in codes,
          "R001 sin prefijo no cuenta y avisa con W-TEST-UNSCOPED")


def test_contrato_ci(base):
    print("\nContrato con CI")
    p = base / "ci"
    (p / "specs" / "001-x").mkdir(parents=True)
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("001-x\n")
    (p / "specs" / "001-x" / "spec.md").write_text(
        "| ID | Prioridad | Requisito |\n| - | - | - |\n"
        "| R001 | MUST | El sistema DEBERA hacer algo. |\n", encoding="utf-8")

    check(run("trace", cwd=p).returncode == 0, "trace es informativo: exit 0")
    check(run("trace", ["--check"], cwd=p).returncode == 1,
          "trace --check tumba el PR: exit 1")
    d = json.loads(run("trace", ["--json"], cwd=p).stdout)
    check(d["schema"] == "sdd.trace/v1", "schema versionado")
    check(set(d) >= {"schema", "feature", "ok", "counts", "coverage",
                     "requirements", "tasks", "findings"}, "claves del contrato")
    check(all({"code", "severity", "title", "message"} <= set(f)
              for f in d["findings"]), "cada hallazgo lleva code/severity/title/message")
    check(d["ok"] is False, "ok refleja la presencia de errores")


def test_degenerados(base):
    print("\nEntradas degeneradas: nada revienta")
    p = base / "deg"
    (p / "specs" / "001-x").mkdir(parents=True)
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("001-x\n")
    spec = p / "specs" / "001-x" / "spec.md"
    casos = [
        ("spec vacia", b""),
        ("spec sin tabla", b"hola mundo\n"),
        ("tabla malformada", b"| R001 | MUST\n| roto |\n"),
        ("spec binaria", bytes(range(256)) * 4),
    ]
    for nombre, contenido in casos:
        spec.write_bytes(contenido)
        check(run("trace", cwd=p).returncode == 0, nombre)
    spec.unlink()
    check(run("trace", cwd=p).returncode == 0, "spec ausente")
    for sub in ("status", "context"):
        check(run(sub, cwd=p).returncode == 0, f"{sub} sobrevive")


# ------------------------------------------------------------- bash

PARSER = [
    ("echo hi > src/a.py", ["src/a.py"]),
    ("echo hi >src/a.py 2>&1", ["src/a.py"]),
    ("echo hi >> src/a.py && ls", ["src/a.py"]),
    ("cat > src/a.py <<EOF\nprint('x > y')\nEOF", ["src/a.py"]),
    ("cat <<'EOF' | tee -a src/b.py\nhola\nEOF", ["src/b.py"]),
    ("sed -i '' 's/a/b/' src/c.py", ["src/c.py"]),
    ("sed -i.bak -e s/a/b/ src/c.py src/d.py", ["src/c.py", "src/d.py"]),
    ("sed -n 1,5p src/c.py", []),
    ("perl -pi -e 's/a/b/' src/e.py", ["src/e.py"]),
    ("cp tmp/x.py src/f.py", ["src/f.py"]),
    ("rm -rf build src/h.py", ["build", "src/h.py"]),
    ("FOO=1 sudo touch src/i.py", ["src/i.py"]),
    ("dd if=/dev/zero of=src/j.bin bs=1", ["src/j.bin"]),
    ("ls > /dev/null 2>&1", []),
    ("echo $X > \"$OUT\"", []),
    ("git status; grep -r foo src | head", []),
    ("echo \"sin cerrar", []),
]


def bash_payload(cmd, cwd, tool_use_id="t1", sub_cwd=None):
    return json.dumps({"tool_name": "Bash", "tool_use_id": tool_use_id,
                       "session_id": "s", "cwd": str(sub_cwd or cwd),
                       "tool_input": {"command": cmd}})


def bash_bloquea(cwd, cmd, tool_use_id="t1", sub_cwd=None):
    r = run("guard", stdin=bash_payload(cmd, cwd, tool_use_id, sub_cwd), cwd=cwd)
    assert r.returncode == 0, f"guard debe salir 0 siempre, salio {r.returncode}"
    return bool(r.stdout.strip())


def audita(cwd, tool_use_id="t1"):
    return run("audit", stdin=bash_payload("", cwd, tool_use_id), cwd=cwd)


def test_bash(base):
    print("\nCompuerta sobre Bash: analizador")
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_bash
    for cmd, esperado in PARSER:
        got = sdd_bash.write_targets(cmd)
        check(got == esperado, f"destinos de {cmd.splitlines()[0][:40]!r}", f"{got}")
    check(sdd_bash.invokes_approve("python3 x/sdd.py approve plan"), "detecta sdd.py approve")

    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    check(any("Bash" in h["matcher"].split("|") for h in hooks["PreToolUse"]),
          "hooks.json: guard cubre Bash")
    check(any(h["matcher"] == "Bash" for h in hooks["PostToolUse"]),
          "hooks.json: audit sobre Bash")

    print("\nCompuerta sobre Bash: prevencion")
    p = base / "bash"
    (p / "src").mkdir(parents=True)
    run("new", ["login"], cwd=p)
    feat = next((p / "specs").iterdir())
    check(bash_bloquea(p, "echo y > src/a.py"), "redireccion a codigo con compuerta cerrada")
    check(bash_bloquea(p, "sed -i 's/a/b/' src/a.py"), "sed -i con compuerta cerrada")
    check(bash_bloquea(p, "echo 1 > c.py", sub_cwd=p / "src"),
          "ruta relativa al cwd del comando")
    check(not bash_bloquea(p, "ls src && git status"), "comando de lectura pasa")
    check(not bash_bloquea(p, "echo nota > specs/notas.md"), "destino exento pasa")
    check(not bash_bloquea(p, "echo y > /tmp/fuera.txt"), "fuera del proyecto pasa")
    check(bash_bloquea(p, "python3 /x/scripts/sdd.py approve"),
          "el modelo no puede lanzar sdd.py approve")
    check(bash_bloquea(p, f"sed -i 's/Draft/Approved/' specs/{feat.name}/spec.md"),
          "sed que aprueba un artefacto: bloquea")
    check(not bash_bloquea(p, f"sed -i 's/X/Y/' specs/{feat.name}/spec.md"),
          "sed que edita la spec sin aprobar: pasa")
    r = run("guard", stdin=bash_payload("echo y > src/a.py", p), cwd=p,
            env_extra={"SDD_BYPASS": "1"})
    check(not r.stdout.strip(), "SDD_BYPASS=1 tambien desactiva la compuerta sobre Bash")

    print("\nCompuerta sobre Bash: auditoria")
    if shutil.which("git") is None:
        print("  (sin git: auditoria omitida)")
        return
    git = ["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q"], check=True)
    (p / "src" / "a.py").write_text("x\n")
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-qm", "init"], check=True)

    check(audita(p, "nada").returncode == 0, "sin instantanea: no opina")
    r = run("audit", stdin="no soy json", cwd=p)
    check(r.returncode == 0, "stdin no-JSON: no revienta")

    bash_bloquea(p, "python3 script.py", "t2")
    (p / "src" / "b.py").write_text("1\n")
    r = audita(p, "t2")
    check(r.returncode == 2 and "src/b.py" in r.stderr,
          "detecta un archivo de codigo escrito por un comando opaco")

    bash_bloquea(p, "python3 otro.py", "t3")
    r = audita(p, "t3")
    check(r.returncode == 0, "si el comando no cambia nada, silencio")

    bash_bloquea(p, "python3 otro.py", "t4")
    (p / "specs" / "nota.md").write_text("x\n")
    check(audita(p, "t4").returncode == 0, "cambios en rutas exentas no se reportan")

    spec = feat / "spec.md"
    bash_bloquea(p, "python3 ofuscado.py", "t5")
    spec.write_text(spec.read_text().replace("| Estado | Draft ", "| Estado | Approved ", 1))
    r = audita(p, "t5")
    check(r.returncode == 2 and "devuelto" in r.stderr, "detecta la autoaprobacion")
    check("| Estado | Draft" in spec.read_text(), "y revierte el Estado a Draft")

    # Con la compuerta abierta, la auditoria de codigo no aplica.
    (p / ".sdd" / "config.json").write_text('{"gate": "off"}')
    bash_bloquea(p, "python3 script.py", "t6")
    (p / "src" / "c.py").write_text("1\n")
    check(audita(p, "t6").returncode == 0, 'gate:"off": no audita')


def main():
    base = Path(tempfile.mkdtemp(prefix="sdd-selftest-"))
    try:
        test_compuerta(base)
        test_trazabilidad(base)
        test_deteccion_pruebas(base)
        test_contrato_ci(base)
        test_degenerados(base)
        test_bash(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    if fallos:
        print(f"FALLA: {len(fallos)} comprobacion(es)")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("OK: todas las comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
