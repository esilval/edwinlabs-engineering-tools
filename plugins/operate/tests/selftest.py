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
import operate  # noqa: E402
import operate_sources  # noqa: E402

SCRIPT = PLUGIN / "scripts" / "operate.py"

# Los plugins reales del repositorio, solo para las pruebas de contrato.
PLUGINS = PLUGIN.parent
DISCOVERY = PLUGINS / "discovery" / "scripts" / "discovery.py"
ARCHITECTURE = PLUGINS / "architecture" / "scripts" / "architecture.py"
SDD = PLUGINS / "sdd" / "scripts" / "sdd.py"
RELEASE = PLUGINS / "release" / "scripts" / "release.py"

fallos = []
BASE = Path(tempfile.mkdtemp(prefix="operate-selftest-"))
# Codigos que alguna prueba vio emitirse (ver cobertura_de_codigos).
PROBADOS = set()


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


def hallazgos(root, objetivo=None):
    """Hallazgos de check; cada codigo visto cuenta como probado."""
    out = operate.analyze(root, objetivo)["findings"]
    for f in out:
        PROBADOS.add(f["code"])
    return out


def de(root, code, objetivo=None):
    return [f["message"] for f in hallazgos(root, objetivo) if f["code"] == code]


def version(p, numero, features="001", aprobada=True):
    """releases/v<numero>.md en el formato de release, sellada si se pide."""
    path = p / "releases" / f"v{numero}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Versión {numero}\n\n| Campo    | Valor |\n| -------- | ----- |\n"
                    f"| Estado   | Draft |\n| Versión  | {numero} |\n| Fecha    | 2026-10-22 |\n"
                    f"| Anterior | — |\n| Features | {features} |\n\n## Contenido\n\nAlgo.\n",
                    encoding="utf-8")
    if aprobada:
        sella(path)
    return path


def incidente(p, titulo="Caída del resumen diario"):
    """Registra un incidente con operate.py incident; devuelve (ID, Path)."""
    r = run(p, "incident", titulo)
    data = json.loads(r.stdout)
    return data["incident"], p / data["file"]


def completa_incidente(path, version="0.4.0", acciones=None):
    """Rellena los huecos del incidente como lo harian /operate:incident y
    /operate:postmortem, con las acciones dadas: [(ID, titulo)]."""
    texto = path.read_text(encoding="utf-8")
    texto = re.sub(r"\| Fecha            \| _[^|]*_ \|", "| Fecha            | 2026-10-25 |", texto)
    texto = re.sub(r"\| Versión afectada \| _[^|]*_ \|",
                   f"| Versión afectada | {version} |", texto)
    texto = re.sub(r"\| Severidad        \| _[^|]*_ \|", "| Severidad        | alta |", texto)
    bloques = "\n\n".join(f"### {aid} — {titulo}\n\n- **Qué:** {titulo.lower()}."
                           for aid, titulo in (acciones or []))
    texto = re.sub(r"^_Las acciones[^\n]*_$", bloques or "Ninguna.", texto, flags=re.M)
    texto = re.sub(r"^_.*_$", "Texto redactado.", texto, flags=re.M)
    path.write_text(texto, encoding="utf-8")
    return path


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


# ----------------------------------------------------------------- T002

def test_F011_R006_registro_de_incidentes():
    print("\nF011 · R006: cada incidente con un ID que no se recicla")
    p = proyecto("r006")
    i1, f1 = incidente(p, "Caída del resumen diario")
    i2, f2 = incidente(p, "Exportación lenta")
    expect((i1, i2) == ("I001", "I002") and f1.name == "I001-caida-resumen-diario.md",
           "I001 e I002, con su archivo", f"{i1} {i2} {f1.name}")
    texto = f1.read_text(encoding="utf-8")
    cabecera = texto.split("\n## ", 1)[0]
    expect("| ID               | I001 |" in cabecera
           and all(f"| {campo}" in cabecera for campo in ("Fecha ", "Versión afectada",
                                                          "Severidad "))
           and all(f"## {s}" in texto for s in ("Qué pasó", "Impacto", "Cronología",
                                                 "Causas", "Acciones")),
           "el incidente pide fecha, versión, severidad, qué pasó e impacto", texto[:600])
    huecos = operate.holes(texto)
    expect(len(huecos) == 8, "con sus huecos por completar", f"{huecos}")
    f2.unlink()
    i3, _ = incidente(p, "Otra caída")
    expect(i3 == "I003", "con I002 borrado, el siguiente es I003", i3)
    registro = (p / "operations" / "incidents.md").read_text(encoding="utf-8")
    expect(all(f"| {i} |" in registro for i in ("I001", "I002", "I003")),
           "el registro conserva la fila del borrado", registro)
    r = run(p, "incident")
    expect(r.returncode == 1 and "título" in r.stderr, "sin título sale con 1", r.stderr)
    i4, f4 = incidente(p, "Cobro | doble\nen caja")
    registro = (p / "operations" / "incidents.md").read_text(encoding="utf-8")
    expect(f"| {i4} | " in registro and "Cobro / doble en caja |" in registro
           and f4.read_text(encoding="utf-8").startswith(
               f"# Incidente {i4} — Cobro | doble en caja\n"),
           "un título con | o con salto de línea no rompe el registro", registro)
    expect(len(de(p, "E-INCIDENT-TEMPLATE")) == 3
           and len(de(p, "W-INCIDENT-NOT-APPROVED")) == 3,
           "mientras tenga huecos: error de plantilla y aviso de postmortem pendiente")


