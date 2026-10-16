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
  questions [--json]  Preguntas del brief: abiertas, respondidas y citas rotas.
  check [--json] [--check]
                      Coherencia del producto: citas, cobertura, numeracion.
                      --json emite discovery.check/v1; --check sale con 1 si
                      hay errores (para CI).
  approve [--skill]   Aprueba brief y backlog si check no da errores. Solo
                      lo lanza el usuario, con /discovery:approve.
  guard               Hook PreToolUse: impide que el modelo apruebe.
  audit               Hook PostToolUse sobre Bash: revierte una aprobacion
                      escrita por un comando.
"""

import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PRODUCT_DIR = "product"


# --------------------------------------------------------------------------
# Localizacion del proyecto y escritura confinada a product/
# --------------------------------------------------------------------------

def project_root(payload=None):
    """
    Raiz del proyecto. CLAUDE_PROJECT_DIR es la fuente autoritativa y se usa
    tal cual. Sin ella (la inyeccion de comandos de una skill no la recibe),
    se sube desde el cwd hasta el directorio que contiene product/.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    start = Path((payload or {}).get("cwd") or os.getcwd()).resolve()
    return find_upwards(start, (PRODUCT_DIR,)) or start


def find_upwards(start, markers):
    """
    El directorio mas cercano, desde start hacia arriba, que contiene alguno de
    los directorios markers, o None. Se detiene en el primer directorio con
    .git (carpeta, o archivo en un worktree) despues de examinarlo: la busqueda
    no sale del repositorio. Un directorio que no se puede leer cuenta como
    vacio.

    Copia de find_upwards en plugins/sdd/scripts/sdd.py: los plugins no
    comparten codigo. Un arreglo en una se replica en la otra.
    """
    for directory in (start, *start.parents):
        try:
            if any((directory / m).is_dir() for m in markers):
                return directory
            if (directory / ".git").exists():
                return None
        except OSError:
            continue
    return None


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
    cabecera, que es donde se guarda la propia huella.

    plugins/sdd/scripts/sdd_product.py y plugins/architecture/scripts/
    architecture.py tienen una copia de esta huella para saber si el producto
    esta aprobado: un cambio aqui se replica alli, y las pruebas de contrato de
    sus selftests lo comprueban."""
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
    questions, in_answer = [], False
    for line in section(text, "preguntas", "questions").splitlines():
        m = QUESTION.match(line)
        if m:
            questions.append({"open": m.group(1) == " ", "text": m.group(2).strip(),
                              "refs": refs(m.group(2)), "answer": ""})
            in_answer = False
            continue
        answer = ITEM_FIELD.match(line)
        if answer and questions and norm(answer.group(1)) in ("respuesta", "answer"):
            questions[-1]["answer"] = answer.group(2).strip()
            in_answer = True
        elif in_answer and line.startswith("    ") and line.strip():
            # Continuacion sangrada de la respuesta, tambien si la linea
            # `**Respuesta:**` iba vacia.
            questions[-1]["answer"] = (questions[-1]["answer"] + " " + line.strip()).strip()
        elif line.strip():
            in_answer = False
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
# El producto entero y sus citas
# --------------------------------------------------------------------------

def load_product(root):
    """Documentos, brief y backlog leidos de product/."""
    documents = {}
    for num, path in sorted(source_files(root).items()):
        text = path.read_text(encoding="utf-8", errors="replace")
        documents[f"D{num}"] = {"path": path, "text": text,
                                "fields": header_fields(text), "sections": sections(text)}
    brief_text = read_product(root, BRIEF)
    backlog_text = read_product(root, BACKLOG)
    return {
        "documents": documents,
        "brief_text": brief_text,
        "backlog_text": backlog_text,
        "brief": parse_brief(brief_text or ""),
        "backlog": parse_backlog(backlog_text or ""),
    }


def broken_refs(product, cited):
    """Citas de `cited` (salida de refs) que no existen en el producto."""
    docs = product["documents"]
    goals = {g["id"] for g in product["brief"]["goals"]}
    cands = {c["id"] for c in product["backlog"]["candidates"]}
    broken = []
    for ref in cited["sections"]:
        did, sec = ref.split("§")
        if did not in docs:
            broken.append(f"{ref} (no existe {did})")
        elif sec not in docs[did]["sections"]:
            broken.append(f"{ref} (no existe la sección {sec} en {did})")
    for did in cited["documents"]:
        if did not in docs and not any(b.startswith(did + "§") for b in broken):
            broken.append(f"{did} (no existe)")
    broken += [f"{g} (no existe)" for g in cited["goals"] if g not in goals]
    broken += [f"{b} (no existe)" for b in cited["candidates"] if b not in cands]
    return broken


def question_report(product):
    """Preguntas del brief con los problemas de cada una."""
    out = []
    for q in product["brief"]["questions"]:
        issues = broken_refs(product, q["refs"])
        if not q["refs"]["sections"]:
            issues.append("no cita ninguna sección de origen (Dn§x)")
        out.append(dict(q, issues=issues))
    return out


def cmd_questions(args):
    product = load_product(project_root())
    report = question_report(product)
    if "--json" in args:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    if product["brief_text"] is None:
        print("No hay brief.md todavía: las preguntas se registran en él.")
        return 0
    open_q = [q for q in report if q["open"]]
    print(f"Preguntas abiertas: {len(open_q)} · respondidas: {len(report) - len(open_q)}")
    for q in open_q:
        print(f"  - {q['text']}")
        for issue in q["issues"]:
            print(f"      ! {issue}")
    bad_closed = [q for q in report if not q["open"] and q["issues"]]
    for q in bad_closed:
        print(f"  (respondida) {q['text']}")
        for issue in q["issues"]:
            print(f"      ! {issue}")
    return 0


# --------------------------------------------------------------------------
# Comprobacion de coherencia
# --------------------------------------------------------------------------

# Catalogo de hallazgos. Es contrato publico (schema discovery.check/v1): no
# renombrar codigos existentes; anadir es aditivo.
FINDINGS = {
    "E-GOAL-NO-FEATURE": "Objetivo sin ninguna candidata que lo persiga",
    "E-SOURCE-UNCOVERED": "Sección de documento sin objetivo, candidata ni descarte",
    "E-REF-UNKNOWN": "Cita a un documento, sección, objetivo o candidata inexistentes",
    "E-BACKLOG-DEP-CYCLE": "Dependencias circulares entre candidatas",
    "E-SOURCE-MODIFIED": "Documento editado después de ingerirse",
    "E-BACKLOG-ID-GAP": "Numeración rota: hueco o ID repetido en documentos, objetivos o candidatas",
    "E-BACKLOG-REQUIREMENT": "Objetivo o candidata redactado como requisito",
    "E-QUESTION-OPEN-GOAL": "Pregunta abierta que afecta a un objetivo",
    "E-PRODUCT-TEMPLATE": "Brief o backlog con huecos de plantilla sin rellenar",
    "W-FEATURE-NO-GOAL": "Candidata que no persigue ningún objetivo",
    "W-FEATURE-NO-OUTCOME": "Candidata sin resultado observable",
    "W-QUESTION-OPEN": "Preguntas abiertas que no afectan a ningún objetivo",
    "W-PRODUCT-NOT-APPROVED": "Brief o backlog sin aprobar, o cambiados después de aprobarse",
}

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
INLINE_PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9])_[^_\n]*(?:\.\.\.|\\<)[^_\n]*_(?![A-Za-z0-9])")
# Forma EARS de un requisito, no cualquier futuro: «DEBERÁ» en mayusculas, o
# «el sistema / la aplicacion… deberá». «El dueño deberá cerrar la caja» es
# una descripcion valida de un problema.
EARS_UPPER = re.compile(r"\b(?:DEBER[AÁ]N?|SHALL)\b")
EARS_SUBJECT = re.compile(r"\b(?:el|la)\s+(?:sistema|aplicaci[oó]n|plataforma|producto|servicio)"
                          r"\s+deber[aá]n?\b", re.I)
ITALIC_FRAGMENT = re.compile(r"(?<![A-Za-z0-9_])_([^_\n]+?)_(?![A-Za-z0-9_])")


def template_fragments(name):
    """Textos en cursiva de la plantilla: cada uno es un hueco por rellenar."""
    path = TEMPLATES_DIR / name
    if not path.is_file():
        return set()
    return {norm(m.group(1).strip()) for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith(">") for m in ITALIC_FRAGMENT.finditer(line)}


def find_placeholders(text, template_name):
    """
    Lineas que conservan un hueco de la plantilla. Se compara cada fragmento en
    cursiva, no la linea entera: un bloque copiado para B02 con su
    `_título de la feature candidata_` sin rellenar tambien cuenta.
    """
    known = template_fragments(template_name)
    out = []
    for i, raw in enumerate((text or "").splitlines(), 1):
        if raw.lstrip().startswith(">"):
            continue
        frags = {norm(m.group(1).strip()) for m in ITALIC_FRAGMENT.finditer(raw)}
        if frags & known or INLINE_PLACEHOLDER.search(raw):
            out.append((i, raw.strip()))
    return out


def is_requirement(text):
    return bool(EARS_UPPER.search(text) or EARS_SUBJECT.search(text))


def _related(a, b):
    """True si la seccion a es b, la contiene o esta contenida en ella."""
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def _cycles(graph):
    state, found = {}, []

    def visit(node, path):
        if state.get(node) == "done":
            return
        if state.get(node) == "open":
            # `path` ya termina en el nodo que cierra el ciclo.
            found.append(path[path.index(node):])
            return
        state[node] = "open"
        for nxt in graph.get(node, []):
            visit(nxt, path + [nxt])
        state[node] = "done"

    for node in sorted(graph):
        visit(node, [node])
    return found


def _id_gaps(ids, label, hint):
    """Mensajes por huecos o repetidos en una serie de IDs ('G', 'B', 'D')."""
    if not ids:
        return []
    prefix = ids[0][0]
    width = 2 if prefix == "B" else 1
    nums = [int(i[1:]) for i in ids]
    fmt = lambda n: f"{prefix}{n:0{width}d}"  # noqa: E731
    out = []
    repeated = sorted({n for n in nums if nums.count(n) > 1})
    if repeated:
        out.append(f"IDs repetidos en {label}: " + ", ".join(fmt(n) for n in repeated) + ".")
    missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
    if missing:
        out.append(f"Faltan IDs en {label}: " + ", ".join(fmt(n) for n in missing) + f". {hint}")
    return out


def analyze(root):
    product = load_product(root)
    docs, brief, backlog = product["documents"], product["brief"], product["backlog"]
    findings = []

    def add(code, message, **extra):
        if code not in FINDINGS:
            # Todo codigo emitido esta en el catalogo: es contrato publico.
            raise ValueError(f"codigo de hallazgo no declarado: {code}")
        findings.append({"code": code, "severity": "error" if code.startswith("E-") else "warning",
                         "title": FINDINGS[code], "message": message, **extra})

    goals = brief["goals"]
    candidates = backlog["candidates"]
    live = [c for c in candidates if c["state"] != "descartada"]

    # E-SOURCE-MODIFIED
    for did, d in docs.items():
        stored = d["fields"].get("Huella")
        if stored != text_digest(source_content(d["text"])):
            add("E-SOURCE-MODIFIED", f"{did} se editó después de ingerirlo, o su cabecera ya no "
                "tiene la huella. Los documentos no se editan: restaura el archivo y trae el "
                "cambio como documento nuevo.", document=did)

    # E-REF-UNKNOWN: toda cita del brief y del backlog, fuera de las notas en
    # blockquote (que traen ejemplos como D2§4.2).
    for name, text in ((BRIEF, product["brief_text"]), (BACKLOG, product["backlog_text"])):
        seen = set()
        for n, line in enumerate((text or "").splitlines(), 1):
            if line.lstrip().startswith(">"):
                continue
            for broken in broken_refs(product, refs(line)):
                if (name, broken) not in seen:
                    seen.add((name, broken))
                    add("E-REF-UNKNOWN", f"{name}, línea {n}, cita {broken}.", file=name)

    # E-GOAL-NO-FEATURE
    pursued = {g for c in live for g in refs(c["fields"].get("objetivos", ""))["goals"]}
    for g in goals:
        if g["id"] not in pursued:
            add("E-GOAL-NO-FEATURE", f"{g['id']} ({g['title']}) no lo persigue ninguna candidata "
                "viva.", goal=g["id"])

    # E-SOURCE-UNCOVERED
    cited = set(brief["discarded"])
    for g in goals:
        cited |= set(refs(g["fields"].get("origen", ""))["sections"])
    for c in live:
        cited |= set(refs(c["fields"].get("origen", ""))["sections"])
    if product["brief_text"] is not None or product["backlog_text"] is not None:
        for did, d in docs.items():
            for sec in d["sections"]:
                ref = f"{did}§{sec}"
                if not any(c.split("§")[0] == did and _related(sec, c.split("§")[1])
                           for c in cited):
                    add("E-SOURCE-UNCOVERED", f"{ref} no lo cita ningún objetivo ni candidata y "
                        "no está descartada.", section=ref)

    # E-BACKLOG-DEP-CYCLE
    graph = {c["id"]: refs(c["fields"].get("depende de", ""))["candidates"] for c in candidates}
    for cycle in _cycles(graph):
        add("E-BACKLOG-DEP-CYCLE", "Dependencias circulares: " + " -> ".join(cycle))

    # E-BACKLOG-ID-GAP
    # Los documentos se cuentan por archivo: D1-a.md y D1-b.md son un repetido.
    base = product_root(root) / SOURCES_DIR
    doc_ids = sorted((f"D{SOURCE_FILE.match(p.name).group(1)}" for p in base.iterdir()
                      if SOURCE_FILE.match(p.name)), key=lambda d: int(d[1:])) \
        if base.is_dir() else []
    for ids, label, hint in (
            (doc_ids, "documentos", "Un documento ingerido no se borra."),
            ([g["id"] for g in goals], "objetivos", "Un objetivo se descarta, no se borra."),
            ([c["id"] for c in candidates], "candidatas",
             "Una candidata se descarta (Estado: descartada), no se borra.")):
        for message in _id_gaps(ids, label, hint):
            add("E-BACKLOG-ID-GAP", message)

    # E-BACKLOG-REQUIREMENT
    for item in goals + candidates:
        if is_requirement(item["title"] + " " + " ".join(item["fields"].values())):
            add("E-BACKLOG-REQUIREMENT", f"{item['id']} está redactado como requisito "
                "(«DEBERÁ»). Aquí va problema y resultado; los requisitos los escribe "
                "/sdd:specify.", item=item["id"])

    # E-QUESTION-OPEN-GOAL
    for q in brief["questions"]:
        if q["open"] and q["refs"]["goals"]:
            add("E-QUESTION-OPEN-GOAL", f"Pregunta abierta sobre {', '.join(q['refs']['goals'])}: "
                f"{q['text'][:100]}. Ciérrala con /discovery:clarify.")

    # E-PRODUCT-TEMPLATE
    for name, text in ((BRIEF, product["brief_text"]), (BACKLOG, product["backlog_text"])):
        holes = find_placeholders(text, name)
        if holes:
            line, sample = holes[0]
            add("E-PRODUCT-TEMPLATE", f"{name} conserva {len(holes)} hueco(s) de plantilla; el "
                f"primero en la línea {line}: {sample[:70]}", file=name)

    # Avisos: no bloquean la aprobacion
    for c in live:
        if not refs(c["fields"].get("objetivos", ""))["goals"]:
            add("W-FEATURE-NO-GOAL", f"{c['id']} no persigue ningún objetivo: o sobra, o falta "
                "el objetivo en el brief.", item=c["id"])
        outcome = c["fields"].get("resultado observable", "").strip(" —-_")
        if not outcome:
            add("W-FEATURE-NO-OUTCOME", f"{c['id']} no tiene resultado observable: suele ser una "
                "capa técnica disfrazada de feature.", item=c["id"])
    loose = [q for q in brief["questions"] if q["open"] and not q["refs"]["goals"]]
    if loose:
        add("W-QUESTION-OPEN", f"Quedan {len(loose)} pregunta(s) abierta(s) que no citan ningún "
            "objetivo. Si afectan a uno, cítalo: (D1§2; G2).")
    for name, text in ((BRIEF, product["brief_text"]), (BACKLOG, product["backlog_text"])):
        if text is None:
            continue
        if is_stale(text):
            add("W-PRODUCT-NOT-APPROVED", f"{name} cambió después de aprobarse: la aprobación "
                "era sobre otra versión. El usuario lo revisa y ejecuta /discovery:approve.",
                file=name)
        elif not is_approved(text):
            add("W-PRODUCT-NOT-APPROVED", f"{name} no está aprobado. Lo aprueba el usuario con "
                "/discovery:approve.", file=name)

    errors = [f for f in findings if f["severity"] == "error"]
    return {
        "schema": "discovery.check/v1",
        "ok": not errors,
        "counts": {"documents": len(docs), "goals": len(goals), "candidates": len(candidates),
                   "questions_open": sum(1 for q in brief["questions"] if q["open"]),
                   "errors": len(errors), "warnings": len(findings) - len(errors)},
        "documents": {did: {"sections": d["sections"], "original": d["fields"].get("Original")}
                      for did, d in docs.items()},
        "goals": [g["id"] for g in goals],
        "candidates": [{"id": c["id"], "state": c["state"]} for c in candidates],
        "questions": [{"text": q["text"], "open": q["open"]} for q in brief["questions"]],
        "findings": findings,
    }


def report(data):
    c = data["counts"]
    out = [f"Producto: {c['documents']} documento(s), {c['goals']} objetivo(s), "
           f"{c['candidates']} candidata(s), {c['questions_open']} pregunta(s) abierta(s)"]
    for sev, label in (("error", "ERRORES"), ("warning", "AVISOS")):
        items = [f for f in data["findings"] if f["severity"] == sev]
        if items:
            out.append(f"\n  {label} ({len(items)})")
            out += [f"    [{f['code']}] {f['message']}" for f in items]
    out.append("\n  OK: sin errores." if data["ok"] else f"\n  FALLA: {c['errors']} error(es).")
    return "\n".join(out)


def cmd_check(args):
    """
    Informe legible (siempre exit 0), --json (schema discovery.check/v1) o
    --check (exit 1 si hay errores): lo mismo en local y en CI.
    """
    unknown = [a for a in args if a not in ("--json", "--check")]
    if unknown:
        # En CI, una errata como --chek no debe convertirse en un exit 0.
        print(f"error: argumento desconocido {' '.join(unknown)}. "
              "Uso: discovery.py check [--json] [--check]", file=sys.stderr)
        return 2
    data = analyze(project_root())
    if "--json" in args:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(report(data))
    return 1 if ("--check" in args and not data["ok"]) else 0


# --------------------------------------------------------------------------
# Aprobacion: solo la lanza el usuario, con /discovery:approve
# --------------------------------------------------------------------------

def approve(root):
    """
    Sella brief.md y backlog.md con 'Approved · <huella>' si el producto no
    tiene errores (R014). Devuelve (ok, lineas_de_mensaje).
    """
    missing = [n for n in (BRIEF, BACKLOG) if read_product(root, n) is None]
    if missing:
        return False, [f"No se puede aprobar: falta {' y '.join(missing)}. "
                       "Lo produce /discovery:decompose."]

    data = analyze(root)
    errors = [f for f in data["findings"] if f["severity"] == "error"]
    if errors:
        return False, (["No se puede aprobar: la comprobación da errores."]
                       + [f"  [{f['code']}] {f['message']}" for f in errors])

    texts = {n: read_product(root, n) for n in (BRIEF, BACKLOG)}
    if all(is_approved(t) and not is_stale(t) for t in texts.values()):
        return True, ["Brief y backlog ya estaban aprobados."]

    sealed = {}
    for name, text in texts.items():
        stamp = f"Approved · {content_digest(text)}"
        new, changed = set_status(text, stamp)
        if not changed:
            return False, [f"{name} no tiene la fila '| Estado | ... |' en la cabecera. "
                           "Añádela y vuelve a aprobar."]
        sealed[name] = (new, stamp)
    for name, (new, _stamp) in sealed.items():
        write_product(root, name, new)
    return True, [f"{name} aprobado ({stamp})." for name, (_n, stamp) in sealed.items()]


def cmd_approve(args):
    """
    Con --skill (lo usa /discovery:approve) todo va a stdout y sale siempre con
    0: el resultado lo lee el modelo como texto, no como codigo de salida.
    """
    try:
        ok, lines = approve(project_root())
    except Exception as exc:  # noqa: BLE001
        if "--skill" not in args:
            raise
        ok, lines = False, [f"No se pudo aprobar: error inesperado ({exc})."]
    stream = sys.stdout if (ok or "--skill" in args) else sys.stderr
    print("\n".join(lines), file=stream)
    return 0 if (ok or "--skill" in args) else 1


# --------------------------------------------------------------------------
# Guard y auditoria: hooks que protegen la aprobacion (R015)
# --------------------------------------------------------------------------

APPROVABLE = (BRIEF, BACKLOG)
# Solo para comandos que no se pueden analizar por palabras.
APPROVE_TEXT = re.compile(r"discovery\.py['\"]?\s+approve\b")


# --------------------------------------------------------------------------
# Analisis de comandos: ejecutar la orden de aprobar frente a mencionarla.
#
# Copia adaptada de plugins/sdd/scripts/sdd_bash.py (invokes_approve y sus
# ayudantes): los plugins no comparten codigo. Un arreglo en una copia se
# replica en la otra, y los dos selftests usan listas de casos equivalentes.
# --------------------------------------------------------------------------

_WRAPPERS = {"sudo", "env", "command", "nohup", "time", "nice", "builtin", "exec"}
_SEPARATORS = {";", "&&", "||", "|", "|&", "&", "(", ")", ";;"}
_REDIRECTS = {">", ">>", ">|", "&>", "&>>", "<", "<<", "<<<", "<<-", "<>", ">&", "<&"}
_HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)",
    re.S,
)


def _strip_heredocs(command):
    """Quita el cuerpo de los heredocs: es texto, no comandos."""
    return _HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], command)


def _command_segments(command):
    """Palabras de cada comando simple, sin redirecciones ni su destino."""
    import shlex
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)  # ValueError si las comillas no cierran
    segments, seg, i = [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _SEPARATORS:
            segments.append(seg)
            seg = []
        elif tok in _REDIRECTS:
            i += 1  # el siguiente token es el destino o la entrada
        else:
            seg.append(tok)
        i += 1
    segments.append(seg)
    return segments


def _command_words(seg):
    """Quita asignaciones VAR=x y envoltorios como sudo o env."""
    words = list(seg)
    while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])
                     or os.path.basename(words[0]) in _WRAPPERS):
        words.pop(0)
    return words


def _substitutions(command):
    """
    Contenido de las sustituciones `…` y $(…) que bash ejecutaria. Se recorre
    respetando las comillas: dentro de comillas simples no hay sustitucion, y
    una \\$( o \\` escapada tampoco lo es. Dentro de comillas dobles si.
    """
    found, i, n, single = [], 0, len(command), False
    while i < n:
        ch = command[i]
        if single:
            if ch == "'":
                single = False
            i += 1
            continue
        if ch == "\\":
            i += 2
            continue
        if ch == "'":
            if command.count('"', 0, i) % 2 == 0:
                single = True
            i += 1
            continue
        if ch == "`":
            j = i + 1
            while j < n and command[j] != "`":
                j += 2 if command[j] == "\\" else 1
            if j >= n:
                break
            found.append(command[i + 1:j])
            i = j + 1
            continue
        if command.startswith("$(", i) and not command.startswith("$((", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if command[j] == "\\":
                    j += 2
                    continue
                if command[j] == "(":
                    depth += 1
                elif command[j] == ")":
                    depth -= 1
                j += 1
            if depth:
                break
            found.append(command[i + 2:j - 1])
            i = j
            continue
        i += 1
    return found


def invokes_approve(command):
    """
    True si el comando **ejecuta** la orden de aprobar: en algun segmento, una
    palabra cuyo nombre de archivo es discovery.py seguida de approve, tambien
    dentro de una sustitucion que se ejecuta. Una mencion (un mensaje de
    commit, la descripcion de un PR, un heredoc) no cuenta. Lo que no se puede
    analizar se evalua por su texto; lo que esta compuerta no ve (un script,
    bash -c) lo revierte la auditoria de PostToolUse.
    """
    command = _strip_heredocs(command or "")
    if any(invokes_approve(inner) for inner in _substitutions(command)):
        return True
    try:
        segments = _command_segments(command)
    except ValueError:
        return bool(APPROVE_TEXT.search(command))
    for seg in segments:
        words = _command_words(seg)
        for word, nxt in zip(words, words[1:]):
            if os.path.basename(word) == "discovery.py" and nxt == "approve":
                return True
    return False


def claims_approval(text):
    """True si el Estado empieza por Approved, tenga huella o no."""
    words = norm(doc_status(text) or "").strip("`*_ ").split()
    return bool(words) and words[0].strip("`*_") in APPROVED


def deny(reason):
    """Bloquea. El JSON solo se procesa con exit 0: nunca combinar con exit 2."""
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}, sys.stdout)
    sys.stdout.write("\n")
    return 0


