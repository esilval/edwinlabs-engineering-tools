#!/usr/bin/env python3
"""
discovery.py - utilidades deterministas del plugin discovery.

Todo lo que no requiere criterio vive aqui: identificadores de documentos,
objetivos y candidatas, numeracion de secciones, huellas, comprobacion de
coherencia y aprobacion. Las skills solo redactan y preguntan.

El plugin solo escribe dentro de product/. No lee ni escribe specs/: es una
etapa independiente, unida a las demas por archivos.

Subcomandos:
  ingest <archivo> [--original <archivo>]
                      Anade un documento al producto como Dn, con sus
                      secciones numeradas para citarlas (D2§4.2).
  next-id G|B         Siguiente objetivo (G4) o candidata (B07) libre.
"""

import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

PRODUCT_DIR = "product"


# --------------------------------------------------------------------------
# Localizacion del proyecto y escritura confinada a product/
# --------------------------------------------------------------------------

def project_root(payload=None):
    """Raiz del proyecto. CLAUDE_PROJECT_DIR es la fuente autoritativa."""
    for candidate in (
        os.environ.get("CLAUDE_PROJECT_DIR"),
        (payload or {}).get("cwd"),
        os.getcwd(),
    ):
        if candidate:
            return Path(candidate).resolve()
    return Path.cwd().resolve()


def product_root(root):
    return root / PRODUCT_DIR


class OutsideProduct(ValueError):
    """Intento de escribir fuera de product/."""


def product_path(root, rel):
    """
    Ruta absoluta de `rel` dentro de product/. Lanza OutsideProduct si `rel`
    escapa del directorio (`..`, ruta absoluta, enlace): el plugin no toca
    nada fuera de su etapa.
    """
    base = product_root(root).resolve()
    target = (base / rel).resolve()
    if base not in target.parents:
        raise OutsideProduct(f"{rel} queda fuera de {PRODUCT_DIR}/")
    return target