def test_F011_R007_version_inexistente():
    print("\nF011 · R007: la versión afectada tiene que existir")
    p = proyecto("r007")
    version(p, "0.4.0")
    version(p, "0.5.0", aprobada=False)
    _, f1 = incidente(p)
    completa_incidente(f1, "0.9.0")
    msgs = de(p, "E-INCIDENT-RELEASE")
    expect(len(msgs) == 1 and "I001" in msgs[0] and "0.9.0" in msgs[0],
           "0.9.0 no existe: error que nombra I001 y 0.9.0", f"{msgs}")
    for valor in ("0.4.0", "v0.4.0", "0.5.0", "desconocida"):
        completa_incidente(f1, valor)
        texto = f1.read_text(encoding="utf-8")
        f1.write_text(re.sub(r"\| Versión afectada \| [^|]* \|",
                             f"| Versión afectada | {valor} |", texto), encoding="utf-8")
        expect(not de(p, "E-INCIDENT-RELEASE"), f"«{valor}» vale")
    expect(not de(p, "E-INCIDENT-TEMPLATE"), "completo, sin huecos")


def test_F011_R016_check_en_ci():
    print("\nF011 · R016: check da lo mismo en local y en CI")
    p = proyecto("r016")
    _, f1 = incidente(p)
    completa_incidente(f1, "0.9.0")
    r = run(p, "check", "--check")
    expect(r.returncode == 1 and "E-INCIDENT-RELEASE" in r.stdout,
           "--check sale con 1 y el informe trae el código", r.stdout + r.stderr)
    r = run(p, "check", "I001", "--json", "--check")
    data = json.loads(r.stdout) if r.stdout.strip() else {}
    expect(r.returncode == 1 and data.get("schema") == "operate.check/v1"
           and data.get("ok") is False
           and "E-INCIDENT-RELEASE" in {f["code"] for f in data["findings"]}
           and {"code", "severity", "message", "artifact"} <= set(data["findings"][0])
           and data["findings"][0]["artifact"].startswith("operations/incidents/I001-"),
           "--json emite operate.check/v1 con el código del error", r.stdout + r.stderr)
    expect(run(p, "check", "i001", "--json").stdout == run(p, "check", "I001", "--json").stdout,
           "la salida es estable")
    expect(run(p, "check", "--chek").returncode == 2, "un argumento desconocido sale con 2")
    expect(run(p, "check", "I009").returncode == 2, "un incidente que no existe sale con 2")
    r = run(proyecto("r016-vacio"), "check", "--check")
    expect(r.returncode == 0 and "0 incidente(s)" in r.stdout, "sin operations/, nada que fallar")


def test_F011_R017_sin_los_demas():
    print("\nF011 · R017: sin versiones ni arquitectura")
    p = proyecto("r017")
    iid, f1 = incidente(p)
    expect(iid == "I001" and not (p / "releases").exists(),
           "sin releases/, el incidente se registra")
    completa_incidente(f1, "desconocida")
    expect(not [f for f in hallazgos(p) if f["severity"] == "error"],
           "con la versión desconocida, sin errores")


# ----------------------------------------------------------------- T003

def acciones_de(path, *bloques):
    """Sustituye la sección Acciones del incidente por los bloques dados."""
    texto = path.read_text(encoding="utf-8")
    cabeza, _, _ = texto.partition("## Acciones")
    path.write_text(cabeza + "## Acciones\n\n" + "\n\n".join(bloques) + "\n", encoding="utf-8")


def accion(aid, titulo="Revisar la caché"):
    return f"### {aid} — {titulo}\n\n- **Qué:** {titulo.lower()}."


