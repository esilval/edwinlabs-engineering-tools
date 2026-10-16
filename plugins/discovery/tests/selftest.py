#!/usr/bin/env python3
"""
Regresion del plugin discovery. Sin dependencias externas: solo stdlib.

Cada prueba es una funcion test_F001_Rxxx_* que cita el requisito de la
feature 001 al que sirve, para que la trazabilidad de sdd la reconozca, y
verifica con expect(...). Corre en CI y en local:

    python3 plugins/discovery/tests/selftest.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN / "scripts" / "discovery.py"
sys.path.insert(0, str(PLUGIN / "scripts"))
import discovery  # noqa: E402

fallos = []
BASE = Path(tempfile.mkdtemp(prefix="discovery-selftest-"))


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

def test_F001_R010_escritura_solo_en_product():
    root = proyecto("r010-rutas")
    discovery.write_product(root, "brief.md", "x\n")
    expect((root / "product" / "brief.md").is_file(), "escribe dentro de product/")
    (root / "fuera").mkdir()
    (root / "product" / "enlace").symlink_to(root / "fuera")
    for malo in ("../fuera.md", "../specs/spec.md", "/tmp/absoluta.md",
                 "sources/../../x.md", ".", "enlace/x.md"):
        try:
            discovery.write_product(root, malo, "x\n")
            escapo = True
        except discovery.OutsideProduct:
            escapo = False
        expect(not escapo, f"rechaza escribir en {malo}")
    expect(not (root / "fuera.md").exists() and not (root / "specs").exists()
           and not (root / "fuera" / "x.md").exists(),
           "nada se escribio fuera de product/")


def test_cli_sin_subcomando():
    r = run(proyecto("cli"))
    expect(r.returncode == 2 and "Subcomandos" in r.stderr,
           "sin subcomando: exit 2 y ayuda", f"{r.returncode} {r.stderr[:80]}")


# ----------------------------------------------------------------- T002

BACKLOG_APROBADO = """# Backlog

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Candidatas

### B01 — Exportar movimientos

