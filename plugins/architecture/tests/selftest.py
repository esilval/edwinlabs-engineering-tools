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


# ----------------------------------------------------------------- T004

def con_codigo(root, code):
    """
    Hallazgos de un codigo. Solo cuenta como probado si de verdad se emitio:
    una prueba que afirma su ausencia no demuestra que sea alcanzable.
    """
    out = [f for f in architecture.analyze(root)["findings"] if f["code"] == code]
    if out:
        PROBADOS.add(code)
    return out


def codigos(root):
    return {f["code"] for f in architecture.analyze(root)["findings"]}


def errores(root):
    """Codigos de error: una arquitectura sin aprobar siempre trae avisos."""
    return {c for c in codigos(root) if c.startswith("E-")}


def test_F006_R002_atributo_no_medible_o_sin_motivo():
    p = con_arquitectura(proyecto("r002-coherente"))
    expect(not ({"E-QUALITY-NOT-MEASURABLE", "E-QUALITY-NO-MOTIVE"} & codigos(p)),
           "la arquitectura de prueba no tiene hallazgos de atributos", f"{codigos(p)}")

    vago = ARQ_QUALITY.replace(
        "al cerrar la caja, el total del día aparece en menos de 2 segundos con 5000 ventas",
        "el sistema es escalable")
    p = con_arquitectura(proyecto("r002-vago"), quality=vago)
    h = con_codigo(p, "E-QUALITY-NOT-MEASURABLE")
    expect(len(h) == 1 and "Q1" in h[0]["message"],
           "«el sistema es escalable» sin cifra: atributo no medible", f"{h}")
    citado = ARQ_QUALITY.replace(
        "al cerrar la caja, el total del día aparece en menos de 2 segundos con 5000 ventas",
        "el sistema es escalable, como pide G1 y dice D1§3")
    p = con_arquitectura(proyecto("r002-solo-citas"), quality=citado)
    expect(len(con_codigo(p, "E-QUALITY-NOT-MEASURABLE")) == 1,
           "los numeros de una cita (G1, D1§3) no cuentan como cifra")

    for nombre, motivo in (("sin-cita", "porque sí"), ("objetivo-inexistente", "G9"),
                           ("seccion-que-no-es-restriccion", "D1§4")):
        texto = ARQ_QUALITY.replace("- **Motivo:** G2", f"- **Motivo:** {motivo}")
        p = con_arquitectura(proyecto(f"r002-{nombre}"), quality=texto)
        h = con_codigo(p, "E-QUALITY-NO-MOTIVE")
        expect(len(h) == 1 and "Q2" in h[0]["message"],
               f"motivo {motivo!r}: atributo sin motivo", f"{h}")

    texto = ARQ_QUALITY.replace("- **Motivo:** G2", "- **Motivo:** D1§3")
    p = con_arquitectura(proyecto("r002-restriccion"), quality=texto)
    expect("E-QUALITY-NO-MOTIVE" not in codigos(p),
           "un motivo que cita la seccion de una restriccion del brief (D1§3) vale")