def _approvable_target(root, raw_path):
    """Nombre del artefacto aprobable al que apunta raw_path, o None."""
    try:
        target = Path(raw_path)
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
        base = product_root(root).resolve()
        rel = target.relative_to(base)
    except (OSError, ValueError):
        return None, None
    # Comparacion sin mayusculas: en macOS y Windows `product/BACKLOG.md` es el
    # mismo archivo que `product/backlog.md`, y resolve() no lo normaliza.
    for name in APPROVABLE:
        if rel.as_posix().casefold() == name.casefold():
            return name, base / name
    return None, None


SNAPSHOT_TTL = 24 * 3600


def _snapshot_path(root, payload):
    key = payload.get("tool_use_id") or payload.get("session_id") or "nosession"
    digest = hashlib.sha1(f"{root}|{key}".encode("utf-8")).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / "discovery-audit" / f"{digest}.json"


def _prune(directory):
    """Si un comando falla o se rechaza, PostToolUse no llega y la instantanea
    queda huerfana. Se barren las de mas de un dia."""
    import time
    limit = time.time() - SNAPSHOT_TTL
    try:
        for old in directory.glob("*.json"):
            if old.stat().st_mtime < limit:
                old.unlink()
    except OSError:
        pass


def _statuses(root):
    return {n: doc_status(read_product(root, n) or "") for n in APPROVABLE
            if read_product(root, n) is not None}


