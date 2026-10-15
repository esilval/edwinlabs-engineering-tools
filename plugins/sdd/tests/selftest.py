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

    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_trace
    declarados = set(sdd_trace.FINDINGS)
    probados = set(FIXTURES) | {"E-REQ-NO-TASK", "E-REQ-NO-TEST",
                                "E-REQ-NO-CRITERIA", "W-REQ-NO-TASK",
                                "W-TEST-UNSCOPED", "W-TASK-NO-DONE-WHEN",
                                "W-TEST-EMPTY", "W-TEST-NO-ASSERT"} | set(planes)
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


def test_F002_R001_fixture_en_cadena_no_cuenta(base):
    print("\nF002 · R001: un fixture en una cadena no es una prueba")
    p = repo_con_feature(base, "f002-r001-fixture", archivos={"tests/test_f.py": FIXTURE_PY})
    expect(evidencia(p, "R001") == [], "una cadena de una linea no cuenta",
           f"{evidencia(p, 'R001')}")
    expect(evidencia(p, "R002") == [], "una cadena de varias lineas tampoco",
           f"{evidencia(p, 'R002')}")


def test_F002_R001_cita_en_texto_no_cuenta(base):
    print("\nF002 · R001: una cita dentro de un texto no cuenta")
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


def test_F002_R002_titulo_js_cuenta(base):
    print("\nF002 · R002: el titulo de una prueba JS o Ruby sigue contando")
    p = repo_con_feature(base, "f002-r002-js", archivos={
        "tests/login.spec.ts": ("describe('login', () => {\n"
                                "  it('F001_R001 rechaza el token caducado', () => {\n"
                                "    expect(login('x')).toBe(false);\n  });\n});\n"),
        "spec/pagos_spec.rb": ("describe 'pagos' do\n  it 'F001-R002 cobra a fin de mes' do\n"
                               "    expect(cobro).to eq(1)\n  end\nend\n"),
    })
    expect(evidencia(p, "R001") == ["tests/login.spec.ts::F001_R001 rechaza el token caducado"],
           "it('…') en TypeScript cuenta", f"{evidencia(p, 'R001')}")
    expect(evidencia(p, "R002") != [], "it '…' do en Ruby cuenta", f"{evidencia(p, 'R002')}")


def test_F002_R001_cadena_js_no_cuenta(base):
    print("\nF002 · R001: una cadena en JS que no es titulo no cuenta")
    p = repo_con_feature(base, "f002-r001-js", archivos={"tests/fix.test.js": (
        "const FIXTURE = \"it('F001_R001 falso', () => {})\";\n"
        "test('usa el fixture', () => {\n"
        "  const nota = `ver F001-R002`;\n  expect(FIXTURE).toBeTruthy();\n});\n")})
    expect(evidencia(p, "R001") == [], "un it('…') dentro de una cadena no cuenta",
           f"{evidencia(p, 'R001')}")
    expect(evidencia(p, "R002") == [], "una plantilla `…` con la cita no cuenta",
           f"{evidencia(p, 'R002')}")


MENCIONES = [
    "git commit -q -m 'sdd: la compuerta ya no bloquea sdd.py approve ni set_status(x)'",
    'gh pr create --title t --body "Corrige: python3 sdd.py approve y set_status(texto, v)"',
    "cat > notas.md <<'EOF'\npython3 plugins/sdd/scripts/sdd.py approve\nEOF",
    'echo "para aprobar: python3 sdd.py approve"',
    "grep -rn 'sdd.py approve' plugins/sdd/README.md",
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
]


def test_F002_R004_mencion_no_bloquea(base):
    print("\nF002 · R004: mencionar la aprobacion no bloquea")
    p = repo_con_feature(base, "f002-r004")
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import sdd_bash
    for cmd in MENCIONES:
        expect(not sdd_bash.invokes_approve(cmd), f"no es ejecucion: {cmd.splitlines()[0][:50]!r}")
        expect(not bash_bloquea(p, cmd), f"la compuerta no bloquea: {cmd.splitlines()[0][:50]!r}")
    expect(not sdd_bash.invokes_approve('echo "sin cerrar'), "un comando que no se analiza: no")


def test_F002_R005_ejecucion_bloquea(base):
    print("\nF002 · R005: ejecutar sdd.py approve sigue bloqueado")
    p = repo_con_feature(base, "f002-r005")
    for cmd in EJECUCIONES:
        expect(bash_bloquea(p, cmd), f"bloquea: {cmd!r}")


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
        test_F002_R001_fixture_en_cadena_no_cuenta(base)
        test_F002_R001_cita_en_texto_no_cuenta(base)
        test_F002_R002_nombre_y_comentario_cuentan(base)
        test_F002_R002_python_invalido_no_revienta(base)
        test_F002_R002_salto_de_pagina(base)
        test_F002_R002_titulo_js_cuenta(base)
        test_F002_R001_cadena_js_no_cuenta(base)
        test_F002_R004_mencion_no_bloquea(base)
        test_F002_R005_ejecucion_bloquea(base)
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
