#!/usr/bin/env python3
"""
Regresion del plugin architecture. Sin dependencias externas: solo stdlib.

Cada prueba es una funcion test_F006_Rxxx_* que cita el requisito de la
feature 006 al que sirve, para que la trazabilidad de sdd la reconozca, y
verifica con expect(...). Los productos de prueba se construyen a mano en el
formato de discovery: solo la prueba de contrato ejecuta discovery.py.
Corre en CI y en local:

    python3 plugins/architecture/tests/selftest.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN / "scripts" / "architecture.py"
sys.path.insert(0, str(PLUGIN / "scripts"))
import architecture  # noqa: E402

fallos = []
BASE = Path(tempfile.mkdtemp(prefix="architecture-selftest-"))
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
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True, cwd=str(cwd), env=env, timeout=60,
    )


# ----------------------------------------------------------------- T001

def test_F006_R015_no_importa_otros_plugins():
    # architecture funciona sin discovery ni sdd instalados: ni el script ni
    # este selftest pueden importar su codigo.
    import ast
    prohibido = re.compile(r"^(discovery|sdd\w*)$")
    for path in (SCRIPT, Path(__file__)):
        modulos = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modulos += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modulos.append(node.module.split(".")[0])
            elif (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "import_module"
                  and node.args and isinstance(node.args[0], ast.Constant)):
                modulos.append(str(node.args[0].value).split(".")[0])
        malos = [m for m in modulos if prohibido.match(m)]
        expect(not malos, f"{path.name} no importa discovery ni sdd", f"{malos}")
    r = run(proyecto("r015-sin-subcomando"))
    expect(r.returncode == 2 and "Subcomandos" in r.stderr,
           "sin subcomando: uso por stderr y salida 2", r.stderr[:200])


# ----------------------------------------------------------------- T002
# Un producto coherente en el formato de discovery, construido a mano (copia de
# los fixtures de su selftest, con una restriccion que cita su seccion).

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

- Las ventas del día se consultan al cerrar la caja (D1§3)

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


def sella(path):
    """Aprueba un artefacto con la huella de architecture, como lo haria su dueño."""
    texto = path.read_text(encoding="utf-8")
    path.write_text(architecture.STATUS_ROW.sub(
        rf"\g<1>Approved · {architecture.content_digest(texto)}\3", texto, count=1),
        encoding="utf-8")


def con_producto(p, aprobado=True, brief=PRODUCTO_BRIEF, backlog=PRODUCTO_BACKLOG):
    """Pone en p un product/ de discovery: brief y backlog, sellados si aprobado."""
    (p / "product" / "sources").mkdir(parents=True, exist_ok=True)
    (p / "product" / "brief.md").write_text(brief, encoding="utf-8")
    (p / "product" / "backlog.md").write_text(backlog, encoding="utf-8")
    if aprobado:
        sella(p / "product" / "brief.md")
        sella(p / "product" / "backlog.md")
    return p


def test_F006_R001_init_sin_producto_aprobado():
    casos = []
    p = con_producto(proyecto("r001-draft"), aprobado=False)
    casos.append((p, "product/backlog.md no está aprobado", "/discovery:approve"))
    p = con_producto(proyecto("r001-cambiado"))
    brief = p / "product" / "brief.md"
    brief.write_text(brief.read_text(encoding="utf-8").replace("sin calcularlas", "al vuelo"),
                     encoding="utf-8")
    casos.append((p, "product/brief.md cambió después de aprobarse", "/discovery:approve"))
    casos.append((proyecto("r001-sin-product"), "no hay product/", "/discovery:"))
    for p, motivo, remedio in casos:
        r = run(p, "init")
        expect(r.returncode == 1 and motivo in r.stderr and remedio in r.stderr
               and not (p / "architecture").exists(),
               f"{p.name}: no crea nada y dice {motivo!r}", r.stderr)


def test_F006_R001_init_crea_las_plantillas():
    p = con_producto(proyecto("r001-init"))
    r = run(p, "init")
    creados = sorted(x.name for x in (p / "architecture").iterdir()) \
        if (p / "architecture").is_dir() else []
    expect(r.returncode == 0 and creados == ["adr", "components.md", "quality.md",
                                             "questions.md", "standards.md"],
           "con el producto aprobado: crea los cuatro artefactos y adr/", r.stdout + r.stderr)
    (p / "architecture" / "quality.md").write_text("propio\n", encoding="utf-8")
    run(p, "init")
    expect((p / "architecture" / "quality.md").read_text(encoding="utf-8") == "propio\n",
           "un segundo init no sobrescribe lo que ya existe")


def test_F006_R015_lee_el_producto():
    # Lo que architecture lee de product/ con su copia del formato de discovery.
    p = con_producto(proyecto("r015-lectura"))
    brief = p / "product" / "brief.md"
    brief.write_text(brief.read_text(encoding="utf-8").replace(
        "## Restricciones\n",
        "## Restricciones\n\nTexto suelto que cita D1§4 y no es una viñeta.\n"),
        encoding="utf-8")
    objetivos = architecture.product_goals(p)
    expect(sorted(objetivos) == ["G1", "G2"]
           and objetivos["G2"]["title"] == "Que el comercio use sus datos fuera",
           "objetivos del brief con su titulo", f"{sorted(objetivos)}")
    expect(architecture.product_restriction_sections(p) == {"D1§3"},
           "restricciones: solo las secciones que citan sus viñetas",
           f"{architecture.product_restriction_sections(p)}")
    candidatas = architecture.product_candidates(p)
    expect(sorted(candidatas) == ["B01", "B02", "B03"]
           and candidatas["B03"]["state"] == "descartada"
           and candidatas["B01"]["state"] == "candidata",
           "candidatas con su estado, la descartada incluida",
           f"{ {k: v['state'] for k, v in candidatas.items()} }")
    huellas = architecture.product_digests(p)
    expect(huellas["backlog"] == architecture.content_digest(
               (p / "product" / "backlog.md").read_text(encoding="utf-8"))
           and huellas["brief"] is not None,
           "huellas del contenido actual del brief y del backlog", f"{huellas}")


def test_F006_R015_contrato_con_discovery():
    if not DISCOVERY.is_file():
        print("  (sin plugins/discovery en el repositorio: prueba de contrato omitida)")
        return
    p = proyecto("r015-contrato")
    (p / "entrada").mkdir()
    (p / "entrada" / "vision.md").write_text(PRODUCTO_DOC, encoding="utf-8")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(p),
               CLAUDE_PLUGIN_ROOT=str(DISCOVERY.parent.parent))

    def discovery(*args):
        return subprocess.run([sys.executable, str(DISCOVERY), *args], capture_output=True,
                              text=True, cwd=str(p), env=env, timeout=60)

    r = discovery("ingest", str(p / "entrada" / "vision.md"))
    expect(r.returncode == 0, "discovery ingiere el documento de prueba", r.stderr)
    con_producto(p, aprobado=False)
    r = discovery("approve")
    expect(r.returncode == 0 and architecture.product_problems(p) == [],
           "lo que discovery aprueba, architecture lo da por aprobado",
           r.stdout + r.stderr + f"{architecture.product_problems(p)}")
    brief = p / "product" / "brief.md"
    aprobado = brief.read_text(encoding="utf-8")
    brief.write_text(aprobado.replace("\n## Usuarios", "\n\n\n## Usuarios   "), encoding="utf-8")
    expect(architecture.product_problems(p) == [],
           "reformatear sin cambiar el contenido no invalida la aprobacion")
    brief.write_text(aprobado.replace("sin calcularlas", "sin calcularlas a mano"),
                     encoding="utf-8")
    expect(any("brief.md cambió" in x for x in architecture.product_problems(p)),
           "un brief editado tras aprobarse: cambiado", f"{architecture.product_problems(p)}")


# ----------------------------------------------------------------- T003
# Una arquitectura coherente sobre el producto de prueba: las pruebas de las
# tareas siguientes la rompen de una en una.

def cabecera(titulo, estado="Draft"):
    return f"# {titulo}\n\n| Campo  | Valor |\n| ------ | ----- |\n| Estado | {estado} |\n\n"


ARQ_QUALITY = cabecera("Atributos de calidad") + """## Atributos

