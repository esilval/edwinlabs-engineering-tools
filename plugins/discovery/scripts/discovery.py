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
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
NUMBERED = re.compile(r"^#{1,6}\s+(\d+(?:\.\d+)*)\s")
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

    Un unico encabezado del nivel mas alto, si es el primero, es el titulo del
    documento: no es seccion y no se numera. El resto se numera por niveles
    (1, 1.1, 1.1.1). Sin encabezados, el documento entero es la seccion 1.
    """
    lines = text.splitlines()
    heads = [(i, len(HEADING.match(lines[i]).group(1)), HEADING.match(lines[i]).group(2))
             for i in _outside_fences(lines) if HEADING.match(lines[i])]
    if not heads:
        return text, None, ["1"]

    title = None
    top = min(level for _i, level, _t in heads)
    if sum(1 for _i, level, _t in heads if level == top) == 1 and heads[0][1] == top:
        title = heads[0][2]
        heads = heads[1:]
    if not heads:
        return text, title, ["1"]

    levels = sorted({level for _i, level, _t in heads})
    counters, numbers = [], []
    for i, level, words in heads:
        depth = levels.index(level) + 1
        counters = counters[:depth] + [0] * (depth - len(counters))
        counters[depth - 1] += 1
        counters = counters[:depth]
        number = ".".join(str(n) for n in counters)
        numbers.append(number)
        lines[i] = f"{'#' * level} {number} {words}"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), title, numbers


def sections(text):
    """Numeros de seccion de un documento ingerido ('1', '4.2'…)."""
    content = source_content(text)
    lines = content.splitlines()
    found = [NUMBERED.match(lines[i]).group(1) for i in _outside_fences(lines)
             if NUMBERED.match(lines[i])]
    return found or ["1"]


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
            raise Rejected(f"El documento es idéntico a D{num} ({fields.get('Original', path.name)}); "
                           "no se ingiere de nuevo.")

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
        f"| Huella | {text_digest(body)} |\n\n"
        "> Documento ingerido por discovery. No se edita: un cambio entra como\n"
        "> documento nuevo. Las secciones se citan como "
        f"{did}§<número>.\n\n"
        f"{CONTENT_MARK}\n"
    )
    rel = f"{SOURCES_DIR}/{did}-{slugify(Path(original_name).stem)}.md"
    write_product(root, rel, header + body)
    return {"document": did, "path": f"{PRODUCT_DIR}/{rel}", "title": title,
            "sections": len(numbers)}


def cmd_ingest(args):
    original = None
    if "--original" in args:
        i = args.index("--original")
        if i + 1 >= len(args):
            print("error: --original necesita un archivo", file=sys.stderr)
            return 1
        original = args[i + 1]
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
        if ext not in TEXT_FORMATS:
            raise Rejected(f"{source.name} todavía no se puede ingerir directamente.")
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

COMMANDS = {
    "ingest": cmd_ingest,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