def test_F011_R008_acciones():
    print("\nF011 · R008: cada acción con un ID estable dentro de su incidente")
    p = proyecto("r008")
    _, f1 = incidente(p)
    completa_incidente(f1, "desconocida")
    r = run(p, "next-action", "I001")
    expect(r.returncode == 0 and r.stdout.strip() == "I001-A1", "la primera es I001-A1",
           r.stdout + r.stderr)
    acciones_de(f1, accion("I001-A1"), accion("I001-A2", "Alarma de latencia"))
    expect(run(p, "next-action", "i001").stdout.strip() == "I001-A3", "después, I001-A3")
    acciones_de(f1, accion("I001-A2", "Alarma de latencia, editada"))
    expect(run(p, "next-action", "I001").stdout.strip() == "I001-A3"
           and operate.actions(f1.read_text(encoding="utf-8"))
           == [("I001-A2", "Alarma de latencia, editada")],
           "editar una y borrar otra no renumera: I001-A2 sigue y la siguiente es I001-A3")
    expect(not de(p, "E-INCIDENT-ACTION-ID"), "IDs bien formados, sin error")
    acciones_de(f1, "### I001-A1: Revisar la caché\n\n- **Qué:** algo.",
                "### i001-a2—Alarma\n\n- **Qué:** algo.")
    expect(operate.actions(f1.read_text(encoding="utf-8"))
           == [("I001-A1", "Revisar la caché"), ("I001-A2", "Alarma")]
           and not de(p, "E-INCIDENT-ACTION-ID"),
           "el ID se lee con «:», con «—» pegado y en minúsculas")
    for bloque, nombre, trozo in (
            (accion("I001-A2") + "\n\n" + accion("I001-A2"), "repetida", "I001-A2 está repetida"),
            (accion("I002-A1"), "de otro incidente", "I002-A1 es de otro incidente"),
            ("### Revisar la caché\n\n- **Qué:** algo.", "sin ID", "«Revisar la caché»")):
        acciones_de(f1, bloque)
        msgs = de(p, "E-INCIDENT-ACTION-ID")
        expect(len(msgs) == 1 and trozo in msgs[0] and msgs[0].startswith("I001:"),
               f"una acción {nombre} da error", f"{msgs}")
    r = run(p, "next-action", "I009")
    expect(r.returncode == 1 and "I009" in r.stderr, "un incidente que no existe sale con 1",
           r.stdout + r.stderr)
    expect(run(p, "next-action").returncode == 1, "sin incidente sale con 1")


def test_F011_R015_accion_sin_feature():
    print("\nF011 · R015: las acciones de un postmortem aprobado sin feature se avisan")
    p = proyecto("r015")
    _, f1 = incidente(p)
    completa_incidente(f1, "desconocida",
                       [("I001-A1", "Revisar la caché"), ("I001-A2", "Alarma de latencia")])
    expect(not de(p, "W-INCIDENT-ACTION-NO-FEATURE"),
           "sin aprobar el postmortem, no se avisa de las acciones")
    sella(f1)
    d = p / "specs" / "001-revisar-cache"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# Spec: Revisar la caché\n\n| Campo  | Valor |\n"
                               "| ------ | ----- |\n| Estado | Draft |\n"
                               "| Origen | I001-A1 · — |\n\n## Problema\n\nAlgo.\n",
                               encoding="utf-8")
    msgs = de(p, "W-INCIDENT-ACTION-NO-FEATURE")
    expect(len(msgs) == 1 and "I001-A2" in msgs[0] and "I001-A1" not in msgs[0]
           and "/sdd:specify I001-A2" in msgs[0],
           "aviso para I001-A2, y ninguno para I001-A1, que tiene feature", f"{msgs}")
    expect(not [f for f in hallazgos(p) if f["severity"] == "error"],
           "el postmortem aprobado no da errores")


# ----------------------------------------------------------------- T004

def feature_a_mano(p, slug, titulo, origen=None, plan=""):
    """specs/<slug>/ con spec y plan en el formato de sdd."""
    d = p / "specs" / slug
    d.mkdir(parents=True)
    fila = f"| Origen | {origen} |\n" if origen else ""
    (d / "spec.md").write_text(f"# Spec: {titulo}\n\n| Campo  | Valor |\n| ------ | ----- |\n"
                               f"| Estado | Draft |\n{fila}\n## Problema\n\nAlgo.\n",
                               encoding="utf-8")
    (d / "plan.md").write_text("# Plan: x\n\n| Campo  | Valor |\n| ------ | ----- |\n"
                               f"| Estado | Draft |\n\n## Decisiones\n\n{plan or 'Ninguna.'}\n",
                               encoding="utf-8")
    return d


def con_version(nombre, aprobada=True, **origenes):
    """Proyecto con 008 y 009 y la versión 0.4.0 que las incluye."""
    p = proyecto(nombre)
    feature_a_mano(p, "008-resumen-diario", "Resumen diario", origenes.get("o008"),
                   origenes.get("p008", ""))
    feature_a_mano(p, "009-exportar", "Exportar movimientos", origenes.get("o009"))
    version(p, "0.4.0", "008, 009", aprobada=aprobada)
    return p


def prepara(p, numero="0.4.0"):
    r = run(p, "prepare", f"v{numero}")
    path = p / "operations" / f"v{numero}.md"
    return r, (path.read_text(encoding="utf-8") if path.is_file() else "")


def seccion(texto, titulo):
    return texto.split(f"## {titulo}\n", 1)[1].split("\n## ", 1)[0]


