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
    # Base de la deteccion de duplicados; el criterio de R002 lo prueba T003.
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

- **Origen:** D1§1, D1§3
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
    expect(discovery.refs(b["goals"][0]["fields"].get("origen"))["sections"] == ["D1§1", "D1§3"],
           "cada objetivo cita su origen")
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
- [ ] (D1§9; G7) ¿Pregunta con citas rotas?
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
    expect(any("D1§9" in i for i in rotas) and any("G7" in i for i in rotas),
           "señala la seccion y el objetivo inexistentes", f"{rotas}")
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


# --------------------------------------------------------------------------

def main():
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    try:
        for nombre, fn in tests:
            print(f"\n{nombre}")
            fn()
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
