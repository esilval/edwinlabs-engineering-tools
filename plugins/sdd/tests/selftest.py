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
import re
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
    (feat / "plan.md").write_text(PLAN_LISTO.replace("R001, R002", "R001, R002, R007"))
    check("R007" in razon(p), "plan que cita un requisito inexistente: incompleto")
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

    print("\nDeriva: cambios despues de aprobar")
    import re as _re
    check(bool(_re.search(r"\| Estado \| Approved · [0-9a-f]{12}", spec_path.read_text())),
          "approve guarda la huella del contenido")
    tasks_path = feat / "tasks.md"
    tasks_path.write_text(tasks_path.read_text().replace("`[ ]`", "`[x]`"))
    check(not bloquea(p), "cambiar el estado de una tarea no invalida tasks.md")
    spec_path.write_text(spec_path.read_text().replace("\n\n## Requisitos", "\n\n\n## Requisitos"))
    check(not bloquea(p), "reformatear espacios no invalida la spec")
    original = spec_path.read_text()
    spec_path.write_text(original.replace("CUANDO X, el sistema DEBERA Y.",
                                          "CUANDO X, el sistema DEBERA Z."))
    check("cambio despues" in razon(p), "editar una spec aprobada cierra la compuerta")
    check("[!] spec.md" in run("status", cwd=p).stdout, "status marca la spec con [!]")
    estado = _re.search(r"\| Estado \| (Approved · [0-9a-f]{12})", original).group(1)
    check(edita(p, spec_path, estado, "Approved · 000000000000"),
          "el modelo no puede reescribir la huella")
    r = run("approve", cwd=p)
    check(r.returncode == 0 and "Vuelven a borrador" in r.stdout,
          "reaprobar la spec devuelve plan y tasks a borrador")
    check("| Estado | Draft" in (feat / "plan.md").read_text()
          and "| Estado | Draft" in tasks_path.read_text(), "plan y tasks quedan en Draft")
    check(run("approve", cwd=p).returncode == 0 and run("approve", cwd=p).returncode == 0
          and not bloquea(p), "tras reaprobar plan y tasks, la compuerta se abre")

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
    "W-TASK-OBSOLETE-REQ": ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                            "| R001 | OBSOLETO | El sistema DEBERA X. |\n"
                            "| R002 | MUST | SI Z, ENTONCES el sistema DEBERA W. |\n",
                            "### T001 — a\n- **Estado:** `[ ]`\n- **Requisitos:** R001\n"
                            "- **Hecho cuando:** x\n"),
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
    print("\nTrazabilidad: consistencia del plan y las tareas")
    planes = {
        "E-PLAN-REQ-MISSING": "# Plan\n\nNada que ver.\n",
        "E-PLAN-UNKNOWN-REQ": "# Plan\n\nCubre R001 y R009.\n",
        "E-PLAN-TEMPLATE": "# Plan\n\nR001\n\n### D1 — _\\<título de la decisión\\>_\n",
        "W-PLAN-NO-CONSTITUTION-CHECK": "# Plan\n\nCubre R001.\n",
    }
    for code, plan in planes.items():
        p = base / f"tr-{code.lower()}"
        (p / "specs" / "001-x").mkdir(parents=True)
        (p / ".sdd").mkdir()
        (p / ".sdd" / "current").write_text("001-x\n")
        (p / "specs" / "001-x" / "spec.md").write_text(SPEC_BASE, encoding="utf-8")
        (p / "specs" / "001-x" / "plan.md").write_text(plan, encoding="utf-8")
        (p / "specs" / "constitution.md").write_text("# C\n", encoding="utf-8")
        check(code in codigos(p), code)
    p = base / "tr-plan-ok"
    (p / "specs" / "001-x").mkdir(parents=True)
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("001-x\n")
    (p / "specs" / "001-x" / "spec.md").write_text(SPEC_BASE, encoding="utf-8")
    (p / "specs" / "constitution.md").write_text("# C\n", encoding="utf-8")
    (p / "specs" / "001-x" / "plan.md").write_text(
        "# Plan\n\nCubre R001.\n\n## Comprobacion de constitucion\n\n| R | si |\n")
    got = codigos(p)
    check(not got & set(planes), "plan coherente: ningun hallazgo de plan", f"{got & set(planes)}")
    (p / "specs" / "001-x" / "tasks.md").write_text(
        "### T001 — a\n- **Estado:** `[ ]`\n- **Requisitos:** R001\n- **Depende de:** —\n")
    check("W-TASK-NO-DONE-WHEN" in codigos(p), "W-TASK-NO-DONE-WHEN")

    print("\nRequisitos obsoletos")
    p = base / "tr-obsoleto"
    (p / "specs" / "001-x").mkdir(parents=True)
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("001-x\n")
    (p / "specs" / "001-x" / "spec.md").write_text(
        "| ID | Prioridad | Requisito |\n| - | - | - |\n"
        "| R001 | MUST | SI Z, ENTONCES el sistema DEBERA W. |\n"
        "| R004 | OBSOLETO | El login rapido (reemplazado por R001). |\n"
        "\n## Criterios de aceptacion\n### R001\n- **Dado** a **cuando** b **entonces** c\n",
        encoding="utf-8")
    d = json.loads(run("trace", ["--json"], cwd=p).stdout)
    r004 = [f for f in d["findings"] if f.get("requirement") == "R004"]
    check(not r004, "un requisito obsoleto no exige tarea, prueba ni EARS", f"{r004}")
    check(run("next-req", cwd=p).stdout.strip() == "R005",
          "next-req cuenta los obsoletos: los IDs no se reciclan")

    p2 = base / "tr-should"
    (p2 / "specs" / "001-x").mkdir(parents=True)
    (p2 / ".sdd").mkdir()
    (p2 / ".sdd" / "current").write_text("001-x\n")
    (p2 / "specs" / "001-x" / "spec.md").write_text(SPEC_BASE, encoding="utf-8")
    check("W-REQ-NO-TASK" in codigos(p2), "W-REQ-NO-TASK")

    print("\nPlanes contra la arquitectura (feature 007)")
    arquitectura = codigos_plan_arquitectura(base)
    check(len(arquitectura) == 4, "los cuatro codigos de plan contra arquitectura se emiten",
          f"{sorted(arquitectura)}")

    print("\nDiagramas del plan (feature 009)")
    diagramas_plan = codigos_plan_diagramas(base)
    check(len(diagramas_plan) == 3, "los tres codigos de diagramas del plan se emiten",
          f"{sorted(diagramas_plan)}")

    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_trace
    declarados = set(sdd_trace.FINDINGS)
    probados = set(FIXTURES) | {"E-REQ-NO-TASK", "E-REQ-NO-TEST",
                                "E-REQ-NO-CRITERIA", "W-REQ-NO-TASK",
                                "W-TEST-UNSCOPED", "W-TASK-NO-DONE-WHEN",
                                "W-TEST-EMPTY", "W-TEST-NO-ASSERT"} | set(planes) \
        | arquitectura | diagramas_plan
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
        "def test_F001_R001_algo():\n    assert login() is True\n", encoding="utf-8")
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

    print("\nCuerpo de las pruebas")
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_trace
    cuerpos = [
        (".py", "def test_a():\n    pass\n", "empty"),
        (".py", "def test_a():\n    \"\"\"Doc.\"\"\"\n    # nada\n    ...\n", "empty"),
        (".py", "def test_a(x: int) -> None: pass\n", "empty"),
        (".py", "def test_a():\n    assert f() == 1\n", "ok"),
        (".py", "def test_a(self):\n    self.assertEqual(f(), 1)\n", "ok"),
        (".py", "def test_a():\n    with pytest.raises(E):\n        f()\n", "ok"),
        (".py", "def test_a():\n    f()\n\ndef otra():\n    assert 1\n", "no-assert"),
        (".ts", "it('R1', () => {\n  // pendiente\n});\n", "empty"),
        (".ts", "it('R1', async () => {\n  expect(await f()).toBe(1);\n});\n", "ok"),
        (".ts", "test('R1', () => { f(); });\n", "no-assert"),
        (".go", "func TestA(t *testing.T) {\n}\n", "empty"),
        (".go", "func TestA(t *testing.T) {\n  if f() != 1 { t.Errorf(\"x\") }\n}\n", "ok"),
        (".rb", "it 'x' do\nend\n", "ok"),
    ]
    for suf, src, esperado in cuerpos:
        got = sdd_trace.test_body_kind(src.splitlines(), 0, suf)
        check(got == esperado, f"cuerpo {suf} {src.splitlines()[0][:30]!r} -> {esperado}", got)

    (p / "tests" / "test_vacio.py").write_text(
        "def test_F001_R002_vacio():\n    pass\n", encoding="utf-8")
    d = json.loads(run("trace", ["--json"], cwd=p).stdout)
    r002 = next(r for r in d["requirements"] if r["id"] == "R002")
    check(r002["empty_tests"] == ["tests/test_vacio.py::test_F001_R002_vacio"]
          and "tests/test_vacio.py::test_F001_R002_vacio" not in r002["tests"],
          "una prueba vacia no cuenta como evidencia")
    check("W-TEST-EMPTY" in {f["code"] for f in d["findings"]}, "W-TEST-EMPTY")
    (p / "tests" / "test_vacio.py").write_text(
        "def test_F001_R001_sin_assert():\n    login()\n", encoding="utf-8")
    check("W-TEST-NO-ASSERT" in codigos(p), "W-TEST-NO-ASSERT")
    (p / "tests" / "test_vacio.py").unlink()

    print("\nIDs con alcance de feature")
    (p / "tests" / "test_c.py").write_text(
        "def test_otro():\n    # F001-R002 en comentario\n    assert 1\n", encoding="utf-8")
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
        "def test_R001_sin_prefijo():\n    assert 1\n", encoding="utf-8")
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

    spec.write_text(spec.read_text().replace("| Estado | Draft ", "| Estado | Approved · 111111111111 ", 1))
    bash_bloquea(p, "python3 ofuscado.py", "t7")
    spec.write_text(spec.read_text().replace("111111111111", "222222222222", 1))
    r = audita(p, "t7")
    check(r.returncode == 2 and "111111111111" in spec.read_text(),
          "revierte una huella de aprobacion reescrita")

    # Con la compuerta abierta, la auditoria de codigo no aplica.
    (p / ".sdd" / "config.json").write_text('{"gate": "off"}')
    bash_bloquea(p, "python3 script.py", "t6")
    (p / "src" / "c.py").write_text("1\n")
    check(audita(p, "t6").returncode == 0, 'gate:"off": no audita')


# ------------------------------------------- feature 002: arreglos de sdd

def expect(ok, nombre, detalle=""):
    """Como check; con este nombre la trazabilidad lo reconoce como asercion."""
    return check(ok, nombre, detalle)


def repo_con_feature(base, nombre, spec=SPEC_BASE, archivos=None):
    """Repo de prueba con la feature 001-x activa y los archivos dados."""
    p = base / nombre
    (p / "specs" / "001-x").mkdir(parents=True)
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("001-x\n")
    (p / "specs" / "001-x" / "spec.md").write_text(spec, encoding="utf-8")
    for rel, texto in (archivos or {}).items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(texto, encoding="utf-8")
    return p


def traza(cwd):
    return json.loads(run("trace", ["--json"], cwd=cwd).stdout)


def test_F002_R003_aviso_nombra_el_requisito(base):
    print("\nF002 · R003: el aviso sin prefijo nombra el requisito real")
    spec = SPEC_BASE.replace("| R002 | SHOULD |", "| R004 | MUST |")
    p = repo_con_feature(base, "f002-r003", spec=spec, archivos={
        "tests/test_x.py": "def test_R004_x():\n    assert True\n"})
    avisos = [f["message"] for f in traza(p)["findings"] if f["code"] == "W-TEST-UNSCOPED"]
    expect(len(avisos) == 1 and "No cuenta: R004 existe" in avisos[0]
           and "R001" not in avisos[0], "el aviso nombra R004, no R001", f"{avisos}")


def evidencia(cwd, rid):
    return next(r for r in traza(cwd)["requirements"] if r["id"] == rid)["tests"]


FIXTURE_PY = '''import sdd

FIXTURE = "def test_F001_R001_algo():\\n    assert x\\n"
MULTILINEA = """
def test_F001_R002_falso():
    assert y
"""


def test_que_usa_los_fixtures():
    assert FIXTURE and MULTILINEA
'''


def test_F002_R010_fixture_en_cadena_no_cuenta(base):
    print("\nF002 · R010: en Python, un fixture en una cadena no es una prueba")
    p = repo_con_feature(base, "f002-r001-fixture", archivos={"tests/test_f.py": FIXTURE_PY})
    expect(evidencia(p, "R001") == [], "una cadena de una linea no cuenta",
           f"{evidencia(p, 'R001')}")
    expect(evidencia(p, "R002") == [], "una cadena de varias lineas tampoco",
           f"{evidencia(p, 'R002')}")


def test_F002_R010_cita_en_texto_no_cuenta(base):
    print("\nF002 · R010: en Python, una cita dentro de un texto no cuenta")
    p = repo_con_feature(base, "f002-r001-texto", archivos={"tests/test_t.py": (
        "def test_otro():\n    msg = 'ver F001-R002 en la spec'\n    assert msg\n")})
    expect(evidencia(p, "R002") == [], "F001-R002 entre comillas no cuenta",
           f"{evidencia(p, 'R002')}")


def test_F002_R002_nombre_y_comentario_cuentan(base):
    print("\nF002 · R002: nombre y comentario siguen contando")
    p = repo_con_feature(base, "f002-r002", archivos={"tests/test_ok.py": (
        "def test_F001_R001_ok():\n    assert login() == 'ok'\n\n\n"
        "def test_otro():\n    # F001-R002\n    assert True  # con 'una cadena' en la linea\n")})
    expect(evidencia(p, "R001") == ["tests/test_ok.py::test_F001_R001_ok"],
           "el nombre de la prueba cuenta", f"{evidencia(p, 'R001')}")
    expect(evidencia(p, "R002") == ["tests/test_ok.py::test_otro"],
           "un comentario en el cuerpo cuenta", f"{evidencia(p, 'R002')}")


def test_F002_R002_python_invalido_no_revienta(base):
    print("\nF002 · R002: un archivo Python que no se tokeniza no rompe nada")
    p = repo_con_feature(base, "f002-r002-invalido", archivos={"tests/test_roto.py": (
        "def test_otro():\n    a = 'F001-R002'\n    assert '''sin cerrar\n")})
    r = run("trace", ["--json"], cwd=p)
    expect(r.returncode == 0, "trace no revienta", r.stderr)
    expect(evidencia(p, "R002") == ["tests/test_roto.py::test_otro"],
           "se usa el texto tal cual, como antes: la cita en la cadena vuelve a contar",
           f"{evidencia(p, 'R002')}")


def test_F002_R002_salto_de_pagina(base):
    print("\nF002 · R002: un salto de pagina no desalinea la vista de codigo")
    p = repo_con_feature(base, "f002-r002-ff", archivos={"tests/test_ff.py": (
        "\x0c\ndef test_F001_R001_ok():\n    s = 'F001-R002 en texto'\n    assert s\n")})
    expect(evidencia(p, "R001") == ["tests/test_ff.py::test_F001_R001_ok"],
           "el nombre de la prueba sigue contando", f"{evidencia(p, 'R001')}")
    expect(evidencia(p, "R002") == [], "y la cita en el texto sigue sin contar",
           f"{evidencia(p, 'R002')}")