def test_F011_R001_borrador_de_preparacion():
    print("\nF011 · R001: prepare escribe la preparación de una versión publicada")
    p = con_version("r001")
    r, texto = prepara(p)
    expect(r.returncode == 0 and "| Estado   | Draft |" in texto,
           "prepare v0.4.0 escribe operations/v0.4.0.md en borrador", r.stdout + r.stderr)
    huella = operate_sources.release(p, "0.4.0")["digest"]
    expect(f"| Versión  | 0.4.0 · {huella} |" in texto and "| Features | 008, 009 |" in texto,
           "la cabecera guarda la versión con su huella y las features", texto[:400])
    expect("- 008 — Resumen diario" in seccion(texto, "Features")
           and "- 009 — Exportar movimientos" in seccion(texto, "Features"),
           "nombra 008 y 009 con su título", seccion(texto, "Features"))
    expect(all(f"## {s}" in texto for s in ("Puesta en marcha", "Señales", "Vuelta atrás"))
           and operate.holes(seccion(texto, "Puesta en marcha"))
           and operate.holes(seccion(texto, "Vuelta atrás")),
           "con puesta en marcha, señales y vuelta atrás por completar")
    expect(len(de(p, "E-PREP-TEMPLATE", "0.4.0")) == 1, "check da sus huecos por error")
    antes = (p / "operations" / "v0.4.0.md").read_bytes()
    r, _ = prepara(p)
    expect(r.returncode == 0 and "ya existe" in r.stdout
           and (p / "operations" / "v0.4.0.md").read_bytes() == antes,
           "pedirla otra vez no la cambia y lo dice", r.stdout)
    expect(run(p, "prepare").returncode == 2, "sin versión sale con 2")
    expect(run(p, "check", "v0.4.0", "--json").returncode == 0
           and run(p, "check", "v9.9.9").returncode == 2,
           "check de una preparación que existe, y de una que no (2)")


def test_F011_R002_version_no_publicada():
    print("\nF011 · R002: solo se prepara una versión publicada")
    p = con_version("r002", aprobada=False)
    r, texto = prepara(p)
    expect(r.returncode == 1 and "no está publicada" in r.stderr and not texto
           and not (p / "operations").exists(),
           "la 0.4.0 en borrador: no se crea nada y se dice", r.stdout + r.stderr)
    r, texto = prepara(p, "9.9.9")
    expect(r.returncode == 1 and "9.9.9" in r.stderr and not texto,
           "la 9.9.9 no existe: no se crea nada y se nombra", r.stdout + r.stderr)
    (p / "operations").mkdir()
    (p / "operations" / "v0.4.0.md").write_text("# x\n\n| Campo | Valor |\n| - | - |\n"
                                                "| Estado | Draft |\n", encoding="utf-8")
    msgs = de(p, "E-PREP-RELEASE")
    expect(len(msgs) == 1 and "0.4.0" in msgs[0] and "no está publicada" in msgs[0],
           "una preparación de una versión sin publicar da error en check", f"{msgs}")


def test_F011_R017_preparacion_sin_arquitectura():
    print("\nF011 · R017: sin architecture/, preparación sin señales propuestas")
    p = con_version("r017-prep", o008="B01 · G1 · D1§1")
    r, texto = prepara(p)
    senales = seccion(texto, "Señales")
    expect(r.returncode == 0 and len(re.findall(r"^### SG", senales, re.M)) == 1
           and "- **Atributo:** —" in senales and operate.holes(senales),
           "una sola señal con huecos y sin atributo", senales)
    expect({f["code"] for f in hallazgos(p)} == {"E-PREP-TEMPLATE", "W-PREP-NOT-APPROVED"},
           "sin hallazgos de arquitectura: solo los huecos y el aviso de borrador",
           f"{hallazgos(p)}")
    path = p / "operations" / "v0.4.0.md"
    path.write_text(re.sub(r"^- \*\*(.+?):\*\* _.*_$", r"- **\1:** 5 por minuto", texto,
                           flags=re.M).replace("_Los pasos", "Los pasos").replace("funciona._",
                                                                               "funciona."),
                    encoding="utf-8")
    msgs = de(p, "E-PREP-TEMPLATE")
    expect(len(msgs) == 1 and "1 hueco(s)" in msgs[0] and "nombre de la señal" in msgs[0],
           "el nombre de la señal sin poner también es un hueco", f"{msgs}")


# ----------------------------------------------------------------- T005

def senales_de(p):
    _, texto = prepara(p)
    return operate.prep_signals(texto), seccion(texto, "Señales")


