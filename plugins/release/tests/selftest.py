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
import release_specs  # noqa: E402

# El sdd.py del repositorio, solo para las pruebas de contrato.
SDD = PLUGIN.parent / "sdd" / "scripts" / "sdd.py"

fallos = []
BASE = Path(tempfile.mkdtemp(prefix="release-selftest-"))


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


def main():
    try:
        test_F010_R006_lee_las_features()
        test_F010_R002_contrato_con_sdd()
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