OTROS_LENGUAJES = {
    "tests/a.test.js": (
        "describe('login', () => {\n"
        "  it('caduca', () => {\n"
        "    /*\n"
        "     * Doesn't retry: F001-R001 it's the token case\n"
        "     */\n"
        "    expect(login('x')).toBe(false);\n  });\n"
        "  it.only('F001_R002 solo esta', () => { expect(1).toBe(1); });\n"
        "  test.each([[1]])('F001_R001 caso %s', (n) => { expect(n).toBe(1); });\n"
        "});\n"),
    # Un dato en una cadena: fuera de Python sigue contando (consecuencia de R010).
    "tests/datos.test.js": (
        "const FIXTURE = \"it('F001_R002 dato', () => { expect(1).toBe(1) })\";\n"),
    "spec/pagos_spec.rb": (
        "describe 'pagos' do\n"
        "  xit 'F001_R001 pendiente' do\n    expect(1).to eq(1)\n  end\n"
        "  scenario 'F001_R002 rechaza' do\n"
        "    # it's F001-R001, the user's charge\n    expect(1).to eq(1)\n  end\nend\n"),
    "test/login.bats": "@test \"F001_R001 login\" {\n  run login\n  [ \"$status\" -eq 0 ]\n}\n",
    "src/test/kotlin/LoginTest.kt": (
        "@Test fun `F001_R002 rechaza el token`() { assertEquals(1, login()) }\n"),
    "LoginTests.cs": ("[Fact(DisplayName = \"F001_R001 caduca\")]\n"
                      "public void Caduca() { Assert.Equal(1, Login()); }\n"),
    "src/test/scala/LoginSpec.scala": (
        "\"login\" should \"F001_R002 rechazar\" in { assert(login() == 1) }\n"),
    "login_test.go": (
        "func TestLogin(t *testing.T) {\n"
        "\tcases := []struct{ name string }{{\"F001_R002 caducado\"}}\n"
        "\tfor _, tc := range cases {\n"
        "\t\tt.Run(tc.name, func(t *testing.T) { if login() != 1 { t.Errorf(\"x\") } })\n\t}\n"
        "\tt.Run(\"F001_R001 subcaso\", func(t *testing.T) {})\n}\n"),
    "src/test/java/PagosTest.java": (
        "@DisplayName(\"F001-R002 cobra a fin de mes\")\n"
        "void cobra() { assertEquals(1, cobro()); }\n"),
}

# Evidencia exacta, etiquetas incluidas: la misma que daba sdd_trace.py antes de
# la feature 002 sobre estos archivos (verificado contra 23b5c1e).
ESPERADO = {
    "R001": ["LoginTests.cs", "login_test.go::TestLogin", "spec/pagos_spec.rb",
             "test/login.bats", "tests/a.test.js::caduca"],
    "R002": ["login_test.go::TestLogin", "spec/pagos_spec.rb", "src/test/java/PagosTest.java",
             "src/test/kotlin/LoginTest.kt", "src/test/scala/LoginSpec.scala",
             "tests/a.test.js::caduca", "tests/datos.test.js::F001_R002 dato"],
}


def test_F002_R010_otros_lenguajes_como_antes(base):
    print("\nF002 · R010: fuera de Python las citas cuentan como antes")
    spec = SPEC_BASE.replace("| R002 | SHOULD |", "| R002 | MUST |")
    p = repo_con_feature(base, "f002-r010-otros", spec=spec, archivos=OTROS_LENGUAJES)
    for rid, esperada in ESPERADO.items():
        encontrados = evidencia(p, rid)
        expect(encontrados == esperada, f"la evidencia de {rid} es exactamente la de antes",
               f"{encontrados}")


# Equivalentes a MENCIONES y EJECUCIONES de plugins/discovery/tests/selftest.py,
# que prueba la copia del analizador en discovery.py: si cambian aqui, alli.
MENCIONES = [
    "git commit -q -m 'sdd: la compuerta ya no bloquea sdd.py approve ni set_status(x)'",
    'gh pr create --title t --body "Corrige: python3 sdd.py approve y set_status(texto, v)"',
    "cat > notas.md <<'EOF'\npython3 plugins/sdd/scripts/sdd.py approve\nEOF",
    'echo "para aprobar: python3 sdd.py approve"',
    "grep -rn 'sdd.py approve' plugins/sdd/README.md",
    "git commit -m 'la compuerta ya no bloquea `python3 sdd.py approve`'",
    "gh pr create --title t --body 'Ahora `sdd.py approve` solo se bloquea si se ejecuta'",
    "git commit -m 'cita $(python3 sdd.py approve) en texto'",
]

EJECUCIONES = [
    "python3 sdd.py approve",
    "python3 /x/plugins/sdd/scripts/sdd.py approve plan",
    'python3 "$HOME/plugins/sdd/scripts/sdd.py" approve',
    "cd plugins/sdd && python3 scripts/sdd.py approve",
    "ls; FOO=1 python3 sdd.py approve tasks",
    "echo `python3 sdd.py approve`",
    'echo "$(python3 sdd.py approve)"',
    'git commit -m "$(python3 /x/sdd.py approve plan)"',
    "x=$(cd y && python3 sdd.py approve)",
    "python3 sdd.py approve; echo $'it\\'s'",
]


def test_F002_R004_mencion_no_bloquea(base):
    print("\nF002 · R004: mencionar la aprobacion no bloquea")
    p = repo_con_feature(base, "f002-r004")
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_bash
    for cmd in MENCIONES:
        expect(not sdd_bash.invokes_approve(cmd), f"no es ejecucion: {cmd.splitlines()[0][:50]!r}")
        expect(not bash_bloquea(p, cmd), f"la compuerta no bloquea: {cmd.splitlines()[0][:50]!r}")
    expect(not sdd_bash.invokes_approve('echo "sin cerrar'),
           "un comando que no se analiza y no contiene la orden: no")


def test_F002_R005_ejecucion_bloquea(base):
    print("\nF002 · R005: ejecutar sdd.py approve sigue bloqueado")
    p = repo_con_feature(base, "f002-r005")
    for cmd in EJECUCIONES:
        expect(bash_bloquea(p, cmd), f"bloquea: {cmd!r}")


def test_F002_R006_auditoria_revierte_lo_que_la_compuerta_deja_pasar(base):
    print("\nF002 · R006: la auditoria revierte lo que la compuerta ya no bloquea")
    if shutil.which("git") is None:
        print("  (sin git: omitida)")
        return
    p = repo_con_feature(base, "f002-r006")
    spec = p / "specs" / "001-x" / "spec.md"
    spec.write_text("# S\n\n| Campo | Valor |\n| - | - |\n| Estado | Draft |\n\n## R\n\n"
                    + SPEC_BASE, encoding="utf-8")
    git = ["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-qm", "init"], check=True)
    opaco = "bash -c 'python3 plugins/sdd/scripts/sdd.py approve'"
    expect(not bash_bloquea(p, opaco, "r006"), "la compuerta deja pasar un bash -c")
    spec.write_text(spec.read_text(encoding="utf-8").replace(
        "| Estado | Draft |", "| Estado | Approved · 0123456789ab |"), encoding="utf-8")
    r = audita(p, "r006")
    expect(r.returncode == 2 and "| Estado | Draft |" in spec.read_text(encoding="utf-8"),
           "y la auditoria devuelve el Estado a Draft", r.stderr)


# ------------------------------------------- feature 003: robustez de sdd

SPEC_CON_OBSOLETO = ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
                     "| R001 | OBSOLETO | CUANDO X, el sistema DEBERA Y. "
                     "(reemplazado por R002) |\n"
                     "| R002 | MUST | CUANDO X, el sistema DEBERA Z. |\n"
                     "| R003 | MUST | CUANDO V, el sistema DEBERA W. |\n"
                     "\n## Criterios de aceptacion\n"
                     "### R002\n- **Dado** a **cuando** b **entonces** c\n"
                     "### R003\n- **Dado** a **cuando** b **entonces** c\n")


def tarea_cerrada(*rids):
    return ("### T001 — a\n- **Estado:** `[x]`\n"
            f"- **Requisitos:** {', '.join(rids)}\n- **Depende de:** —\n")


def test_F003_R004_obsoleto_no_da_error_en_tarea_cerrada(base):
    print("\nF003 · R004: una tarea cerrada no da error por un requisito obsoleto")
    prueba = {"tests/test_z.py": "def test_F001_R002_z():\n    assert z()\n"}
    p = repo_con_feature(base, "f003-r004-obsoleto", spec=SPEC_CON_OBSOLETO,
                         archivos=prueba)
    (p / "specs" / "001-x" / "tasks.md").write_text(tarea_cerrada("R001", "R002"),
                                                     encoding="utf-8")
    hallazgos = [f for f in traza(p)["findings"] if f["code"] == "E-DONE-NO-TEST"]
    expect(not hallazgos,
           "obsoleto sin prueba + vigente con prueba: sin E-DONE-NO-TEST",
           f"{hallazgos}")

    p = repo_con_feature(base, "f003-r004-vigente", spec=SPEC_CON_OBSOLETO,
                         archivos=prueba)
    (p / "specs" / "001-x" / "tasks.md").write_text(tarea_cerrada("R001", "R003"),
                                                     encoding="utf-8")
    hallazgos = [f["message"] for f in traza(p)["findings"] if f["code"] == "E-DONE-NO-TEST"]
    expect(len(hallazgos) == 1 and "R003" in hallazgos[0] and "R001" not in hallazgos[0],
           "un vigente sin prueba sigue dando E-DONE-NO-TEST, sin nombrar el obsoleto",
           f"{hallazgos}")


def siguiente_id(base, nombre, spec):
    return run("next-req", cwd=repo_con_feature(base, nombre, spec=spec)).stdout.strip()


def test_F003_R003_siguiente_id_ignora_menciones(base):
    print("\nF003 · R003: el siguiente ID sale de los requisitos declarados")
    filas = "".join(f"| R00{n} | MUST | CUANDO X, el sistema DEBERA Y{n}. |\n"
                    for n in range(1, 7))
    spec = ("## Problema\n\nLa feature anterior dejo R007 y R009 sin cubrir.\n\n"
            "| ID | Prioridad | Requisito |\n| - | - | - |\n" + filas
            + "\nComo en R009 de la otra feature.\n")
    obtenido = siguiente_id(base, "f003-r003-menciones", spec)
    expect(obtenido == "R007", "las menciones R007 y R009 en el texto no ocupan ID", obtenido)

    spec = ("| ID | Prioridad | Requisito |\n| - | - | - |\n"
            + "".join(f"| R00{n} | MUST | CUANDO X, el sistema DEBERA Y{n}. |\n"
                      for n in range(1, 5))
            + "| R005 | OBSOLETO | CUANDO X, el sistema DEBERA Y5. |\n")
    obtenido = siguiente_id(base, "f003-r003-obsoleto", spec)
    expect(obtenido == "R006", "el ultimo declarado es obsoleto y tambien cuenta", obtenido)

    spec = "".join(f"## R00{n} — algo\n\nEl sistema DEBERA hacer {n}.\n\n" for n in range(1, 4))
    obtenido = siguiente_id(base, "f003-r003-encabezados", spec)
    expect(obtenido == "R004", "una spec antigua con encabezados no recicla IDs", obtenido)


def artefacto(estado, cuerpo="x"):
    return f"# A\n\n| Campo | Valor |\n| - | - |\n| Estado | {estado} |\n\n{cuerpo}\n"


def repo_dos_features(base, nombre):
    """001-a y 002-b con spec, plan y tasks en Draft; activa la 002."""
    p = base / nombre
    for slug in ("001-a", "002-b"):
        (p / "specs" / slug).mkdir(parents=True)
        for fname in ("spec.md", "plan.md", "tasks.md"):
            (p / "specs" / slug / fname).write_text(artefacto("Draft"), encoding="utf-8")
    (p / ".sdd").mkdir()
    (p / ".sdd" / "current").write_text("002-b\n")
    return p


def aprueba_a_mano(path, estado="Approved · 0123456789ab"):
    texto = path.read_text(encoding="utf-8")
    viejo = texto.split("| Estado | ", 1)[1].split(" |", 1)[0]
    path.write_text(texto.replace(f"| Estado | {viejo} |", f"| Estado | {estado} |", 1),
                    encoding="utf-8")


def estado_de(path):
    return path.read_text(encoding="utf-8").split("| Estado | ", 1)[1].split(" |", 1)[0]


def test_F003_R001_auditoria_revierte_otra_feature(base):
    print("\nF003 · R001: la auditoria protege la aprobacion de todas las features")
    p = repo_dos_features(base, "f003-r001-otra")
    spec = p / "specs" / "001-a" / "spec.md"
    bash_bloquea(p, "python3 opaco.py", "f3a")
    aprueba_a_mano(spec)
    r = audita(p, "f3a")
    expect(r.returncode == 2 and estado_de(spec) == "Draft" and "001-a/spec.md" in r.stderr,
           "con la 002 activa, aprobar el spec de la 001 se revierte y se avisa",
           f"{r.returncode} {estado_de(spec)!r} {r.stderr!r}")
    expect("Detente y dile al usuario" in r.stderr and r.stderr.count("Detente") == 1,
           "el aviso pide detenerse y avisar al usuario, una sola vez", r.stderr)

    p = repo_dos_features(base, "f003-r001-puntero")
    plan = p / "specs" / "001-a" / "plan.md"
    bash_bloquea(p, "python3 opaco.py", "f3b")
    (p / ".sdd" / "current").write_text("001-a\n")
    aprueba_a_mano(plan)
    (p / ".sdd" / "current").write_text("002-b\n")
    r = audita(p, "f3b")
    expect(r.returncode == 2 and estado_de(plan) == "Draft",
           "cambiar el puntero, aprobar y restaurarlo: el plan de la 001 vuelve a Draft",
           f"{r.returncode} {estado_de(plan)!r}")

    p = repo_dos_features(base, "f003-r001-huella")
    tasks = p / "specs" / "001-a" / "tasks.md"
    aprueba_a_mano(tasks, "Approved · 111111111111")
    bash_bloquea(p, "python3 opaco.py", "f3c")
    aprueba_a_mano(tasks, "Approved · 222222222222")
    r = audita(p, "f3c")
    expect(r.returncode == 2 and estado_de(tasks) == "Approved · 111111111111",
           "una huella reescrita en otra feature recupera la anterior",
           f"{r.returncode} {estado_de(tasks)!r}")