APPROVAL_REASON = (
    "Guardrail discovery: la aprobación del producto es del usuario, no tuya. Es la "
    "prueba de que una persona revisó el brief y el backlog.\n\nNo cambies el campo "
    "Estado ni ejecutes `discovery.py approve`: pídele al usuario que lo revise y "
    "ejecute /discovery:approve.\n\nEscape puntual: DISCOVERY_BYPASS=1."
)


def cmd_guard(_args):
    """Hook PreToolUse sobre Write|Edit|Bash. Nunca devuelve allow."""
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    root = project_root(payload)
    if os.environ.get("DISCOVERY_BYPASS") == "1" or not product_root(root).is_dir():
        return 0
    tool_input = payload.get("tool_input") or {}

    if payload.get("tool_name") == "Bash":
        if invokes_approve(tool_input.get("command") or ""):
            return deny(APPROVAL_REASON)
        # Lo que un comando opaco cambie lo revisa la auditoria de PostToolUse.
        path = _snapshot_path(root, payload)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_statuses(root)), encoding="utf-8")
        except OSError:
            return 0
        _prune(path.parent)
        return 0

    name, target = _approvable_target(root, tool_input.get("file_path") or "")
    if not name:
        return 0
    before = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    if "content" in tool_input:
        after = tool_input.get("content") or ""
    elif "new_string" in tool_input:
        old = tool_input.get("old_string") or ""
        if not old or old not in before:
            return 0
        count = -1 if tool_input.get("replace_all") else 1
        after = before.replace(old, tool_input.get("new_string") or "", count)
    else:
        return 0
    if claims_approval(after) and doc_status(after) != doc_status(before):
        return deny(APPROVAL_REASON)
    return 0