def write_product(root, rel, text):
    """Unica via de escritura del plugin."""
    target = product_path(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# --------------------------------------------------------------------------
# Huellas y campo Estado
#
# Copia deliberada de la logica de sdd (sdd_trace.py): la constitucion pide
# que los plugins se unan solo por archivos, asi que no se importa codigo de
# otro plugin. Si cambia la regla de normalizacion aqui, cambiala alli.
# --------------------------------------------------------------------------

ACCENTS = str.maketrans(
    "áàäâéèëê"
    "íìïîóòöô"
    "úùüûñç",
    "aaaaeeeeiiiioooouuuunc",
)


def norm(text):
    """Minusculas sin acentos, para comparar etiquetas y buscar palabras."""
    return text.lower().translate(ACCENTS)


def _squash(line):
    """Normaliza espacios y relleno de tablas para comparar lineas."""
    line = re.sub(r"\s*\|\s*", "|", line.strip())
    return re.sub(r"\s+", " ", line)


def text_digest(text):
    """
    Huella de un texto: ignora espacios sobrantes y lineas en blanco, porque
    reformatear no es cambiar el contenido.
    """
    lines = [_squash(raw) for raw in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


STATUS_ROW = re.compile(
    r"^(\|\s*(?:Estado|Status)\s*\|\s*)([^|\n]*?)(\s*\|)", re.I | re.M
)
APPROVED = {"approved", "aprobado", "aprobada"}
DIGEST = re.compile(r"\b([0-9a-f]{12})\b")


def _header_end(text):
    """Fin de la cabecera: el primer encabezado de nivel 2."""
    m = re.search(r"^##\s", text, re.M)
    return m.start() if m else len(text)


def doc_status(text):
    """Valor del campo Estado de la cabecera, o None si no existe."""
    text = text or ""
    m = STATUS_ROW.search(text, 0, _header_end(text))
    return m.group(2).strip() if m else None


def is_approved(text):
    """
    Aprobado = 'Approved · <huella>'. A diferencia de sdd, aqui no hay
    artefactos anteriores a la huella que respetar: un 'Approved' sin huella
    lo ha escrito alguien a mano y no cuenta.
    """
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    return (bool(words) and words[0].strip("`*_") in APPROVED
            and approval_digest(text) is not None)


def set_status(text, value):
    """Devuelve (texto_nuevo, cambiado?)."""
    end = _header_end(text)
    head, n = STATUS_ROW.subn(lambda m: m.group(1) + value + m.group(3),
                              text[:end], count=1)
    return head + text[end:], bool(n)


def content_digest(text):
    """Huella del contenido revisable: todo menos la fila Estado de la
    cabecera, que es donde se guarda la propia huella."""
    end = _header_end(text)
    return text_digest(STATUS_ROW.sub("", text[:end], count=1) + text[end:])


def approval_digest(text):
    """Huella guardada al aprobar ('Approved · 3f9a2c1b0d4e'), o None."""
    m = DIGEST.search(doc_status(text) or "")
    return m.group(1) if m else None


def is_stale(text):
    """True si el artefacto cambio despues de aprobarse."""
    stamp = approval_digest(text)
    return bool(is_approved(text) and stamp and stamp != content_digest(text))


# --------------------------------------------------------------------------
# Documentos del producto: product/sources/Dn-slug.md
# --------------------------------------------------------------------------

SOURCES_DIR = "sources"
SOURCE_FILE = re.compile(r"^D(\d+)-[a-z0-9-]+\.md$")
TEXT_FORMATS = {".md", ".markdown"}
SUPPORTED = TEXT_FORMATS | {".docx", ".pdf"}
# Lo que va despues de esta marca es el contenido del documento; lo de antes,
# la cabecera que escribe ingest. La huella de R011 cubre solo el contenido.
CONTENT_MARK = "<!-- discovery:contenido -->"
# La secuencia de cierre (`## Titulo ##`) solo cuenta si va precedida de
# espacio, como en CommonMark: `## Soporte C#` conserva su `#`.
HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
# Numeracion que el documento ya traia ("1.", "2.3", "IV."): se sustituye por
# la de discovery para no acabar con "## 1 1. Intro".
OWN_NUMBER = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.)\s+")
FIELD_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$", re.M)


class Rejected(Exception):
    """Ingesta rechazada: el producto no se modifica."""


def source_files(root):
    """{numero: Path} de los documentos ingeridos."""
    base = product_root(root) / SOURCES_DIR
    out = {}
    if base.is_dir():
        for p in base.iterdir():
            m = SOURCE_FILE.match(p.name)
            if m and p.is_file():
                out[int(m.group(1))] = p
    return out


def header_fields(text):
    """Campos de la tabla de cabecera de un documento ingerido."""
    head = text.split(CONTENT_MARK, 1)[0]
    return {k.strip(): v.strip() for k, v in FIELD_ROW.findall(head)}


def source_content(text):
    """Contenido del documento ingerido, sin la cabecera."""
    parts = text.split(CONTENT_MARK, 1)
    return parts[1] if len(parts) == 2 else ""


def _outside_fences(lines):
    """Indices de las lineas que no estan dentro de un bloque de codigo."""
    fence = None
    for i, line in enumerate(lines):
        m = re.match(r"^\s*(```+|~~~+)", line)
        if m:
            mark = m.group(1)[0]
            fence = None if fence == mark else (fence or mark)
            continue
        if fence is None:
            yield i


def number_sections(text):
    """
    Devuelve (texto con los encabezados numerados, titulo o None, numeros).

    Si el documento tiene un unico H1 y es su primer encabezado, es el titulo:
    no es seccion y no se numera. El resto se numera por anidamiento real
    (1, 1.1, 1.1.1): la profundidad la da la pila de niveles abiertos, asi que
    un nivel que se salta o un encabezado profundo al principio no producen
    ceros. Sin encabezados, el documento entero es la seccion 1.
    """
    lines = text.splitlines()
    heads = []
    for i in _outside_fences(lines):
        m = HEADING.match(lines[i])
        if m:
            heads.append((i, len(m.group(1)), m.group(2)))
    if not heads:
        return text, None, ["1"]

    title = None
    if heads[0][1] == 1 and sum(1 for _i, level, _t in heads if level == 1) == 1:
        title = heads[0][2]
        heads = heads[1:]
    if not heads:
        return text, title, ["1"]

    stack, counters, numbers = [], [], []
    for i, level, words in heads:
        while stack and stack[-1] >= level:
            stack.pop()
        stack.append(level)
        depth = len(stack)
        counters = counters[:depth] + [0] * (depth - len(counters))
        counters[depth - 1] += 1
        number = ".".join(str(n) for n in counters[:depth])
        numbers.append(number)
        lines[i] = f"{'#' * level} {number} {OWN_NUMBER.sub('', words)}"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), title, numbers


