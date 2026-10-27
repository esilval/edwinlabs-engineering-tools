#!/usr/bin/env python3
"""
Regresion del plugin operate. Sin dependencias externas: solo stdlib.

Cada prueba es una funcion test_F011_Rxxx_* que cita el requisito de la
feature 011 al que sirve, para que la trazabilidad de sdd la reconozca, y
verifica con expect(...). releases/, architecture/ y specs/ se escriben a mano
en el formato de cada plugin: solo las pruebas de contrato ejecutan los
release.py, architecture.py, discovery.py y sdd.py reales.
Corre en CI y en local:

    python3 plugins/operate/tests/selftest.py
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
import operate_sources  # noqa: E402

# Los plugins reales del repositorio, solo para las pruebas de contrato.
PLUGINS = PLUGIN.parent
DISCOVERY = PLUGINS / "discovery" / "scripts" / "discovery.py"
ARCHITECTURE = PLUGINS / "architecture" / "scripts" / "architecture.py"
SDD = PLUGINS / "sdd" / "scripts" / "sdd.py"
RELEASE = PLUGINS / "release" / "scripts" / "release.py"

fallos = []
BASE = Path(tempfile.mkdtemp(prefix="operate-selftest-"))


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


def run_plugin(script, cwd, *args, env_extra=None):
    """Ejecuta el script real de otro plugin sobre el proyecto cwd."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd),
               CLAUDE_PLUGIN_ROOT=str(script.parent.parent))
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(script), *args], capture_output=True,
                          text=True, cwd=str(cwd), env=env, timeout=60)


def sella(path):
    """Aprueba a mano como lo haria el plugin dueño: 'Approved · <huella>'."""
    texto = path.read_text(encoding="utf-8")
    huella = operate_sources.content_digest(texto)
    path.write_text(operate_sources.STATUS_ROW.sub(rf"\g<1>Approved · {huella}\3", texto,
                                                   count=1), encoding="utf-8")


# ------------------------------------------------------------- fixtures
# El producto, la arquitectura, las features y las versiones de prueba, en el
# formato de discovery, architecture, sdd y release (copia de los fixtures de
# sus selftests): operate lee esos archivos, no importa su codigo.

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
"""


def cabecera(titulo, estado="Draft"):
    return f"# {titulo}\n\n| Campo  | Valor |\n| ------ | ----- |\n| Estado | {estado} |\n\n"


# B01 sirve a G1. Q1 se relaciona con B01 por su motivo, G1; Q2 (motivo G2)
# solo porque motiva ADR-0002, que cita su plan; Q3 (G2, motiva la ADR-0003
# propuesta) no se relaciona.
ARQ_QUALITY = cabecera("Atributos de calidad") + """## Atributos

### Q1 — Resumen al cerrar

- **Escenario:** al cerrar la caja, el total del día aparece en menos de 2 segundos con 5000 ventas
- **Motivo:** G1

### Q2 — Base disponible

- **Escenario:** la base de datos responde el 99,9 % de las consultas del mes
- **Motivo:** G2

### Q3 — Exportación completa

- **Escenario:** exportar 12 meses de movimientos termina en menos de 30 segundos
- **Motivo:** G2
"""

ARQ_COMPONENTS = cabecera("Componentes") + """## Componentes

### C1 — Ventas

- **Responsabilidad:** registra ventas y calcula los totales del día
- **Candidatas:** B01

### C2 — Exportación

- **Responsabilidad:** genera archivos de movimientos a partir de las ventas
- **Candidatas:** B02
"""

ARQ_STANDARDS = cabecera("Estándares") + """## Estándares

### S1 — Exportación depende de Ventas, nunca al revés

- **Tipo:** dependencia
- **Detalle:** C2 → C1
- **Decisión:** ADR-0001
"""

ARQ_QUESTIONS = cabecera("Preguntas de arquitectura") + "## Preguntas\n\nNinguna por ahora.\n"


def adr(numero, titulo, estado="Draft", motivo="Q1"):
    return (f"# ADR-{numero} — {titulo}\n\n| Campo     | Valor |\n| --------- | ----- |\n"
            f"| Estado    | {estado} |\n| Fecha     | 2026-10-16 |\n| Motivo    | {motivo} |\n"
            "| Sustituye | — |\n\n"
            "## Contexto\n\nLas ventas del día se consultan al cerrar.\n\n"
            "## Decisión\n\nUna sola base de datos relacional.\n\n"
            "## Alternativas descartadas\n\n- Una base por componente: sin necesidad hoy.\n\n"
            "## Consecuencias\n\n- Los dos componentes comparten esquema.\n")


# ADR-0001 (Q1) y ADR-0002 (Q2) aprobables; ADR-0003 (Q3) propuesta.
ADRS = (("0001", "Base de datos única", "Draft", "Q1"),
        ("0002", "Réplica de la base", "Draft", "Q2"),
        ("0003", "Caché de exportación", "Proposed", "Q3"))


def con_arquitectura(p, aprobada=True):
    """architecture/ coherente en p, sellada a mano si se pide. Sin producto:
    operate solo mira la aprobacion del conjunto, no el producto."""
    arq = p / "architecture"
    (arq / "adr").mkdir(parents=True, exist_ok=True)
    for nombre, texto in (("quality.md", ARQ_QUALITY), ("components.md", ARQ_COMPONENTS),
                          ("standards.md", ARQ_STANDARDS), ("questions.md", ARQ_QUESTIONS)):
        (arq / nombre).write_text(texto, encoding="utf-8")
    for numero, titulo, estado, motivo in ADRS:
        (arq / "adr" / f"{numero}-x.md").write_text(adr(numero, titulo, estado, motivo),
                                                    encoding="utf-8")
    if aprobada:
        for nombre in ("quality.md", "components.md", "standards.md", "questions.md"):
            sella(arq / nombre)
        for numero, _t, estado, _m in ADRS:
            if estado == "Draft":
                sella(arq / "adr" / f"{numero}-x.md")
    return p


SPEC_CUERPO = """## Problema