def test_F006_R004_candidata_sin_componente():
    base = con_arquitectura(proyecto("r004-coherente"))
    expect(not ({"E-COMPONENT-NO-RESPONSIBILITY", "E-COMPONENT-CANDIDATE-UNPLACED"}
                & codigos(base)),
           "la arquitectura de prueba no tiene hallazgos de componentes", f"{codigos(base)}")
    sin_b02 =ARQ_COMPONENTS.replace("- **Candidatas:** B02", "- **Candidatas:** —")
    p = con_arquitectura(proyecto("r004-sin-b02"), components=sin_b02)
    h = con_codigo(p, "E-COMPONENT-CANDIDATE-UNPLACED")
    expect(len(h) == 1 and "B02" in h[0]["message"] and h[0]["severity"] == "error",
           "B02 sin componente: error que la nombra", f"{h}")
    expect(not any("B03" in x["message"] for x in h),
           "B03 esta descartada: ningun error por ella")

    sin_resp = ARQ_COMPONENTS.replace(
        "- **Responsabilidad:** genera archivos de movimientos a partir de las ventas",
        "- **Responsabilidad:** —")
    p = con_arquitectura(proyecto("r004-sin-responsabilidad"), components=sin_resp)
    h = con_codigo(p, "E-COMPONENT-NO-RESPONSIBILITY")
    expect(len(h) == 1 and "C2" in h[0]["message"], "componente con responsabilidad «—»", f"{h}")
    sin_campo = ARQ_COMPONENTS.replace(
        "- **Responsabilidad:** genera archivos de movimientos a partir de las ventas\n", "")
    p = con_arquitectura(proyecto("r004-sin-campo"), components=sin_campo)
    h = con_codigo(p, "E-COMPONENT-NO-RESPONSIBILITY")
    expect(len(h) == 1 and "C2" in h[0]["message"], "componente sin el campo", f"{h}")


# ----------------------------------------------------------------- T005

def test_F006_R005_adr_incompleto_o_sin_motivo():
    base = con_arquitectura(proyecto("r005-coherente"))
    expect(errores(base) == set(), "la arquitectura de prueba no tiene ningun error",
           f"{architecture.analyze(base)['findings']}")

    p = con_arquitectura(proyecto("r005-incompleto"), adrs={
        "0001-base-de-datos-unica.md": adr("0001", "Base de datos única", completo=False)})
    h = con_codigo(p, "E-ADR-INCOMPLETE")
    expect(len(h) == 1 and "ADR-0001" in h[0]["message"] and "consecuencias" in h[0]["message"]
           and h[0]["artifact"].endswith("0001-base-de-datos-unica.md"),
           "un ADR sin consecuencias esta incompleto y lo dice", f"{h}")
    sin_alternativas = adr("0001", "Base de datos única").replace(
        "- Una base por componente: sin necesidad hoy.", "")
    p = con_arquitectura(proyecto("r005-sin-alternativas"),
                         adrs={"0001-base-de-datos-unica.md": sin_alternativas})
    h = con_codigo(p, "E-ADR-INCOMPLETE")
    expect(len(h) == 1 and "alternativas" in h[0]["message"],
           "un ADR sin alternativas descartadas es un error", f"{h}")

    p = con_arquitectura(proyecto("r005-sin-motivo"), adrs={
        "0001-base-de-datos-unica.md": adr("0001", "Base de datos única", motivo="—")})
    h = con_codigo(p, "E-ADR-NO-MOTIVE")
    expect(len(h) == 1 and "ADR-0001" in h[0]["message"],
           "un ADR que no cita atributo ni objetivo: decision sin motivo", f"{h}")

    p = con_arquitectura(proyecto("r005-duplicado"), adrs={
        "0001-base-de-datos-unica.md": adr("0001", "Base de datos única"),
        "0001-otra.md": adr("0001", "Otra"),
    })
    h = con_codigo(p, "E-ADR-ID-DUPLICATE")
    expect(len(h) == 1 and "ADR-0001" in h[0]["message"], "dos archivos con el 0001", f"{h}")

    for estado in ("Rejected", "Superseded by ADR-0001"):
        historia = adr("0002", "Historia", estado=estado, motivo="Q9", sustituye="ADR-0042",
                       completo=False)
        p = con_arquitectura(proyecto(f"r005-historia-{estado.split()[0].lower()}"), adrs={
            "0001-base-de-datos-unica.md": adr("0001", "Base de datos única"),
            "0002-historia.md": historia})
        expect(errores(p) == set(),
               f"una decision {estado.split()[0]} queda como historia: ni forma ni citas",
               f"{architecture.analyze(p)['findings']}")

    cuerpo = adr("0001", "Base de datos única").replace(
        "Las ventas del día se consultan al cerrar.",
        "Las ventas del día se consultan al cerrar. Revisa ADR-0042 y `_cache_`.")
    p = con_arquitectura(proyecto("r005-cuerpo"),
                         adrs={"0001-base-de-datos-unica.md": cuerpo})
    expect(any("ADR-0042" in f["message"] for f in con_codigo(p, "E-ARCH-REF-UNKNOWN"))
           and "E-ARCH-TEMPLATE" not in codigos(p),
           "un ADR-NNNN inexistente en el cuerpo es error; `_cache_` en codigo no es hueco")