def test_F003_R002_auditoria_silenciosa_sin_cambios(base):
    print("\nF003 · R002: sin cambios de Estado, la auditoria no avisa ni escribe")
    p = repo_dos_features(base, "f003-r002-nada")
    artefactos = sorted((p / "specs").rglob("*.md"))
    antes = {a: a.read_bytes() for a in artefactos}
    bash_bloquea(p, "python3 nada.py", "f3d")
    r = audita(p, "f3d")
    expect(r.returncode == 0 and not r.stderr and all(a.read_bytes() == antes[a]
                                                      for a in artefactos),
           "varias features y un comando que no toca nada: exit 0, sin aviso, sin escrituras",
           f"{r.returncode} {r.stderr!r}")

    p = base / "f003-r002-sin-specs"
    p.mkdir()
    (p / "a.txt").write_text("x\n")
    bash_bloquea(p, "python3 nada.py", "f3e")
    r = audita(p, "f3e")
    expect(r.returncode == 0 and not r.stderr and sorted(x.name for x in p.iterdir()) == ["a.txt"],
           "sin specs/: la auditoria no hace nada", f"{r.returncode} {r.stderr!r}")

    p = repo_dos_features(base, "f003-r002-ilegible")
    roto = p / "specs" / "002-b" / "plan.md"
    roto.write_bytes(b"\xff\xfe| Estado | Draft |\n\x80\x81")
    sin_permiso = p / "specs" / "002-b" / "tasks.md"
    sin_permiso.chmod(0)
    spec = p / "specs" / "001-a" / "spec.md"
    # Un comando sin destinos visibles y otro con uno: la compuerta evalua el
    # destino antes de guardar la instantanea.
    comandos = [("python3 opaco.py", "f3f"), ("echo x > src/a.py; python3 opaco.py", "f3g")]
    try:
        for cmd, tid in comandos:
            r_guard = run("guard", stdin=bash_payload(cmd, p, tid), cwd=p)
            aprueba_a_mano(spec)
            r = audita(p, tid)
            # main() convierte cualquier excepcion en "sdd.py: <error>" por stderr.
            expect(r_guard.returncode == 0 and not r_guard.stderr and "sdd.py:" not in r.stderr,
                   f"artefactos ilegibles (no UTF-8, sin permiso): {cmd!r} no hace fallar "
                   "ni la compuerta ni la auditoria", f"{r_guard.stderr!r} {r.stderr!r}")
            expect(r.returncode == 2 and estado_de(spec) == "Draft",
                   f"y los demas artefactos siguen protegidos: {cmd!r}",
                   f"{r.returncode} {estado_de(spec)!r}")
    finally:
        sin_permiso.chmod(0o644)


SPEC_DOS_MUST = SPEC_BASE.replace("| R002 | SHOULD |", "| R002 | MUST |")

CITAS_FUERA = '''# F001-R002: comentario de modulo, fuera de toda prueba


def test_F001_R003_otra():
    assert otra()


def ayudante():
    return 1  # F001-R002 en una funcion que no es prueba


def main():
    test_F001_R001_algo(base)
'''


def test_F003_R005_cita_fuera_de_prueba_no_cuenta(base):
    print("\nF003 · R005: en Python, una cita fuera de una prueba no cuenta")
    p = repo_con_feature(base, "f003-r005", spec=SPEC_DOS_MUST,
                         archivos={"tests/test_fuera.py": CITAS_FUERA})
    r001, r002 = evidencia(p, "R001"), evidencia(p, "R002")
    expect(r001 == [], "la llamada desde main() no es evidencia ni se atribuye a otra prueba",
           f"{r001}")
    expect(r002 == [], "un comentario de modulo o de un ayudante no es evidencia", f"{r002}")


DENTRO = '''import unittest


def test_F001_R001_algo():
    assert login() is True


class PruebaLogin(unittest.TestCase):
    def test_x(self):
        # F001-R002
        self.assertTrue(login())
'''


def test_F003_R006_nombre_y_cuerpo_cuentan(base):
    print("\nF003 · R006: el nombre y el cuerpo de una prueba Python siguen contando")
    p = repo_con_feature(base, "f003-r006", spec=SPEC_DOS_MUST,
                         archivos={"tests/test_dentro.py": DENTRO})
    r001, r002 = evidencia(p, "R001"), evidencia(p, "R002")
    expect(r001 == ["tests/test_dentro.py::test_F001_R001_algo"],
           "la prueba con asercion cuenta a su nombre", f"{r001}")
    expect(r002 == ["tests/test_dentro.py::test_x"],
           "el comentario dentro de un metodo de clase cuenta a nombre del metodo", f"{r002}")


def test_F003_R006_python_sin_ast_usa_la_atribucion_anterior(base):
    print("\nF003 · R006: si ast no puede analizar el archivo, se atribuye como antes")
    roto = "def test_F001_R001_algo():\n    assert login()\n\ndef roto(:\n"
    p = repo_con_feature(base, "f003-r006-sin-ast", spec=SPEC_DOS_MUST,
                         archivos={"tests/test_roto.py": roto})
    r = run("trace", ["--json"], cwd=p)
    r001 = evidencia(p, "R001")
    expect(r.returncode in (0, 1) and "Traceback" not in r.stderr
           and r001 == ["tests/test_roto.py::test_F001_R001_algo"],
           "un archivo que ast rechaza sigue dando la evidencia de su prueba",
           f"{r001} {r.stderr!r}")


def test_F003_R007_otros_lenguajes_identicos(base):
    print("\nF003 · R007: fuera de Python la atribucion no cambia")
    p = repo_con_feature(base, "f003-r007", spec=SPEC_DOS_MUST, archivos=OTROS_LENGUAJES)
    for rid, esperada in ESPERADO.items():
        encontrados = evidencia(p, rid)
        expect(encontrados == esperada,
               f"{rid}: evidencia identica a la anterior, etiquetas incluidas", f"{encontrados}")


# ------------------------------------------- feature 004: raiz del proyecto

def run_sin_raiz(sub, args=(), cwd=None):
    """Como run, pero sin CLAUDE_PROJECT_DIR: como la inyeccion de una skill."""
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN))
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run([sys.executable, str(SDD), sub, *args], capture_output=True,
                          text=True, cwd=str(cwd), env=env, timeout=60)


def test_F004_R001_raiz_desde_subdirectorio(base):
    print("\nF004 · R001: sdd encuentra la raiz desde un subdirectorio")
    p = repo_con_feature(base, "f004-r001", spec=SPEC_LISTA)
    feat = p / "specs" / "001-x"
    r = run_sin_raiz("status", cwd=feat)
    expect(r.returncode == 0 and "001-x" in r.stdout,
           "status desde specs/<feature>/ muestra la feature activa", r.stdout + r.stderr)

    r = run_sin_raiz("approve", ["--skill"], cwd=feat)
    expect("aprobado" in r.stdout and "| Estado | Approved" in (feat / "spec.md").read_text(),
           "aprobar desde specs/<feature>/ aprueba la spec de esa feature", r.stdout)

    (p / "src" / "specs").mkdir(parents=True)
    (p / "src" / "componentes").mkdir()
    r = run_sin_raiz("status", cwd=p / "src" / "componentes")
    expect("001-x" in r.stdout, "un src/specs/ mas cercano no gana a .sdd/", r.stdout)

    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd
    # Segun la version de Python, is_dir() lanza PermissionError o devuelve
    # False ante un directorio sin permiso: se fuerza la excepcion.
    cerrado = p / "cerrado"
    (cerrado / "x").mkdir(parents=True)
    original = Path.is_dir

    def is_dir_sin_permiso(ruta):
        if cerrado in ruta.parents:
            raise PermissionError(13, "sin permiso", str(ruta))
        return original(ruta)

    Path.is_dir = is_dir_sin_permiso
    try:
        hallado = sdd.find_upwards(cerrado / "x", (".sdd",))
    finally:
        Path.is_dir = original
    expect(hallado == p, "un directorio sin permiso cuenta como vacio y se sigue subiendo",
           f"{hallado}")


def test_F004_R003_sin_datos_usa_el_directorio_actual(base):
    print("\nF004 · R003: sin datos hacia arriba, el directorio actual, sin salir del repo")
    fuera = base / "f004-r003"
    (fuera / "specs" / "001-ajena").mkdir(parents=True)  # fuera del repositorio
    repo = fuera / "repo"
    (repo / "sub").mkdir(parents=True)
    (repo / ".git").mkdir()  # basta con que exista: es el tope de la busqueda
    sin = run_sin_raiz("status", cwd=repo / "sub")
    como_hoy = run("status", cwd=repo / "sub")
    expect((sin.returncode, sin.stdout) == (como_hoy.returncode, como_hoy.stdout)
           and "001-ajena" not in sin.stdout + sin.stderr,
           "sin datos en el repo: como hoy, sin usar el specs/ de fuera",
           f"{sin.stdout!r} vs {como_hoy.stdout!r}")


def test_F004_R004_variable_de_entorno_manda(base):
    print("\nF004 · R004: CLAUDE_PROJECT_DIR se usa tal cual")
    a = repo_con_feature(base, "f004-r004-a")
    b = base / "f004-r004-b"
    (b / "specs" / "007-otra").mkdir(parents=True)
    (b / ".sdd").mkdir()
    (b / ".sdd" / "current").write_text("007-otra\n")
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN), CLAUDE_PROJECT_DIR=str(a))
    r = subprocess.run([sys.executable, str(SDD), "status"], capture_output=True, text=True,
                       cwd=str(b / "specs" / "007-otra"), env=env, timeout=60)
    expect("001-x" in r.stdout and "007-otra" not in r.stdout,
           "con la variable en un proyecto y el cwd en otro, manda la variable", r.stdout)


# ------------------------------------------- feature 005: traspaso desde discovery
# Un producto coherente en el formato de discovery (copia de los fixtures de su
# selftest): sdd lee esos archivos, no importa codigo de discovery.

DISCOVERY = PLUGIN.parent / "discovery" / "scripts" / "discovery.py"

PRODUCTO_DOC = """# Visión

## Problema

Los comercios no saben cuánto venden cada día.

## Usuarios

Dueños de comercios pequeños.

## Informes

Un resumen diario de ventas.

## Exportación

Bajar los movimientos a una hoja de cálculo.
"""

PRODUCTO_BRIEF = """# Brief del producto

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Objetivos

### G1 — Que el comercio sepa cuánto vende

- **Origen:** D1§1, D1§2, D1§3
- **Descripción:** el dueño ve sus ventas del día sin calcularlas.

### G2 — Que el comercio use sus datos fuera

- **Origen:** D1§4
- **Descripción:** los movimientos salen a otras herramientas.

## Usuarios

- Dueños de comercios pequeños (D1§2)

## Glosario

- **Movimiento:** una venta o una devolución (D1§1)

## Restricciones

- Ninguna en los documentos.

## Invariantes propuestos para la constitución

- Ninguno en los documentos.

## Secciones descartadas

- Ninguna.

## Preguntas

- [x] (D1§3; G1) ¿Diario o semanal?
  - **Respuesta:** diario.
"""

PRODUCTO_BACKLOG = """# Backlog del producto

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Candidatas

### B01 — Resumen diario de ventas

- **Estado:** candidata
- **Objetivos:** G1
- **Origen:** D1§1, D1§3
- **Problema:** el dueño no sabe cuánto vendió hoy, cada día.
- **Resultado observable:** el dueño ve el total del día al cerrar.
- **Dentro:** total del día y número de ventas.
- **Fuera:** comparativas entre días.
- **Depende de:** —

### B02 — Exportar movimientos

- **Estado:** candidata
- **Objetivos:** G2
- **Origen:** D1§4
- **Problema:** el dueño copia a mano sus ventas para su gestor.
- **Resultado observable:** el dueño descarga sus movimientos en un archivo.
- **Dentro:** movimientos de un rango de fechas.
- **Fuera:** envío automático al gestor.
- **Depende de:** B01

### B03 — Envío automático al gestor

- **Estado:** descartada (fuera del alcance acordado)
- **Objetivos:** G2
- **Origen:** D1§4
- **Problema:** el gestor pide los datos cada mes.
- **Resultado observable:** el gestor recibe los movimientos sin pedirlos.
- **Dentro:** —
- **Fuera:** —
- **Depende de:** B02
"""


def sdd_product():
    if str(PLUGIN / "scripts") not in sys.path:
        sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_product as modulo
    return modulo


def run_discovery(cwd, *args):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd),
               CLAUDE_PLUGIN_ROOT=str(DISCOVERY.parent.parent))
    return subprocess.run([sys.executable, str(DISCOVERY), *args], capture_output=True,
                          text=True, cwd=str(cwd), env=env, timeout=60)


def test_F005_R003_contrato_con_discovery(base):
    print("\nF005 · R003: la huella de sdd_product coincide con la de discovery")
    if not DISCOVERY.is_file():
        print("  (sin plugins/discovery en el repositorio: prueba de contrato omitida)")
        return
    sp = sdd_product()
    p = base / "f005-contrato"
    (p / "entrada").mkdir(parents=True)
    (p / "entrada" / "vision.md").write_text(PRODUCTO_DOC, encoding="utf-8")
    r = run_discovery(p, "ingest", str(p / "entrada" / "vision.md"))
    expect(r.returncode == 0, "discovery ingiere el documento de prueba", r.stdout + r.stderr)
    expect(sp.product_approval(p) == {"brief.md": "missing", "backlog.md": "missing"}
           and "product/brief.md no existe" in sp.approval_problems(p)[0],
           "sin brief ni backlog: los dos faltan", f"{sp.approval_problems(p)}")
    (p / "product" / "brief.md").write_text(PRODUCTO_BRIEF, encoding="utf-8")
    (p / "product" / "backlog.md").write_text(PRODUCTO_BACKLOG, encoding="utf-8")
    expect(sp.product_approval(p) == {"brief.md": "draft", "backlog.md": "draft"},
           "antes de aprobar: los dos en draft", f"{sp.product_approval(p)}")

    r = run_discovery(p, "approve")
    expect(r.returncode == 0, "discovery aprueba el producto de prueba", r.stdout + r.stderr)
    expect(sp.product_approval(p) == {"brief.md": "approved", "backlog.md": "approved"},
           "lo que discovery aprueba, sdd_product lo da por aprobado",
           f"{sp.product_approval(p)}")

    def aviso_de_discovery():
        r = run_discovery(p, "check", "--json")
        return [f["message"] for f in json.loads(r.stdout)["findings"]
                if f["code"] == "W-PRODUCT-NOT-APPROVED"]

    brief = p / "product" / "brief.md"
    aprobado = brief.read_text(encoding="utf-8")
    reformateado = aprobado.replace("\n## Usuarios", "\n\n\n## Usuarios   ")
    brief.write_text(reformateado, encoding="utf-8")
    expect(reformateado != aprobado and sp.product_approval(p)["brief.md"] == "approved"
           and not aviso_de_discovery(),
           "reformatear sin cambiar el contenido: aprobado para los dos plugins",
           f"{aviso_de_discovery()}")

    brief.write_text(sp.STATUS_ROW.sub(r"\1Approved\3", aprobado, count=1), encoding="utf-8")
    expect(sp.product_approval(p)["brief.md"] == "draft",
           "un Approved sin huella no cuenta: draft, como en discovery")

    brief.write_text(aprobado.replace("sin calcularlas", "sin calcularlas a mano"),
                     encoding="utf-8")
    codigos = {f["code"]: f["message"] for f in
               json.loads(run_discovery(p, "check", "--json").stdout)["findings"]}
    expect(sp.product_approval(p)["brief.md"] == "stale"
           and "cambió" in codigos.get("W-PRODUCT-NOT-APPROVED", ""),
           "un brief editado tras aprobarse: cambiado para los dos plugins", f"{codigos}")
    problemas = sp.approval_problems(p)
    expect(len(problemas) == 1 and problemas[0].startswith(
               "product/brief.md cambió después de aprobarse")
           and "/discovery:approve" in problemas[0],
           "el motivo nombra el artefacto y lo que le pasa", f"{sp.approval_problems(p)}")


