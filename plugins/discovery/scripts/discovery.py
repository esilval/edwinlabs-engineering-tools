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
ITALIC_EDGE = re.compile(r"(?:^|[\s|*(>\[])_(?=[^\s_])|(?<=[^\s_])_(?=$|[\s|.,;:)*\]])")
INLINE_PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9])_[^_\n]*(?:\.\.\.|\\<)[^_\n]*_(?![A-Za-z0-9])")
REQUIREMENT_WORDS = re.compile(r"\b(?:debera|deberan|shall)\b")


def template_lines(name):
    """Lineas de la plantilla que son huecos por rellenar (texto en cursiva)."""
    path = TEMPLATES_DIR / name
    if not path.is_file():
        return set()
    return {_squash(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and ITALIC_EDGE.search(line.strip())}


def find_placeholders(text, template_name):
    known = template_lines(template_name)
    return [(i, raw.strip()) for i, raw in enumerate((text or "").splitlines(), 1)
            if raw.strip() and (_squash(raw) in known or INLINE_PLACEHOLDER.search(raw))]


def _related(a, b):
    """True si la seccion a es b, la contiene o esta contenida en ella."""
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def _cycles(graph):
    state, found = {}, []

    def visit(node, path):
        if state.get(node) == "done":
            return
        if state.get(node) == "open":
            found.append(path[path.index(node):] + [node])
            return
        state[node] = "open"
        for nxt in graph.get(node, []):
            visit(nxt, path + [nxt])
        state[node] = "done"

    for node in sorted(graph):
        visit(node, [node])
    return found


def _id_gaps(ids, label):
    """Mensajes por huecos o repetidos en una serie de IDs ('G', 'B', 'D')."""
    nums = [int(i[1:]) for i in ids]
    out = []
    repeated = sorted({n for n in nums if nums.count(n) > 1})
    if repeated:
        out.append(f"{label} repetidos: " + ", ".join(f"{ids[0][0]}{n}" for n in repeated))
    missing = sorted(set(range(1, max(nums, default=0) + 1)) - set(nums))
    if missing:
        width = 2 if ids and ids[0].startswith("B") else 1
        out.append(f"faltan {label}: " + ", ".join(f"{ids[0][0]}{n:0{width}d}" for n in missing)
                   + ". Un elemento se descarta, no se borra.")
    return out


def analyze(root):
    product = load_product(root)
    docs, brief, backlog = product["documents"], product["brief"], product["backlog"]
    findings = []

    def add(code, message, **extra):
        findings.append({"code": code, "severity": "error" if code.startswith("E-") else "warning",
                         "title": FINDINGS.get(code, code), "message": message, **extra})

    goals = brief["goals"]
    candidates = backlog["candidates"]
    live = [c for c in candidates if c["state"] != "descartada"]

    # E-SOURCE-MODIFIED
    for did, d in docs.items():
        stored = d["fields"].get("Huella")
        if stored and stored != text_digest(source_content(d["text"])):
            add("E-SOURCE-MODIFIED", f"{did} se editó después de ingerirlo. Los documentos no se "
                "editan: restaura el archivo y trae el cambio como documento nuevo.", document=did)

    # E-REF-UNKNOWN: origen de objetivos y candidatas, objetivos, dependencias, preguntas
    def check_refs(where, text):
        for broken in broken_refs(product, refs(text)):
            add("E-REF-UNKNOWN", f"{where} cita {broken}.")

    for g in goals:
        check_refs(f"{g['id']} (Origen)", g["fields"].get("origen", ""))
    for c in candidates:
        for field in ("objetivos", "origen", "depende de"):
            check_refs(f"{c['id']} ({field.capitalize()})", c["fields"].get(field, ""))
    for q in brief["questions"]:
        check_refs(f"La pregunta «{q['text'][:60]}»", q["text"])
    check_refs("Secciones descartadas", " ".join(brief["discarded"]))

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
    for ids, label in ((list(docs), "documentos"), ([g["id"] for g in goals], "objetivos"),
                       ([c["id"] for c in candidates], "candidatas")):
        for message in _id_gaps(ids, label):
            add("E-BACKLOG-ID-GAP", message[0].upper() + message[1:])

    # E-BACKLOG-REQUIREMENT
    for item in goals + candidates:
        body = norm(item["title"] + " " + " ".join(item["fields"].values()))
        if REQUIREMENT_WORDS.search(body):
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
    ok, lines = approve(project_root())
    stream = sys.stdout if (ok or "--skill" in args) else sys.stderr
    print("\n".join(lines), file=stream)
    if ok:
        print("Siguiente: el handoff de candidatas a sdd (feature aparte) o seguir "
              "ingiriendo documentos.")
    return 0 if (ok or "--skill" in args) else 1


# --------------------------------------------------------------------------

COMMANDS = {
    "ingest": cmd_ingest,
    "next-id": cmd_next_id,
    "questions": cmd_questions,
    "check": cmd_check,
    "approve": cmd_approve,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