def test_F006_R006_estandar_sin_decision():
    sin = ARQ_STANDARDS.replace("- **Decisión:** ADR-0001", "- **Decisión:** —")
    p = con_arquitectura(proyecto("r006-sin-decision"), standards=sin)
    h = con_codigo(p, "E-STANDARD-NO-ADR")
    expect(len(h) == 1 and "S1" in h[0]["message"] and h[0]["severity"] == "error",
           "un estandar sin decision de origen es un error", f"{h}")


def test_F006_R007_citas_inexistentes():
    comps = ARQ_COMPONENTS.replace("- **Candidatas:** B02", "- **Candidatas:** B02, B09")
    stds = ARQ_STANDARDS.replace("- **Decisión:** ADR-0001", "- **Decisión:** ADR-0009")
    p = con_arquitectura(proyecto("r007-citas"), components=comps, standards=stds)
    mensajes = [f["message"] for f in con_codigo(p, "E-ARCH-REF-UNKNOWN")]
    expect(any("B09" in m and "components.md" in m for m in mensajes),
           "un componente que aloja B09, inexistente: error que la nombra", f"{mensajes}")
    expect(any("ADR-0009" in m and "standards.md" in m for m in mensajes),
           "un estandar que cita ADR-0009, inexistente: error que la nombra", f"{mensajes}")
    detalle = ARQ_STANDARDS.replace("C2 → C1", "C2 → C7")
    p = con_arquitectura(proyecto("r007-componente"), standards=detalle)
    expect(any("C7" in f["message"] for f in con_codigo(p, "E-ARCH-REF-UNKNOWN")),
           "un estandar que cita un componente inexistente tambien")


def test_F006_R009_pregunta_abierta_bloquea():
    abierta = ARQ_QUESTIONS + "\n- [ ] (ADR-0001) ¿La base de datos va en la nube del cliente?\n"
    p = con_arquitectura(proyecto("r009-abierta"), questions=abierta)
    h = con_codigo(p, "E-ARCH-OPEN-QUESTION")
    expect(len(h) == 1 and "ADR-0001" in h[0]["message"] and h[0]["severity"] == "error",
           "una pregunta abierta sobre ADR-0001 es un error que la nombra", f"{h}")
    sobre_atributo = ARQ_QUESTIONS + "\n- [ ] (Q1) ¿Cuántas ventas tiene un día malo?\n"
    p = con_arquitectura(proyecto("r009-atributo"), questions=sobre_atributo)
    expect(len(con_codigo(p, "E-ARCH-OPEN-QUESTION")) == 1,
           "tambien bloquea una pregunta abierta sobre un atributo")
    p = con_arquitectura(proyecto("r009-respondida"))
    expect("E-ARCH-OPEN-QUESTION" not in codigos(p),
           "la pregunta respondida de la base no bloquea")


def test_F006_R005_huecos_de_plantilla():
    p = con_producto(proyecto("r005-plantilla"))
    run(p, "init")
    nuevo = (PLUGIN / "templates" / "adr.md").read_text(encoding="utf-8")
    (p / "architecture" / "adr" / "0001-x.md").write_text(
        nuevo.replace("{{NUMBER}}", "0001").replace("{{TITLE}}", "X")
        .replace("{{DATE}}", "2026-10-16"), encoding="utf-8")
    artefactos = {f["artifact"] for f in con_codigo(p, "E-ARCH-TEMPLATE")}
    expect({"architecture/quality.md", "architecture/components.md", "architecture/standards.md",
            "architecture/adr/0001-x.md"} <= artefactos,
           "las plantillas recien copiadas tienen huecos que la comprobacion senala",
           f"{artefactos}")
    expect("architecture/questions.md" not in artefactos,
           "questions.md recien creado no tiene huecos")