### Q1 — Resumen al cerrar

- **Escenario:** al cerrar la caja, el total del día aparece en menos de 2 segundos con 5000 ventas
- **Motivo:** G1, D1§3

### Q2 — Exportación completa

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

ARQ_QUESTIONS = cabecera("Preguntas de arquitectura") + """## Preguntas

- [x] (ADR-0001; Q2) ¿Hace falta exportar en segundo plano?
  - **Respuesta:** no; 30 segundos son aceptables.
"""


def adr(numero, titulo, estado="Draft", motivo="Q1, G1", sustituye="—", completo=True):
    cuerpo = ("## Contexto\n\nLas ventas del día se consultan al cerrar.\n\n"
              "## Decisión\n\nUna sola base de datos relacional para ventas y movimientos.\n\n"
              "## Alternativas descartadas\n\n- Una base por componente: sin necesidad hoy.\n\n")
    if completo:
        cuerpo += "## Consecuencias\n\n- Los dos componentes comparten esquema.\n"
    return (f"# ADR-{numero} — {titulo}\n\n| Campo     | Valor |\n| --------- | ----- |\n"
            f"| Estado    | {estado} |\n| Fecha     | 2026-10-16 |\n| Motivo    | {motivo} |\n"
            f"| Sustituye | {sustituye} |\n\n{cuerpo}")


