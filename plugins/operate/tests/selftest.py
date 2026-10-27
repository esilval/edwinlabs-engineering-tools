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
           and f4.read_text(encoding="utf-8").startswith(f"# Incidente {i4} — Cobro | doble en caja\n"),
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