# ----------------------------------------------------------------- T006

def test_F006_R008_check_en_ci():
    import json
    ok = con_arquitectura(proyecto("r008-ok"))
    r = run(ok, "check", "--check")
    expect(r.returncode == 0 and "OK: sin errores." in r.stdout,
           "sin errores, --check sale con 0", r.stdout + r.stderr)
    base = json.loads(run(ok, "check", "--json").stdout)
    expect(base["counts"]["errors"] == 0 and base["counts"]["warnings"] > 0,
           "los hallazgos de la base son todos avisos", f"{base['counts']}")

    sin_b02 = ARQ_COMPONENTS.replace("- **Candidatas:** B02", "- **Candidatas:** —")
    mal = con_arquitectura(proyecto("r008-error"), components=sin_b02)
    r = run(mal, "check", "--check")
    expect(r.returncode == 1 and "E-COMPONENT-CANDIDATE-UNPLACED" in r.stdout,
           "con un error, --check sale con 1 y lo lista", r.stdout)
    r = run(mal, "check")
    expect(r.returncode == 0 and "FALLA: 1 error(es)." in r.stdout,
           "sin --check, el informe legible sale siempre con 0", r.stdout)

    r = run(mal, "check", "--json")
    data = json.loads(r.stdout)
    hallazgo = data["findings"][0] if data["findings"] else {}
    expect(r.returncode == 0 and data["schema"] == "architecture.check/v1" and not data["ok"]
           and set(hallazgo) == {"code", "severity", "message", "artifact"}
           and hallazgo["artifact"] == "architecture/components.md"
           and hallazgo["code"] == "E-COMPONENT-CANDIDATE-UNPLACED"
           and hallazgo["severity"] == "error"
           and data["counts"]["errors"] == 1,
           "--json: schema, ok, counts y cada hallazgo con code, severity, message y artifact",
           r.stdout[:300])
    r = run(mal, "check", "--json", "--check")
    expect(r.returncode == 1 and json.loads(r.stdout)["ok"] is False,
           "--json --check: el mismo JSON y salida 1")

    # La arquitectura de prueba no tiene errores pero esta sin aprobar: solo
    # avisos reales (W-ARCH-NOT-APPROVED), que no hacen fallar en CI.
    r = run(ok, "check", "--check")
    expect(r.returncode == 0 and "W-ARCH-NOT-APPROVED" in r.stdout
           and "E-" not in r.stdout,
           "con solo avisos, --check sale con 0", r.stdout)

    r = run(ok, "check", "--chek")
    expect(r.returncode == 2 and "argumento desconocido" in r.stderr,
           "un argumento desconocido sale con 2")


# ----------------------------------------------------------------- T007

def estado(p, rel):
    texto = (p / rel).read_text(encoding="utf-8")
    return architecture.doc_status(texto)


def foto(p):
    """Contenido de architecture/, para comprobar que una negativa no cambia nada."""
    base = p / "architecture"
    return {str(x.relative_to(base)): x.read_bytes() for x in sorted(base.rglob("*"))
            if x.is_file()}


DOS_ADR = {
    "0001-base-de-datos-unica.md": adr("0001", "Base de datos única"),
    "0002-despliegue.md": adr("0002", "Despliegue en un solo servidor", motivo="Q2"),
}