def test_F011_R003_senales_de_la_arquitectura():
    print("\nF011 · R003: una señal propuesta por atributo de calidad relacionado")
    p = con_version("r003", o008="B01 · G1 · D1§1", p008="- D1: apoyado en ADR-0002.")
    con_arquitectura(p)
    senales, texto = senales_de(p)
    expect([(s["id"], s["fields"].get("atributo")) for s in senales]
           == [("SG1", "Q1"), ("SG2", "Q2")],
           "Q1 por el objetivo G1 de 008, Q2 por ADR-0002 de su plan, y Q3 no",
           f"{senales}")
    expect(senales[0]["name"] == "Resumen al cerrar"
           and "menos de 2 segundos" in senales[0]["fields"].get("escenario", "")
           and operate.holes(senales[0]["fields"].get("umbral", "")),
           "cada señal trae el escenario del atributo y el umbral por completar", texto)

    q = con_version("r003-propuesta", o008="B02 · G9", p008="- D1: apoyado en ADR-0003.")
    con_arquitectura(q)
    senales, texto = senales_de(q)
    expect([s["fields"].get("atributo") for s in senales] == ["—"]
           and "Ningún atributo" in texto,
           "una ADR propuesta (Q3) no cuenta: señal con huecos y la nota que lo dice", texto)

    q = con_version("r003-sin-aprobar", o008="B01 · G1")
    con_arquitectura(q, aprobada=False)
    senales, texto = senales_de(q)
    expect(len(senales) == 1 and "no está aprobada" in texto,
           "con la arquitectura sin aprobar, sin propuesta y la nota que lo dice", texto)
    q = con_version("r003-sin-arquitectura", o008="B01 · G1")
    _, texto = senales_de(q)
    expect("no tiene architecture/" in texto, "sin architecture/, la nota lo dice", texto)


def preparacion_completa(p, umbral="p95 > 2 s durante 5 minutos", disparador="SG1"):
    """Prepara 0.4.0 y rellena sus huecos; devuelve la ruta."""
    prepara(p)
    path = p / "operations" / "v0.4.0.md"
    texto = path.read_text(encoding="utf-8")
    texto = texto.replace("_nombre de la señal_", "Latencia del resumen")
    texto = re.sub(r"^- \*\*Umbral:\*\* .*$", f"- **Umbral:** {umbral}", texto, flags=re.M)
    texto = re.sub(r"^- \*\*Disparador:\*\* .*$", f"- **Disparador:** {disparador}", texto,
                   flags=re.M)
    texto = re.sub(r"^(- \*\*.+?:\*\*) _.*_$", r"\1 hecho.", texto, flags=re.M)
    texto = re.sub(r"^_.*_$", "Pasos redactados.", texto, flags=re.M)
    path.write_text(texto, encoding="utf-8")
    return path


def test_F011_R004_umbral_sin_cifra():
    print("\nF011 · R004: una señal sin umbral con cifra")
    p = con_version("r004")
    path = preparacion_completa(p, umbral="que vaya rápido")
    msgs = de(p, "E-PREP-SIGNAL-THRESHOLD")
    expect(len(msgs) == 1 and "SG1 — Latencia del resumen" in msgs[0]
           and "que vaya rápido" in msgs[0], "error que nombra la señal", f"{msgs}")
    texto = path.read_text(encoding="utf-8")
    path.write_text(texto.replace("## Vuelta atrás", "### Errores de exportación\n\n"
                                  "- **Umbral:** pocos\n\n## Vuelta atrás"), encoding="utf-8")
    msgs = de(p, "E-PREP-SIGNAL-THRESHOLD")
    expect(len(msgs) == 2 and "la señal Errores de exportación" in msgs[1],
           "una señal escrita a mano sin ID SG también se comprueba", f"{msgs}")
    path.write_text(texto.replace("que vaya rápido", "más de 2 s en el p95"), encoding="utf-8")
    expect(not [f for f in hallazgos(p) if f["severity"] == "error"],
           "con cifra, la preparación completa no da errores", f"{hallazgos(p)}")


def test_F011_R005_sin_disparador():
    print("\nF011 · R005: la vuelta atrás tiene que decir qué la dispara")
    p = con_version("r005")
    path = preparacion_completa(p, disparador="—")
    msgs = de(p, "E-PREP-ROLLBACK-TRIGGER")
    expect(len(msgs) == 1 and "Disparador" in msgs[0], "sin disparador, error", f"{msgs}")
    texto = path.read_text(encoding="utf-8")
    path.write_text(texto.replace("- **Disparador:** —\n", ""), encoding="utf-8")
    expect(len(de(p, "E-PREP-ROLLBACK-TRIGGER")) == 1, "sin el campo, también")
    path.write_text(texto.replace("- **Disparador:** —", "- **Disparador:** SG1 o errores 5xx"),
                    encoding="utf-8")
    expect(not de(p, "E-PREP-ROLLBACK-TRIGGER"), "con una señal o condición, sin error")


# ----------------------------------------------------------------- T006

def postmortem_completo(p, acciones=(("I001-A1", "Revisar la caché"),)):
    """Incidente I001 sobre la 0.4.0 publicada, con el postmortem completo."""
    _, path = incidente(p)
    return completa_incidente(path, "0.4.0", list(acciones))


def estado(path):
    return operate_sources.doc_status(path.read_text(encoding="utf-8"))