PRODUCTO_FUENTE = """# D1 — Visión

| Campo | Valor |
| ----- | ----- |
| Documento | D1 |
| Secciones | 1, 2, 3, 4 |

<!-- discovery:contenido -->
# Visión

## 1 Problema

Los comercios no saben cuánto venden cada día.

## 2 Usuarios

Dueños de comercios pequeños.

## 3 Informes

Un resumen diario de ventas.

## 4 Exportación

Bajar los movimientos a una hoja de cálculo.

```
## 4.1 Encabezado de mentira dentro de un bloque de código
```

### 4.1 Formatos

CSV y hoja de cálculo.
"""


def sella(path):
    """Aprueba un artefacto de discovery con la huella de sdd_product, como /discovery:approve."""
    sp = sdd_product()
    texto = path.read_text(encoding="utf-8")
    path.write_text(sp.STATUS_ROW.sub(rf"\g<1>Approved · {sp.content_digest(texto)}\3",
                                      texto, count=1), encoding="utf-8")


def con_producto(p, aprobado=True, backlog=PRODUCTO_BACKLOG):
    """Pone en p un product/ de discovery: brief, backlog y D1 ingerido."""
    (p / "product" / "sources").mkdir(parents=True)
    (p / "product" / "sources" / "D1-vision.md").write_text(PRODUCTO_FUENTE, encoding="utf-8")
    (p / "product" / "brief.md").write_text(PRODUCTO_BRIEF, encoding="utf-8")
    (p / "product" / "backlog.md").write_text(backlog, encoding="utf-8")
    if aprobado:
        sella(p / "product" / "brief.md")
        sella(p / "product" / "backlog.md")
    return p


def test_F005_R004_lee_candidatas_y_descartadas(base):
    print("\nF005 · R004: sdd_product lee las candidatas del backlog")
    sp = sdd_product()
    p = con_producto(base / "f005-r004-lectura")
    b02 = sp.candidate(p, "b02")
    expect(b02 is not None and b02["id"] == "B02" and b02["title"] == "Exportar movimientos"
           and b02["state"] == "candidata"
           and b02["fields"]["problema"] == "el dueño copia a mano sus ventas para su gestor."
           and b02["fields"]["fuera"] == "envío automático al gestor.",
           "lee B02 (tambien como b02) con su titulo, estado y campos", f"{b02}")
    expect(sp.candidate(p, "B03")["state"] == "descartada",
           "B03 esta descartada aunque el Estado lleve un motivo detras")
    expect(sp.candidate(p, "B09") is None, "B09 no existe: None")
    expect(sp.refs(b02["fields"]["depende de"])["candidates"] == ["B01"],
           "las dependencias se leen como citas a candidatas")


def test_F005_R006_resuelve_objetivos_y_fuentes(base):
    print("\nF005 · R006: sdd_product resuelve objetivos y secciones de origen")
    sp = sdd_product()
    p = con_producto(base / "f005-r006-lectura")
    g2 = sp.goals(p).get("G2")
    expect(g2 == {"id": "G2", "title": "Que el comercio use sus datos fuera",
                  "description": "los movimientos salen a otras herramientas."},
           "G2 con su titulo y su descripcion", f"{g2}")
    fuente = sp.source_section(p, "D1§4")
    expect(fuente == {"ref": "D1§4", "file": "product/sources/D1-vision.md", "section": "4",
                      "title": "Exportación"},
           "D1§4 se resuelve a su archivo, su numero y su titulo", f"{fuente}")
    sub = sp.source_section(p, "D1§4.1")
    expect(sub == {"ref": "D1§4.1", "file": "product/sources/D1-vision.md", "section": "4.1",
                   "title": "Formatos"},
           "una subseccion (D1§4.1) se resuelve igual, sin tomar la de un bloque de codigo",
           f"{sub}")
    perdida = sp.source_section(p, "D7§2")
    expect(perdida["file"] is None and perdida["title"] is None,
           "una cita a un documento que no esta: sin archivo, sin excepcion", f"{perdida}")
    expect(sp.refs("D1§1, D1§3 y G1")["sections"] == ["D1§1", "D1§3"],
           "las secciones se leen en orden de aparicion")


def specs_creadas(p):
    return sorted(x.name for x in (p / "specs").iterdir()) if (p / "specs").is_dir() else []


def test_F005_R001_crea_la_spec_desde_la_candidata(base):
    print("\nF005 · R001: /sdd:specify B02 crea la spec desde la candidata")
    for n, arg in enumerate(("B02", "b02")):
        p = con_producto(base / f"f005-r001-{n}")  # macOS no distingue B02 de b02
        r = run("new", [arg], cwd=p)
        creada = json.loads(r.stdout)["feature"] if r.returncode == 0 else None
        expect(creada == "001-exportar-movimientos",
               f"new {arg}: el nombre sale del titulo de la candidata", r.stdout + r.stderr)
        if not creada:
            continue
        spec = (p / "specs" / creada / "spec.md").read_text(encoding="utf-8")
        expect(spec.startswith("# Spec: Exportar movimientos")
               and "## Problema\n\nel dueño copia a mano sus ventas para su gestor." in spec
               and "- el dueño descarga sus movimientos en un archivo." in spec
               and "- movimientos de un rango de fechas." in spec
               and "### Fuera (non-goals)\n\n- envío automático al gestor." in spec,
               f"new {arg}: problema, resultado observable, Dentro y Fuera de la candidata")
        expect("G2 — Que el comercio use sus datos fuera" in spec and "D1§4" in spec,
               f"new {arg}: el Contexto cita el objetivo y la seccion de origen")


def test_F005_R002_origen_en_la_cabecera(base):
    print("\nF005 · R002: la cabecera registra el origen")
    p = con_producto(base / "f005-r002")
    run("new", ["B02"], cwd=p)
    spec = (p / "specs" / "001-exportar-movimientos" / "spec.md").read_text(encoding="utf-8")
    cabecera = spec.split("\n## ", 1)[0]
    expect("| Issue  | —            |\n| Origen | B02 · G2 · D1§4 |\n" in cabecera,
           "| Origen | B02 · G2 · D1§4 | tras la fila Issue", cabecera)
    p = con_producto(base / "f005-r002-varios")
    run("new", ["B01"], cwd=p)
    spec = next((p / "specs").iterdir()) / "spec.md"
    expect("| Origen | B01 · G1 · D1§1, D1§3 |" in spec.read_text(encoding="utf-8"),
           "varias secciones, separadas por comas en su grupo")


def niega(p, arg, *fragmentos):
    """new arg sale con 1, no crea ninguna feature ni mueve .sdd/current, y el
    motivo contiene los fragmentos."""
    actual = (p / ".sdd" / "current").read_text() if (p / ".sdd" / "current").is_file() else None
    r = run("new", [arg], cwd=p)
    despues = (p / ".sdd" / "current").read_text() if (p / ".sdd" / "current").is_file() else None
    return (r.returncode == 1 and not specs_creadas(p) and actual == despues
            and all(f in r.stderr for f in fragmentos)), r.stderr


def test_F005_R003_producto_sin_aprobar(base):
    print("\nF005 · R003: sin el producto aprobado no se crea la feature")
    p = con_producto(base / "f005-r003-draft", aprobado=False)
    ok, err = niega(p, "B02", "product/backlog.md no está aprobado", "/discovery:approve")
    expect(ok, "backlog en Draft: no se crea y se dice que lo aprueba /discovery:approve", err)

    p = con_producto(base / "f005-r003-cambiado")
    brief = p / "product" / "brief.md"
    brief.write_text(brief.read_text(encoding="utf-8").replace("sin calcularlas", "al vuelo"),
                     encoding="utf-8")
    ok, err = niega(p, "B02", "product/brief.md cambió después de aprobarse")
    expect(ok, "brief editado tras aprobarse: no se crea y se dice que cambio", err)

    p = con_producto(base / "f005-r003-sin-brief")
    (p / "product" / "brief.md").unlink()
    ok, err = niega(p, "B02", "product/brief.md no existe")
    expect(ok, "backlog sin brief: no se crea y se dice que falta el brief", err)


def test_F005_R004_candidata_inexistente_o_descartada(base):
    print("\nF005 · R004: candidata inexistente o descartada")
    p = con_producto(base / "f005-r004-b09")
    ok, err = niega(p, "B09", "B09 no existe")
    expect(ok, "B09 no existe: no se crea y se dice", err)
    p = con_producto(base / "f005-r004-b03")
    ok, err = niega(p, "b03", "B03 está descartada")
    expect(ok, "B03 descartada: no se crea y se dice", err)


def test_F005_R007_sin_backlog_o_sin_id(base):
    print("\nF005 · R007: sin backlog, o sin un ID, como hasta ahora")
    p = base / "f005-r007-sin-backlog"
    p.mkdir()
    r = run("new", ["B03"], cwd=p)
    expect(r.returncode == 0 and json.loads(r.stdout)["feature"] == "001-b03",
           "sin product/backlog.md, B03 es una descripcion mas", r.stdout + r.stderr)
    spec = (p / "specs" / "001-b03" / "spec.md").read_text(encoding="utf-8")
    expect("| Origen |" not in spec and spec.startswith("# Spec: B03"), "sin origen")

    p = con_producto(base / "f005-r007-descripcion")
    r = run("new", ["login con Google"], cwd=p)
    creada = json.loads(r.stdout)["feature"] if r.returncode == 0 else ""
    spec = (p / "specs" / creada / "spec.md").read_text(encoding="utf-8") if creada else ""
    plantilla = (PLUGIN / "templates" / "spec.md").read_text(encoding="utf-8")
    esperada = (plantilla.replace("{{ID}}", creada).replace("{{TITLE}}", "login con Google")
                .replace("{{DATE}}", spec.split("| Fecha  | ")[1].split(" ")[0] if spec else ""))
    expect(creada == "001-login-google" and spec == esperada,
           "con backlog y una descripcion normal: la plantilla de siempre, sin origen",
           r.stdout + r.stderr)


def test_F005_R008_specs_sin_origen_igual(base):
    print("\nF005 · R008: una spec sin origen se trata igual con o sin producto al lado")
    salidas = {}
    for nombre, producto in (("f005-r008-solo", False), ("f005-r008-con-producto", True)):
        p = repo_con_feature(base, nombre, spec=SPEC_LISTA)
        if producto:
            con_producto(p)
        quita = lambda s, p=p: s.replace(str(p), "<raiz>")  # noqa: E731
        salidas[nombre] = (
            quita(run("status", cwd=p).stdout),
            json.loads(run("trace", ["--json"], cwd=p).stdout)["requirements"],
            quita(run("approve", ["--skill"], cwd=p).stdout),
            (p / "specs" / "001-x" / "spec.md").read_text(encoding="utf-8"),
        )
    a, b = salidas["f005-r008-solo"], salidas["f005-r008-con-producto"]
    for i, que in enumerate(("status", "trace", "approve", "spec aprobada")):
        expect(a[i] == b[i], f"{que}: identico con un product/ aprobado al lado",
               f"{a[i]!r} vs {b[i]!r}"[:300])


def test_F005_R005_candidata_con_feature(base):
    print("\nF005 · R005: una candidata con feature no se especifica dos veces")
    p = con_producto(base / "f005-r005")
    run("new", ["B02"], cwd=p)
    antes = specs_creadas(p)
    actual = (p / ".sdd" / "current").read_text()
    for arg in ("B02", "b02"):
        r = run("new", [arg], cwd=p)
        expect(r.returncode == 1 and "001-exportar-movimientos" in r.stderr
               and specs_creadas(p) == antes and (p / ".sdd" / "current").read_text() == actual,
               f"new {arg} otra vez: no se crea y se nombra la existente", r.stderr)


def test_F005_R006_contexto_en_el_json(base):
    print("\nF005 · R006: el JSON de new trae el contexto para redactar")
    p = con_producto(base / "f005-r006-json")
    salida = json.loads(run("new", ["B02"], cwd=p).stdout)
    expect(salida.get("origin") == {"candidate": "B02", "goals": ["G2"], "sections": ["D1§4"]},
           "origin: candidata, objetivos y secciones", f"{salida.get('origin')}")
    ctx = salida.get("context") or {}
    expect(ctx.get("brief") == "product/brief.md"
           and ctx.get("goals") == [{"id": "G2", "title": "Que el comercio use sus datos fuera",
                                     "description": "los movimientos salen a otras herramientas."}]
           and ctx.get("sources") == [{"ref": "D1§4", "file": "product/sources/D1-vision.md",
                                       "section": "4", "title": "Exportación"}],
           "context: el brief, G2 con su titulo y D1§4 con su archivo y su seccion", f"{ctx}")

    p = base / "f005-r006-normal"
    p.mkdir()
    salida = json.loads(run("new", ["login con Google"], cwd=p).stdout)
    expect(sorted(salida) == ["dir", "feature", "next", "spec"],
           "sin traspaso, el JSON de siempre", f"{sorted(salida)}")


def test_F005_R009_dependencia_sin_feature(base):
    print("\nF005 · R009: una dependencia sin feature se avisa sin impedir")
    p = con_producto(base / "f005-r009")
    r = run("new", ["B02"], cwd=p)
    avisos = json.loads(r.stdout).get("warnings", []) if r.returncode == 0 else None
    expect(r.returncode == 0 and avisos and len(avisos) == 1 and "B01" in avisos[0],
           "B02 depende de B01 sin feature: se crea y se avisa de B01", r.stdout + r.stderr)

    p = con_producto(base / "f005-r009-hecha")
    run("new", ["B01"], cwd=p)
    r = run("new", ["B02"], cwd=p)
    expect(r.returncode == 0 and json.loads(r.stdout).get("warnings") == [],
           "con B01 ya especificada, sin avisos", r.stdout + r.stderr)


def test_F005_R006_seccion_que_no_se_puede_leer(base):
    print("\nF005 · R006: una seccion de origen que ya no esta se indica como tal")
    perdida = PRODUCTO_BACKLOG.replace("- **Origen:** D1§1, D1§3", "- **Origen:** D1§1, D7§2")
    p = con_producto(base / "f005-r006-fuente", backlog=perdida)
    r = run("new", ["B01"], cwd=p)
    salida = json.loads(r.stdout) if r.returncode == 0 else {}
    fuentes = {s["ref"]: s["file"] for s in salida.get("context", {}).get("sources", [])}
    expect(fuentes == {"D1§1": "product/sources/D1-vision.md", "D7§2": None}
           and any("D7§2" in a for a in salida.get("warnings", [])),
           "D7§2 sin archivo en el contexto y con aviso; la feature se crea",
           r.stdout + r.stderr)


# ------------------------------------------- feature 007: integracion con architecture
# Una arquitectura en el formato del plugin architecture (copia de los fixtures
# de su selftest), sobre el producto de prueba de la feature 005. sdd lee esos
# archivos; solo la prueba de contrato ejecuta architecture.py.

ARCHITECTURE = PLUGIN.parent / "architecture" / "scripts" / "architecture.py"


def cabecera_arq(titulo, estado="Draft"):
    return f"# {titulo}\n\n| Campo  | Valor |\n| ------ | ----- |\n| Estado | {estado} |\n\n"