- **Resultado observable:** el usuario descarga sus movimientos.
"""


def _aprobar(texto):
    huella = discovery.content_digest(texto)
    sellado, ok = discovery.set_status(texto, f"Approved · {huella}")
    expect(ok, "set_status encuentra la fila Estado")
    return sellado


def test_F001_R016_huella_ignora_formato():
    a = "# T\n\nUna  linea\n\n\n| a |  b |\n"
    b = "# T\nUna linea\n|a|b|\n"
    expect(discovery.text_digest(a) == discovery.text_digest(b),
           "espacios, lineas en blanco y relleno de tablas no cambian la huella")
    sellado = _aprobar(BACKLOG_APROBADO)
    expect(discovery.is_approved(sellado) and not discovery.is_stale(sellado),
           "recien aprobado: aprobado y no cambiado")
    reformateado = (sellado.replace("\n\n### B01", "\n\n\n### B01")
                    .replace("el usuario", "el  usuario"))
    expect(not discovery.is_stale(reformateado), "reformatear tras aprobar no invalida")


def test_F001_R016_huella_detecta_cambio():
    sellado = _aprobar(BACKLOG_APROBADO)
    cambiado = sellado.replace("descarga sus movimientos", "descarga sus facturas")
    expect(discovery.is_stale(cambiado), "cambiar palabras tras aprobar invalida")
    expect(discovery.content_digest(sellado) == discovery.content_digest(
        discovery.set_status(sellado, "Draft")[0]),
        "la huella no depende del propio campo Estado")
    expect(discovery.doc_status("# B\n\n## Tabla\n\n| Estado | Approved |\n") is None,
           "una fila Estado fuera de la cabecera no cuenta")
    expect(not discovery.is_approved(discovery.set_status(sellado, "Draft")[0]),
           "Draft no es aprobado")
    a_mano = discovery.set_status(sellado, "Approved")[0]
    expect(not discovery.is_approved(a_mano), "un Approved sin huella no cuenta como aprobado")
    expect(discovery.set_status("# B\n\n## X\n", "Draft") == ("# B\n\n## X\n", False),
           "set_status sin fila Estado no cambia nada")


def test_huella_de_texto():
    # Base de la deteccion de duplicados. El rechazo de un documento repetido
    # tiene su propia prueba, la del duplicado rechazado.
    a, b = "# Vision\n\nTexto.\n", "# Vision\nTexto.\n"
    expect(discovery.text_digest(a) == discovery.text_digest(b),
           "el mismo contenido con otro formato tiene la misma huella")
    expect(discovery.text_digest(b) != discovery.text_digest("# Vision\nOtro.\n"),
           "contenido distinto, huella distinta")


# ----------------------------------------------------------------- T003

def foto(root):
    """Contenido de product/, para comprobar que un rechazo no cambia nada."""
    base = root / "product"
    if not base.exists():
        return None
    return {str(p.relative_to(base)): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def doc(root, nombre, texto):
    p = root / "entrada" / nombre
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texto, encoding="utf-8")
    return p


def ingerir(root, nombre, texto):
    r = run(root, "ingest", str(doc(root, nombre, texto)))
    return r, (json.loads(r.stdout) if r.returncode == 0 else None)


def guardado(root, did):
    return next((root / "product" / "sources").glob(f"{did}-*.md")).read_text(encoding="utf-8")


def test_F001_R001_ids_correlativos():
    root = proyecto("r001-ids")
    ids = [ingerir(root, f"{n}.md", f"# {n}\n\n## Parte\n\n{n} texto.\n")[1]["document"]
           for n in ("vision", "pagos", "informes")]
    expect(ids == ["D1", "D2", "D3"], "D1, D2, D3 en orden de ingesta", f"{ids}")
    nombres = sorted(p.name for p in (root / "product" / "sources").iterdir())
    expect(nombres == ["D1-vision.md", "D2-pagos.md", "D3-informes.md"],
           "un archivo por documento en product/sources", f"{nombres}")
    cabecera = discovery.header_fields(guardado(root, "D2"))
    expect(cabecera.get("Documento") == "D2" and cabecera.get("Original") == "pagos.md"
           and len(cabecera.get("Huella original", "")) == 12
           and len(cabecera.get("Huella", "")) == 12 and cabecera.get("Ingesta"),
           "cabecera con documento, original, ingesta y las dos huellas", f"{cabecera}")


def test_F001_R001_numeracion_anidada():
    root = proyecto("r001-anidada")
    texto = ("# Producto\n\nIntro.\n\n## Usuarios\n\n### Comercios\n\n### Clientes\n\n"
             "#### Empresas\n\n## Pagos\n\n### Recurrentes\n\n```\n## no es seccion\n```\n")
    r, out = ingerir(root, "producto.md", texto)
    expect(r.returncode == 0, "ingesta correcta", r.stderr)
    guardo = guardado(root, out["document"])
    expect(discovery.sections(guardo) == ["1", "1.1", "1.2", "1.2.1", "2", "2.1"],
           "secciones 1, 1.1, 1.2, 1.2.1, 2, 2.1", f"{discovery.sections(guardo)}")
    for linea in ("## 1 Usuarios", "### 1.2 Clientes",
                  "#### 1.2.1 Empresas", "### 2.1 Recurrentes"):
        expect(linea in guardo, f"encabezado reescrito: {linea}")
    expect("## no es seccion" in guardo, "un encabezado dentro de un bloque de codigo no se numera")


def test_F001_R001_h1_unico_es_titulo():
    root = proyecto("r001-titulo")
    r, out = ingerir(root, "vision.md", "# Visión\n\n## Problema\n\n## Usuarios\n")
    guardo = guardado(root, "D1")
    expect(out["title"] == "Visión" and "\n# Visión\n" in guardo,
           "el H1 unico es el titulo y queda sin numero")
    expect(discovery.sections(guardo) == ["1", "2"], "las secciones bajo el titulo empiezan en 1",
           f"{discovery.sections(guardo)}")
    root2 = proyecto("r001-dos-h1")
    ingerir(root2, "notas.md", "# Uno\n\ntexto\n\n# Dos\n\ntexto\n")
    expect(discovery.sections(guardado(root2, "D1")) == ["1", "2"],
           "con dos H1 no hay titulo: ambos son secciones")


def test_F001_R001_titulo_numerico_no_es_seccion():
    root = proyecto("r001-titulo-numerico")
    ingerir(root, "plan.md", "# 2025 Visión\n\n## Problema\n\n## Usuarios\n")
    expect(discovery.sections(guardado(root, "D1")) == ["1", "2"],
           "un titulo que empieza por numero no es seccion",
           f"{discovery.sections(guardado(root, 'D1'))}")
    ingerir(root, "solo.md", "# 2026 Plan\n\nTexto sin mas encabezados.\n")
    expect(discovery.sections(guardado(root, "D2")) == ["1"],
           "titulo numerico y nada mas: una sola seccion")


def test_F001_R001_casos_de_numeracion():
    root = proyecto("r001-casos")
    ingerir(root, "a.md", "## Resumen\n\n### A\n\n### B\n")
    expect(discovery.sections(guardado(root, "D1")) == ["1", "1.1", "1.2"],
           "sin H1 no hay titulo: el primer nivel tambien es seccion")
    ingerir(root, "b.md", "## Intro\n\n# Cuerpo\n\n## Detalle\n")
    expect(discovery.sections(guardado(root, "D2")) == ["1", "2", "2.1"],
           "un encabezado profundo al principio no produce ceros",
           f"{discovery.sections(guardado(root, 'D2'))}")
    ingerir(root, "c.md", "# Doc\n\n## 1. Intro\n\n## Soporte C#\n\n## Cierre ##\n")
    guardo = guardado(root, "D3")
    expect("## 1 Intro" in guardo and "## 1 1." not in guardo,
           "la numeracion propia del documento se sustituye")
    expect("## 2 Soporte C#" in guardo, "un # final sin espacio delante se conserva")
    expect("## 3 Cierre\n" in guardo, "la secuencia de cierre con espacio se quita")


def test_F001_R001_sin_encabezados_es_una_seccion():
    root = proyecto("r001-plano")
    r, out = ingerir(root, "nota.md", "Solo un parrafo sin encabezados.\n")
    expect(r.returncode == 0 and discovery.sections(guardado(root, "D1")) == ["1"],
           "un documento sin encabezados es la seccion 1")


def test_F001_R002_duplicado_rechazado():
    root = proyecto("r002-duplicado")
    ingerir(root, "vision.md", "# Visión\n\n## Problema\n\nTexto.\n")
    antes = foto(root)
    r, _ = ingerir(root, "copia-con-otro-nombre.md", "# Visión\n## Problema\nTexto.\n")
    expect(r.returncode == 1 and "D1" in r.stderr and "vision.md" in r.stderr,
           "rechaza el duplicado nombrando D1 y su original", r.stderr)
    expect(foto(root) == antes, "el producto no cambia")
    r, out = ingerir(root, "otra.md", "# Visión\n\n## Problema\n\nOtro texto.\n")
    expect(r.returncode == 0 and out["document"] == "D2", "un contenido distinto sí entra")


def test_F001_R003_formato_no_admitido():
    root = proyecto("r003-formato")
    for nombre in ("datos.xlsx", "captura.png", "notas.txt"):
        p = root / "entrada" / nombre
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00\x01binario")
        r = run(root, "ingest", str(p))
        expect(r.returncode == 1 and "Markdown" in r.stderr and "Word" in r.stderr
               and "PDF" in r.stderr, f"rechaza {nombre} listando los formatos admitidos", r.stderr)
    expect(foto(root) is None, "el producto no se crea ni cambia")
    r = run(root, "ingest", str(root / "entrada" / "no-existe.md"))
    expect(r.returncode == 1 and foto(root) is None, "un archivo inexistente se rechaza sin cambios")


# ----------------------------------------------------------------- T004

def docx(path, parrafos, extra=None):
    """
    Fabrica un .docx minimo: [(estilo o None, texto)]. Un estilo 'outline:N'
    usa w:outlineLvl en lugar de w:pStyle. `extra` anade otro archivo al zip,
    como hace Word al guardar de nuevo.
    """
    import zipfile
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    cuerpo = ""
    for estilo, texto in parrafos:
        if estilo and estilo.startswith("outline:"):
            ppr = f'<w:pPr><w:outlineLvl w:val="{estilo[8:]}"/></w:pPr>'
        else:
            ppr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
        cuerpo += f"<w:p>{ppr}<w:r><w:t>{texto}</w:t></w:r></w:p>"
    xml = (f'<?xml version="1.0"?><w:document xmlns:w="{w}">'
           f"<w:body>{cuerpo}</w:body></w:document>")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)
        if extra:
            z.writestr("docProps/core.xml", extra)
    return path


def test_F001_R004_docx_convertido():
    root = proyecto("r004-docx")
    p = docx(root / "entrada" / "pagos.docx", [
        ("Title", "Plan de pagos"), ("Heading1", "Cobros"), (None, "Cobrar a fin de mes."),
        ("Heading2", "Recurrentes"), (None, "Cada mes."), ("Ttulo1", "Devoluciones"),
    ])
    r = run(root, "ingest", str(p))
    expect(r.returncode == 0, "ingesta de un .docx", r.stderr)
    guardo = guardado(root, "D1")
    expect("\n# Plan de pagos\n" in guardo and "## 1 Cobros" in guardo
           and "### 1.1 Recurrentes" in guardo and "## 2 Devoluciones" in guardo,
           "los estilos de titulo dan los encabezados (tambien los de Word en espanol)")
    expect("Cobrar a fin de mes." in guardo, "el texto de los parrafos se conserva")
    cabecera = discovery.header_fields(guardo)
    expect(cabecera["Original"] == "pagos.docx" and cabecera["Ingesta"]
           and cabecera["Huella original"] == discovery.text_digest(discovery.docx_to_markdown(p)),
           "registra nombre, fecha y la huella del contenido convertido")
    otra = docx(root / "entrada" / "pagos-guardado.docx", [
        ("Title", "Plan de pagos"), ("Heading1", "Cobros"), (None, "Cobrar a fin de mes."),
        ("Heading2", "Recurrentes"), (None, "Cada mes."), ("Ttulo1", "Devoluciones"),
    ], extra="<guardado-otra-vez/>")
    expect(otra.read_bytes() != p.read_bytes(), "(el zip guardado de nuevo tiene otros bytes)")
    antes = foto(root)
    r = run(root, "ingest", str(otra))
    expect(r.returncode == 1 and "D1" in r.stderr and foto(root) == antes,
           "el mismo Word guardado de nuevo es un duplicado", r.stderr)
    roto = root / "entrada" / "roto.docx"
    roto.write_bytes(b"no soy un zip")
    antes = foto(root)
    r = run(root, "ingest", str(roto))
    expect(r.returncode == 1 and "Word" in r.stderr and foto(root) == antes,
           "un .docx corrupto se rechaza sin tocar el producto", r.stderr)


def test_F001_R004_docx_estructura():
    root = proyecto("r004-docx-estructura")
    p = docx(root / "entrada" / "notas.docx", [
        ("Title", "Notas"), ("Title", "Subtitulo marcado como titulo"),
        ("outline:0", "Por esquema"), (None, "# no soy titulo"), (None, "- ni lista"),
        ("Heading6", "Muy profundo"),
    ])
    md = discovery.docx_to_markdown(p)
    expect(md.count("\n# ") + md.startswith("# ") == 1 and "Subtitulo marcado como titulo\n" in md,
           "solo el primer Title es H1; el segundo queda como texto", md)
    expect("## Por esquema" in md, "outlineLvl 0 da un H2 (primera seccion)", md)
    expect("\\# no soy titulo" in md and "\\- ni lista" in md,
           "un parrafo normal que empieza por # o - se escapa", md)
    expect("###### Muy profundo" in md, "Heading6 se queda en H6", md)
    run(root, "ingest", str(p))
    expect(discovery.sections(guardado(root, "D1")) == ["1", "1.1"],
           "el # escapado no crea una seccion falsa", f"{discovery.sections(guardado(root, 'D1'))}")


def test_F001_R004_original_registrado():
    root = proyecto("r004-original")
    pdf = root / "entrada" / "vision.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 contenido binario")
    md = doc(root, "vision-convertido.md", "# Visión\n\n## Problema\n")
    r = run(root, "ingest", str(md), "--original", str(pdf))
    cabecera = discovery.header_fields(guardado(root, "D1"))
    expect(r.returncode == 0 and cabecera["Original"] == "vision.pdf"
           and cabecera["Huella original"] == discovery.bytes_digest(pdf.read_bytes())
           and cabecera["Ingesta"], "registra nombre, fecha y huella de los bytes del PDF",
           f"{r.stderr} {cabecera}")
    antes = foto(root)
    r = run(root, "ingest", str(doc(root, "otra-conversion.md", "# Otra\n")), "--original", str(pdf))
    expect(r.returncode == 1 and "D1" in r.stderr and foto(root) == antes,
           "el mismo PDF dos veces es un duplicado", r.stderr)
    r = run(root, "ingest", str(pdf))
    expect(r.returncode == 1 and "--original" in r.stderr and foto(root) == antes,
           "un PDF directo pide convertirlo y usar --original")
    md2 = doc(root, "fuente.md", "# Fuente\n")
    r = run(root, "ingest", str(doc(root, "copia.md", "# Fuente\n")), "--original", str(md2))
    expect(r.returncode == 1 and "PDF" in r.stderr and foto(root) == antes,
           "--original solo admite PDF")


# ----------------------------------------------------------------- T006

DOC_VISION = """# Visión