def test_F011_R009_no_se_aprueba_incompleto():
    print("\nF011 · R009: approve se niega con huecos o con errores, sin cambiar nada")
    p = con_version("r009")
    path = preparacion_completa(p, umbral="que vaya rápido")
    antes = path.read_bytes()
    r = run(p, "approve", "v0.4.0")
    expect(r.returncode == 1 and "E-PREP-SIGNAL-THRESHOLD" in r.stderr
           and path.read_bytes() == antes,
           "una preparación con una señal sin umbral: se niega y no cambia", r.stdout + r.stderr)
    _, inc = incidente(p)
    completa_incidente(inc, "0.4.0")
    texto = inc.read_text(encoding="utf-8")
    texto = texto.split("## Causas", 1)[0] + "## Causas\n\n_Por qué pasó._\n\n## Acciones" \
        + texto.split("## Acciones", 1)[1]
    inc.write_text(texto, encoding="utf-8")
    antes = inc.read_bytes()
    r = run(p, "approve", "I001", "--skill")
    expect(r.returncode == 0 and "No se puede aprobar" in r.stdout
           and "E-INCIDENT-TEMPLATE" in r.stdout and inc.read_bytes() == antes,
           "un postmortem con las causas sin completar: --skill lo explica, sale con 0 "
           "y no cambia nada", r.stdout + r.stderr)
    for args, nombre in ((("approve",), "sin objetivo"), (("approve", "I009"), "I009"),
                         (("approve", "v9.9.9"), "9.9.9"), (("approve", "otra"), "otra")):
        expect(run(p, *args).returncode == 1, f"approve {nombre}: se niega con 1")


def test_F011_R010_aprobacion():
    print("\nF011 · R010: approve sella la preparación y el postmortem")
    p = con_version("r010")
    path = preparacion_completa(p)
    r = run(p, "approve", "v0.4.0")
    texto = path.read_text(encoding="utf-8")
    sello = re.search(r"\| Estado   \| Approved · ([0-9a-f]{12}) \|", texto)
    expect(r.returncode == 0 and sello and sello.group(1) == operate_sources.content_digest(texto),
           "la preparación queda aprobada con la huella de su contenido", r.stdout + r.stderr)
    huella = operate_sources.release(p, "0.4.0")["digest"]
    expect(f"| Versión  | 0.4.0 · {huella} |" in texto, "con la huella de su versión")
    r = run(p, "approve", "v0.4.0")
    expect(r.returncode == 0 and "ya estaba aprobada" in r.stdout
           and path.read_text(encoding="utf-8") == texto, "aprobarla otra vez no cambia nada")

    inc = postmortem_completo(p, (("I001-A1", "Revisar la caché"), ("I001-A2", "Alarma")))
    r = run(p, "approve", "i001")
    expect(r.returncode == 0 and estado(inc).startswith("Approved · ")
           and "/sdd:specify I001-A1, /sdd:specify I001-A2" in r.stdout,
           "el postmortem queda aprobado y se dice cómo crear las correcciones",
           r.stdout + r.stderr)
    expect(not [f for f in hallazgos(p) if f["code"].endswith("NOT-APPROVED")],
           "check ya no avisa de que estén sin aprobar")
    expect("ya estaba aprobado" in run(p, "approve", "I001").stdout, "y el postmortem, aprobado")

    (p / "releases" / "v0.4.0.md").unlink()
    antes = path.read_bytes()
    r = run(p, "approve", "v0.4.0")
    expect(r.returncode == 1 and "E-PREP-RELEASE" in r.stderr and path.read_bytes() == antes
           and de(p, "W-PREP-RELEASE-CHANGED"),
           "si su versión desaparece, check avisa y approve se niega", r.stdout + r.stderr)

    q = con_version("r010-sin-fila")
    sin_fila = preparacion_completa(q)
    sin_fila.write_text(re.sub(r"^\| Versión  \|[^\n]*\n", "", sin_fila.read_text(encoding="utf-8"),
                               flags=re.M), encoding="utf-8")
    antes = sin_fila.read_bytes()
    r = run(q, "approve", "v0.4.0")
    expect(r.returncode == 1 and "| Versión |" in r.stderr and sin_fila.read_bytes() == antes,
           "sin la fila Versión, se niega sin cambiar nada", r.stdout + r.stderr)