ARQ_QUALITY = cabecera_arq("Atributos de calidad") + """## Atributos

### Q1 — Resumen al cerrar

- **Escenario:** al cerrar la caja, el total del día aparece en menos de 2 segundos con 5000 ventas
- **Motivo:** G1

### Q2 — Exportación completa

- **Escenario:** exportar 12 meses de movimientos termina en menos de 30 segundos
- **Motivo:** G2
"""

ARQ_COMPONENTS = cabecera_arq("Componentes") + """## Componentes

### C1 — Ventas

- **Responsabilidad:** registra ventas y calcula los totales del día
- **Candidatas:** B01

### C2 — Exportación

- **Responsabilidad:** genera archivos de movimientos a partir de las ventas
- **Candidatas:** B02
"""

ARQ_STANDARDS = cabecera_arq("Estándares") + """## Estándares

### S1 — Exportación depende de Ventas, nunca al revés

- **Tipo:** dependencia
- **Detalle:** C2 → C1
- **Decisión:** ADR-0001
"""

# Un estandar prohibida con dos pares (feature 009).
ESTANDAR_PROHIBIDO = """
### S2 — Ventas no depende de Exportación ni de Cobros

- **Tipo:** prohibida
- **Detalle:** C1 → C2, C1 -> C3
- **Decisión:** ADR-0001
"""

ARQ_QUESTIONS = cabecera_arq("Preguntas de arquitectura") + "## Preguntas\n\nNinguna por ahora.\n"


def adr_arq(numero, titulo, estado="Draft", motivo="Q1", sustituye="—"):
    return (f"# ADR-{numero} — {titulo}\n\n| Campo     | Valor |\n| --------- | ----- |\n"
            f"| Estado    | {estado} |\n| Fecha     | 2026-10-16 |\n| Motivo    | {motivo} |\n"
            f"| Sustituye | {sustituye} |\n\n"
            "## Contexto\n\nLas ventas del día se consultan al cerrar.\n\n"
            "## Decisión\n\nUna sola base de datos relacional.\n\n"
            "## Alternativas descartadas\n\n- Una base por componente: sin necesidad hoy.\n\n"
            "## Consecuencias\n\n- Los dos componentes comparten esquema.\n")


ADRS_BASE = {
    "0001-base-de-datos-unica.md": ("0001", "Base de datos única", "Draft"),
    "0002-despliegue.md": ("0002", "Despliegue en un servidor", "Draft"),
    "0003-cola.md": ("0003", "Cola de trabajos", "Rejected"),
    "0004-cache.md": ("0004", "Caché de totales", "Proposed"),
}


def sella_arq(p):
    """Aprueba el conjunto como /architecture:approve: los cuatro artefactos y
    los ADR en Draft, con la huella de su contenido."""
    arq = p / "architecture"
    archivos = [arq / n for n in ("quality.md", "components.md", "standards.md",
                                  "questions.md")]
    archivos += [x for x in sorted((arq / "adr").iterdir())
                 if architecture_lee().adr_state(x.read_text(encoding="utf-8")) == "draft"]
    for x in archivos:
        sella(x)


def con_arquitectura(p, aprobada=True, components=ARQ_COMPONENTS, adrs=ADRS_BASE):
    """Producto aprobado y una arquitectura coherente en p, aprobada si se pide."""
    con_producto(p)
    arq = p / "architecture"
    (arq / "adr").mkdir(parents=True, exist_ok=True)
    for nombre, texto in (("quality.md", ARQ_QUALITY), ("components.md", components),
                          ("standards.md", ARQ_STANDARDS), ("questions.md", ARQ_QUESTIONS)):
        (arq / nombre).write_text(texto, encoding="utf-8")
    for archivo, (numero, titulo, estado) in adrs.items():
        motivo = "Q2" if numero == "0004" else "Q1"
        (arq / "adr" / archivo).write_text(adr_arq(numero, titulo, estado, motivo),
                                           encoding="utf-8")
    if aprobada:
        sella_arq(p)
    return p


def architecture_lee():
    if str(PLUGIN / "scripts") not in sys.path:
        sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_architecture
    return sdd_architecture


def test_F007_R002_lee_la_arquitectura(base):
    print("\nF007 · R002: sdd_architecture lee componentes, decisiones y estandares")
    sa = architecture_lee()
    p = con_arquitectura(base / "f007-lectura")
    comps = {c["id"]: c["candidates"] for c in sa.components(p)}
    expect(comps == {"C1": ["B01"], "C2": ["B02"]}, "componentes con sus candidatas", f"{comps}")
    estados = {a["id"]: a["state"] for a in sa.adrs(p)}
    expect(estados == {"ADR-0001": "approved", "ADR-0002": "approved",
                       "ADR-0003": "rejected", "ADR-0004": "proposed"},
           "cada ADR con su estado", f"{estados}")
    s = sa.standards(p)
    expect(len(s) == 1 and s[0]["id"] == "S1" and s[0]["adr"] == "ADR-0001",
           "estandares con su decision", f"{s}")
    expect(sa.next_adr(p) == "ADR-0005", "el siguiente ADR libre es ADR-0005")
    expect(sa.approval_problems(p) == [], "la arquitectura sellada esta aprobada",
           f"{sa.approval_problems(p)}")

    p = con_arquitectura(base / "f007-sin-aprobar", aprobada=False)
    expect(any("components.md no está aprobado" in x for x in sa.approval_problems(p)),
           "sin sellar: no aprobada, y dice que la aprueba /architecture:approve",
           f"{sa.approval_problems(p)}")
    expect(not sa.exists(base / "f005-r001-0"), "un proyecto sin architecture/ no la tiene")

    p = con_arquitectura(base / "f007-sustituida")
    d = p / "architecture" / "adr" / "0002-despliegue.md"
    d.write_text(d.read_text(encoding="utf-8").replace(
        sa.product.doc_status(d.read_text(encoding="utf-8")), "Superseded by ADR-0004"),
        encoding="utf-8")
    (p / "architecture" / "adr" / "0005.md").mkdir()  # ilegible como archivo
    adrs = {a["id"]: a for a in sa.adrs(p)}
    expect(adrs["ADR-0002"]["state"] == "superseded"
           and adrs["ADR-0002"]["superseded_by"] == "ADR-0004",
           "un ADR sustituido trae el que lo sustituye", f"{adrs['ADR-0002']}")
    expect(adrs["ADR-0005"]["state"] == "draft" and sa.next_adr(p) == "ADR-0006",
           "un ADR que no se puede leer cuenta como borrador y ocupa su numero",
           f"{adrs.get('ADR-0005')}")


def test_F007_R009_contrato_con_architecture(base):
    print("\nF007 · R009: la lectura de sdd coincide con el architecture real")
    if not ARCHITECTURE.is_file():
        print("  (sin plugins/architecture en el repositorio: prueba de contrato omitida)")
        return
    sa = architecture_lee()
    p = con_arquitectura(base / "f007-contrato", aprobada=False)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(p),
               CLAUDE_PLUGIN_ROOT=str(ARCHITECTURE.parent.parent))
    r = subprocess.run([sys.executable, str(ARCHITECTURE), "approve"], capture_output=True,
                       text=True, cwd=str(p), env=env, timeout=60)
    expect(r.returncode == 0, "architecture aprueba la arquitectura de prueba",
           r.stdout + r.stderr)
    estados = {a["id"]: a["state"] for a in sa.adrs(p)}
    expect(sa.approval_problems(p) == []
           and estados == {"ADR-0001": "approved", "ADR-0002": "approved",
                           "ADR-0003": "rejected", "ADR-0004": "proposed"},
           "lo que architecture aprueba, sdd lo da por aprobado; cada ADR con su estado",
           f"{sa.approval_problems(p)} {estados}")
    comps = {c["id"]: c["candidates"] for c in sa.components(p)}
    expect(comps == {"C1": ["B01"], "C2": ["B02"]},
           "tras el sellado real (con la fila Producto) los componentes se leen igual",
           f"{comps}")
    comp = p / "architecture" / "components.md"
    comp.write_text(comp.read_text(encoding="utf-8").replace("registra ventas",
                                                             "registra ventas y cobros"),
                    encoding="utf-8")
    expect(any("components.md cambió" in x for x in sa.approval_problems(p)),
           "un componente editado tras aprobar: cambiada para los dos plugins",
           f"{sa.approval_problems(p)}")

    # F009-R005: los pares de los estandares (D4), copia de standard_pairs.
    (p / "architecture" / "standards.md").write_text(ARQ_STANDARDS + ESTANDAR_PROHIBIDO,
                                                     encoding="utf-8")
    codigo = ("import json, sys; sys.path.insert(0, sys.argv[1]); import architecture; "
              "print(json.dumps({k: [list(x[:3]) for x in "
              "architecture.standard_pairs(sys.argv[2], k)] "
              "for k in ('dependencia', 'prohibida')}))")
    r = subprocess.run([sys.executable, "-c", codigo, str(ARCHITECTURE.parent), str(p)],
                       capture_output=True, text=True, timeout=60)
    reales = json.loads(r.stdout) if r.returncode == 0 else r.stderr
    copia = {k: [list(x) for x in sa.standard_pairs(p, k)] for k in ("dependencia", "prohibida")}
    expect(copia == reales and copia == {"dependencia": [["C2", "C1", "S1"]],
                                         "prohibida": [["C1", "C2", "S2"], ["C1", "C3", "S2"]]},
           "los pares dependencia y prohibida coinciden con los de architecture",
           f"{copia} vs {reales}")


def plan_con_adrs(*citas, seccion=True):
    """Plan coherente de la feature 001-x que cita las decisiones dadas."""
    texto = PLAN_LISTO
    if seccion:
        texto += ("\n## Comprobación de arquitectura\n\n| Decisión | Cómo |\n| - | - |\n"
                  + "".join(f"| {c} | se respeta |\n" for c in citas))
    elif citas:
        texto += "\nApoyado en " + ", ".join(citas) + ".\n"
    return texto


def proyecto_plan(base, nombre, *citas, seccion=True, aprobado=False, arquitectura=True):
    """Feature 001-x con spec y plan, y una arquitectura aprobada si se pide."""
    p = repo_con_feature(base, nombre, spec=SPEC_LISTA)
    plan = p / "specs" / "001-x" / "plan.md"
    plan.write_text(plan_con_adrs(*citas, seccion=seccion), encoding="utf-8")
    if aprobado:
        sys.path.insert(0, str(PLUGIN / "scripts"))
        import sdd_trace
        texto = plan.read_text(encoding="utf-8")
        plan.write_text(sdd_trace.set_status(
            texto, f"Approved · {sdd_trace.content_digest(texto, 'plan.md')}")[0],
            encoding="utf-8")
    if arquitectura:
        con_arquitectura(p)
    return p


def hallazgos_de(p, code):
    return [f for f in traza(p)["findings"] if f["code"] == code]


def codigos_plan_arquitectura(base):
    """Los cuatro codigos de la feature 007, emitidos de verdad (para la cobertura)."""
    vistos = set()
    p = proyecto_plan(base, "tr-arq-codigos", "ADR-0009", "ADR-0004", seccion=False)
    vistos |= {f["code"] for f in traza(p)["findings"]}
    p = proyecto_plan(base, "tr-arq-sustituida", "ADR-0002", aprobado=True)
    d = p / "architecture" / "adr" / "0002-despliegue.md"
    texto = d.read_text(encoding="utf-8")
    d.write_text(texto.replace(architecture_lee().product.doc_status(texto),
                               "Superseded by ADR-0004"), encoding="utf-8")
    vistos |= {f["code"] for f in traza(p)["findings"]}
    return vistos & {"E-PLAN-ADR-UNKNOWN", "E-PLAN-ADR-NOT-APPROVED",
                     "W-PLAN-NO-ARCHITECTURE-CHECK", "W-PLAN-ADR-SUPERSEDED"}


def test_F007_R003_plan_cita_adr_no_aprobado(base):
    print("\nF007 · R003: el plan solo se apoya en decisiones aprobadas")
    p = proyecto_plan(base, "f007-r003-inexistente", "ADR-0009")
    h = hallazgos_de(p, "E-PLAN-ADR-UNKNOWN")
    expect(len(h) == 1 and "ADR-0009" in h[0]["message"] and h[0]["severity"] == "error",
           "citar ADR-0009, inexistente: error que la nombra", f"{h}")
    p = proyecto_plan(base, "f007-r003-propuesta", "ADR-0004")
    h = hallazgos_de(p, "E-PLAN-ADR-NOT-APPROVED")
    expect(len(h) == 1 and "ADR-0004" in h[0]["message"]
           and "/architecture:review" in h[0]["message"],
           "citar ADR-0004 propuesta: error que remite a /architecture:review", f"{h}")
    p = proyecto_plan(base, "f007-r003-rechazada", "ADR-0003")
    expect(len(hallazgos_de(p, "E-PLAN-ADR-NOT-APPROVED")) == 1,
           "citar ADR-0003 rechazada tambien es error")
    p = proyecto_plan(base, "f007-r003-aprobada", "ADR-0001")
    codigos_p = {f["code"] for f in traza(p)["findings"]}
    expect(not codigos_p & {"E-PLAN-ADR-UNKNOWN", "E-PLAN-ADR-NOT-APPROVED"},
           "citar ADR-0001 aprobada no da nada", f"{codigos_p}")


def test_F007_R004_plan_sin_comprobacion_de_arquitectura(base):
    print("\nF007 · R004: con arquitectura, el plan se contrasta con ella")
    p = proyecto_plan(base, "f007-r004-sin", "ADR-0001", seccion=False)
    h = hallazgos_de(p, "W-PLAN-NO-ARCHITECTURE-CHECK")
    expect(len(h) == 1 and h[0]["severity"] == "warning",
           "sin la seccion 'Comprobacion de arquitectura': aviso", f"{h}")
    p = proyecto_plan(base, "f007-r004-con", "ADR-0001")
    expect(not hallazgos_de(p, "W-PLAN-NO-ARCHITECTURE-CHECK"), "con la seccion: ninguno")


def test_F007_R005_adr_sustituido_tras_aprobar(base):
    print("\nF007 · R005: una decision sustituida tras aprobar el plan se avisa")
    sa = architecture_lee()
    for aprobado in (True, False):
        p = proyecto_plan(base, f"f007-r005-{'aprobado' if aprobado else 'borrador'}",
                          "ADR-0002", aprobado=aprobado)
        d = p / "architecture" / "adr" / "0002-despliegue.md"
        texto = d.read_text(encoding="utf-8")
        d.write_text(texto.replace(sa.product.doc_status(texto), "Superseded by ADR-0004"),
                     encoding="utf-8")
        avisos = hallazgos_de(p, "W-PLAN-ADR-SUPERSEDED")
        errores = hallazgos_de(p, "E-PLAN-ADR-NOT-APPROVED")
        if aprobado:
            expect(len(avisos) == 1 and "ADR-0004" in avisos[0]["message"] and not errores,
                   "plan aprobado: aviso que nombra ADR-0004 y ningun error",
                   f"{avisos} {errores}")
        else:
            expect(not avisos and len(errores) == 1,
                   "plan sin aprobar: error, no aviso", f"{avisos} {errores}")