def sections(text):
    """
    Numeros de seccion de un documento ingerido ('1', '4.2'…). Se leen de la
    cabecera, que los registra ingest: deducirlos de los encabezados confundiria
    un titulo como '# 2025 Vision' con una seccion.
    """
    listed = header_fields(text).get("Secciones", "")
    return [s.strip() for s in listed.split(",") if s.strip()] or ["1"]


def slugify(text, max_words=5):
    text = norm(text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    words = [w for w in re.split(r"[\s_-]+", text) if w]
    return "-".join(words[:max_words]) or "documento"


def ingest_text(root, content, original_name, original_digest, today=None):
    """Registra `content` (Markdown) como el siguiente Dn. Lanza Rejected."""
    existing = source_files(root)
    for num, path in sorted(existing.items()):
        fields = header_fields(path.read_text(encoding="utf-8", errors="replace"))
        if fields.get("Huella original") == original_digest:
            raise Rejected(f"El documento es idéntico a D{num} "
                           f"({fields.get('Original', path.name)}); no se ingiere de nuevo.")

    number = max(existing) + 1 if existing else 1
    numbered, title, numbers = number_sections(content)
    body = numbered if numbered.endswith("\n") else numbered + "\n"
    did = f"D{number}"
    header = (
        f"# {did} — {title or Path(original_name).stem}\n\n"
        "| Campo | Valor |\n| ----- | ----- |\n"
        f"| Documento | {did} |\n"
        f"| Original | {original_name} |\n"
        f"| Ingesta | {(today or datetime.date.today()).isoformat()} |\n"
        f"| Huella original | {original_digest} |\n"
        f"| Huella | {text_digest(body)} |\n"
        f"| Secciones | {', '.join(numbers)} |\n\n"
        "> Documento ingerido por discovery. No se edita: un cambio entra como\n"
        "> documento nuevo. Las secciones se citan como "
        f"{did}§<número>.\n\n"
        f"{CONTENT_MARK}\n"
    )
    rel = f"{SOURCES_DIR}/{did}-{slugify(Path(original_name).stem)}.md"
    write_product(root, rel, header + body)
    return {"document": did, "path": f"{PRODUCT_DIR}/{rel}", "title": title,
            "sections": len(numbers)}


WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# Estilos de titulo de Word: los ids en ingles ("Heading2", "Title") y los de
# una instalacion en espanol ("Ttulo2", "Titulo2"). outlineLvl gana si existe.
WORD_HEADING_STYLE = re.compile(r"^(?:heading|t[ií]?tulo)\s*(\d)$", re.I)
WORD_TITLE_STYLE = re.compile(r"^(?:title|t[ií]?tulo)$", re.I)
# Inicio de linea que Markdown leeria como estructura (encabezado, cita, lista).
MD_STRUCTURE = re.compile(r"^(#|>|[-*+]\s|\d+[.)]\s)")


def bytes_digest(data):
    """Huella de un archivo binario: sus bytes en bruto, sin normalizar."""
    return hashlib.sha1(data).hexdigest()[:12]


def docx_to_markdown(path):
    """
    Convierte un .docx a Markdown con la biblioteca estandar: el .docx es un
    zip con XML. Los parrafos con estilo de titulo dan los encabezados; el
    resto, parrafos de texto. Lanza Rejected si el archivo no es un Word valido.
    """
    import zipfile
    import xml.etree.ElementTree as ET
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
        body = ET.fromstring(xml).find(f"{WORD_NS}body")
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError):
        raise Rejected(f"{Path(path).name} no es un documento Word válido.")
    if body is None:
        raise Rejected(f"{Path(path).name} no tiene cuerpo de documento.")

    out, title_seen = [], False
    for p in body.iter(f"{WORD_NS}p"):
        text = "".join(t.text or "" for t in p.iter(f"{WORD_NS}t")).strip()
        if not text:
            continue
        level = None
        ppr = p.find(f"{WORD_NS}pPr")
        if ppr is not None:
            outline = ppr.find(f"{WORD_NS}outlineLvl")
            style = ppr.find(f"{WORD_NS}pStyle")
            style_id = style.get(f"{WORD_NS}val", "") if style is not None else ""
            # El estilo Titulo es el titulo del documento (H1); Titulo 1 es
            # la primera seccion (H2). Asi un Word con Titulo + Titulo 1, 2…
            # queda con un H1 unico y sus secciones empiezan en §1.
            # Solo el primer parrafo con estilo Titulo es el titulo; un
            # segundo (subtitulo marcado igual) queda como texto.
            if WORD_TITLE_STYLE.match(style_id):
                level = None if title_seen else 1
                title_seen = True
            elif outline is not None and outline.get(f"{WORD_NS}val", "").isdigit():
                level = min(int(outline.get(f"{WORD_NS}val")) + 2, 6)
            elif WORD_HEADING_STYLE.match(style_id):
                level = min(int(WORD_HEADING_STYLE.match(style_id).group(1)) + 1, 6)
        if level:
            out.append(f"{'#' * level} {text}")
        else:
            # Un parrafo normal no puede volverse estructura Markdown: un
            # '# no soy titulo' seria una seccion falsa y romperia las citas.
            out.append("\\" + text if MD_STRUCTURE.match(text) else text)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def cmd_ingest(args):
    original = None
    if "--original" in args:
        i = args.index("--original")
        if i + 1 >= len(args):
            print("error: --original necesita un archivo", file=sys.stderr)
            return 1
        original = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        print("uso: discovery.py ingest <archivo> [--original <archivo>]", file=sys.stderr)
        return 1

    root = project_root()
    source = Path(args[0])
    try:
        ext = source.suffix.lower()
        if ext not in SUPPORTED:
            raise Rejected(f"Formato no admitido: {source.name}. Se admiten Markdown "
                           "(.md, .markdown), Word (.docx) y PDF (.pdf).")
        if not source.is_file():
            raise Rejected(f"No existe el archivo {source}.")
        if ext == ".pdf":
            raise Rejected(f"{source.name} es un PDF: conviértelo a Markdown y llama a "
                           f"ingest <markdown> --original {source.name}.")
        if original is not None:
            # Markdown convertido por el modelo desde un PDF u otro original:
            # se registra el nombre y la huella de los bytes del original.
            if ext not in TEXT_FORMATS:
                raise Rejected("Con --original, el archivo a ingerir es el Markdown convertido.")
            if original.suffix.lower() != ".pdf" or not original.is_file():
                raise Rejected(f"--original es para PDF: {original} no existe o no es un PDF. "
                               "Markdown y Word se ingieren directamente.")
            content = source.read_text(encoding="utf-8")
            result = ingest_text(root, content, original.name,
                                 bytes_digest(original.read_bytes()))
        elif ext == ".docx":
            # Huella del texto convertido, no del zip: el mismo Word guardado
            # otra vez cambia sus bytes pero no su contenido (R002, D5).
            content = docx_to_markdown(source)
            result = ingest_text(root, content, source.name, text_digest(content))
        else:
            content = source.read_text(encoding="utf-8")
            result = ingest_text(root, content, source.name, text_digest(content))
    except Rejected as exc:
        print(f"Rechazado: {exc} El producto no ha cambiado.", file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print(f"Rechazado: {source.name} no es texto UTF-8. El producto no ha cambiado.",
              file=sys.stderr)
        return 1
    result["next"] = "/discovery:clarify"
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------
# Brief y backlog: product/brief.md, product/backlog.md
# --------------------------------------------------------------------------

BRIEF = "brief.md"
BACKLOG = "backlog.md"

ITEM_HEAD = re.compile(r"^#{2,5}\s*(?=([GB]\d+)\b)", re.M)
ITEM_FIELD = re.compile(r"^\s*[-*]\s*\*\*\s*(.+?)\s*:?\s*\*\*\s*(.*)$", re.M)
DOC_REF = re.compile(r"(?<![A-Za-z0-9])D(\d+)§(\d+(?:\.\d+)*)")
DOC_ONLY_REF = re.compile(r"(?<![A-Za-z0-9])D(\d+)(?![\d§])")
GOAL_REF = re.compile(r"(?<![A-Za-z0-9])G(\d+)(?![0-9])")
CAND_REF = re.compile(r"(?<![A-Za-z0-9])B(\d{2,})(?![0-9])")
QUESTION = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.*)$")


