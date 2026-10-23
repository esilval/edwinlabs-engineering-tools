#!/usr/bin/env python3
"""
Regresion del plugin release. Sin dependencias externas: solo stdlib.

Cada prueba es una funcion test_F010_Rxxx_* que cita el requisito de la
feature 010 al que sirve, para que la trazabilidad de sdd la reconozca, y
verifica con expect(...). Las features de prueba se escriben a mano en el
formato de sdd: solo la prueba de contrato ejecuta el sdd.py real.
Corre en CI y en local:

    python3 plugins/release/tests/selftest.py
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
sys.path.insert(0, str(PLUGIN / "scripts"))
import release  # noqa: E402
import release_specs  # noqa: E402

SCRIPT = PLUGIN / "scripts" / "release.py"

# El sdd.py del repositorio, solo para las pruebas de contrato.
SDD = PLUGIN.parent / "sdd" / "scripts" / "sdd.py"

fallos = []
BASE = Path(tempfile.mkdtemp(prefix="release-selftest-"))
# Codigos que alguna prueba vio emitirse (ver cobertura_de_codigos).
PROBADOS = set()


def sdd_falso(nombre, findings=(), salida=None, codigo=0):
    """Un sdd.py falso para SDD_SCRIPT: anota con que argumentos y proyecto
    lo llaman, y responde sdd.trace/v1 con findings (o salida tal cual)."""
    d = BASE / "sdd-falsos" / nombre
    d.mkdir(parents=True, exist_ok=True)
    datos = salida if salida is not None else json.dumps(
        {"schema": "sdd.trace/v1", "feature": "x", "ok": not findings,
         "findings": list(findings)})
    script = d / "sdd.py"
    script.write_text(
        "import json, os, sys\n"
        f"with open({str(d / 'llamadas.txt')!r}, 'a') as f:\n"
        "    f.write(json.dumps([sys.argv[1:], os.environ.get('CLAUDE_PROJECT_DIR')]) + '\\n')\n"
        f"sys.stdout.write({datos!r})\n"
        f"sys.exit({codigo})\n", encoding="utf-8")
    return script


def llamadas(script):
    path = script.parent / "llamadas.txt"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


# Por defecto, una trazabilidad limpia: las features de prueba no tienen
# pruebas propias, y el sdd.py real daria errores que no son de la prueba.
os.environ["SDD_SCRIPT"] = str(sdd_falso("limpio"))


def expect(ok, nombre, detalle=""):
    extra = f" :: {detalle}" if detalle and not ok else ""
    print(f"  {'ok  ' if ok else 'FALLA'} {nombre}{extra}")
    if not ok:
        fallos.append(nombre)
    return ok


def proyecto(nombre):
    """Directorio de proyecto vacio y aislado para una prueba."""
    p = BASE / nombre
    p.mkdir(parents=True)
    return p


def run(cwd, *args, stdin=None, env_extra=None):
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN), CLAUDE_PROJECT_DIR=str(cwd))
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                          capture_output=True, text=True, cwd=str(cwd), env=env, timeout=60)


def run_sdd(cwd, *args):
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(SDD.parent.parent),
               CLAUDE_PROJECT_DIR=str(cwd))
    return subprocess.run([sys.executable, str(SDD), *args], capture_output=True,
                          text=True, cwd=str(cwd), env=env, timeout=60)


# ------------------------------------------------------------- fixtures

def spec_md(titulo="Exportar ventas", reqs=(("R001", "MUST"), ("R002", "MUST")),
            tipo="funcionalidad", origen=None):
    """spec.md en el formato de sdd. tipo=None no escribe la fila Tipo."""
    filas = ["| Campo  | Valor |", "| ------ | ----- |", "| ID     | `x` |",
             "| Estado | Draft |"]
    if tipo is not None:
        filas.append(f"| Tipo   | {tipo} |")
    filas.append("| Issue  | — |")
    if origen:
        filas.append(f"| Origen | {origen} |")
    tabla = "\n".join(f"| {rid} | {prio} | CUANDO X{rid}, el sistema DEBERÁ Y. |"
                      for rid, prio in reqs)
    criterios = "\n\n".join(f"### {rid}\n\n- **Dado** a **cuando** b **entonces** c"
                            for rid, _p in reqs)
    return (f"# Spec: {titulo}\n\n" + "\n".join(filas) + "\n\n## Problema\n\nAlgo.\n\n"
            "## Requisitos\n\n| ID   | Prioridad | Requisito |\n| ---- | --------- | --------- |\n"
            f"{tabla}\n\n## Criterios de aceptación\n\n{criterios}\n")


def plan_md(reqs=("R001", "R002"), adrs=(), contratos="No aplica.", modelo="No aplica."):
    citas = "".join(f"\n- Se apoya en {a}." for a in adrs)
    return ("# Plan: x\n\n| Campo  | Valor |\n| ------ | ----- |\n| Estado | Draft |\n\n"
            f"## Decisiones\n\n- D1: algo.{citas}\n\n"
            "## Componentes afectados\n\n| Componente | Cambio | Requisitos |\n"
            f"| ---------- | ------ | ---------- |\n| src/app.py | nuevo  | {', '.join(reqs)} |\n\n"
            f"## Modelo de datos\n\n{modelo}\n\n## Contratos\n\n{contratos}\n\n"
            "## Diagramas\n\n### Modelo de datos\n\nNo aplica.\n")


def tasks_md(reqs=("R001", "R002"), estados=("x", "x")):
    bloques = "\n\n".join(
        f"### T00{n} — tarea {n}\n\n- **Estado:** `[{e}]`\n- **Requisitos:** {', '.join(reqs)}\n"
        f"- **Depende de:** —\n- **Hecho cuando:** pasan los tests"
        for n, e in enumerate(estados, 1))
    return ("# Tasks: x\n\n| Campo  | Valor |\n| ------ | ----- |\n| Estado | Draft |\n\n"
            f"## Tareas\n\n{bloques}\n")


def sella(path):
    """Aprueba a mano como lo haria sdd.py approve: 'Approved · <huella>'."""
    texto = path.read_text(encoding="utf-8")
    huella = release_specs.content_digest(texto, path.name)
    path.write_text(re.sub(r"^\| Estado \|[^|\n]*\|", f"| Estado | Approved · {huella} |",
                           texto, count=1, flags=re.M), encoding="utf-8")


def feature(p, slug, aprobar=("spec", "plan", "tasks"), spec=None, plan=None, tasks=None):
    """specs/<slug>/ con spec, plan y tasks, aprobadas las fases de aprobar."""
    d = p / "specs" / slug
    d.mkdir(parents=True)
    for fname, texto in (("spec.md", spec or spec_md()), ("plan.md", plan or plan_md()),
                         ("tasks.md", tasks or tasks_md())):
        (d / fname).write_text(texto, encoding="utf-8")
        if fname[:-3] in aprobar:
            sella(d / fname)
    return d


def release_md(version, features="008", estado="Draft", anterior="—", cuerpo=""):
    """releases/vX.Y.Z.md escrita a mano con la cabecera de D2."""
    return (f"# Versión {version}\n\n| Campo    | Valor |\n| -------- | ----- |\n"
            f"| Estado   | {estado} |\n| Versión  | {version} |\n| Fecha    | 2026-10-22 |\n"
            f"| Anterior | {anterior} |\n| Features | {features} |\n\n"
            f"## Contenido\n\n{cuerpo or 'Algo.'}\n")


def version(p, numero, features="008", aprobada=False, **kw):
    """Escribe releases/v<numero>.md; aprobada la sella con su huella."""
    path = p / "releases" / f"v{numero}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(release_md(numero, features, **kw), encoding="utf-8")
    if aprobada:
        texto = path.read_text(encoding="utf-8")
        sello = f"Approved · {release.content_digest(texto)}"
        path.write_text(texto.replace("| Estado   | Draft |", f"| Estado   | {sello} |"),
                        encoding="utf-8")
    return path


def hallazgos(root, numero=None):
    """Hallazgos de check; cada codigo visto cuenta como probado."""
    out = release.analyze(root, numero)["findings"]
    for f in out:
        PROBADOS.add(f["code"])
    return out


def de(root, code, numero=None):
    return [f["message"] for f in hallazgos(root, numero) if f["code"] == code]


# ----------------------------------------------------------------- T003

def test_F010_R006_lee_las_features():
    print("\nF010 · R002, R003, R006, R017: release_specs lee specs/ en el formato de sdd")
    p = proyecto("lectura")
    feature(p, "008-exportar-ventas",
            spec=spec_md("Exportar ventas", reqs=(("R001", "MUST"), ("R002", "SHOULD"),
                                                  ("R003", "OBSOLETO")),
                         tipo="Corrección", origen="B01 · G1 · D1§1"),
            plan=plan_md(adrs=("ADR-0001", "ADR-0003"), contratos="- `GET /ventas`: CSV."),
            tasks=tasks_md(estados=("~", "x")))
    feature(p, "009-diagramas", aprobar=("spec",), spec=spec_md("Diagramas", tipo=None))
    (p / "specs" / "notas").mkdir()

    expect([d.name for d in release_specs.feature_dirs(p)] == ["008-exportar-ventas",
                                                                 "009-diagramas"],
           "solo los directorios NNN-slug son features")
    expect([d.name for d in release_specs.resolve(p, "008")] == ["008-exportar-ventas"]
           and [d.name for d in release_specs.resolve(p, "008-exportar-ventas")]
           == ["008-exportar-ventas"],
           "008 y 008-slug resuelven a la misma feature")
    expect(release_specs.resolve(p, "042") == [], "042 no existe")

    f = release_specs.feature(p / "specs" / "008-exportar-ventas")
    expect(f["id"] == "008" and f["title"] == "Exportar ventas", "número y título", f"{f}")
    expect(f["phases"] == {"spec": "approved", "plan": "approved", "tasks": "approved"},
           "las tres fases aprobadas", f"{f['phases']}")
    expect([(t["id"], t["state"]) for t in f["tasks"]] == [("T001", "wip"), ("T002", "done")],
           "las tareas con su estado", f"{f['tasks']}")
    expect([(r["id"], r["priority"]) for r in f["requirements"]]
           == [("R001", "MUST"), ("R002", "SHOULD"), ("R003", "OBSOLETE")],
           "los requisitos con su prioridad, incluido el obsoleto", f"{f['requirements']}")
    expect(f["type"] == "corrección" and f["origin"] == "B01 · G1 · D1§1",
           "Tipo con mayúscula y Origen", f"{f['type']} {f['origin']}")
    expect(f["adrs"] == ["ADR-0001", "ADR-0003"] and f["contracts"] and not f["data_model"],
           "las decisiones del plan y qué secciones tienen contenido",
           f"{f['adrs']} {f['contracts']} {f['data_model']}")

    g = release_specs.feature(p / "specs" / "009-diagramas")
    expect(g["phases"] == {"spec": "approved", "plan": "draft", "tasks": "draft"},
           "fases en borrador", f"{g['phases']}")
    expect(g["type"] == "funcionalidad" and g["type_raw"] is None and g["origin"] is None,
           "sin fila Tipo cuenta como funcionalidad; sin Origen, None")

    for escrito, tipo in (("correccion", "corrección"), ("FUNCIONALIDAD", "funcionalidad"),
                          ("`corrección`", "corrección"), ("mejora", None)):
        expect(release_specs.feature_type(spec_md(tipo=escrito))[0] == tipo,
               f"Tipo «{escrito}» se lee como {tipo}")

    spec = p / "specs" / "009-diagramas" / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("Algo.", "Otra cosa."),
                    encoding="utf-8")
    expect(release_specs.feature(spec.parent)["phases"]["spec"] == "stale",
           "una spec editada tras aprobarse está cambiada")

    import ast
    for path in sorted((PLUGIN / "scripts").glob("*.py")) + [Path(__file__)]:
        modulos = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modulos += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modulos.append(node.module.split(".")[0])
        malos = [m for m in modulos if re.match(r"^(discovery|architecture|sdd\w*)$", m)]
        expect(not malos, f"{path.name} no importa código de otros plugins", f"{malos}")


def test_F010_R002_contrato_con_sdd():
    print("\nF010 · R002: contrato de release_specs con el sdd.py real")
    if not expect(SDD.is_file(), "sdd.py está en el repositorio", str(SDD)):
        return
    p = proyecto("contrato")
    r = run_sdd(p, "new", "exportar ventas")
    slug = json.loads(r.stdout)["feature"] if r.returncode == 0 else None
    if not expect(slug is not None, "sdd.py new crea la feature", r.stdout + r.stderr):
        return
    d = p / "specs" / slug
    plantilla = (d / "spec.md").read_text(encoding="utf-8")
    expect(release_specs.feature_type(plantilla) == ("funcionalidad", "funcionalidad"),
           "la plantilla de sdd trae Tipo en funcionalidad")
    (d / "spec.md").write_text(spec_md(tipo="corrección", origen="B01 · G1 · D1§1"),
                               encoding="utf-8")
    pasos = ((d / "spec.md", None), (d / "plan.md", plan_md()),
             (d / "tasks.md", tasks_md(estados=("~", "x"))))
    for path, texto in pasos:
        if texto:
            path.write_text(texto, encoding="utf-8")
        r = run_sdd(p, "approve")
        expect(r.returncode == 0, f"sdd.py approve aprueba {path.name}", r.stdout + r.stderr)

    aprobada = (d / "spec.md").read_text(encoding="utf-8")
    f = release_specs.feature(d)
    expect(f["phases"] == {"spec": "approved", "plan": "approved", "tasks": "approved"},
           "release ve aprobadas las tres fases que aprobó sdd", f"{f['phases']}")
    traza = json.loads(run_sdd(p, "trace", "--json").stdout)
    expect([(t["id"], t["state"]) for t in f["tasks"]]
           == [(t["id"], t["state"]) for t in traza["tasks"]],
           "las tareas [~] y [x] se leen igual que trace", f"{f['tasks']} {traza['tasks']}")
    expect([(r["id"], r["priority"]) for r in f["requirements"]]
           == [(r["id"], r["priority"]) for r in traza["requirements"]],
           "los requisitos se leen igual que trace")
    viejo = spec_md(reqs=(("R001", "MUST"),)) + "\n### R004 — exportar (SHOULD)\n\nAlgo.\n"
    (d / "spec.md").write_text(viejo, encoding="utf-8")
    traza = json.loads(run_sdd(p, "trace", "--json").stdout)
    expect([(r["id"], r["priority"]) for r in release_specs.requirements(viejo)]
           == [(r["id"], r["priority"]) for r in traza["requirements"]]
           == [("R001", "MUST"), ("R004", "SHOULD")],
           "un requisito declarado como encabezado también se lee igual que trace",
           f"{release_specs.requirements(viejo)} {traza['requirements']}")
    (d / "spec.md").write_text(aprobada, encoding="utf-8")
    expect(f["type"] == "corrección" and f["origin"] == "B01 · G1 · D1§1", "Tipo y Origen")

    tareas = d / "tasks.md"
    tareas.write_text(tareas.read_text(encoding="utf-8").replace("`[~]`", "`[x]`"),
                      encoding="utf-8")
    estado = run_sdd(p, "status").stdout
    expect(release_specs.feature(d)["phases"]["tasks"] == "approved"
           and "[x] tasks.md" in estado,
           "cerrar una tarea no cambia tasks.md ni para sdd ni para release", estado)

    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8")
                               .replace("Algo.", "Otra cosa."), encoding="utf-8")
    estado = run_sdd(p, "status").stdout
    expect(release_specs.feature(d)["phases"]["spec"] == "stale" and "[!] spec.md" in estado,
           "una spec editada tras aprobarse está cambiada para los dos", estado)

    # D4: el trace --feature real del repositorio se lee sin aviso.
    repo = PLUGIN.parent.parent
    with con_sdd(None):
        datos, motivo = release.trace(repo, release_specs.feature_dirs(repo)[0].name)
        avisos = [x for x in release.check_trace(repo, {"slug": "009"}, "x")
                  if x["code"] == "W-RELEASE-NO-TRACE"]
    expect(datos is not None and motivo is None and datos["schema"] == "sdd.trace/v1",
           "release lee el sdd.trace/v1 real del repositorio", f"{motivo}")
    expect(not avisos, "trace --feature 009 real, sin aviso", f"{avisos}")


# ----------------------------------------------------------------- T004

def test_F010_R002_fases_sin_aprobar():
    print("\nF010 · R002: una feature con fases sin aprobar o cambiadas no entra")
    p = proyecto("r002")
    feature(p, "008-exportar", aprobar=("spec", "tasks"))
    d = feature(p, "009-avisos")
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8")
                               .replace("Algo.", "Otra cosa."), encoding="utf-8")
    feature(p, "010-limpio")
    version(p, "0.1.0", "008, 009, 010")
    msgs = de(p, "E-RELEASE-FEATURE-NOT-APPROVED")
    expect(len(msgs) == 2, "un error por fase sin aprobar", f"{msgs}")
    expect(any("008-exportar" in m and "plan.md" in m and "sin aprobar" in m for m in msgs),
           "nombra la feature 008 y el plan", f"{msgs}")
    expect(any("009-avisos" in m and "spec.md" in m and "cambió" in m for m in msgs),
           "nombra la 009 y su spec cambiada tras aprobarse", f"{msgs}")
    expect(not any("010-limpio" in m for m in msgs), "la feature aprobada no da error")


def test_F010_R003_tareas_abiertas():
    print("\nF010 · R003: una feature con tareas sin cerrar no entra")
    p = proyecto("r003")
    feature(p, "008-exportar", tasks=tasks_md(estados=("x", "x", "x", "~", " ")))
    version(p, "0.1.0")
    msgs = de(p, "E-RELEASE-FEATURE-OPEN-TASKS")
    expect(len(msgs) == 1 and "008-exportar" in msgs[0] and "T004, T005" in msgs[0]
           and "T003" not in msgs[0], "nombra la feature y las tareas T004 y T005", f"{msgs}")
    expect(not de(p, "E-RELEASE-FEATURE-NOT-APPROVED"),
           "cambiar el estado de las tareas no desaprueba tasks.md")


def test_F010_R006_ya_publicada_o_inexistente():
    print("\nF010 · R006: feature ya publicada o inexistente")
    p = proyecto("r006")
    feature(p, "008-exportar")
    feature(p, "009-avisos")
    version(p, "0.1.0", "008", aprobada=True)
    version(p, "0.2.0", "008-exportar, 009, 042")
    msgs = de(p, "E-RELEASE-FEATURE-RELEASED", "0.2.0")
    expect(len(msgs) == 1 and "008-exportar" in msgs[0] and "v0.1.0" in msgs[0],
           "la 008 ya salió en la 0.1.0, nombrada", f"{msgs}")
    msgs = de(p, "E-RELEASE-FEATURE-UNKNOWN", "0.2.0")
    expect(len(msgs) == 1 and "042" in msgs[0], "la 042 no existe y se nombra", f"{msgs}")
    expect(not [f for f in hallazgos(p, "0.1.0") if f["severity"] == "error"],
           "la versión publicada no se vuelve a juzgar por sus features")

    (p / "specs" / "009-avisos-bis").mkdir()
    version(p, "0.3.0", "009")
    msgs = de(p, "E-RELEASE-FEATURE-UNKNOWN", "0.3.0")
    expect(len(msgs) == 1 and "ambigua" in msgs[0] and "009-avisos-bis" in msgs[0],
           "un número que comparten dos features es ambiguo", f"{msgs}")

    q = proyecto("r006-vacia")
    version(q, "0.1.0", "—")
    expect(len(de(q, "E-RELEASE-NO-FEATURES")) == 1, "una versión sin features da error")


def test_F010_R017_tipo():
    print("\nF010 · R017: el Tipo de la spec solo vale funcionalidad o corrección")
    p = proyecto("r017")
    feature(p, "008-exportar", spec=spec_md(tipo="mejora"))
    feature(p, "009-avisos", spec=spec_md(tipo="Correccion"))
    feature(p, "010-sin-tipo", spec=spec_md(tipo=None))
    feature(p, "011-vacio", spec=spec_md(tipo=""))
    version(p, "0.1.0", "008, 009, 010, 011")
    msgs = de(p, "E-RELEASE-FEATURE-TYPE")
    expect(len(msgs) == 2 and "008-exportar" in msgs[0] and "«mejora»" in msgs[0],
           "nombra la feature y el valor; las variantes y la fila ausente valen", f"{msgs}")
    expect(len(msgs) == 2 and "011-vacio" in msgs[1] and "«»" in msgs[1],
           "una fila Tipo vacía no es ninguno de los dos valores", f"{msgs}")


def test_F010_R014_check_en_ci():
    print("\nF010 · R014: check da lo mismo en local y en CI")
    p = proyecto("r014")
    feature(p, "008-exportar", aprobar=("spec",))
    version(p, "0.1.0")
    r = run(p, "check", "--check")
    expect(r.returncode == 1 and "E-RELEASE-FEATURE-NOT-APPROVED" in r.stdout,
           "--check sale con 1 y el informe trae el código", r.stdout + r.stderr)
    r = run(p, "check", "v0.1.0", "--json")
    data = json.loads(r.stdout) if r.returncode == 0 else {}
    expect(data.get("schema") == "release.check/v1" and data.get("ok") is False
           and {"code", "severity", "message", "artifact"} <= set(data["findings"][0])
           and data["findings"][0]["artifact"] == "releases/v0.1.0.md"
           and "E-RELEASE-FEATURE-NOT-APPROVED" in {f["code"] for f in data["findings"]},
           "--json emite release.check/v1 con el código del error", r.stdout + r.stderr)
    r = run(p, "check", "--check", "--json")
    expect(r.returncode == 1 and json.loads(r.stdout)["ok"] is False,
           "--check --json: sale con 1 y emite el JSON", r.stdout + r.stderr)
    expect(run(p, "check", "0.1.0", "--json").stdout == r.stdout,
           "la salida es estable y acepta el número sin v")
    expect(run(p, "check", "--chek").returncode == 2, "un argumento desconocido sale con 2")
    expect(run(p, "check", "v9.9.9").returncode == 2, "una versión que no existe sale con 2")
    feature(p, "009-avisos")
    version(p, "0.2.0", "009")
    expect(run(p, "check", "v0.2.0", "--check").returncode == 0,
           "una versión sin errores sale con 0, aunque otra tenga errores")
    r = run(proyecto("r014-sin-nada"), "check", "--check")
    expect(r.returncode == 0 and "Versiones: 0" in r.stdout,
           "sin releases/ no hay nada que fallar")


def test_F010_R014_borrador_avisa():
    print("\nF010 · R014: una versión en borrador lo avisa")
    p = proyecto("r012-borrador")
    feature(p, "008-exportar")
    version(p, "0.1.0")
    expect(len(de(p, "W-RELEASE-NOT-APPROVED")) == 1, "aviso de versión sin aprobar")


# ----------------------------------------------------------------- T005

def con_sdd(script):
    """Contexto que cambia SDD_SCRIPT (None la quita) y la restaura."""
    import contextlib

    @contextlib.contextmanager
    def ctx():
        antes = os.environ.get("SDD_SCRIPT")
        if script is None:
            os.environ.pop("SDD_SCRIPT", None)
        else:
            os.environ["SDD_SCRIPT"] = str(script)
        try:
            yield
        finally:
            if antes is None:
                os.environ.pop("SDD_SCRIPT", None)
            else:
                os.environ["SDD_SCRIPT"] = antes
    return ctx()


def test_F010_R004_trazabilidad_con_errores():
    print("\nF010 · R004: una feature con errores de trazabilidad no entra")
    p = proyecto("r004")
    feature(p, "008-exportar")
    version(p, "0.1.0", "008")
    falso = sdd_falso("r004", [
        {"code": "W-TEST-UNSCOPED", "severity": "warning", "message": "aviso"},
        {"code": "E-REQ-NO-TEST", "severity": "error", "message": "R001 sin prueba."},
        {"code": "E-DONE-NO-TEST", "severity": "error", "message": "T001 sin prueba."}])
    with con_sdd(falso):
        msgs = de(p, "E-RELEASE-FEATURE-TRACE")
    expect(len(msgs) == 1 and "008-exportar" in msgs[0] and "2 error(es)" in msgs[0]
           and "E-REQ-NO-TEST" in msgs[0], "nombra la feature y el primer código", f"{msgs}")
    expect([c[0] for c in llamadas(falso)] == [["trace", "--feature", "008-exportar", "--json"]]
           and llamadas(falso)[0][1] == str(p),
           "llama a trace --feature con la feature y el proyecto", f"{llamadas(falso)}")
    with con_sdd(sdd_falso("r004-avisos", [
            {"code": "W-PLAN-NO-DIAGRAMS", "severity": "warning", "message": "aviso"}])):
        expect(not de(p, "E-RELEASE-FEATURE-TRACE") and not de(p, "W-RELEASE-NO-TRACE"),
               "los avisos de la trazabilidad no impiden la versión")
    with con_sdd(sdd_falso("r004-proc", [
            {"code": "E-REQ-NO-TEST", "severity": "error", "message": "R001 sin prueba."}])):
        r = run(p, "check", "--check")
    expect(r.returncode == 1 and "E-RELEASE-FEATURE-TRACE" in r.stdout,
           "también desde la línea de órdenes", r.stdout + r.stderr)


def test_F010_R005_adr_no_aprobado():
    print("\nF010 · R005: un plan que cita una decisión no aprobada no entra")
    p = proyecto("r005")
    feature(p, "008-exportar", plan=plan_md(adrs=("ADR-0004",)))
    version(p, "0.1.0", "008")
    with con_sdd(sdd_falso("r005", [
            {"code": "E-PLAN-ADR-NOT-APPROVED", "severity": "error",
             "message": "plan.md cita ADR-0004, que no está aprobada (Proposed)."}])):
        adr = de(p, "E-RELEASE-FEATURE-ADR")
        traza = de(p, "E-RELEASE-FEATURE-TRACE")
    expect(len(adr) == 1 and "008-exportar" in adr[0] and "ADR-0004" in adr[0],
           "nombra la feature y la decisión", f"{adr}")
    expect(not traza, "la decisión no se cuenta además como error de trazabilidad", f"{traza}")


def test_F010_R016_sin_trazabilidad():
    print("\nF010 · R016: sin trazabilidad, aviso y el resto de comprobaciones")
    p = proyecto("r016")
    feature(p, "008-exportar", tasks=tasks_md(estados=("x", "~")))
    version(p, "0.1.0", "008")
    aislado = BASE / "aislado" / "release"
    (aislado / "scripts").mkdir(parents=True)
    with con_sdd(None):
        r = run(p, "check", "--json", env_extra={"CLAUDE_PLUGIN_ROOT": str(aislado)})
    data = json.loads(r.stdout) if r.returncode == 0 else {"findings": []}
    codigos = [f["code"] for f in data["findings"]]
    PROBADOS.update(codigos)
    avisos = [f["message"] for f in data["findings"] if f["code"] == "W-RELEASE-NO-TRACE"]
    expect(len(avisos) == 1 and "008-exportar" in avisos[0] and "sdd.py" in avisos[0],
           "sin sdd.py: aviso que nombra la feature", r.stdout + r.stderr)
    expect("E-RELEASE-FEATURE-OPEN-TASKS" in codigos,
           "y el resto de comprobaciones se aplica", f"{codigos}")
    for nombre, falso in (("sale con 1", sdd_falso("r016-falla", codigo=1)),
                          ("salida ilegible", sdd_falso("r016-basura", salida="no es json")),
                          ("otro schema", sdd_falso("r016-otro", salida='{"findings": []}'))):
        with con_sdd(falso):
            expect(len(de(p, "W-RELEASE-NO-TRACE")) == 1, f"{nombre}: aviso")
    lento = sdd_falso("r016-lento")
    lento.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    limite, release.TRACE_TIMEOUT = release.TRACE_TIMEOUT, 0.5
    try:
        with con_sdd(lento):
            msgs = de(p, "W-RELEASE-NO-TRACE")
    finally:
        release.TRACE_TIMEOUT = limite
    expect(len(msgs) == 1 and "TimeoutExpired" in msgs[0],
           "pasado el tiempo máximo: aviso", f"{msgs}")

    cache = BASE / "cache"
    (cache / "release" / "abc" / "scripts").mkdir(parents=True)
    viejo = sdd_falso("cache-viejo")
    for version_dir, origen in (("111", viejo), ("222", sdd_falso("cache-nuevo"))):
        d = cache / "sdd" / version_dir / "scripts"
        d.mkdir(parents=True)
        shutil.copy(origen, d / "sdd.py")
    os.utime(cache / "sdd" / "111" / "scripts" / "sdd.py", (1, 1))
    antes = os.environ.get("CLAUDE_PLUGIN_ROOT")
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(cache / "release" / "abc")
    try:
        with con_sdd(None):
            elegido = release.sdd_script()
        with con_sdd(BASE / "no-existe.py"):
            sin_variable = release.sdd_script()
    finally:
        if antes is None:
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        else:
            os.environ["CLAUDE_PLUGIN_ROOT"] = antes
    expect(elegido == cache / "sdd" / "222" / "scripts" / "sdd.py",
           "en la caché del marketplace elige la versión más reciente", f"{elegido}")
    expect(sin_variable == elegido, "un SDD_SCRIPT que no existe se salta")
    with con_sdd(None):
        expect(release.sdd_script() == SDD, "en el repositorio, el sdd hermano")


def cobertura_de_codigos():
    # main() la ejecuta despues de todas las pruebas: compara los codigos
    # declarados con los que las pruebas vieron emitirse.
    print("\ncobertura de codigos de hallazgo")
    declarados = set(release.FINDINGS)
    expect(declarados <= PROBADOS, f"los {len(declarados)} codigos declarados se prueban",
           f"sin probar: {sorted(declarados - PROBADOS)}")


def main():
    tests = [f for n, f in globals().items() if n.startswith("test_") and callable(f)]
    try:
        for fn in tests:
            fn()
        cobertura_de_codigos()
    finally:
        shutil.rmtree(BASE, ignore_errors=True)

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