def test_F007_R001_trace_sin_arquitectura_igual(base):
    print("\nF007 · R001: sin architecture/ la trazabilidad no cambia")
    con = proyecto_plan(base, "f007-r001-cita", "ADR-0009", "ADR-0004", seccion=False,
                        arquitectura=False)
    sin = proyecto_plan(base, "f007-r001-sin-cita", seccion=False, arquitectura=False)
    a, b = traza(con), traza(sin)
    expect(a["findings"] == b["findings"] and a["requirements"] == b["requirements"],
           "un plan que cita ADR da los mismos hallazgos que uno que no",
           f"{a['findings']} vs {b['findings']}")


def test_F007_R002_contexto_de_planificacion(base):
    print("\nF007 · R002: arch-context da al plan la arquitectura de su feature")
    p = base / "f007-contexto"
    p.mkdir()
    con_arquitectura(p)
    r = run("new", ["B02"], cwd=p)
    expect(r.returncode == 0, "se crea la feature de B02", r.stdout + r.stderr)
    data = json.loads(run("arch-context", ["--json"], cwd=p).stdout)
    expect(data["architecture"] and data["approved"] and data["candidate"] == "B02"
           and data["components_scope"] == "candidate"
           and [c["id"] for c in data["components"]] == ["C2"],
           "los componentes de la candidata: C2", f"{data.get('components')}")
    ids = [a["id"] for a in data["adrs"]]
    expect(ids == ["ADR-0001", "ADR-0002"] and "ADR-0003" not in ids,
           "las decisiones vigentes, sin la rechazada", f"{ids}")
    expect([a["id"] for a in data["proposed"]] == ["ADR-0004"],
           "la propuesta va aparte", f"{data['proposed']}")
    expect([s["id"] for s in data["standards"]] == ["S1"], "y los estandares")
    r = run("arch-context", cwd=p)
    expect(r.returncode == 0 and "C2 — Exportación" in r.stdout and "ADR-0004" in r.stdout,
           "la salida legible lista lo mismo", r.stdout)

    q = repo_con_feature(base, "f007-contexto-sin-candidata", spec=SPEC_LISTA)
    con_arquitectura(q)
    data = json.loads(run("arch-context", ["--json"], cwd=q).stdout)
    expect(data["components_scope"] == "all" and len(data["components"]) == 2,
           "una feature sin candidata recibe todos los componentes, marcados como tales")

    comp = p / "architecture" / "components.md"
    comp.write_text(comp.read_text(encoding="utf-8").replace("- **Candidatas:** B02",
                                                             "- **Candidatas:** —"),
                    encoding="utf-8")
    data = json.loads(run("arch-context", ["--json"], cwd=p).stdout)
    expect(not data["approved"] and any("components.md cambió" in x for x in data["problems"])
           and any("B02 no vive en ningún componente" in x for x in data["problems"]),
           "arquitectura cambiada y candidata sin componente: approved false y el motivo",
           f"{data['problems']}")


def test_F007_R001_contexto_sin_arquitectura(base):
    print("\nF007 · R001: arch-context sin architecture/")
    p = repo_con_feature(base, "f007-contexto-vacio", spec=SPEC_LISTA)
    r = run("arch-context", ["--json"], cwd=p)
    expect(r.returncode == 0 and json.loads(r.stdout) == {"architecture": False},
           "{'architecture': false} con salida 0", r.stdout + r.stderr)


def test_F007_R006_propone_una_decision(base):
    print("\nF007 · R006: sdd propone una decision sin aprobarla")
    sa = architecture_lee()
    adrs_hasta_3 = {k: v for k, v in ADRS_BASE.items() if not k.startswith("0004")}
    p = repo_con_feature(base, "f007-propuesta", spec=SPEC_LISTA)
    con_arquitectura(p, adrs=adrs_hasta_3)
    r = run("propose-adr", ["Cola de exportaciones en segundo plano"], cwd=p)
    salida = json.loads(r.stdout) if r.returncode == 0 else {}
    expect(salida.get("id") == "ADR-0004"
           and salida.get("file") == "architecture/adr/0004-cola-exportaciones-segundo-plano.md",
           "con ADR-0001 a ADR-0003, crea ADR-0004", r.stdout + r.stderr)
    adrs = {a["id"]: a for a in sa.adrs(p)}
    texto = (p / salida.get("file", "x")).read_text(encoding="utf-8") if salida else ""
    expect(adrs.get("ADR-0004", {}).get("state") == "proposed"
           and "| Propuesto por | `specs/001-x/plan.md` |" in texto
           and "| Estado        | Proposed |" in texto,
           "queda propuesta, con el plan de la feature activa como origen", texto[:400])
    expect(sa.approval_problems(p) == [],
           "una propuesta no rompe la aprobacion del conjunto: se decide aparte",
           f"{sa.approval_problems(p)}")
    expect(sa.next_adr(p) == "ADR-0005", "y su numero queda ocupado")

    q = repo_con_feature(base, "f007-propuesta-sin-arq", spec=SPEC_LISTA)
    r = run("propose-adr", ["Algo"], cwd=q)
    expect(r.returncode == 1 and "No hay architecture/" in r.stderr
           and not (q / "architecture").exists(),
           "sin architecture/: sale con 1 y no crea nada", r.stderr)
    expect(run("propose-adr", [], cwd=p).returncode == 2, "sin titulo: uso y salida 2")

    sin_feature = base / "f007-propuesta-sin-feature"
    sin_feature.mkdir()
    con_arquitectura(sin_feature)
    r = run("propose-adr", ["Algo"], cwd=sin_feature)
    expect(r.returncode == 1 and "No hay una feature activa" in r.stderr
           and sa.next_adr(sin_feature) == "ADR-0005",
           "sin feature activa: sale con 1 y no crea nada", r.stderr)
    r = run("propose-adr", ["¿?!"], cwd=p)
    expect(r.returncode == 0 and json.loads(r.stdout)["file"].endswith("0005-decision.md"),
           "un titulo sin letras ni cifras da un nombre de reserva", r.stdout)

    if ARCHITECTURE.is_file():
        # Contrato: el architecture real reconoce la propuesta y solo pide
        # rellenar sus huecos de plantilla.
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(p),
                   CLAUDE_PLUGIN_ROOT=str(ARCHITECTURE.parent.parent))
        r = subprocess.run([sys.executable, str(ARCHITECTURE), "check", "--json"],
                           capture_output=True, text=True, cwd=str(p), env=env, timeout=60)
        de_la_propuesta = {f["code"] for f in json.loads(r.stdout)["findings"]
                           if "0004-" in f["artifact"]}
        expect(de_la_propuesta == {"E-ARCH-TEMPLATE"},
               "architecture lee la propuesta de sdd y solo senala sus huecos",
               f"{de_la_propuesta}")


def test_F007_R007_origen_con_componentes(base):
    print("\nF007 · R007: el traspaso registra los componentes de la candidata")
    p = base / "f007-r007"
    p.mkdir()
    con_arquitectura(p)
    r = run("new", ["B02"], cwd=p)
    salida = json.loads(r.stdout) if r.returncode == 0 else {}
    spec = (p / "specs" / "001-exportar-movimientos" / "spec.md").read_text(encoding="utf-8") \
        if salida else ""
    expect("| Origen | B02 · G2 · D1§4 · C2 |" in spec,
           "| Origen | B02 · G2 · D1§4 · C2 |", r.stdout + r.stderr)
    expect(salida.get("origin", {}).get("components") == ["C2"]
           and salida.get("context", {}).get("components") == ["C2"],
           "el JSON de new trae los componentes en origin y context")


def test_F007_R008_traspaso_sin_arquitectura_lista(base):
    print("\nF007 · R008: el traspaso se niega si la arquitectura no esta lista")
    sin_b02 = ARQ_COMPONENTS.replace("- **Candidatas:** B02", "- **Candidatas:** —")
    p = base / "f007-r008-sin-componente"
    p.mkdir()
    con_arquitectura(p, components=sin_b02)
    ok, err = niega(p, "B02", "B02 no vive en ningún componente", "/architecture:init")
    expect(ok, "B02 sin componente: no se crea y se dice que se corrige en architecture", err)

    p = base / "f007-r008-sin-aprobar"
    p.mkdir()
    con_arquitectura(p, aprobada=False)
    ok, err = niega(p, "B02", "la arquitectura no está aprobada", "/architecture:approve")
    expect(ok, "arquitectura sin aprobar: no se crea y se remite a /architecture:approve", err)

    p = base / "f007-r008-cambiada"
    p.mkdir()
    con_arquitectura(p)
    comp = p / "architecture" / "components.md"
    comp.write_text(comp.read_text(encoding="utf-8").replace("registra ventas",
                                                             "registra ventas y cobros"),
                    encoding="utf-8")
    ok, err = niega(p, "B02", "components.md cambió después de aprobarse",
                    "/architecture:approve")
    expect(ok, "arquitectura cambiada tras aprobarse: no se crea y se dice cual", err)


def test_F007_R001_traspaso_sin_arquitectura_igual(base):
    print("\nF007 · R001: sin architecture/, el traspaso es el de siempre")
    p = con_producto(base / "f007-r001-traspaso")
    r = run("new", ["B02"], cwd=p)
    spec = (p / "specs" / "001-exportar-movimientos" / "spec.md").read_text(encoding="utf-8")
    expect("| Origen | B02 · G2 · D1§4 |\n" in spec
           and "components" not in json.loads(r.stdout)["origin"],
           "Origen de tres grupos y sin componentes en el JSON", spec[:400])


# ------------------------------------------- feature 009: diagramas en el plan

PLANTILLA_PLAN = PLUGIN / "templates" / "plan.md"


def seccion_diagramas():
    """La seccion ## Diagramas de la plantilla del plan, tal cual."""
    texto = PLANTILLA_PLAN.read_text(encoding="utf-8")
    inicio = texto.index("## Diagramas")
    fin = texto.index("\n## ", inicio + 1)
    return texto[inicio:fin].rstrip() + "\n"


def no_aplica(seccion):
    """La seccion con los tres apartados cerrados con «No aplica.»."""
    return "\n".join("No aplica." if l.startswith("_Bloque mermaid") else l
                      for l in seccion.splitlines()) + "\n"


def test_F009_R001_seccion_de_diagramas(base):
    print("\nF009 · R001: el plan tiene un lugar para sus diagramas")
    seccion = seccion_diagramas()
    for apartado, tipo in (("### Secuencia", "sequenceDiagram"),
                           ("### Modelo de datos", "erDiagram"),
                           ("### Clases", "classDiagram")):
        expect(apartado in seccion and tipo in seccion,
               f"la plantilla tiene {apartado} con {tipo}", seccion)
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd
    import sdd_trace
    expect(not sdd_trace.ADR_REF.search(seccion) and not sdd_trace.REQ_ID.search(seccion),
           "la seccion no cita un ADR ni un requisito literal")
    p = repo_con_feature(base, "f009-r001-huecos", spec=SPEC_LISTA, archivos={
        "specs/001-x/plan.md": PLAN_LISTO + "\n" + seccion})
    huecos = hallazgos_de(p, "E-PLAN-TEMPLATE")
    problemas = sdd.phase_problems(p / "specs" / "001-x", "plan")
    expect(len(huecos) == 1 and re.search(r"\b3 hueco", huecos[0]["message"])
           and any("hueco" in x for x in problemas),
           "con los tres huecos sin tocar: E-PLAN-TEMPLATE y la compuerta no lo aprueba",
           f"{huecos} {problemas}")
    p = repo_con_feature(base, "f009-r001-no-aplica", spec=SPEC_LISTA, archivos={
        "specs/001-x/plan.md": PLAN_LISTO + "\n" + no_aplica(seccion)})
    expect(not hallazgos_de(p, "E-PLAN-TEMPLATE")
           and sdd.phase_problems(p / "specs" / "001-x", "plan") == [],
           "con «No aplica.» en los tres apartados: ningun hueco",
           f"{hallazgos_de(p, 'E-PLAN-TEMPLATE')}")


def feature_con_plan(base, nombre, plan, candidata="B01", arquitectura=True):
    """Proyecto con producto (y arquitectura), la feature de la candidata (o una
    descripcion libre si candidata es None) y su plan.md. Devuelve (p, plan)."""
    p = base / nombre
    p.mkdir()
    if arquitectura:
        con_arquitectura(p)
    else:
        con_producto(p)
    r = run("new", [candidata or "informe libre de prueba"], cwd=p)
    feature = p / json.loads(r.stdout)["dir"]
    (feature / "plan.md").write_text(plan, encoding="utf-8")
    return p, feature / "plan.md"


def secuencia(texto):
    """Cuerpo del apartado ### Secuencia del plan."""
    m = re.search(r"^### Secuencia\n(.*?)(?=^#{2,3} |\Z)", texto, re.M | re.S)
    return m.group(1) if m else ""


def test_F009_R002_esqueleto_con_componentes(base):
    print("\nF009 · R002: el esqueleto de secuencia trae los componentes de la feature")
    p, plan = feature_con_plan(base, "f009-r002", PLAN_LISTO + "\n" + seccion_diagramas())
    r = run("diagram", cwd=p)
    cuerpo = secuencia(plan.read_text(encoding="utf-8"))
    expect(r.returncode == 0 and "```mermaid\nsequenceDiagram\n  participant C1 as Ventas\n"
           in cuerpo and "C2" not in cuerpo.split("%%")[0],
           "una feature de B01: participant C1 as Ventas, y solo C1", r.stdout + r.stderr + cuerpo)
    huecos = [h for h in hallazgos_de(p, "E-PLAN-TEMPLATE")]
    adr = hallazgos_de(p, "E-PLAN-ADR-UNKNOWN") + hallazgos_de(p, "E-PLAN-ADR-NOT-APPROVED")
    expect(len(huecos) == 1 and "%% _Completa" in huecos[0]["message"] and not adr,
           "sin completar: E-PLAN-TEMPLATE por el hueco, y ninguna cita de ADR falsa",
           f"{huecos} {adr}")
    texto = plan.read_text(encoding="utf-8")
    texto = re.sub(r"^  %% _Completa.*$", "  actor U as Dueño\n  U->>C1: cierra la caja (D1)",
                   texto, flags=re.M)
    plan.write_text(no_aplica(texto), encoding="utf-8")
    expect(not hallazgos_de(p, "E-PLAN-TEMPLATE")
           and not [f for f in traza(p)["findings"] if "DIAGRAM" in f["code"]],
           "completado: ningun hueco ni hallazgo de diagramas", f"{traza(p)['findings']}")

    p, plan = feature_con_plan(base, "f009-r002-libre", PLAN_LISTO + "\n" + seccion_diagramas(),
                               candidata=None)
    r = run("diagram", cwd=p)
    cuerpo = secuencia(plan.read_text(encoding="utf-8"))
    expect(r.returncode == 0 and "  participant " not in cuerpo
           and "C1 (Ventas), C2 (Exportación)" in cuerpo,
           "sin candidata: ningun participante, y el hueco lista los componentes", cuerpo)

    p, plan = feature_con_plan(base, "f009-r002-sin-seccion", PLAN_LISTO)
    r = run("diagram", cwd=p)
    texto = plan.read_text(encoding="utf-8")
    expect(r.returncode == 0 and texto.startswith(PLAN_LISTO.rstrip("\n"))
           and texto.rstrip().endswith("o «No aplica.»_")
           and "participant C1 as Ventas" in secuencia(texto)
           and "### Modelo de datos" in texto and "### Clases" in texto,
           "un plan anterior sin la seccion la recibe al final, con el esqueleto", texto)

    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_trace
    aprobado = sdd_trace.set_status(PLAN_LISTO, "Approved · "
                                    + sdd_trace.content_digest(PLAN_LISTO, "plan.md"))[0]
    p, plan = feature_con_plan(base, "f009-r002-aprobado", aprobado)
    r = run("diagram", cwd=p)
    expect(r.returncode == 0 and "participant C1" in plan.read_text(encoding="utf-8")
           and "estaba aprobado" in r.stdout and "/sdd:approve" in r.stdout
           and "tasks.md" in r.stdout,
           "un plan aprobado se escribe, y se avisa de volver a aprobarlo", r.stdout)

    # El traspaso exige la arquitectura aprobada: se cambia despues de crear la feature.
    p, plan = feature_con_plan(base, "f009-r002-sin-aprobar", PLAN_LISTO)
    comp = p / "architecture" / "components.md"
    comp.write_text(comp.read_text(encoding="utf-8").replace("registra ventas",
                                                             "registra ventas y cobros"),
                    encoding="utf-8")
    r = run("diagram", cwd=p)
    expect(r.returncode == 1 and "no está aprobada" in r.stderr
           and "components.md cambió" in r.stderr
           and plan.read_text(encoding="utf-8") == PLAN_LISTO,
           "arquitectura sin aprobar: sale con 1, dice por que y no escribe", r.stderr)
    plan.unlink()
    r = run("diagram", cwd=p)
    expect(r.returncode == 1 and "/sdd:plan" in r.stderr,
           "sin plan.md: sale con 1 y remite a /sdd:plan", r.stderr)

    import sdd
    bloque = sdd.sequence_skeleton({"components_scope": "candidate", "components": [
        {"id": "C3", "title": "Cobros; pagos"}]})
    expect("  participant C3 as Cobros#59; pagos\n" in bloque,
           "un ; en el nombre se escribe #59;, que Mermaid no toma por separador", bloque)