def read_product(root, name):
    path = product_root(root) / name
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


def section(text, *titles):
    """
    Cuerpo de una seccion de nivel 2 (`## Titulo`) cuyo titulo, sin acentos ni
    mayusculas, es uno de `titles` o empieza por el (`## Invariantes propuestos
    para la constitucion` encaja con 'invariantes'). Solo nivel 2: un objetivo
    `### G1 — Responder preguntas` nunca se confunde con `## Preguntas`.
    """
    wanted = [norm(t) for t in titles]
    out, capturing = [], False
    for line in (text or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m and len(m.group(1)) <= 2:
            if capturing:
                break
            title = norm(m.group(2))
            if len(m.group(1)) == 2 and any(title == w or title.startswith(w + " ")
                                            for w in wanted):
                capturing = True
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def refs(text):
    """Citas que contiene un texto: secciones Dn§x, documentos, objetivos, candidatas."""
    text = text or ""
    return {
        "sections": sorted({f"D{d}§{s}" for d, s in DOC_REF.findall(text)}),
        "documents": sorted({f"D{d}" for d in DOC_ONLY_REF.findall(text)}
                            | {f"D{d}" for d, _s in DOC_REF.findall(text)}),
        "goals": sorted({f"G{g}" for g in GOAL_REF.findall(text)}, key=lambda g: int(g[1:])),
        "candidates": sorted({f"B{b}" for b in CAND_REF.findall(text)}),
    }


def parse_items(text, prefix):
    """
    Objetivos (prefix 'G') o candidatas ('B') declarados como encabezado
    '### G1 — titulo', con campos '- **Campo:** valor'. Devuelve una lista en
    orden de aparicion, con los IDs repetidos marcados.
    """
    items, seen = [], set()
    blocks = ITEM_HEAD.split(text or "")
    # split con grupo: [antes, id1, bloque1, id2, bloque2, ...]
    for i in range(1, len(blocks) - 1, 2):
        iid, block = blocks[i], blocks[i + 1]
        if not iid.startswith(prefix):
            continue
        head, _, rest = block.partition("\n")
        title = re.sub(rf"^{iid}\s*[—–:-]?\s*", "", head).strip()
        # El bloque termina en el siguiente encabezado de cualquier nivel.
        rest = re.split(r"^#{1,6}\s", rest, maxsplit=1, flags=re.M)[0]
        fields = {norm(k): v.strip() for k, v in ITEM_FIELD.findall(rest)}
        items.append({"id": iid, "title": title, "fields": fields,
                      "duplicate": iid in seen})
        seen.add(iid)
    return items


def parse_brief(text):
    goals = parse_items(section(text, "objetivos", "goals"), "G")
    questions = []
    for line in section(text, "preguntas", "questions").splitlines():
        m = QUESTION.match(line)
        if m:
            questions.append({"open": m.group(1) == " ", "text": m.group(2).strip(),
                              "refs": refs(m.group(2)), "answer": ""})
            continue
        answer = ITEM_FIELD.match(line)
        if answer and questions and norm(answer.group(1)) in ("respuesta", "answer"):
            questions[-1]["answer"] = answer.group(2).strip()
    discarded = refs(section(text, "secciones descartadas", "descartes"))["sections"]
    return {"goals": goals, "questions": questions, "discarded": discarded}


def parse_backlog(text):
    candidates = parse_items(section(text, "candidatas", "candidates"), "B")
    for c in candidates:
        raw = norm(c["fields"].get("estado", "")).replace("`", "").replace("_", "")
        c["state"] = (raw.split() or ["candidata"])[0]
    return {"candidates": candidates}


def next_id(root, prefix):
    """Siguiente ID libre: maximo + 1, contando descartadas. Nunca se recicla."""
    if prefix == "G":
        used = [int(g["id"][1:]) for g in parse_brief(read_product(root, BRIEF) or "")["goals"]]
        return f"G{max(used, default=0) + 1}"
    used = [int(c["id"][1:]) for c in parse_backlog(read_product(root, BACKLOG) or "")["candidates"]]
    return f"B{max(used, default=0) + 1:02d}"


def cmd_next_id(args):
    if len(args) != 1 or args[0].upper() not in ("G", "B"):
        print("uso: discovery.py next-id G|B", file=sys.stderr)
        return 1
    print(next_id(project_root(), args[0].upper()))
    return 0


# --------------------------------------------------------------------------

COMMANDS = {
    "ingest": cmd_ingest,
    "next-id": cmd_next_id,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