def test_F006_R010_aprueba_el_conjunto():
    adrs = dict(DOS_ADR)
    adrs["0003-cache.md"] = adr("0003", "Caché de totales", estado="Proposed")
    adrs["0004-rechazada.md"] = adr("0004", "Rechazada", estado="Rejected")
    p = con_arquitectura(proyecto("r010-aprueba"), adrs=adrs)
    r = run(p, "approve")
    expect(r.returncode == 0, "una arquitectura coherente se aprueba", r.stdout + r.stderr)
    for rel in ("architecture/quality.md", "architecture/components.md",
                "architecture/standards.md", "architecture/questions.md",
                "architecture/adr/0001-base-de-datos-unica.md",
                "architecture/adr/0002-despliegue.md"):
        texto = (p / rel).read_text(encoding="utf-8")
        expect(architecture.artifact_state(texto) == "approved",
               f"{rel} queda sellado con la huella de su contenido", estado(p, rel))
    expect(estado(p, "architecture/adr/0003-cache.md") == "Proposed"
           and "ADR-0003" in r.stdout,
           "un ADR propuesto no se toca y se dice que espera la revision", r.stdout)
    expect(estado(p, "architecture/adr/0004-rechazada.md") == "Rejected",
           "un ADR rechazado no se toca")
    comp = p / "architecture" / "components.md"
    vacia = architecture.PRODUCT_ROW.sub("| Producto |  |", comp.read_text(encoding="utf-8"))
    expect(architecture.recorded_product(p) and "| Producto |  |" in vacia
           and architecture.PRODUCT_ROW.search(
               architecture.with_product_row(vacia, {"brief": "a" * 12, "backlog": "b" * 12})),
           "una fila Producto vacia se rellena en su sitio")
    huellas = architecture.product_digests(p)
    expect(architecture.recorded_product(p) == huellas,
           "components.md guarda la huella del brief y del backlog", f"{huellas}")
    expect("W-ARCH-NOT-APPROVED" not in codigos(p),
           "tras aprobar no queda ningun aviso de aprobacion")
    r = run(p, "approve")
    expect(r.returncode == 0 and "ya estaba aprobada" in r.stdout,
           "aprobar dos veces no cambia nada")

    sin_b02 = ARQ_COMPONENTS.replace("- **Candidatas:** B02", "- **Candidatas:** —")
    p = con_arquitectura(proyecto("r010-errores"), components=sin_b02)
    antes = foto(p)
    r = run(p, "approve")
    expect(r.returncode == 1 and "E-COMPONENT-CANDIDATE-UNPLACED" in r.stderr
           and foto(p) == antes,
           "con un error se niega, lista los errores y no cambia nada", r.stderr)

    p = con_arquitectura(proyecto("r010-producto"))
    backlog = p / "product" / "backlog.md"
    backlog.write_text(backlog.read_text(encoding="utf-8").replace("Approved", "Draft", 1),
                       encoding="utf-8")
    r = run(p, "approve")
    expect(r.returncode == 1 and "product/backlog.md no está aprobado" in r.stderr,
           "sin el producto aprobado no se aprueba la arquitectura", r.stderr)
    r = run(p, "approve", "--skill")
    expect(r.returncode == 0 and "no está aprobado" in r.stdout,
           "con --skill, la negativa sale por stdout con 0", r.stdout)


def test_F006_R009_pregunta_abierta_impide_aprobar():
    abierta = ARQ_QUESTIONS + "\n- [ ] (ADR-0002) ¿Un servidor aguanta el cierre de 50 cajas?\n"
    p = con_arquitectura(proyecto("r009-aprobar"), questions=abierta, adrs=DOS_ADR)
    antes = foto(p)
    r = run(p, "approve")
    expect(r.returncode == 1 and "E-ARCH-OPEN-QUESTION" in r.stderr
           and "ADR-0002" in r.stderr and foto(p) == antes,
           "una pregunta abierta sobre ADR-0002 impide aprobar y se nombra", r.stderr)