def cmd_audit(_args):
    """
    Hook PostToolUse sobre Bash: si un comando cambio el Estado de brief o
    backlog hacia una aprobacion, lo devuelve a su valor anterior. Exit 2 para
    que el modelo lea el aviso; PostToolUse no puede deshacer el comando.
    """
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    root = project_root(payload)
    path = _snapshot_path(root, payload)
    try:
        before = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except (OSError, ValueError):
        return 0
    if os.environ.get("DISCOVERY_BYPASS") == "1":
        return 0
    restored = []
    # Se recorren los dos artefactos, no solo los que existian antes: un
    # archivo borrado y recreado ya aprobado tambien vuelve a Draft.
    for name in APPROVABLE:
        old = before.get(name)
        text = read_product(root, name)
        if text is not None and claims_approval(text) and doc_status(text) != old:
            write_product(root, name, set_status(text, old or "Draft")[0])
            restored.append(f"{name} (vuelve a '{old or 'Draft'}')")
    if not restored:
        return 0
    sys.stderr.write("Guardrail discovery: el comando cambió el Estado de "
                     + ", ".join(restored) + ". La aprobación es del usuario, con "
                     "/discovery:approve.\n")
    return 2


# --------------------------------------------------------------------------

COMMANDS = {
    "ingest": cmd_ingest,
    "next-id": cmd_next_id,
    "questions": cmd_questions,
    "check": cmd_check,
    "approve": cmd_approve,
    "guard": cmd_guard,
    "audit": cmd_audit,
}

# Un hook que revienta nunca debe bloquear al usuario: falla abierto.
HOOKS = {"guard", "audit"}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[1]](argv[2:])
    except Exception as exc:  # noqa: BLE001
        if argv[1] in HOOKS:
            print(f"discovery.py {argv[1]}: {exc}", file=sys.stderr)
            return 0
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv))