def con_arquitectura(p, quality=ARQ_QUALITY, components=ARQ_COMPONENTS,
                     standards=ARQ_STANDARDS, questions=ARQ_QUESTIONS, adrs=None):
    """Pone en p un producto aprobado y una arquitectura coherente en Draft."""
    con_producto(p)
    arq = p / "architecture"
    (arq / "adr").mkdir(parents=True, exist_ok=True)
    for nombre, texto in (("quality.md", quality), ("components.md", components),
                          ("standards.md", standards), ("questions.md", questions)):
        (arq / nombre).write_text(texto, encoding="utf-8")
    for archivo, texto in (adrs if adrs is not None else
                           {"0001-base-de-datos-unica.md": adr("0001", "Base de datos única")}
                           ).items():
        (arq / "adr" / archivo).write_text(texto, encoding="utf-8")
    return p


def test_F006_R003_lee_componentes_y_candidatas():
    p = con_arquitectura(proyecto("r003-lectura"))
    comps = {c["id"]: c for c in architecture.components(p)}
    expect(sorted(comps) == ["C1", "C2"]
           and comps["C1"]["fields"]["responsabilidad"].startswith("registra ventas")
           and comps["C1"]["fields"]["candidatas"] == "B01",
           "C1 con su responsabilidad y sus candidatas", f"{comps}")
    otro = ARQ_COMPONENTS.replace("- **Candidatas:** B01", "- **Candidatas:** B01, B02")
    p = con_arquitectura(proyecto("r003-varias"), components=otro)
    c1 = architecture.components(p)[0]
    expect(architecture.CAND_REF.findall(c1["fields"]["candidatas"]) == ["01", "02"],
           "un componente que aloja B01 y B02 las lista las dos")
    q = architecture.quality(p)
    expect([x["id"] for x in q] == ["Q1", "Q2"] and q[1]["fields"]["motivo"] == "G2",
           "atributos con su escenario y su motivo")
    s = architecture.standards(p)
    expect(s and s[0]["fields"]["decision"] == "ADR-0001" and s[0]["fields"]["tipo"] == "dependencia",
           "estandares con su tipo y su decision", f"{s}")
    preguntas = architecture.questions(p)
    expect(len(preguntas) == 1 and not preguntas[0]["open"]
           and preguntas[0]["adrs"] == ["ADR-0001"] and preguntas[0]["items"] == ["Q2"],
           "preguntas con su estado y lo que citan", f"{preguntas}")
    d = architecture.adrs(p)[0]
    expect(d["id"] == "ADR-0001" and d["title"] == "Base de datos única" and d["state"] == "draft"
           and d["motivo"] == "Q1, G1" and all(d["sections"].values()),
           "un ADR con su titulo, estado, motivo y las cuatro secciones", f"{d}")


def test_F006_R005_numeracion_no_reutiliza():
    p = con_arquitectura(proyecto("r005-numeracion"), adrs={
        "0001-base-de-datos-unica.md": adr("0001", "Base de datos única"),
        "0002-cola-de-trabajos.md": adr("0002", "Cola de trabajos", estado="Rejected"),
    })
    estados = [a["state"] for a in architecture.adrs(p)]
    r = run(p, "next-id", "ADR")
    expect(estados == ["draft", "rejected"] and r.stdout.strip() == "ADR-0003",
           "con 0001 y 0002 rechazada, el siguiente es ADR-0003", f"{estados} {r.stdout}")
    expect([run(p, "next-id", k).stdout.strip() for k in ("Q", "c", "S")] == ["Q3", "C3", "S2"],
           "Q, C y S tambien siguen al maximo, en mayusculas o minusculas")
    expect(run(p, "next-id", "X").returncode == 2, "un tipo desconocido sale con 2")
    for raro in ("0003-Cache_Local.md", "0004.md"):
        (p / "architecture" / "adr" / raro).write_text(adr(raro[:4], "Raro"), encoding="utf-8")
    expect(run(p, "next-id", "ADR").stdout.strip() == "ADR-0005",
           "archivos con nombre fuera del patron tambien ocupan su numero")

    preguntas = ARQ_QUESTIONS + "\n- [ ] (Q1) ¿Guardamos en S3 o en disco?\n"
    q = con_arquitectura(proyecto("r005-citas"), questions=preguntas)
    abierta = architecture.questions(q)[-1]
    expect(abierta["open"] and abierta["items"] == ["Q1"] and abierta["adrs"] == [],
           "las citas de una pregunta salen solo de su parentesis inicial", f"{abierta}")
    vacio = con_producto(proyecto("r005-vacio"))
    expect(run(vacio, "next-id", "ADR").stdout.strip() == "ADR-0001",
           "sin architecture/, el primero es ADR-0001")


# --------------------------------------------------------------------------

def cobertura_de_codigos():
    # main() la ejecuta despues de todas las pruebas: compara los codigos
    # declarados con los que las pruebas vieron emitirse.
    print("\ncobertura de codigos de hallazgo")
    declarados = set(architecture.FINDINGS)
    expect(declarados <= PROBADOS, f"los {len(declarados)} codigos declarados se prueban",
           f"sin probar: {sorted(declarados - PROBADOS)}")


def main():
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    try:
        for nombre, fn in tests:
            print(f"\n{nombre}")
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
    print(f"OK: {len(tests)} pruebas, todas las comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