def test_F009_R003_no_sobrescribe(base):
    print("\nF009 · R003: un plan con diagramas no se sobrescribe")
    p, plan = feature_con_plan(base, "f009-r003", PLAN_LISTO + "\n" + seccion_diagramas())
    run("diagram", cwd=p)
    antes = plan.read_bytes()
    r = run("diagram", cwd=p)
    expect(r.returncode == 0 and plan.read_bytes() == antes and "ya tenía" in r.stdout,
           "un segundo diagram deja el plan igual byte a byte y lo dice", r.stdout + r.stderr)
    sin_secuencia = re.sub(r"### Secuencia\n\n[^\n]*\n\n", "", seccion_diagramas())
    p, plan = feature_con_plan(base, "f009-r003-sin-apartado", PLAN_LISTO + "\n" + sin_secuencia)
    antes = plan.read_bytes()
    r = run("diagram", cwd=p)
    expect(r.returncode == 0 and plan.read_bytes() == antes and "### Secuencia" in r.stdout,
           "una seccion sin el apartado de secuencia no se toca, y se dice", r.stdout)
    p, plan = feature_con_plan(base, "f009-r003-no-aplica",
                               PLAN_LISTO + "\n" + no_aplica(seccion_diagramas()))
    antes = plan.read_bytes()
    r = run("diagram", cwd=p)
    expect(r.returncode == 0 and plan.read_bytes() == antes and "ya tenía" in r.stdout,
           "un apartado con «No aplica.» tampoco se toca", r.stdout + r.stderr)


def test_F009_R007_sin_arquitectura(base):
    print("\nF009 · R007: sin architecture/ no hay esqueleto")
    p, plan = feature_con_plan(base, "f009-r007", PLAN_LISTO + "\n" + seccion_diagramas(),
                               arquitectura=False)
    antes = plan.read_bytes()
    r = run("diagram", cwd=p)
    expect(r.returncode == 0 and plan.read_bytes() == antes and "architecture/" in r.stdout,
           "diagram sale con 0, no escribe y dice que hace falta arquitectura",
           r.stdout + r.stderr)


def plan_con_secuencia(base, nombre, cuerpo, arquitectura=True, estandares=None):
    """Feature 001-x con un plan cuyo diagrama de secuencia es cuerpo, sobre la
    arquitectura de prueba (con otros estandares si se dan)."""
    plan = (PLAN_LISTO + "\n## Comprobación de arquitectura\n\n| Decisión | Cómo |\n"
            "| - | - |\n| ADR-0001 | se respeta |\n\n"
            + no_aplica(seccion_diagramas()).replace(
                "### Secuencia\n\nNo aplica.\n",
                "### Secuencia\n\n```mermaid\nsequenceDiagram\n" + cuerpo + "```\n", 1))
    p = repo_con_feature(base, nombre, spec=SPEC_LISTA,
                         archivos={"specs/001-x/plan.md": plan})
    if arquitectura:
        con_arquitectura(p)
        if estandares:
            (p / "architecture" / "standards.md").write_text(estandares, encoding="utf-8")
    return p


SECUENCIA_COHERENTE = """  actor U as Dueño
  participant C2 as Exportación
  participant C1 as Ventas
  U->>C2: exporta el mes (D1)
  C2->>C1: movimientos del mes (ADR-0001)
  C1-->>C2: movimientos
  C2-->>U: archivo
"""


def codigos_plan_diagramas(base):
    """Los tres codigos de la feature 009, emitidos de verdad (para la cobertura)."""
    vistos = set()
    p = plan_con_secuencia(base, "tr-diag-codigos",
                           "  participant C7 as Otro\n  C1->>C2: al reves (D1)\n")
    vistos |= {f["code"] for f in traza(p)["findings"]}
    p = proyecto_plan(base, "tr-diag-sin", "ADR-0001")
    vistos |= {f["code"] for f in traza(p)["findings"]}
    return vistos & {"E-PLAN-DIAGRAM-UNKNOWN", "E-PLAN-DIAGRAM-VIOLATION", "W-PLAN-NO-DIAGRAMS"}


def diagramas(p):
    return [f for f in traza(p)["findings"] if "DIAGRAM" in f["code"]]


def test_F009_R004_componente_inexistente(base):
    print("\nF009 · R004: un componente inexistente en el diagrama se nombra")
    p = plan_con_secuencia(base, "f009-coherente", SECUENCIA_COHERENTE)
    errores = [f for f in traza(p)["findings"] if f["severity"] == "error"
               and f["code"].startswith("E-PLAN")]
    expect(not diagramas(p) and not errores,
           "un diagrama que respeta la arquitectura no da hallazgos de plan", f"{errores}")
    p = plan_con_secuencia(base, "f009-r004", "  participant C1 as Ventas\n"
                           "  participant C7 as Facturación\n  C1->>C7: factura (D1)\n"
                           "  C1->>C8: avisa (D1)\n")
    h = hallazgos_de(p, "E-PLAN-DIAGRAM-UNKNOWN")
    expect(len(h) == 2 and "C7" in h[0]["message"] and "C8" in h[1]["message"]
           and h[0]["severity"] == "error",
           "C7 declarado y C8 solo en un mensaje: un error que nombra cada uno", f"{h}")


def test_F009_R005_llamada_contra_estandar(base):
    print("\nF009 · R005: una llamada contra un estandar nombra el estandar")
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_trace
    nombres, llamadas = sdd_trace.sequence_graph(
        "participant A\nactor U as Usuario\ncreate participant N\n"
        "A->>B: a\nB-->>A: b\nA->C: c\nC-->A: d\nA-xD: e\nA--xD: f\nA-)E: g\n"
        "A--)E: h\nF<<->>G: i\nH<<-->>I: j\nA->>+J: k\nJ-->>-A: l\n"
        "Note over A,B: nota\nloop cada dia\nend\n%% A->>Z: comentario\n")
    expect(set(llamadas) == {("A", "B"), ("A", "C"), ("A", "D"), ("A", "E"), ("F", "G"),
                             ("G", "F"), ("A", "J")}
           and nombres >= {"A", "U", "N", "B", "J"} and "Z" not in nombres,
           "solo las flechas continuas son llamadas; respuestas, notas y comentarios no",
           f"{nombres} {llamadas}")
    p = plan_con_secuencia(base, "f009-r005", "  participant C1 as Ventas\n"
                           "  participant C2 as Exportación\n  C1->>C2: pide (D1)\n")
    h = hallazgos_de(p, "E-PLAN-DIAGRAM-VIOLATION")
    expect(len(h) == 1 and "S1" in h[0]["message"] and "C1 a C2" in h[0]["message"],
           "C1->>C2 contra S1 (C2 -> C1): un error que nombra S1", f"{h}")
    expect(sdd_trace.diagram_kind("---\ntitle: x\n---\n%%{init: {}}%%\nsequenceDiagram\n")
           == "sequenceDiagram", "el frontmatter y las directivas no ocultan el tipo")
    p = plan_con_secuencia(base, "f009-r005-respuesta", "  C1-->>C2: totales\n")
    expect(not hallazgos_de(p, "E-PLAN-DIAGRAM-VIOLATION"),
           "la respuesta C1-->>C2 no es una dependencia")
    p = plan_con_secuencia(base, "f009-r005-prohibida",
                           "  participant C1 as Ventas\n  C1-)C2: avisa (D1)\n",
                           estandares=ARQ_STANDARDS.replace(
                               "- **Detalle:** C2 → C1", "- **Detalle:** C3 → C2")
                           + ESTANDAR_PROHIBIDO)
    h = hallazgos_de(p, "E-PLAN-DIAGRAM-VIOLATION")
    expect(len(h) == 1 and "S2" in h[0]["message"] and "prohibe" in h[0]["message"],
           "una llamada prohibida por S2: un error que nombra S2", f"{h}")


def test_F009_R006_sin_diagramas_avisa(base):
    print("\nF009 · R006: un plan sin diagramas solo avisa")
    p = proyecto_plan(base, "f009-r006", "ADR-0001")
    h = hallazgos_de(p, "W-PLAN-NO-DIAGRAMS")
    expect(len(h) == 1 and h[0]["severity"] == "warning"
           and not [f for f in diagramas(p) if f["severity"] == "error"],
           "sin la seccion: un aviso y ningun error de diagramas", f"{diagramas(p)}")
    nota = "\n## Diagramas\n\n> Solo una nota.\n"
    p = repo_con_feature(base, "f009-r006-nota", spec=SPEC_LISTA,
                         archivos={"specs/001-x/plan.md": PLAN_LISTO + nota})
    expect(len(hallazgos_de(p, "W-PLAN-NO-DIAGRAMS")) == 1,
           "una seccion con solo notas tambien avisa")
    p = repo_con_feature(base, "f009-r006-no-aplica", spec=SPEC_LISTA, archivos={
        "specs/001-x/plan.md": PLAN_LISTO + "\n" + no_aplica(seccion_diagramas())})
    expect(not hallazgos_de(p, "W-PLAN-NO-DIAGRAMS"),
           "con «No aplica.» declarado, ningun aviso")


def test_F009_R007_trace_sin_arquitectura(base):
    print("\nF009 · R007: sin architecture/ los diagramas no se contrastan")
    p = plan_con_secuencia(base, "f009-r007-trace", "  participant C7 as Otro\n"
                           "  C1->>C2: al reves (D1)\n", arquitectura=False)
    expect(not diagramas(p), "ningun hallazgo de diagramas sin arquitectura",
           f"{diagramas(p)}")


def test_F009_R008_pide_citar_la_decision(base):
    print("\nF009 · R008: al completar los diagramas se pide citar la decision")
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd
    for alcance in ("candidate", "all"):
        bloque = sdd.sequence_skeleton({"components_scope": alcance, "components": [
            {"id": "C1", "title": "Ventas"}]})
        hueco = [x for x in bloque.splitlines() if x.lstrip().startswith("%%")]
        expect(len(hueco) == 1 and "cita en cada llamada entre componentes la decisión"
               in hueco[0] and "(Dn) o el ADR" in hueco[0],
               f"el hueco del esqueleto ({alcance}) pide citar la Dn o el ADR", bloque)
    skill = (PLUGIN / "skills" / "plan" / "SKILL.md").read_text(encoding="utf-8")
    expect("Cada llamada entre componentes cita en su texto la decisión" in skill
           and "(ADR-0001)" in skill,
           "la skill del plan pide citar la decision en cada llamada, con un ejemplo")


def test_F010_R017_tipo(base):
    print("\nF010 · R017: la spec nace con la fila Tipo")
    p = base / "f010-tipo"
    p.mkdir()
    r = run("new", ["exportar ventas"], cwd=p)
    feature = json.loads(r.stdout)["feature"] if r.returncode == 0 else None
    expect(feature is not None, "new crea la feature", r.stdout + r.stderr)
    if feature:
        spec = (p / "specs" / feature / "spec.md").read_text(encoding="utf-8")
        cabecera = spec.split("\n## ", 1)[0]
        expect(re.search(r"^\| Estado \|[^\n]*\n\| Tipo   \| funcionalidad \|$", cabecera, re.M),
               "Tipo en funcionalidad, tras Estado", cabecera)
        if str(PLUGIN / "scripts") not in sys.path:
            sys.path.insert(0, str(PLUGIN / "scripts"))
        import sdd_trace
        huecos = [linea for _, linea in sdd_trace.find_placeholders(cabecera, "spec.md")]
        expect(not any("Tipo" in h for h in huecos), "la fila Tipo no es un hueco", f"{huecos}")

    p = con_producto(base / "f010-tipo-candidata")
    run("new", ["B02"], cwd=p)
    spec = (p / "specs" / "001-exportar-movimientos" / "spec.md").read_text(encoding="utf-8")
    cabecera = spec.split("\n## ", 1)[0]
    expect("| Tipo   | funcionalidad |\n| Issue  | —            |\n| Origen | B02 · G2 · D1§4 |\n"
           in cabecera, "el traspaso desde la candidata conserva Tipo junto a Origen", cabecera)
    skill = (PLUGIN / "skills" / "specify" / "SKILL.md").read_text(encoding="utf-8")
    expect("`corrección`" in skill and "`Tipo`" in skill,
           "la skill dice cuándo cambiarla a corrección")