## Problema

Los comercios no saben cuánto venden cada día.

## Usuarios

Dueños de comercios pequeños.

## Informes

Un resumen diario de ventas.

## Exportación

Bajar los movimientos a una hoja de cálculo.
"""

BRIEF_OK = """# Brief del producto

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

BACKLOG_OK = """# Backlog del producto

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


def producto_ok(nombre, brief=BRIEF_OK, backlog=BACKLOG_OK):
    """Proyecto con D1 ingerido y un brief y backlog coherentes."""
    root = proyecto(nombre)
    ingerir(root, "vision.md", DOC_VISION)
    discovery.write_product(root, "brief.md", brief)
    discovery.write_product(root, "backlog.md", backlog)
    return root


def test_F001_R006_lee_objetivos():
    b = discovery.parse_brief(BRIEF_OK)
    expect([g["id"] for g in b["goals"]] == ["G1", "G2"], "lee G1 y G2")
    expect(discovery.refs(b["goals"][0]["fields"].get("origen"))["sections"]
           == ["D1§1", "D1§2", "D1§3"], "cada objetivo cita su origen")
    expect(len(b["questions"]) == 1 and not b["questions"][0]["open"]
           and b["questions"][0]["refs"]["goals"] == ["G1"], "lee la pregunta respondida y sus citas")
    root = producto_ok("r006-next-id")
    expect(run(root, "next-id", "G").stdout.strip() == "G3", "next-id G = G3")


BRIEF_TRAMPA = """# Brief del producto

| Campo  | Valor |
| ------ | ----- |
| Estado | Draft |

## Objetivos

### G1 — Responder preguntas de clientes

- **Origen:** D1§1

### G2 — Reducir descartes

- **Origen:** D1§2

## Secciones descartadas

- D1§4 — fuera del alcance acordado

## Preguntas

- [ ] (D1§2; G2) ¿Qué cuenta como descarte?
- [x] (D1§1) ¿Por email o chat?
  - **Respuesta:** por chat.
"""


def test_F001_R006_secciones_no_se_confunden():
    b = discovery.parse_brief(BRIEF_TRAMPA)
    expect([g["id"] for g in b["goals"]] == ["G1", "G2"],
           "un objetivo con «preguntas» o «descartes» en el titulo sigue siendo objetivo")
    expect(b["discarded"] == ["D1§4"], "lee el descarte real, no el origen de G2",
           f"{b['discarded']}")
    abiertas = [q for q in b["questions"] if q["open"]]
    expect(len(b["questions"]) == 2 and len(abiertas) == 1
           and abiertas[0]["refs"]["goals"] == ["G2"],
           "lee la pregunta abierta sobre G2", f"{b['questions']}")
    expect(b["questions"][1]["answer"] == "por chat.", "lee la respuesta junto a su pregunta")
    estado = discovery.parse_backlog(
        "## Candidatas\n\n### B01 — X\n\n- **Estado:** `descartada`\n")["candidates"][0]
    expect(estado["state"] == "descartada", "el estado ignora el formato de codigo")


def test_F001_R007_lee_candidata_completa():
    c = discovery.parse_backlog(BACKLOG_OK)["candidates"]
    expect([x["id"] for x in c] == ["B01", "B02", "B03"], "lee B01, B02, B03")
    campos = {"estado", "objetivos", "origen", "problema", "resultado observable",
              "dentro", "fuera", "depende de"}
    expect(campos <= set(c[1]["fields"]), "una candidata trae todos sus campos",
           f"{sorted(c[1]['fields'])}")
    expect(c[2]["state"] == "descartada" and c[0]["state"] == "candidata", "lee el estado")
    expect(discovery.refs(c[1]["fields"]["depende de"])["candidates"] == ["B01"],
           "lee las dependencias")


def test_F001_R008_next_id_no_reutiliza():
    root = producto_ok("r008-next-id")
    expect(run(root, "next-id", "B").stdout.strip() == "B04",
           "next-id B = B04: cuenta la descartada B03")
    vacio = proyecto("r008-vacio")
    expect(run(vacio, "next-id", "B").stdout.strip() == "B01"
           and run(vacio, "next-id", "G").stdout.strip() == "G1", "sin backlog: B01 y G1")
    expect(run(vacio, "next-id", "X").returncode == 1, "prefijo desconocido: error")


# ----------------------------------------------------------------- T007

def preguntas(root):
    r = run(root, "questions", "--json")
    return json.loads(r.stdout) if r.returncode == 0 else None


BRIEF_CON_PREGUNTAS = BRIEF_OK.replace("""- [x] (D1§3; G1) ¿Diario o semanal?
  - **Respuesta:** diario.
""", """- [ ] (D1§1; G1) ¿Qué cuenta como venta?
- [ ] (D1§9; G7; D9§1) ¿Pregunta con citas rotas?
- [ ] ¿Pregunta sin origen?
- [x] (D1§3; G1) ¿Diario o semanal?
  - **Respuesta:** diario, al cerrar la caja,
    salvo los domingos.