def test_F011_R011_cambio_tras_aprobar():
    print("\nF011 · R011: lo aprobado que cambia, o cuya versión cambia, se avisa")
    p = con_version("r011")
    path = preparacion_completa(p)
    run(p, "approve", "v0.4.0")
    inc = postmortem_completo(p)
    run(p, "approve", "I001")
    inc.write_text(inc.read_text(encoding="utf-8").replace("Texto redactado.",
                                                           "Otra causa.", 1), encoding="utf-8")
    msgs = de(p, "W-INCIDENT-NOT-APPROVED")
    expect(len(msgs) == 1 and "I001 cambió después de aprobarse" in msgs[0],
           "el postmortem editado tras aprobar avisa", f"{msgs}")
    expect(not de(p, "W-INCIDENT-ACTION-NO-FEATURE"),
           "cambiado, ya no cuenta como aprobado: no avisa de sus acciones")

    rel = p / "releases" / "v0.4.0.md"
    rel.write_text(rel.read_text(encoding="utf-8").replace("Algo.", "Errata."), encoding="utf-8")
    msgs = de(p, "W-PREP-RELEASE-CHANGED")
    expect(len(msgs) == 1 and "0.4.0" in msgs[0], "la versión cambió: aviso en la preparación",
           f"{msgs}")
    r = run(p, "approve", "v0.4.0")
    huella = operate_sources.release(p, "0.4.0")["digest"]
    expect(r.returncode == 0 and f"0.4.0 · {huella}" in path.read_text(encoding="utf-8")
           and not de(p, "W-PREP-RELEASE-CHANGED"),
           "aprobarla de nuevo guarda la huella nueva y el aviso desaparece", r.stdout + r.stderr)
    path.write_text(path.read_text(encoding="utf-8").replace("Pasos redactados.",
                                                             "Otros pasos.", 1),
                    encoding="utf-8")
    msgs = de(p, "W-PREP-NOT-APPROVED")
    expect(len(msgs) == 1 and "cambió después de aprobarse" in msgs[0],
           "la preparación editada tras aprobar avisa", f"{msgs}")


# ----------------------------------------------------------------- T007

# La misma lista de casos que los selftests de release, architecture,
# discovery y sdd, con operate.py approve en lugar de la orden de cada plugin:
# las cinco copias del analizador de comandos responden igual.
MENCIONES = [
    "git commit -q -m 'operate: la compuerta ya no bloquea operate.py approve'",
    'gh pr create --title t --body "Corrige: python3 operate.py approve en texto"',
    "cat > notas.md <<'EOF'\npython3 plugins/operate/scripts/operate.py approve\nEOF",
    'echo "para aprobar: python3 operate.py approve"',
    "grep -rn 'operate.py approve' plugins/operate/README.md",
    "git commit -m 'la compuerta ya no bloquea `python3 operate.py approve`'",
    "gh pr create --title t --body 'Ahora `operate.py approve` solo se bloquea si se ejecuta'",
    "git commit -m 'cita $(python3 operate.py approve) en texto'",
]

EJECUCIONES = [
    "python3 operate.py approve",
    "python3 /x/plugins/operate/scripts/operate.py approve --skill",
    'python3 "$HOME/plugins/operate/scripts/operate.py" approve v0.4.0',
    "cd plugins/operate && python3 scripts/operate.py approve",
    "ls; FOO=1 python3 operate.py approve I001",
    "echo `python3 operate.py approve`",
    'echo "$(python3 operate.py approve)"',
    'git commit -m "$(python3 /x/operate.py approve)"',
    "x=$(cd y && python3 operate.py approve)",
    "python3 operate.py approve; echo $'it\\'s'",
]


def hook(root, sub, tool, tool_input, tool_use_id="t1", env_extra=None):
    payload = json.dumps({"tool_name": tool, "tool_use_id": tool_use_id, "cwd": str(root),
                          "tool_input": tool_input})
    return run(root, sub, stdin=payload, env_extra=env_extra)


def deniega(r):
    if r.returncode != 0:
        return None
    if not r.stdout.strip():
        return False
    d = json.loads(r.stdout)["hookSpecificOutput"]
    return d["permissionDecision"] == "deny" and bool(d["permissionDecisionReason"])