def test_F006_R011_cambio_tras_aprobar():
    p = con_arquitectura(proyecto("r011-cambio"))
    run(p, "approve")
    comp = p / "architecture" / "components.md"
    comp.write_text(comp.read_text(encoding="utf-8").replace(
        "registra ventas y calcula los totales del día",
        "registra ventas, devoluciones y calcula los totales del día"), encoding="utf-8")
    h = con_codigo(p, "W-ARCH-NOT-APPROVED")
    expect(len(h) == 1 and h[0]["artifact"] == "architecture/components.md"
           and "cambió después de aprobarse" in h[0]["message"],
           "editar un componente tras aprobar: aviso que nombra components.md", f"{h}")

    # Un ADR aprobado que se edita deja de contar como aprobado y approve lo
    # vuelve a sellar (D4), igual que el resto del conjunto.
    p = con_arquitectura(proyecto("r011-adr"))
    run(p, "approve")
    rel = "architecture/adr/0001-base-de-datos-unica.md"
    d = p / rel
    d.write_text(d.read_text(encoding="utf-8").replace(
        "Una sola base de datos relacional", "Una sola base de datos relacional gestionada"),
        encoding="utf-8")
    h = con_codigo(p, "W-ARCH-NOT-APPROVED")
    expect(len(h) == 1 and h[0]["artifact"] == rel and "cambió" in h[0]["message"],
           "editar un ADR aprobado: aviso que lo nombra", f"{h}")
    r = run(p, "approve")
    expect(r.returncode == 0 and rel in r.stdout
           and architecture.artifact_state(d.read_text(encoding="utf-8")) == "approved",
           "y approve lo vuelve a sellar con la huella nueva", r.stdout + r.stderr)

    p = con_arquitectura(proyecto("r011-formato"))
    run(p, "approve")
    q = p / "architecture" / "quality.md"
    q.write_text(q.read_text(encoding="utf-8").replace("\n## Atributos", "\n\n\n## Atributos   "),
                 encoding="utf-8")
    expect("W-ARCH-NOT-APPROVED" not in codigos(p),
           "reformatear sin cambiar el contenido sigue aprobado")


def test_F006_R014_producto_cambiado():
    p = con_arquitectura(proyecto("r014-producto"))
    run(p, "approve")
    nueva = PRODUCTO_BACKLOG + """
### B04 — Avisos de stock

- **Estado:** candidata
- **Objetivos:** G1
- **Origen:** D1§3
- **Problema:** el dueño se queda sin producto sin darse cuenta.
- **Resultado observable:** el dueño recibe un aviso cuando un producto baja de un umbral.
- **Dentro:** un umbral por producto.
- **Fuera:** pedidos automáticos.
- **Depende de:** B01
"""
    con_producto(p, backlog=nueva)  # el backlog se reaprueba con una candidata nueva
    h = con_codigo(p, "W-ARCH-PRODUCT-CHANGED")
    expect(len(h) == 1 and "product/backlog.md" in h[0]["message"]
           and "product/brief.md" not in h[0]["message"],
           "avisa de que el producto cambio desde la arquitectura y dice que fue el backlog",
           f"{h}")
    expect(any("B04" in f["message"] for f in con_codigo(p, "E-COMPONENT-CANDIDATE-UNPLACED")),
           "y da error por la candidata nueva sin componente")


# ----------------------------------------------------------------- T008

def codigos_de(root, code):
    """Hallazgos de un codigo sin contarlo como probado (para afirmar ausencias)."""
    return [f for f in architecture.analyze(root)["findings"] if f["code"] == code]


def con_propuesta(nombre, sustituye="—", completo=True):
    """Arquitectura aprobada (ADR-0001 y 0002) y una ADR-0004 propuesta."""
    p = con_arquitectura(proyecto(nombre), adrs=dict(DOS_ADR))
    run(p, "approve")
    propuesta = adr("0004", "Base de datos gestionada", estado="Proposed",
                    sustituye=sustituye, completo=completo)
    (p / "architecture" / "adr" / "0004-base-gestionada.md").write_text(propuesta,
                                                                       encoding="utf-8")
    return p