""")


def test_F001_R005_lista_abiertas():
    root = producto_ok("r005-abiertas", brief=BRIEF_CON_PREGUNTAS)
    q = preguntas(root)
    abiertas = [x for x in q if x["open"]]
    expect(len(q) == 4 and len(abiertas) == 3, "lista 3 abiertas y 1 respondida", f"{q}")
    expect(abiertas[0]["issues"] == [], "una pregunta bien citada no tiene problemas")
    rotas = abiertas[1]["issues"]
    expect(any("D1§9" in i for i in rotas) and any("G7" in i for i in rotas)
           and any("no existe D9" in i for i in rotas),
           "señala la seccion, el objetivo y el documento inexistentes", f"{rotas}")
    expect(any("sección de origen" in i for i in abiertas[2]["issues"]),
           "señala una pregunta sin seccion de origen")
    texto = run(root, "questions").stdout
    expect("Preguntas abiertas: 3" in texto and "D1§9" in texto, "salida legible", texto)


def test_F001_R005_respondida_no_cuenta():
    root = producto_ok("r005-respondida")
    q = preguntas(root)
    expect(len(q) == 1 and not q[0]["open"], "la respondida no figura como abierta")
    expect(q[0]["answer"] == "diario.", "conserva la respuesta")
    multilinea = discovery.parse_brief(BRIEF_CON_PREGUNTAS)["questions"][-1]
    expect(multilinea["answer"] == "diario, al cerrar la caja, salvo los domingos.",
           "una respuesta de varias lineas se lee entera", multilinea["answer"])
    vacia = discovery.parse_brief("## Preguntas\n\n- [x] (D1§1) ¿Algo?\n  - **Respuesta:**\n"
                                  "    en la linea siguiente.\n")["questions"][0]
    expect(vacia["answer"] == "en la linea siguiente.",
           "una respuesta que empieza en la linea siguiente se lee", vacia["answer"])
    vacio = proyecto("r005-sin-brief")
    expect("No hay brief.md" in run(vacio, "questions").stdout, "sin brief lo dice")


def test_F001_R009_pregunta_cita_dos_documentos():
    root = producto_ok("r009-contradiccion")
    ingerir(root, "acceso.md", "# Acceso\n\n## Usuarios\n\nAcceso anónimo.\n")
    brief = BRIEF_OK.replace("- [x] (D1§3; G1)", "- [ ] (D1§2 contra D2§1) ¿Registrados o "
                             "anónimos?\n- [x] (D1§3; G1)")
    discovery.write_product(root, "brief.md", brief)
    q = [x for x in preguntas(root) if x["open"]]
    expect(len(q) == 1 and q[0]["refs"]["sections"] == ["D1§2", "D2§1"] and q[0]["issues"] == [],
           "una contradiccion cita las dos secciones y ambas son validas", f"{q}")


# ----------------------------------------------------------------- T008

def comprobar(root):
    return discovery.analyze(root)


PROBADOS = set()


def con_codigo(root, code):
    """
    Hallazgos de un codigo. Solo cuenta como probado si de verdad se emitio:
    una prueba que afirma su ausencia no demuestra que sea alcanzable.
    """
    out = [f for f in comprobar(root)["findings"] if f["code"] == code]
    if out:
        PROBADOS.add(code)
    return out


def codigos(root):
    return {f["code"] for f in comprobar(root)["findings"]}


def test_F001_R011_producto_coherente_sin_errores():
    root = producto_ok("r011-coherente")
    d = comprobar(root)
    errores = [f for f in d["findings"] if f["severity"] == "error"]
    expect(d["ok"] and not errores, "un producto coherente no da errores", f"{errores}")
    texto = run(root, "check").stdout
    expect("OK: sin errores" in texto, "la salida legible lo dice", texto)


def test_F001_R011_objetivo_sin_candidata():
    brief = BRIEF_OK.replace("## Usuarios", "### G3 — Objetivo huérfano\n\n- **Origen:** D1§4\n\n"
                             "## Usuarios")
    root = producto_ok("r011-goal", brief=brief)
    f = con_codigo(root, "E-GOAL-NO-FEATURE")
    expect(len(f) == 1 and "G3" in f[0]["message"], "E-GOAL-NO-FEATURE nombra G3", f"{f}")
    solo_descartada = BACKLOG_OK.replace("- **Objetivos:** G2\n- **Origen:** D1§4\n- **Problema:** "
                                         "el dueño copia", "- **Objetivos:** G1\n- **Origen:** "
                                         "D1§4\n- **Problema:** el dueño copia")
    root2 = producto_ok("r011-goal-descartada", backlog=solo_descartada)
    expect("E-GOAL-NO-FEATURE" in codigos(root2),
           "un objetivo que solo persigue una candidata descartada cuenta como huerfano")


def test_F001_R011_seccion_sin_cubrir():
    brief = BRIEF_OK.replace("D1§1, D1§2, D1§3", "D1§1, D1§3")
    root = producto_ok("r011-uncovered", brief=brief)
    f = con_codigo(root, "E-SOURCE-UNCOVERED")
    expect(len(f) == 1 and f[0]["section"] == "D1§2", "E-SOURCE-UNCOVERED nombra D1§2", f"{f}")
    descartada = brief.replace("- Ninguna.\n\n## Preguntas", "- D1§2 — los usuarios ya se "
                               "describen en el brief\n\n## Preguntas")
    discovery.write_product(root, "brief.md", descartada)
    expect("E-SOURCE-UNCOVERED" not in codigos(root), "un descarte explicito la cubre")


def test_F001_R011_referencia_inexistente():
    backlog = BACKLOG_OK.replace("- **Objetivos:** G1\n", "- **Objetivos:** G1, G9\n", 1)
    backlog = backlog.replace("- **Origen:** D1§1, D1§3\n", "- **Origen:** D1§1, D1§3, D4§1\n", 1)
    backlog = backlog.replace("- **Depende de:** B01", "- **Depende de:** B01, B42")
    root = producto_ok("r011-refs", backlog=backlog)
    msgs = [x["message"] for x in con_codigo(root, "E-REF-UNKNOWN")]
    expect(any("G9" in m for m in msgs) and any("D4§1" in m for m in msgs)
           and any("B42" in m for m in msgs), "un error por cada cita rota", f"{msgs}")
    brief = BRIEF_OK.replace("- **Movimiento:** una venta o una devolución (D1§1)",
                             "- **Movimiento:** una venta o una devolución (D1§8)")
    discovery.write_product(root, "brief.md", brief)
    msgs = [x["message"] for x in con_codigo(root, "E-REF-UNKNOWN")]
    expect(any("brief.md" in m and "D1§8" in m for m in msgs),
           "tambien una cita rota en el glosario", f"{msgs}")
    nota = BRIEF_OK.replace("## Objetivos", "> Ejemplo de cita: D7§4.2.\n\n## Objetivos")
    discovery.write_product(root, "brief.md", nota)
    expect(not any("D7" in x["message"] for x in con_codigo(root, "E-REF-UNKNOWN")),
           "una cita de ejemplo en una nota (blockquote) no cuenta")


def test_F001_R011_dependencia_circular():
    backlog = BACKLOG_OK.replace("- **Fuera:** comparativas entre días.\n- **Depende de:** —",
                                 "- **Fuera:** comparativas entre días.\n- **Depende de:** B02")
    root = producto_ok("r011-ciclo", backlog=backlog)
    f = con_codigo(root, "E-BACKLOG-DEP-CYCLE")
    expect(len(f) == 1 and f[0]["message"].endswith("B01 -> B02 -> B01"),
           "E-BACKLOG-DEP-CYCLE describe el ciclo exacto", f"{f}")
    propio = BACKLOG_OK.replace("- **Depende de:** B01", "- **Depende de:** B02")
    discovery.write_product(root, "backlog.md", propio)
    f = con_codigo(root, "E-BACKLOG-DEP-CYCLE")
    expect(len(f) == 1 and f[0]["message"].endswith("B02 -> B02"),
           "una candidata que depende de si misma", f"{f}")


def test_F001_R011_documento_modificado():
    root = producto_ok("r011-modificado")
    p = next((root / "product" / "sources").glob("D1-*.md"))
    p.write_text(p.read_text(encoding="utf-8").replace("Un resumen diario", "Un resumen semanal"),
                 encoding="utf-8")
    f = con_codigo(root, "E-SOURCE-MODIFIED")
    expect(len(f) == 1 and f[0]["document"] == "D1", "E-SOURCE-MODIFIED nombra D1", f"{f}")
    sin_huella = proyecto("r011-sin-huella")
    ingerir(sin_huella, "vision.md", DOC_VISION)
    p = next((sin_huella / "product" / "sources").glob("D1-*.md"))
    texto = p.read_text(encoding="utf-8")
    p.write_text("\n".join(l for l in texto.splitlines() if not l.startswith("| Huella |")) + "\n",
                 encoding="utf-8")
    expect(len(con_codigo(sin_huella, "E-SOURCE-MODIFIED")) == 1,
           "borrar la fila Huella tambien cuenta como modificado")


def test_F001_R008_hueco_en_ids():
    backlog = BACKLOG_OK.replace("### B02 — Exportar movimientos", "### B04 — Exportar movimientos")
    backlog = backlog.replace("- **Depende de:** B02", "- **Depende de:** B04")
    root = producto_ok("r008-hueco", backlog=backlog)
    msgs = [x["message"] for x in con_codigo(root, "E-BACKLOG-ID-GAP")]
    expect(any("B02" in m for m in msgs), "E-BACKLOG-ID-GAP señala que falta B02", f"{msgs}")
    repetido = BACKLOG_OK.replace("### B03 —", "### B02 —")
    discovery.write_product(root, "backlog.md", repetido)
    msgs = [x["message"] for x in con_codigo(root, "E-BACKLOG-ID-GAP")]
    expect("IDs repetidos en candidatas: B02." in msgs, "y un ID repetido, con su formato", f"{msgs}")
    duplicado = producto_ok("r008-doc-repetido")
    origen = next((duplicado / "product" / "sources").glob("D1-*.md"))
    (origen.parent / "D1-copia.md").write_text(origen.read_text(encoding="utf-8"), encoding="utf-8")
    msgs = [x["message"] for x in con_codigo(duplicado, "E-BACKLOG-ID-GAP")]
    expect("IDs repetidos en documentos: D1." in msgs, "dos archivos con el mismo Dn", f"{msgs}")


def test_F001_R010_candidata_redactada_como_requisito():
    backlog = BACKLOG_OK.replace("el dueño ve el total del día al cerrar.",
                                 "el sistema DEBERÁ mostrar el total del día.")
    root = producto_ok("r010-requisito", backlog=backlog)
    f = con_codigo(root, "E-BACKLOG-REQUIREMENT")
    expect(len(f) == 1 and f[0]["item"] == "B01", "E-BACKLOG-REQUIREMENT nombra B01", f"{f}")
    for texto in ("la aplicación deberá enviar un correo.", "the system SHALL send it."):
        discovery.write_product(root, "backlog.md",
                                BACKLOG_OK.replace("el dueño ve el total del día al cerrar.", texto))
        expect(len(con_codigo(root, "E-BACKLOG-REQUIREMENT")) == 1, f"detecta «{texto}»")
    futuro = BACKLOG_OK.replace("el dueño no sabe cuánto vendió hoy, cada día.",
                                "el dueño deberá cerrar la caja a mano cada noche.")
    discovery.write_product(root, "backlog.md", futuro)
    expect(not con_codigo(root, "E-BACKLOG-REQUIREMENT"),
           "un futuro normal («el dueño deberá cerrar…») no es un requisito")


def test_F001_R010_comandos_no_tocan_specs():
    root = producto_ok("r010-specs")
    (root / "specs").mkdir()
    (root / "specs" / "constitution.md").write_text("# C\n", encoding="utf-8")
    antes = sorted((p.name, p.read_bytes()) for p in (root / "specs").rglob("*") if p.is_file())
    ingerir(root, "otro.md", "# Otro\n\n## Algo\n")
    for args in (("questions",), ("check",), ("next-id", "B"), ("next-id", "G")):
        run(root, *args)
    despues = sorted((p.name, p.read_bytes()) for p in (root / "specs").rglob("*") if p.is_file())
    expect(antes == despues, "ingest, questions, check y next-id no tocan specs/")


def test_F001_R014_pregunta_abierta_sobre_objetivo():
    root = producto_ok("r014-pregunta", brief=BRIEF_OK.replace("- [x] (D1§3; G1)", "- [ ] (D1§3; G1)"))
    f = con_codigo(root, "E-QUESTION-OPEN-GOAL")
    expect(len(f) == 1 and "G1" in f[0]["message"], "E-QUESTION-OPEN-GOAL nombra G1", f"{f}")


def test_F001_R014_huecos_de_plantilla():
    plantilla = (PLUGIN / "templates" / "backlog.md").read_text(encoding="utf-8")
    root = producto_ok("r014-plantilla", backlog=plantilla)
    f = con_codigo(root, "E-PRODUCT-TEMPLATE")
    expect(len(f) == 1 and f[0]["file"] == "backlog.md", "E-PRODUCT-TEMPLATE en backlog.md", f"{f}")
    plantilla_brief = (PLUGIN / "templates" / "brief.md").read_text(encoding="utf-8")
    discovery.write_product(root, "brief.md", plantilla_brief)
    expect(any(x["file"] == "brief.md" for x in comprobar(root)["findings"]
               if x["code"] == "E-PRODUCT-TEMPLATE"), "y en brief.md")
    copiado = BACKLOG_OK + ("\n### B04 — _título de la feature candidata_\n\n- **Estado:** candidata"
                            "\n- **Objetivos:** G1\n- **Origen:** _D1§4.2_, D1§3\n")
    root2 = producto_ok("r014-plantilla-copiada", backlog=copiado)
    f = con_codigo(root2, "E-PRODUCT-TEMPLATE")
    expect(len(f) == 1 and "2 hueco" in f[0]["message"],
           "un bloque copiado para B04 con sus cursivas sin rellenar", f"{f}")
    expect(not con_codigo(producto_ok("r014-cursiva-propia",
                                      backlog=BACKLOG_OK.replace("total del día", "_total_ del día")),
                          "E-PRODUCT-TEMPLATE"), "una cursiva propia no es un hueco")


def test_F001_R011_contencion_de_secciones():
    root = proyecto("r011-contencion")
    ingerir(root, "pagos.md", "# Pagos\n\n## Cobros\n\n### Tarjeta\n\n### Efectivo\n\n## Cierre\n")
    brief = BRIEF_OK.replace("D1§1, D1§2, D1§3", "D1§1.1").replace("- **Origen:** D1§4\n",
                                                                  "- **Origen:** D1§2\n")
    backlog = BACKLOG_OK.replace("D1§1, D1§3", "D1§1.1").replace("- **Origen:** D1§4\n",
                                                                "- **Origen:** D1§2\n")
    discovery.write_product(root, "brief.md", brief)
    discovery.write_product(root, "backlog.md", backlog)
    sin = {x["section"] for x in con_codigo(root, "E-SOURCE-UNCOVERED")}
    expect(sin == {"D1§1.2"}, "citar D1§1.1 cubre su padre D1§1 pero no a su hermana D1§1.2",
           f"{sin}")


# ----------------------------------------------------------------- T009

def test_F001_R012_avisos():
    backlog = BACKLOG_OK.replace("- **Objetivos:** G2\n- **Origen:** D1§4\n- **Problema:** el dueño "
                                 "copia", "- **Objetivos:** —\n- **Origen:** D1§4\n- **Problema:** "
                                 "el dueño copia")
    backlog = backlog.replace("- **Resultado observable:** el dueño ve el total del día al cerrar.",
                              "- **Resultado observable:** —")
    brief = BRIEF_OK.replace("- [x] (D1§3; G1)", "- [ ] (D1§2) ¿Algo general?\n- [x] (D1§3; G1)")
    root = producto_ok("r012-avisos", brief=brief, backlog=backlog)
    sin_objetivo = con_codigo(root, "W-FEATURE-NO-GOAL")
    sin_resultado = con_codigo(root, "W-FEATURE-NO-OUTCOME")
    expect([f["item"] for f in sin_objetivo] == ["B02"], "W-FEATURE-NO-GOAL nombra B02",
           f"{sin_objetivo}")
    expect([f["item"] for f in sin_resultado] == ["B01"], "W-FEATURE-NO-OUTCOME nombra B01",
           f"{sin_resultado}")
    expect(all(f["severity"] == "warning" for f in sin_objetivo + sin_resultado),
           "los dos son avisos")


def test_F001_R005_aviso_pregunta_sin_objetivo():
    brief = BRIEF_OK.replace("- [x] (D1§3; G1)", "- [ ] (D1§2) ¿Algo general?\n- [x] (D1§3; G1)")
    root = producto_ok("r005-aviso", brief=brief)
    sueltas = con_codigo(root, "W-QUESTION-OPEN")
    expect(len(sueltas) == 1 and "1 pregunta" in sueltas[0]["message"]
           and sueltas[0]["severity"] == "warning",
           "W-QUESTION-OPEN avisa de la pregunta que no cita objetivo")
    r = run(root, "check", "--check")
    expect(r.returncode == 0, "con avisos pero sin errores, --check sale con 0", r.stdout)


def test_F001_R013_json_schema():
    root = producto_ok("r013-json", brief=BRIEF_OK.replace("D1§1, D1§2, D1§3", "D1§1, D1§3"))
    r = run(root, "check", "--json")
    d = json.loads(r.stdout)
    expect(r.returncode == 0 and d["schema"] == "discovery.check/v1", "schema versionado")
    expect(set(d) >= {"schema", "ok", "counts", "documents", "goals", "candidates",
                      "questions", "findings"}, "claves del contrato", f"{sorted(d)}")
    expect(d["findings"] and all({"code", "severity", "title", "message"} <= set(f)
                                 for f in d["findings"]),
           "cada hallazgo lleva code, severity, title y message")
    expect(d["ok"] is False and d["counts"]["errors"] >= 1, "ok refleja los errores")


def test_F001_R013_check_exit():
    malo = producto_ok("r013-exit-malo", brief=BRIEF_OK.replace("D1§1, D1§2, D1§3", "D1§1, D1§3"))
    bueno = producto_ok("r013-exit-bueno")
    expect(run(malo, "check").returncode == 0, "sin --check el informe sale con 0")
    expect(run(malo, "check", "--check").returncode == 1, "--check sale con 1 si hay errores")
    expect(run(bueno, "check", "--check").returncode == 0, "--check sale con 0 si no los hay")
    r = run(malo, "check", "--chek")
    expect(r.returncode == 2 and "--chek" in r.stderr,
           "un argumento desconocido es un error, no un exit 0 silencioso")


# ----------------------------------------------------------------- T010

def estado(root, nombre):
    return discovery.doc_status((root / "product" / nombre).read_text(encoding="utf-8"))


def test_F001_R014_rechaza_sin_artefactos():
    root = proyecto("r014-sin-artefactos")
    ingerir(root, "vision.md", DOC_VISION)
    discovery.write_product(root, "brief.md", BRIEF_OK)
    antes = foto(root)
    r = run(root, "approve")
    expect(r.returncode == 1 and "backlog.md" in r.stderr and foto(root) == antes,
           "sin backlog.md no aprueba, lo dice y no crea nada", r.stderr)
    r = run(proyecto("r014-vacio"), "approve")
    expect(r.returncode == 1 and "brief.md" in r.stderr, "un producto vacío no se aprueba")


def test_F001_R014_rechaza_con_errores():
    root = producto_ok("r014-errores", brief=BRIEF_OK.replace("D1§1, D1§2, D1§3", "D1§1, D1§3"))
    antes = foto(root)
    r = run(root, "approve")
    expect(r.returncode == 1 and "E-SOURCE-UNCOVERED" in r.stderr and foto(root) == antes,
           "con errores no aprueba nada y los lista", r.stderr)


def test_F001_R014_rechaza_pregunta_sobre_objetivo():
    root = producto_ok("r014-pregunta-approve",
                       brief=BRIEF_OK.replace("- [x] (D1§3; G1)", "- [ ] (D1§3; G1)"))
    antes = foto(root)
    r = run(root, "approve")
    expect(r.returncode == 1 and "E-QUESTION-OPEN-GOAL" in r.stderr
           and "¿Diario o semanal?" in r.stderr and foto(root) == antes,
           "una pregunta abierta sobre G1 bloquea, se nombra y no cambia nada", r.stderr)


def test_F001_R014_aprueba_coherente():
    root = producto_ok("r014-aprueba")
    r = run(root, "approve")
    expect(r.returncode == 0, "aprueba un producto coherente", r.stderr)
    for nombre in ("brief.md", "backlog.md"):
        texto = (root / "product" / nombre).read_text(encoding="utf-8")
        expect(discovery.is_approved(texto) and not discovery.is_stale(texto),
               f"{nombre} queda como Approved · <huella>", estado(root, nombre))
    expect(not con_codigo(root, "W-PRODUCT-NOT-APPROVED"), "check ya no avisa de aprobacion")
    expect("ya estaban aprobados" in run(root, "approve").stdout, "aprobar dos veces no cambia nada")
    r = run(producto_ok("r014-skill", brief=BRIEF_OK.replace("D1§1, D1§2, D1§3", "D1§1, D1§3")),
            "approve", "--skill")
    expect(r.returncode == 0 and "No se puede aprobar" in r.stdout,
           "approve --skill sale con 0 y escribe todo en stdout")


def test_F001_R016_cambio_invalida():
    root = producto_ok("r016-cambio")
    run(root, "approve")
    p = root / "product" / "backlog.md"
    p.write_text(p.read_text(encoding="utf-8").replace("descarga sus movimientos",
                                                       "descarga sus facturas"), encoding="utf-8")
    f = con_codigo(root, "W-PRODUCT-NOT-APPROVED")
    expect(len(f) == 1 and f[0]["file"] == "backlog.md" and "cambió" in f[0]["message"],
           "un cambio de palabras tras aprobar figura como no aprobado", f"{f}")


def test_F001_R016_reformateo_no_invalida():
    root = producto_ok("r016-reformateo")
    run(root, "approve")
    p = root / "product" / "brief.md"
    p.write_text(p.read_text(encoding="utf-8").replace("\n## Usuarios", "\n\n\n## Usuarios")
                 .replace("el dueño ve", "el  dueño  ve"), encoding="utf-8")
    b = root / "product" / "backlog.md"
    b.write_text(b.read_text(encoding="utf-8").replace("\n### B02", "\n\n\n### B02")
                 .replace("descarga sus movimientos", "descarga  sus   movimientos"),
                 encoding="utf-8")
    expect(not con_codigo(root, "W-PRODUCT-NOT-APPROVED"),
           "reformatear el brief y el backlog no invalida")


# ----------------------------------------------------------------- T011

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


def test_F001_R015_guard_edit():
    root = producto_ok("r015-edit")
    backlog = root / "product" / "backlog.md"
    r = hook(root, "guard", "Edit", {"file_path": str(backlog), "old_string": "| Estado | Draft |",
                                     "new_string": "| Estado | Approved · 0123456789ab |"})
    expect(deniega(r) is True, "un Edit que aprueba backlog.md se deniega", r.stdout)
    expect("allow" not in r.stdout, "nunca devuelve allow")
    sellado = BRIEF_OK.replace("| Estado | Draft |", "| Estado | Approved |")
    r = hook(root, "guard", "Write", {"file_path": "product/brief.md", "content": sellado})
    expect(deniega(r) is True, "un Write que aprueba brief.md, aunque sea sin huella, se deniega")
    r = hook(root, "guard", "Edit", {"file_path": str(backlog), "old_string": "al cerrar.",
                                     "new_string": "al cerrar la caja."})
    expect(deniega(r) is False, "editar otra parte del backlog no se bloquea")
    r = hook(root, "guard", "Write", {"file_path": "product/sources/nota.md", "content": "x"})
    expect(deniega(r) is False, "otros archivos no le interesan")
    r = hook(root, "guard", "Write", {"file_path": "product/BACKLOG.md",
                                      "content": BACKLOG_OK.replace("| Estado | Draft |",
                                                                    "| Estado | Approved |")})
    expect(deniega(r) is True, "product/BACKLOG.md en mayusculas tambien se reconoce")


def test_F001_R015_guard_bash():
    root = producto_ok("r015-bash")
    r = hook(root, "guard", "Bash", {"command": "python3 /x/scripts/discovery.py approve --skill"})
    expect(deniega(r) is True, "el modelo no puede lanzar discovery.py approve")
    r = hook(root, "guard", "Bash", {"command": "python3 /x/scripts/discovery.py check"})
    expect(deniega(r) is False, "otros comandos pasan")


def test_F001_R015_auditoria_restaura():
    root = producto_ok("r015-auditoria")
    backlog = root / "product" / "backlog.md"
    hook(root, "guard", "Bash", {"command": "python3 ofuscado.py"}, tool_use_id="a1")
    texto = backlog.read_text(encoding="utf-8")
    sellado = discovery.set_status(texto, f"Approved · {discovery.content_digest(texto)}")[0]
    backlog.write_text(sellado, encoding="utf-8")
    r = hook(root, "audit", "Bash", {}, tool_use_id="a1")
    expect(r.returncode == 2 and "backlog.md" in r.stderr, "detecta la autoaprobacion", r.stderr)
    expect(estado(root, "backlog.md") == "Draft", "y devuelve el Estado a Draft")
    hook(root, "guard", "Bash", {"command": "ls"}, tool_use_id="a2")
    r = hook(root, "audit", "Bash", {}, tool_use_id="a2")
    expect(r.returncode == 0 and not r.stderr, "un comando que no toca el Estado: silencio")
    expect(hook(root, "audit", "Bash", {}, tool_use_id="sin-foto").returncode == 0,
           "sin instantanea no opina")

    # Borrar el brief y recrearlo ya aprobado, en dos comandos.
    brief = root / "product" / "brief.md"
    contenido = brief.read_text(encoding="utf-8")
    hook(root, "guard", "Bash", {"command": "mv product/brief.md /tmp/x"}, tool_use_id="m1")
    brief.unlink()
    hook(root, "audit", "Bash", {}, tool_use_id="m1")
    hook(root, "guard", "Bash", {"command": "python3 recrea.py"}, tool_use_id="m2")
    brief.write_text(discovery.set_status(contenido, "Approved · 0123456789ab")[0],
                     encoding="utf-8")
    r = hook(root, "audit", "Bash", {}, tool_use_id="m2")
    expect(r.returncode == 2 and estado(root, "brief.md") == "Draft",
           "un brief borrado y recreado ya aprobado vuelve a Draft", r.stderr)

    hook(root, "guard", "Bash", {"command": "python3 x.py"}, tool_use_id="b1")
    sellado = discovery.set_status(texto, "Approved · 0123456789ab")[0]
    backlog.write_text(sellado, encoding="utf-8")
    r = hook(root, "audit", "Bash", {}, tool_use_id="b1", env_extra={"DISCOVERY_BYPASS": "1"})
    expect(r.returncode == 0 and estado(root, "backlog.md").startswith("Approved"),
           "DISCOVERY_BYPASS=1 tambien desactiva la auditoria")


def test_F001_R015_sin_product_no_opina():
    root = proyecto("r015-sin-product")
    r = hook(root, "guard", "Bash", {"command": "python3 x/discovery.py approve"})
    expect(deniega(r) is False, "sin product/ el plugin no opina")
    con = producto_ok("r015-bypass")
    r = hook(con, "guard", "Bash", {"command": "python3 x/discovery.py approve"},
             env_extra={"DISCOVERY_BYPASS": "1"})
    expect(deniega(r) is False, "DISCOVERY_BYPASS=1 lo desactiva")
    r = run(con, "guard", stdin="no soy json")
    expect(r.returncode == 0 and not r.stdout.strip(), "stdin roto: deja pasar")
    r = run(con, "guard", stdin="[1]")
    expect(r.returncode == 0 and not r.stdout.strip(), "un payload inesperado: falla abierto")
    r = hook(root, "guard", "Write", {"file_path": "product/brief.md",
                                      "content": "| Estado | Approved |\n"})
    expect(deniega(r) is False, "sin product/ tampoco opina sobre Write")
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    expect(any("Bash" in h["matcher"] and "Edit" in h["matcher"] for h in hooks["PreToolUse"])
           and any(h["matcher"] == "Bash" for h in hooks["PostToolUse"]),
           "hooks.json registra guard y auditoria")


def cobertura_de_codigos():
    # main() la ejecuta despues de todas las pruebas: compara los codigos
    # declarados con los que las pruebas vieron emitirse mediante con_codigo().
    print("\ncobertura de codigos de hallazgo")
    declarados = set(discovery.FINDINGS)
    expect(declarados <= PROBADOS, f"los {len(declarados)} codigos declarados se prueban",
           f"sin probar: {sorted(declarados - PROBADOS)}")


# --------------------------------------------------------------------------

# ------------------------------------------------- feature 004 (sdd) · T002

def run_sin_raiz(cwd, *args):
    """Como run, pero sin CLAUDE_PROJECT_DIR: como la inyeccion de una skill."""
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN))
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, cwd=str(cwd), env=env, timeout=60)


def test_F004_R002_raiz_desde_subdirectorio():
    root = producto_ok("f004-r002")
    sources = root / "product" / "sources"
    desde_sub = run_sin_raiz(sources, "check", "--json")
    desde_raiz = run(root, "check", "--json")
    expect(desde_sub.returncode == 0 and desde_sub.stdout == desde_raiz.stdout
           and json.loads(desde_sub.stdout)["ok"],
           "check desde product/sources/ analiza el brief y el backlog del proyecto",
           desde_sub.stdout[:200] + desde_sub.stderr)

    # Segun la version de Python, is_dir() lanza PermissionError o devuelve
    # False ante un directorio sin permiso: se fuerza la excepcion.
    cerrado = root / "cerrado"
    (cerrado / "x").mkdir(parents=True)
    original = Path.is_dir

    def is_dir_sin_permiso(ruta):
        if cerrado in ruta.parents:
            raise PermissionError(13, "sin permiso", str(ruta))
        return original(ruta)

    Path.is_dir = is_dir_sin_permiso
    try:
        hallado = discovery.find_upwards(cerrado / "x", ("product",))
    finally:
        Path.is_dir = original
    expect(hallado == root, "un directorio sin permiso cuenta como vacio y se sigue subiendo",
           f"{hallado}")


def test_F004_R003_sin_product_usa_el_directorio_actual():
    # Fuera del repositorio hay un producto con contenido: si la busqueda se
    # saliera del repo, la salida cambiaria.
    fuera = producto_ok("f004-r003")
    de_fuera = run(fuera, "check", "--json").stdout
    for variante, crea_git in (("carpeta", lambda g: g.mkdir()),
                               ("archivo de worktree", lambda g: g.write_text("gitdir: x\n"))):
        repo = fuera / f"repo-{variante.split()[0]}"
        (repo / "sub").mkdir(parents=True)
        crea_git(repo / ".git")  # basta con que exista: es el tope de la busqueda
        sin = run_sin_raiz(repo / "sub", "check", "--json")
        como_hoy = run(repo / "sub", "check", "--json")
        expect((sin.returncode, sin.stdout) == (como_hoy.returncode, como_hoy.stdout)
               and sin.stdout != de_fuera,
               f"sin product/ en el repo (.git como {variante}): como hoy, sin usar el de fuera",
               f"{sin.stdout[:200]!r} vs {como_hoy.stdout[:200]!r}")
        guardada = os.environ.pop("CLAUDE_PROJECT_DIR", None)
        try:
            raiz = discovery.project_root({"cwd": str(repo / "sub")})
        finally:
            if guardada is not None:
                os.environ["CLAUDE_PROJECT_DIR"] = guardada
        expect(raiz == (repo / "sub").resolve(),
               f"la raiz es el directorio actual (.git como {variante})", f"{raiz}")


def test_F004_R004_variable_de_entorno_manda():
    a = producto_ok("f004-r004-a")
    b = proyecto("f004-r004-b")
    (b / "product" / "sources").mkdir(parents=True)
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN), CLAUDE_PROJECT_DIR=str(a))
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--json"], capture_output=True,
                       text=True, cwd=str(b / "product" / "sources"), env=env, timeout=60)
    expect(r.stdout == run(a, "check", "--json").stdout and json.loads(r.stdout)["ok"],
           "con la variable en un proyecto y el cwd en otro, manda la variable", r.stdout[:200])


# ------------------------------------------------- feature 004 (sdd) · T003
# Listas equivalentes a MENCIONES y EJECUCIONES del selftest de sdd: las dos
# copias del analizador deben dar lo mismo.

MENCIONES = [
    "git commit -q -m 'discovery: la compuerta ya no bloquea discovery.py approve'",
    'gh pr create --title t --body "Corrige: python3 discovery.py approve en texto"',
    "cat > notas.md <<'EOF'\npython3 plugins/discovery/scripts/discovery.py approve\nEOF",
    'echo "para aprobar: python3 discovery.py approve"',
    "grep -rn 'discovery.py approve' plugins/discovery/README.md",
    "git commit -m 'la compuerta ya no bloquea `python3 discovery.py approve`'",
    "gh pr create --title t --body 'Ahora `discovery.py approve` solo se bloquea si se ejecuta'",
    "git commit -m 'cita $(python3 discovery.py approve) en texto'",
]

EJECUCIONES = [
    "python3 discovery.py approve",
    "python3 /x/plugins/discovery/scripts/discovery.py approve --skill",
    'python3 "$HOME/plugins/discovery/scripts/discovery.py" approve',
    "cd plugins/discovery && python3 scripts/discovery.py approve",
    "ls; FOO=1 python3 discovery.py approve",
    "echo `python3 discovery.py approve`",
    'echo "$(python3 discovery.py approve)"',
    'git commit -m "$(python3 /x/discovery.py approve)"',
    "x=$(cd y && python3 discovery.py approve)",
    "python3 discovery.py approve; echo $'it\\'s'",
]


def test_F004_R005_mencion_no_bloquea():
    root = producto_ok("f004-r005")
    for cmd in MENCIONES:
        corto = cmd.splitlines()[0][:50]
        expect(not discovery.invokes_approve(cmd), f"no es ejecucion: {corto!r}")
        r = hook(root, "guard", "Bash", {"command": cmd})
        expect(deniega(r) is False, f"la compuerta no bloquea: {corto!r}", r.stdout)
    expect(not discovery.invokes_approve('echo "sin cerrar'),
           "un comando que no se analiza y no contiene la orden: no")


def test_F004_R006_ejecucion_bloquea():
    root = producto_ok("f004-r006")
    for cmd in EJECUCIONES:
        expect(discovery.invokes_approve(cmd), f"es ejecucion: {cmd!r}")
        r = hook(root, "guard", "Bash", {"command": cmd})
        expect(deniega(r) is True, f"bloquea: {cmd!r}", r.stdout)
        expect("allow" not in r.stdout, f"nunca devuelve allow: {cmd!r}")


def test_F004_R007_auditoria_revierte():
    root = producto_ok("f004-r007")
    opaco = "bash -c 'python3 plugins/discovery/scripts/discovery.py approve --skill'"
    r = hook(root, "guard", "Bash", {"command": opaco}, tool_use_id="f4")
    expect(deniega(r) is False, "la compuerta deja pasar un bash -c", r.stdout)
    backlog = root / "product" / "backlog.md"
    texto = backlog.read_text(encoding="utf-8")
    backlog.write_text(discovery.set_status(texto, "Approved · 0123456789ab")[0],
                       encoding="utf-8")
    r = hook(root, "audit", "Bash", {}, tool_use_id="f4")
    expect(r.returncode == 2 and estado(root, "backlog.md") == "Draft"
           and "backlog.md" in r.stderr,
           "y la auditoria devuelve el backlog a Draft y avisa", r.stderr)


# ------------------------------------------------- feature 004 (sdd) · T004

def test_F004_R008_sin_citas_sin_prefijo():
    # La trazabilidad de sdd cuenta como cita ambigua un ID de requisito sin el
    # prefijo de feature en un archivo de pruebas, y avisa en cada feature.
    import re
    con_prefijo = re.compile(r"(?<![A-Za-z0-9])F\d{3,}[_-]R\d{2,}(?![0-9])")
    sin_prefijo = re.compile(r"(?<![A-Za-z0-9])R\d{2,}(?![0-9])")
    texto = Path(__file__).read_text(encoding="utf-8")
    sueltas = [n for n, linea in enumerate(texto.splitlines(), 1)
               if sin_prefijo.search(con_prefijo.sub(" ", linea))]
    expect(not sueltas, "el selftest no cita ningun requisito sin prefijo de feature",
           f"lineas {sueltas}")


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