def test_F010_R018_trace_de_otra_feature(base):
    print("\nF010 · R018: trace --feature traza otra feature sin cambiar la activa")
    p = repo_dos_features(base, "f010-trace-feature")
    (p / "specs" / "001-a" / "spec.md").write_text(SPEC_BASE, encoding="utf-8")
    actual = p / ".sdd" / "current"
    antes = actual.read_text()
    con_opcion = {arg: run("trace", ["--feature", arg, "--json"], cwd=p)
                  for arg in ("001", "001-a")}
    check_opcion = run("trace", ["--check", "--feature", "001"], cwd=p)
    expect(actual.read_text() == antes, ".sdd/current no cambia", actual.read_text())
    actual.write_text("001-a\n")
    activa = run("trace", ["--json"], cwd=p)
    check_activa = run("trace", ["--check"], cwd=p)
    for arg, r in con_opcion.items():
        expect(r.returncode == activa.returncode and r.stdout == activa.stdout
               and json.loads(r.stdout)["requirements"],
               f"--feature {arg} da el mismo JSON que con la 001 activa", r.stdout + r.stderr)
    expect(check_opcion.returncode == check_activa.returncode == 1
           and check_opcion.stdout == check_activa.stdout,
           "--check se comporta igual", f"{check_opcion.returncode} {check_activa.returncode}")

    actual.write_text("002-b\n")
    r = run("trace", ["--feature", "042", "--json"], cwd=p)
    expect(r.returncode == 1 and "042" in r.stderr and not r.stdout.strip(),
           "--feature 042 sale con 1 y la nombra", r.stdout + r.stderr)
    r = run("trace", ["--feature=001-a", "--json"], cwd=p)
    expect(r.returncode == 0 and json.loads(r.stdout)["requirements"],
           "--feature=001-a también vale", r.stdout + r.stderr)
    (p / "specs" / "001-otra").mkdir()
    r = run("trace", ["--feature", "001", "--json"], cwd=p)
    expect(r.returncode == 1 and "001-a" in r.stderr and "001-otra" in r.stderr,
           "dos features con el mismo número: sale con 1 y las nombra", r.stdout + r.stderr)
    r = run("trace", ["--feature", "001-otra", "--json"], cwd=p)
    expect(r.returncode == 0, "con el nombre completo no hay ambigüedad", r.stderr)
    r = run("trace", ["--feature"], cwd=p)
    expect(r.returncode == 1 and "--feature" in r.stderr, "--feature sin valor sale con 1", r.stderr)
    expect(actual.read_text() == "002-b\n", "y la activa sigue siendo la 002")


# ------------------------------------------- feature 011: traspaso desde operate
# Un incidente con su postmortem en el formato de operate (copia de su
# plantilla): sdd lee esos archivos, no importa codigo de operate.

OPERATE = PLUGIN.parent / "operate" / "scripts" / "operate.py"

INCIDENTE = """# Incidente I001 — Caída del resumen diario

| Campo            | Valor |
| ---------------- | ----- |
| Estado           | Draft |
| ID               | I001 |
| Fecha            | 2026-10-25 |
| Versión afectada | 0.4.0 |
| Severidad        | alta |

## Qué pasó

El resumen diario dejó de aparecer al cerrar la caja.

## Impacto

Los dueños no vieron el total del día durante dos horas.

## Cronología

10:00 detección; 12:00 recuperación.

## Causas

La caché de totales no se invalidaba al cambiar de día.

## Acciones

### I001-A1 — Invalidar la caché al cambiar de día

- **Qué:** borrar la entrada del día anterior a medianoche.

### I001-A2 — Alarma de latencia

- **Qué:** avisar si el resumen tarda más de 2 segundos.
"""


def con_incidente(p, aprobado=True, registro=True, version="0.4.0"):
    """Pone en p un operations/ de operate con el incidente I001."""
    d = p / "operations" / "incidents"
    d.mkdir(parents=True)
    if registro:
        (p / "operations" / "incidents.md").write_text(
            "# Registro de incidentes\n\n| ID | Fecha | Título | Archivo |\n| - | - | - | - |\n"
            "| I001 | 2026-10-25 | Caída del resumen | incidents/I001-caida.md |\n",
            encoding="utf-8")
    (d / "I001-caida.md").write_text(INCIDENTE.replace("| 0.4.0 |", f"| {version} |"),
                                     encoding="utf-8")
    if aprobado:
        sella(d / "I001-caida.md")
    return p


def test_F011_R013_feature_desde_accion(base):
    print("\nF011 · R013: /sdd:specify I001-A2 crea una corrección desde la acción")
    p = base / "f011-r013"
    p.mkdir()
    con_incidente(p)
    r = run("new", ["i001-a2"], cwd=p)
    data = json.loads(r.stdout) if r.returncode == 0 else {}
    expect(r.returncode == 0 and data.get("feature") == "001-alarma-latencia"
           and data.get("origin") == {"action": "I001-A2", "incident": "I001",
                                      "version": "0.4.0"},
           "la feature toma el nombre de la acción y el JSON trae su origen", r.stdout + r.stderr)
    if r.returncode != 0:
        return
    spec = (p / "specs" / "001-alarma-latencia" / "spec.md").read_text(encoding="utf-8")
    cabecera = spec.split("\n## ", 1)[0]
    expect("| Tipo   | corrección |" in cabecera
           and "| Issue  | —            |\n| Origen | I001-A2 · 0.4.0 |\n" in cabecera,
           "Tipo corrección y la fila Origen con la acción y la versión", cabecera)
    problema = spec.split("## Problema\n", 1)[1].split("\n## ", 1)[0]
    expect("El resumen diario dejó de aparecer" in problema and "dos horas" in problema
           and "I001-A2" in problema and "más de 2 segundos" in problema,
           "el problema cuenta el incidente, su impacto y la acción", problema)
    contexto = spec.split("## Contexto\n", 1)[1].split("\n## ", 1)[0]
    expect("I001" in contexto and "0.4.0" in contexto and "caché de totales" in contexto,
           "el contexto cita el incidente, la versión y las causas", contexto)
    expect((p / ".sdd" / "current").read_text().strip() == "001-alarma-latencia",
           "y queda como feature activa")

    q = base / "f011-r013-desconocida"
    q.mkdir()
    con_incidente(q, version="desconocida")
    run("new", ["I001-A1"], cwd=q)
    spec = next((q / "specs").iterdir()) / "spec.md"
    expect("| Origen | I001-A1 · — |" in spec.read_text(encoding="utf-8"),
           "con la versión desconocida, el segundo grupo es —")


def test_F011_R014_traspaso_denegado(base):
    print("\nF011 · R014: sin postmortem aprobado, acción inexistente o con feature, nada")
    casos = []
    p = base / "f011-r014-sin-aprobar"
    p.mkdir()
    con_incidente(p, aprobado=False)
    casos.append((p, "I001-A2", ("no está aprobado", "/operate:approve")))
    p = base / "f011-r014-cambiado"
    p.mkdir()
    con_incidente(p)
    f = p / "operations" / "incidents" / "I001-caida.md"
    f.write_text(f.read_text(encoding="utf-8").replace("dos horas", "tres horas"),
                 encoding="utf-8")
    casos.append((p, "I001-A2", ("cambió después de aprobarse",)))
    p = base / "f011-r014-inexistente"
    p.mkdir()
    con_incidente(p)
    casos.append((p, "I001-A9", ("I001-A9 no existe",)))
    casos.append((p, "I009-A1", ("I009 no existe",)))
    for p, arg, fragmentos in casos:
        r = run("new", [arg], cwd=p)
        expect(r.returncode == 1 and all(x in r.stderr for x in fragmentos)
               and not (p / "specs").exists() and not (p / ".sdd").exists(),
               f"{p.name} {arg}: sale con 1, lo dice y no crea nada", r.stdout + r.stderr)

    p = base / "f011-r014-con-feature"
    p.mkdir()
    con_incidente(p)
    run("new", ["I001-A2"], cwd=p)
    antes = sorted(x.name for x in (p / "specs").iterdir())
    r = run("new", ["I001-A2"], cwd=p)
    expect(r.returncode == 1 and "001-alarma-latencia" in r.stderr
           and sorted(x.name for x in (p / "specs").iterdir()) == antes,
           "la acción que ya tiene feature: se nombra la feature y no se crea otra",
           r.stdout + r.stderr)


def test_F011_R018_sin_registro_igual(base):
    print("\nF011 · R018: sin el registro de incidentes, I001-A2 es una descripción")
    p = base / "f011-r018"
    p.mkdir()
    con_incidente(p, registro=False)
    r = run("new", ["I001-A2"], cwd=p)
    data = json.loads(r.stdout) if r.returncode == 0 else {}
    spec = (p / data["spec"]).read_text(encoding="utf-8") if data else ""
    expect(r.returncode == 0 and data.get("feature") == "001-i001-a2" and "origin" not in data
           and "| Origen |" not in spec and "| Tipo   | funcionalidad |" in spec,
           "se crea como cualquier descripción de texto, como antes", r.stdout + r.stderr)


def test_F011_R013_contrato_con_operate(base):
    print("\nF011 · R013: la lectura de sdd coincide con el operate real")
    if not OPERATE.is_file():
        print("  (sin plugins/operate en el repositorio: prueba de contrato omitida)")
        return
    p = base / "f011-contrato"
    p.mkdir()
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(p),
               CLAUDE_PLUGIN_ROOT=str(OPERATE.parent.parent))

    def operate(*args):
        return subprocess.run([sys.executable, str(OPERATE), *args], capture_output=True,
                              text=True, cwd=str(p), env=env, timeout=60)

    r = operate("incident", "Caída del resumen diario")
    archivo = p / json.loads(r.stdout)["file"] if r.returncode == 0 else None
    if not expect(archivo is not None, "operate registra el incidente", r.stdout + r.stderr):
        return
    cuerpo = INCIDENTE.split("\n## ", 1)[1]
    cabecera = archivo.read_text(encoding="utf-8").split("\n## ", 1)[0]
    cabecera = re.sub(r"\| Fecha            \| _[^|]*_ \|", "| Fecha            | 2026-10-25 |",
                      cabecera)
    cabecera = re.sub(r"\| Versión afectada \| _[^|]*_ \|",
                      "| Versión afectada | desconocida |", cabecera)
    cabecera = re.sub(r"\| Severidad        \| _[^|]*_ \|", "| Severidad        | alta |",
                      cabecera)
    archivo.write_text(cabecera + "\n## " + cuerpo, encoding="utf-8")
    op = _operate_lee()
    expect(op.incident(p, "I001")["state"] == "draft", "antes de aprobar, en borrador")
    r = operate("approve", "I001")
    expect(r.returncode == 0, "operate aprueba el postmortem", r.stdout + r.stderr)
    inc = op.incident(p, "I001")
    expect(inc["state"] == "approved" and op.has_registry(p),
           "lo que operate aprueba, sdd lo da por aprobado, con su registro", f"{inc['state']}")
    expect(op.action(inc["text"], "I001-A2")
           == {"id": "I001-A2", "title": "Alarma de latencia",
               "what": "avisar si el resumen tarda más de 2 segundos."},
           "la acción se lee igual", f"{op.action(inc['text'], 'I001-A2')}")
    siguiente = operate("next-action", "I001").stdout.strip()
    expect(siguiente == "I001-A3", "next-action de operate sigue las acciones que lee sdd",
           siguiente)
    r = run("new", ["I001-A1"], cwd=p)
    expect(r.returncode == 0, "sdd crea la corrección desde el incidente real", r.stderr)
    avisos = [f["message"] for f in json.loads(operate("check", "--json").stdout)["findings"]
              if f["code"] == "W-INCIDENT-ACTION-NO-FEATURE"]
    expect(len(avisos) == 1 and "I001-A2" in avisos[0],
           "operate ve que I001-A1 ya tiene feature y avisa solo de I001-A2", f"{avisos}")
    archivo.write_text(archivo.read_text(encoding="utf-8").replace("dos horas", "tres horas"),
                       encoding="utf-8")
    expect(op.incident(p, "I001")["state"] == "stale",
           "editado tras aprobar: cambiado para los dos plugins")


def _operate_lee():
    if str(PLUGIN / "scripts") not in sys.path:
        sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_operate
    return sdd_operate


def main():
    base = Path(tempfile.mkdtemp(prefix="sdd-selftest-"))
    try:
        test_compuerta(base)
        test_trazabilidad(base)
        test_deteccion_pruebas(base)
        test_contrato_ci(base)
        test_degenerados(base)
        test_bash(base)
        test_F002_R003_aviso_nombra_el_requisito(base)
        test_F002_R010_fixture_en_cadena_no_cuenta(base)
        test_F002_R010_cita_en_texto_no_cuenta(base)
        test_F002_R002_nombre_y_comentario_cuentan(base)
        test_F002_R002_python_invalido_no_revienta(base)
        test_F002_R002_salto_de_pagina(base)
        test_F002_R010_otros_lenguajes_como_antes(base)
        test_F002_R004_mencion_no_bloquea(base)
        test_F002_R005_ejecucion_bloquea(base)
        test_F002_R006_auditoria_revierte_lo_que_la_compuerta_deja_pasar(base)
        test_F003_R004_obsoleto_no_da_error_en_tarea_cerrada(base)
        test_F003_R003_siguiente_id_ignora_menciones(base)
        test_F003_R001_auditoria_revierte_otra_feature(base)
        test_F003_R002_auditoria_silenciosa_sin_cambios(base)
        test_F003_R005_cita_fuera_de_prueba_no_cuenta(base)
        test_F003_R006_nombre_y_cuerpo_cuentan(base)
        test_F003_R006_python_sin_ast_usa_la_atribucion_anterior(base)
        test_F003_R007_otros_lenguajes_identicos(base)
        test_F004_R001_raiz_desde_subdirectorio(base)
        test_F004_R003_sin_datos_usa_el_directorio_actual(base)
        test_F004_R004_variable_de_entorno_manda(base)
        test_F005_R003_contrato_con_discovery(base)
        test_F005_R004_lee_candidatas_y_descartadas(base)
        test_F005_R006_resuelve_objetivos_y_fuentes(base)
        test_F005_R001_crea_la_spec_desde_la_candidata(base)
        test_F005_R002_origen_en_la_cabecera(base)
        test_F005_R003_producto_sin_aprobar(base)
        test_F005_R004_candidata_inexistente_o_descartada(base)
        test_F005_R007_sin_backlog_o_sin_id(base)
        test_F005_R008_specs_sin_origen_igual(base)
        test_F005_R005_candidata_con_feature(base)
        test_F005_R006_contexto_en_el_json(base)
        test_F005_R009_dependencia_sin_feature(base)
        test_F005_R006_seccion_que_no_se_puede_leer(base)
        test_F007_R002_lee_la_arquitectura(base)
        test_F007_R009_contrato_con_architecture(base)
        test_F007_R003_plan_cita_adr_no_aprobado(base)
        test_F007_R004_plan_sin_comprobacion_de_arquitectura(base)
        test_F007_R005_adr_sustituido_tras_aprobar(base)
        test_F007_R001_trace_sin_arquitectura_igual(base)
        test_F007_R002_contexto_de_planificacion(base)
        test_F007_R001_contexto_sin_arquitectura(base)
        test_F007_R006_propone_una_decision(base)
        test_F007_R007_origen_con_componentes(base)
        test_F007_R008_traspaso_sin_arquitectura_lista(base)
        test_F007_R001_traspaso_sin_arquitectura_igual(base)
        test_F009_R001_seccion_de_diagramas(base)
        test_F009_R002_esqueleto_con_componentes(base)
        test_F009_R003_no_sobrescribe(base)
        test_F009_R007_sin_arquitectura(base)
        test_F009_R004_componente_inexistente(base)
        test_F009_R005_llamada_contra_estandar(base)
        test_F009_R006_sin_diagramas_avisa(base)
        test_F009_R007_trace_sin_arquitectura(base)
        test_F009_R008_pide_citar_la_decision(base)
        test_F010_R017_tipo(base)
        test_F010_R018_trace_de_otra_feature(base)
        test_F011_R013_feature_desde_accion(base)
        test_F011_R014_traspaso_denegado(base)
        test_F011_R018_sin_registro_igual(base)
        test_F011_R013_contrato_con_operate(base)
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