def test_F006_R013_revision():
    rel = "architecture/adr/0004-base-gestionada.md"

    p = con_propuesta("r013-aceptar")
    r = run(p, "review", "ADR-0004", "aceptar")
    texto = (p / rel).read_text(encoding="utf-8")
    expect(r.returncode == 0 and architecture.adr_state(texto) == "approved",
           "aceptar una propuesta la deja aprobada con su huella", r.stdout + r.stderr)

    p = con_propuesta("r013-rechazar")
    r = run(p, "review", "adr-0004", "rechazar")
    adrs = {a["id"]: a for a in architecture.adrs(p)}
    expect(r.returncode == 0 and adrs["ADR-0004"]["state"] == "rejected"
           and run(p, "next-id", "ADR").stdout.strip() == "ADR-0005",
           "rechazar la deja rechazada y conserva su numero", r.stdout + r.stderr)

    p = con_propuesta("r013-sustituir", sustituye="ADR-0002")
    r = run(p, "review", "ADR-0004", "aceptar")
    adrs = {a["id"]: a for a in architecture.adrs(p)}
    expect(r.returncode == 0 and adrs["ADR-0004"]["state"] == "approved"
           and adrs["ADR-0002"]["state"] == "superseded"
           and adrs["ADR-0002"]["superseded_by"] == "ADR-0004"
           and adrs["ADR-0001"]["state"] == "approved"
           and "ADR-0002" in r.stdout,
           "aceptar la 0004, que sustituye a la 0002: 0004 aprobada y 0002 sustituida",
           r.stdout + r.stderr)
    expect(not [f for f in codigos_de(p, "W-ARCH-NOT-APPROVED") if "0002" in f["artifact"]],
           "la sustituida no cuenta como cambiada")

    p = con_propuesta("r013-sustituye-cambiada", sustituye="ADR-0002")
    d = p / "architecture" / "adr" / "0002-despliegue.md"
    d.write_text(d.read_text(encoding="utf-8").replace("Una sola base", "Una única base"),
                 encoding="utf-8")
    antes = foto(p)
    r = run(p, "review", "ADR-0004", "aceptar")
    expect(r.returncode == 1 and "ADR-0002 cambió después de aprobarse" in r.stderr
           and "/architecture:approve" in r.stderr and foto(p) == antes,
           "no se sustituye a una decision aprobada que cambio despues: se dice como seguir",
           r.stderr)

    p = con_propuesta("r013-no-propuesta")
    antes = foto(p)
    r = run(p, "review", "ADR-0001", "aceptar")
    expect(r.returncode == 1 and "solo se revisan decisiones propuestas" in r.stderr
           and foto(p) == antes,
           "una decision que no esta propuesta no se revisa", r.stderr)

    p = con_propuesta("r013-sustituye-borrador", sustituye="ADR-0005")
    (p / "architecture" / "adr" / "0005-borrador.md").write_text(
        adr("0005", "Borrador"), encoding="utf-8")
    antes = foto(p)
    r = run(p, "review", "ADR-0004", "aceptar")
    expect(r.returncode == 1 and "ADR-0005" in r.stderr and foto(p) == antes,
           "no se acepta si sustituye a una decision que no esta aprobada", r.stderr)

    p = con_propuesta("r013-con-errores", completo=False)
    antes = foto(p)
    r = run(p, "review", "ADR-0004", "aceptar")
    expect(r.returncode == 1 and "E-ADR-INCOMPLETE" in r.stderr and foto(p) == antes,
           "no se acepta una propuesta con errores propios, y no se escribe nada", r.stderr)

    p = con_propuesta("r013-skill")
    r = run(p, "review", "ADR-0009", "aceptar", "--skill")
    expect(r.returncode == 0 and "no existe" in r.stdout,
           "con --skill, la negativa sale por stdout con 0", r.stdout)
    expect(run(p, "review", "ADR-0004").returncode == 2, "sin decision: uso y salida 2")


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