El dueño no sabe cuánto vendió hoy.

## Requisitos

| ID   | Prioridad | Requisito |
| ---- | --------- | --------- |
| R001 | MUST | CUANDO el dueño cierra la caja, el sistema DEBERÁ mostrar el total del día. |

## Criterios de aceptación

### R001

- **Dado** ventas **cuando** cierra **entonces** ve el total
"""

PLAN_CON_ADR = """# Plan: x

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Decisiones

- D1: el total se calcula en la base, como decide ADR-0002.

## Componentes afectados

| Componente | Cambio | Requisitos |
| ---------- | ------ | ---------- |
| src/app.py | nuevo  | R001 |
"""

TASKS_HECHAS = """# Tasks: x

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Tareas

### T001 — total del día

- **Estado:** `[x]`
- **Requisitos:** R001
- **Depende de:** —
- **Hecho cuando:** pasan los tests
"""


def sdd_falso():
    """Un sdd.py falso con trazabilidad limpia, para el SDD_SCRIPT de release:
    las features de prueba no tienen pruebas propias."""
    script = BASE / "sdd-falso" / "sdd.py"
    if not script.is_file():
        script.parent.mkdir(parents=True)
        script.write_text("import json\nprint(json.dumps({'schema': 'sdd.trace/v1', "
                          "'feature': 'x', 'ok': True, 'findings': []}))\n", encoding="utf-8")
    return script


# ----------------------------------------------------------------- T001

def test_F011_R003_contrato_con_los_demas():
    print("\nF011 · R003, R011, R015: operate_sources lee lo que dejan los plugins reales")
    reales = (DISCOVERY, ARCHITECTURE, SDD, RELEASE)
    if not expect(all(x.is_file() for x in reales), "los cuatro plugins están en el repositorio"):
        return
    os_ = operate_sources
    import ast
    for path in sorted((PLUGIN / "scripts").glob("*.py")) + [Path(__file__)]:
        modulos = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modulos += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modulos.append(node.module.split(".")[0])
        malos = [m for m in modulos
                 if re.match(r"^(discovery|architecture|release\w*|sdd\w*)$", m)]
        expect(not malos, f"{path.name} no importa código de otros plugins", f"{malos}")
    p = proyecto("contrato")

    print("  discovery y architecture")
    (p / "entrada").mkdir()
    (p / "entrada" / "vision.md").write_text(PRODUCTO_DOC, encoding="utf-8")
    r = run_plugin(DISCOVERY, p, "ingest", str(p / "entrada" / "vision.md"))
    expect(r.returncode == 0, "discovery ingiere el documento", r.stdout + r.stderr)
    (p / "product" / "brief.md").write_text(PRODUCTO_BRIEF, encoding="utf-8")
    (p / "product" / "backlog.md").write_text(PRODUCTO_BACKLOG, encoding="utf-8")
    r = run_plugin(DISCOVERY, p, "approve")
    expect(r.returncode == 0, "discovery aprueba el producto", r.stdout + r.stderr)
    con_arquitectura(p, aprobada=False)
    expect(os_.architecture_problems(p) != [], "antes de aprobarla, la arquitectura no lo está")
    r = run_plugin(ARCHITECTURE, p, "approve")
    expect(r.returncode == 0, "architecture aprueba la arquitectura", r.stdout + r.stderr)
    expect(os_.architecture_problems(p) == [],
           "lo que architecture aprueba, operate lo da por aprobado",
           f"{os_.architecture_problems(p)}")
    expect([(q["id"], q["motive"]) for q in os_.quality(p)]
           == [("Q1", "G1"), ("Q2", "G2"), ("Q3", "G2")]
           and "menos de 2 segundos" in os_.quality(p)[0]["scenario"],
           "los atributos con su escenario y su motivo", f"{os_.quality(p)}")
    expect([(a["id"], a["state"], a["motive"]) for a in os_.adrs(p)]
           == [("ADR-0001", "approved", "Q1"), ("ADR-0002", "approved", "Q2"),
               ("ADR-0003", "proposed", "Q3")],
           "las decisiones con su estado y su motivo", f"{os_.adrs(p)}")
    comp = p / "architecture" / "components.md"
    comp.write_text(comp.read_text(encoding="utf-8").replace("registra ventas",
                                                             "registra ventas y cobros"),
                    encoding="utf-8")
    expect(any("components.md" in x for x in os_.architecture_problems(p)),
           "un componente editado tras aprobar: ya no está aprobada")
    run_plugin(ARCHITECTURE, p, "approve")

    print("  sdd")
    r = run_plugin(SDD, p, "new", "B01")
    slug = json.loads(r.stdout)["feature"] if r.returncode == 0 else None
    if not expect(slug is not None, "sdd crea la feature desde B01", r.stdout + r.stderr):
        return
    d = p / "specs" / slug
    generada = (d / "spec.md").read_text(encoding="utf-8")
    (d / "spec.md").write_text(generada.split("\n## ", 1)[0] + "\n" + SPEC_CUERPO,
                               encoding="utf-8")
    for fname, texto in (("spec.md", None), ("plan.md", PLAN_CON_ADR),
                         ("tasks.md", TASKS_HECHAS)):
        if texto:
            (d / fname).write_text(texto, encoding="utf-8")
        r = run_plugin(SDD, p, "approve")
        expect(r.returncode == 0, f"sdd aprueba {fname}", r.stdout + r.stderr)
    f = os_.feature(d)
    expect(f["goals"] == ["G1"] and f["adrs"] == ["ADR-0002"]
           and f["title"] == "Resumen diario de ventas",
           "la feature: objetivos de su Origen y decisiones de su plan", f"{f}")
    expect([x.name for x in os_.resolve(p, slug.split("-", 1)[0])] == [slug],
           "el número resuelve la feature")
    expect(os_.features_by_origin(p) == {"B01": slug}, "qué spec cita cada origen",
           f"{os_.features_by_origin(p)}")
    # La fila Origen de una feature creada desde una acción (D7). La escribe
    # sdd a partir de esta feature; aquí, a mano en su formato.
    accion = p / "specs" / "042-arreglo-resumen"
    accion.mkdir()
    (accion / "spec.md").write_text(
        "# Spec: Arreglo del resumen\n\n| Campo  | Valor |\n| ------ | ----- |\n"
        "| Estado | Draft |\n| Tipo   | corrección |\n| Issue  | — |\n"
        "| Origen | I001-A2 · 0.4.0 |\n\n## Problema\n\nAlgo.\n", encoding="utf-8")
    sin_origen = p / "specs" / "043-sin-origen"
    sin_origen.mkdir()
    (sin_origen / "spec.md").write_text(
        "# Spec: x\n\n| Campo | Valor |\n| - | - |\n| Estado | Draft |\n"
        "| Origen | — |\n\n## Problema\n\n| origen | I009-A9 |\n", encoding="utf-8")
    expect(os_.features_by_origin(p) == {"B01": slug, "I001-A2": "042-arreglo-resumen"},
           "la acción que cita cada spec; un Origen «—» o fuera de la cabecera no cuenta",
           f"{os_.features_by_origin(p)}")
    expect(os_.feature(accion)["goals"] == [],
           "el segundo grupo de una acción es su versión, no un objetivo")

    print("  release")
    con_traza = {"SDD_SCRIPT": str(sdd_falso())}
    numero = slug.split("-", 1)[0]
    r = run_plugin(RELEASE, p, "new", numero, env_extra=con_traza)
    version = p / "releases" / "v0.1.0.md"
    expect(r.returncode == 0 and version.is_file(), "release crea la versión 0.1.0",
           r.stdout + r.stderr)
    expect(os_.release(p, "0.1.0")["state"] == "draft"
           and not os_.published(os_.release(p, "0.1.0")),
           "en borrador no está publicada")
    version.write_text(re.sub(r"^_.*_$", "Texto redactado.", version.read_text(encoding="utf-8"),
                              flags=re.M), encoding="utf-8")
    r = run_plugin(RELEASE, p, "approve", "v0.1.0", env_extra=con_traza)
    v = os_.release(p, "0.1.0")
    expect(r.returncode == 0 and v["state"] == "approved" and os_.published(v)
           and v["features"] == [numero],
           "lo que release aprueba está publicado, con sus features", r.stdout + r.stderr)
    antes = v["digest"]
    version.write_text(version.read_text(encoding="utf-8").replace("Texto redactado.",
                                                                   "Errata.", 1),
                       encoding="utf-8")
    v = os_.release(p, "0.1.0")
    expect(v["state"] == "stale" and os_.published(v) and v["digest"] != antes,
           "editada tras aprobarse: cambiada, sigue publicada y su huella cambia")
    expect(os_.release(p, "9.9.9") is None and not os_.published(None),
           "una versión que no existe")


def main():
    tests = [f for n, f in globals().items() if n.startswith("test_") and callable(f)]
    try:
        for fn in tests:
            fn()
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