def test_F011_R012_guardrails():
    print("\nF011 · R012: el modelo no puede aprobar una preparación ni un postmortem")
    p = con_version("r012")
    prep = preparacion_completa(p)
    inc = postmortem_completo(p)
    for rel, linea in (("operations/v0.4.0.md", "| Estado   | Draft |"),
                       (f"operations/incidents/{inc.name}", "| Estado           | Draft |")):
        for nuevo in ("Approved", "Approved · 0123456789ab", "Aprobada", "Draft · 0123456789ab"):
            r = hook(p, "guard", "Edit", {"file_path": rel, "old_string": linea,
                                          "new_string": linea.replace("Draft", nuevo)})
            expect(deniega(r) is True and "/operate:approve" in r.stdout,
                   f"un Edit que pone {nuevo!r} en {rel.split('/')[-1]} se deniega", r.stdout)
    aprobada = prep.read_text(encoding="utf-8").replace(
        "| Estado   | Draft |", "| Estado   | Approved · 0123456789ab |")
    r = hook(p, "guard", "Write", {"file_path": str(prep), "content": aprobada})
    expect(deniega(r) is True, "un Write que aprueba se deniega", r.stdout)
    r = hook(p, "guard", "Write", {"file_path": "operations/incidents/I009-x.md",
                                   "content": "# x\n\n| Campo | Valor |\n| - | - |\n"
                                              "| Estado | Approved |\n"})
    expect(deniega(r) is True, "crear un incidente ya aprobado se deniega")
    r = hook(p, "guard", "Edit", {"file_path": str(prep), "old_string": "Pasos redactados.",
                                  "new_string": "Otros pasos."})
    expect(deniega(r) is False, "editar el contenido de un borrador no se bloquea")
    for ruta in ("operations/incidents.md", "operations/notas.md", "specs/x.md"):
        r = hook(p, "guard", "Write", {"file_path": ruta, "content": "| Estado | Approved |"})
        expect(deniega(r) is False, f"{ruta} no se protege")

    for cmd in MENCIONES:
        corto = cmd.splitlines()[0][:50]
        expect(not operate.invokes_approve(cmd), f"no es ejecución: {corto!r}")
        expect(deniega(hook(p, "guard", "Bash", {"command": cmd})) is False,
               f"la compuerta no bloquea: {corto!r}")
    for cmd in EJECUCIONES:
        expect(operate.invokes_approve(cmd), f"es ejecución: {cmd!r}")
        r = hook(p, "guard", "Bash", {"command": cmd})
        expect(deniega(r) is True and "allow" not in r.stdout, f"bloquea: {cmd!r}", r.stdout)
    for cmd in ("python3 operate.py check --check", "python3 operate.py prepare v0.4.0"):
        expect(deniega(hook(p, "guard", "Bash", {"command": cmd})) is False,
               f"otros subcomandos pasan: {cmd!r}")

    print("  auditoría")
    opaco = "bash -c 'python3 plugins/operate/scripts/operate.py approve I001'"
    r = hook(p, "guard", "Bash", {"command": opaco}, tool_use_id="a1")
    expect(deniega(r) is False, "la compuerta deja pasar un bash -c", r.stdout)
    run(p, "approve", "I001")
    expect(estado(inc).startswith("Approved"), "el comando opaco aprobó")
    r = hook(p, "audit", "Bash", {}, tool_use_id="a1")
    expect(r.returncode == 2 and estado(inc) == "Draft" and inc.name in r.stderr,
           "y la auditoría devuelve el postmortem a Draft y avisa", r.stderr)
    hook(p, "guard", "Bash", {"command": "ls"}, tool_use_id="a2")
    r = hook(p, "audit", "Bash", {}, tool_use_id="a2")
    expect(r.returncode == 0 and not r.stderr, "un comando que no toca el Estado: silencio")
    expect(hook(p, "audit", "Bash", {}, tool_use_id="sin-foto").returncode == 0,
           "sin instantánea no opina")

    q = con_version("r012-sin-operations")
    hook(q, "guard", "Bash", {"command": "python3 crea.py"}, tool_use_id="a3")
    nuevo = q / "operations" / "v0.4.0.md"
    nuevo.parent.mkdir()
    nuevo.write_text("# x\n\n| Campo | Valor |\n| - | - |\n| Estado | Approved · 0123456789ab |\n",
                     encoding="utf-8")
    r = hook(q, "audit", "Bash", {}, tool_use_id="a3")
    expect(r.returncode == 2 and estado(nuevo) == "Draft",
           "sin operations/ al empezar: una preparación creada ya aprobada vuelve a Draft",
           r.stderr)

    print("  escape y fallo abierto")
    r = hook(p, "guard", "Bash", {"command": "python3 operate.py approve"},
             env_extra={"OPERATE_BYPASS": "1"})
    expect(deniega(r) is False, "OPERATE_BYPASS=1 desactiva la compuerta")
    hook(p, "guard", "Bash", {"command": "python3 x.py"}, tool_use_id="b1")
    run(p, "approve", "v0.4.0")
    r = hook(p, "audit", "Bash", {}, tool_use_id="b1", env_extra={"OPERATE_BYPASS": "1"})
    expect(r.returncode == 0 and estado(prep).startswith("Approved"),
           "OPERATE_BYPASS=1 también desactiva la auditoría")
    r = run(p, "guard", stdin="no soy json")
    expect(r.returncode == 0 and not r.stdout, "un payload ilegible falla abierto")
    r = run(p, "guard", stdin=json.dumps({"tool_name": "Edit", "cwd": str(p),
                                          "tool_input": {"file_path": 7}}))
    expect(r.returncode == 0 and not r.stdout, "un payload inesperado falla abierto", r.stderr)
    fuente = SCRIPT.read_text(encoding="utf-8")
    expect('"allow"' not in fuente and "'allow'" not in fuente, "nunca devuelve allow")

    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    expect(all(h.get("timeout") and h.get("command") == "python3" and h.get("args")
               for grupo in hooks.values() for m in grupo for h in m["hooks"])
           and any(m["matcher"] == "Write|Edit|Bash" for m in hooks["PreToolUse"])
           and any(m["matcher"] == "Bash" for m in hooks["PostToolUse"]),
           "hooks.json registra guard y audit en forma exec con timeout")


def cobertura_de_codigos():
    # main() la ejecuta despues de todas las pruebas: compara los codigos
    # declarados con los que las pruebas vieron emitirse.
    print("\ncobertura de codigos de hallazgo")
    declarados = set(operate.FINDINGS)
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
