#!/usr/bin/env python3
"""
sdd_bash.py - la compuerta SDD aplicada a la herramienta Bash.

Write y Edit declaran el archivo que tocan; Bash no. Para que `sed -i` o
`cat > src/app.py` no sean una puerta trasera, hay dos capas:

  1. Prevencion (PreToolUse): un analizador conservador extrae del comando
     los archivos que va a escribir -redirecciones, tee, sed -i, perl -i,
     cp, mv, install, ln, rm, touch, truncate, dd of=- y se evaluan contra
     la compuerta igual que un Write.
  2. Deteccion (PostToolUse): lo que el analizador no puede ver (python -c,
     un script, una sustitucion de comando) se detecta comparando
     `git status` antes y despues. PostToolUse no puede deshacer, asi que
     informa al modelo; la aprobacion autoconcedida, en cambio, si se revierte,
     porque devolver un campo a su valor anterior no destruye trabajo.

El analizador no pretende ser un parser de shell completo. Lo que no entiende
lo deja pasar y lo recoge la capa 2.

invokes_approve y sus ayudantes tienen una copia adaptada en
plugins/discovery/scripts/discovery.py: los plugins no comparten codigo. Un
arreglo en una copia se replica en la otra.
"""

import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

# Comandos que preceden a otro sin cambiar lo que hace.
WRAPPERS = {"sudo", "env", "command", "nohup", "time", "nice", "builtin", "exec"}

SEPARATORS = {";", "&&", "||", "|", "|&", "&", "(", ")", ";;"}
OUTPUT_REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
INPUT_REDIRECTS = {"<", "<<", "<<<", "<<-", "<>"}

IGNORED_TARGETS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "-"}

HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)",
    re.S,
)

APPROVAL_WORD = re.compile(r"approved|aprobad[oa]", re.I)
# Solo para comandos que no se pueden analizar por palabras.
APPROVE_TEXT = re.compile(r"sdd\.py['\"]?\s+approve\b")


# --------------------------------------------------------------------------
# Analisis estatico del comando
# --------------------------------------------------------------------------

def _strip_heredocs(command):
    """Quita el cuerpo de los heredocs: es texto, no comandos."""
    return HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], command)


def _tokens(command):
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True,
                      punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def _segments(tokens):
    """Parte la lista de tokens en comandos simples, separando redirecciones."""
    seg, redirects, out = [], [], []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in SEPARATORS:
            out.append((seg, redirects))
            seg, redirects = [], []
        elif tok in OUTPUT_REDIRECTS:
            if i + 1 < len(tokens):
                redirects.append(tokens[i + 1])
            i += 1
        elif tok in INPUT_REDIRECTS or tok in (">&", "<&"):
            i += 1  # el siguiente token es una entrada o un descriptor
        else:
            seg.append(tok)
        i += 1
    out.append((seg, redirects))
    return out


def _command_words(seg):
    """Quita asignaciones VAR=x y envoltorios como sudo o env."""
    words = list(seg)
    while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])
                     or os.path.basename(words[0]) in WRAPPERS):
        words.pop(0)
    return words


def _positionals(args, takes_value=()):
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in takes_value:
            skip = True
            continue
        if (a.startswith("-") and a != "-") or not a:
            continue  # opcion, o el sufijo vacio de `sed -i ""` en macOS
        out.append(a)
    return out


def _targets_of(words):
    if not words:
        return []
    name, args = os.path.basename(words[0]), words[1:]

    if name == "tee":
        return _positionals(args)

    if name == "sed" and any(a.startswith("-i") or a.startswith("--in-place")
                             or re.match(r"^-[a-zA-Z]*i", a) for a in args):
        explicit = any(a in ("-e", "-f", "--expression", "--file")
                       or a.startswith("--expression=") for a in args)
        pos = _positionals(args, takes_value=("-e", "-f", "--expression", "--file"))
        return pos if explicit else pos[1:]

    if name == "perl" and any(re.match(r"^-[a-zA-Z]*i", a) for a in args):
        return _positionals(args, takes_value=("-e", "-E", "-M", "-I"))

    if name in ("cp", "mv", "install", "ln"):
        pos = _positionals(args, takes_value=("-t", "--target-directory", "-m", "-o", "-g"))
        return pos[-1:] if len(pos) >= 2 else []

    if name in ("rm", "touch", "truncate", "unlink", "shred"):
        return _positionals(args, takes_value=("-s", "--size", "-r", "-d"))

    if name == "dd":
        return [a[3:] for a in args if a.startswith("of=")]

    return []


def write_targets(command):
    """
    Rutas que el comando va a escribir o borrar, tal como aparecen en el
    comando. Las que dependen de variables o sustituciones se omiten: no se
    pueden resolver de forma estatica, y para eso existe la auditoria.
    """
    try:
        tokens = _tokens(_strip_heredocs(command or ""))
    except ValueError:
        return []  # comillas sin cerrar: lo recoge la auditoria
    found = []
    for seg, redirects in _segments(tokens):
        for target in redirects + _targets_of(_command_words(seg)):
            if (not target or target in IGNORED_TARGETS or "$" in target
                    or "`" in target or target.startswith("&")):
                continue
            if target not in found:
                found.append(target)
    return found


def invokes_approve(command):
    """
    True si el comando **ejecuta** `sdd.py approve`: en algun segmento, una
    palabra cuyo nombre de archivo es sdd.py seguida de la palabra approve.

    Una mencion no cuenta: un mensaje de commit, la descripcion de un PR o el
    cuerpo de un heredoc son una sola palabra entre comillas, o se descartan
    antes de analizar. Lo que esta compuerta no puede ver (un script, un
    `bash -c` o un interprete con el codigo en linea) lo revierte la auditoria
    de PostToolUse. Un comando que no se puede analizar se deniega solo si su
    texto contiene la orden.
    """
    command = _strip_heredocs(command or "")
    # Lo que va dentro de $(…) o de `…` se ejecuta, aunque este entre comillas
    # dobles: se analiza como un comando aparte.
    if any(invokes_approve(inner) for inner in _substitutions(command)):
        return True
    try:
        tokens = _tokens(command)
    except ValueError:
        # Algo que el analizador no entiende y bash si ($'…', comillas raras):
        # se busca la orden en el texto, como la compuerta anterior. Si no, un
        # trozo ilegible bastaria para colar una aprobacion.
        return bool(APPROVE_TEXT.search(command))
    for seg, _redirects in _segments(tokens):
        words = _command_words(seg)
        for word, nxt in zip(words, words[1:]):
            if os.path.basename(word) == "sdd.py" and nxt == "approve":
                return True
    return False


def _substitutions(command):
    """
    Contenido de las sustituciones de comandos `…` y $(…) que bash ejecutaria.
    Se recorre el comando respetando las comillas: dentro de comillas simples
    no hay sustitucion (es la forma habitual de citar una orden en un mensaje),
    y una \\$( o \\` escapada tampoco lo es. Dentro de comillas dobles si.
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
            # Una comilla simple dentro de comillas dobles es un caracter mas;
            # basta con no tratarla: el analisis por palabras va despues.
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


def mentions_approval(command):
    return bool(APPROVAL_WORD.search(command or ""))


# --------------------------------------------------------------------------
# Auditoria: instantanea antes, comparacion despues
# --------------------------------------------------------------------------

def _snapshot_path(root, payload):
    key = (payload.get("tool_use_id") or payload.get("session_id") or "nosession")
    digest = hashlib.sha1(f"{root}|{key}".encode("utf-8")).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / "sdd-audit" / f"{digest}.json"


def dirty_files(root):
    """
    {ruta_relativa: firma} de los archivos que git ve cambiados o nuevos.
    None si no hay git: sin git no hay auditoria, y no se inventa una.
    """
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "-z",
             "--untracked-files=all"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    out, entries = {}, res.stdout.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        status, rel = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # el origen del rename viene en la siguiente entrada
        path = root / rel
        try:
            st = path.stat()
            out[rel] = [st.st_mtime_ns, st.st_size]
        except OSError:
            out[rel] = None  # borrado
    return out


SNAPSHOT_TTL = 24 * 3600


def _prune(directory):
    """Si el usuario rechaza un comando, PostToolUse no llega y la instantanea
    queda huerfana. Se barren las de mas de un dia."""
    import time
    limit = time.time() - SNAPSHOT_TTL
    try:
        for old in directory.glob("*.json"):
            if old.stat().st_mtime < limit:
                old.unlink()
    except OSError:
        pass


def save_snapshot(root, payload, data):
    path = _snapshot_path(root, payload)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        return
    _prune(path.parent)


def pop_snapshot(root, payload):
    path = _snapshot_path(root, payload)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        path.unlink()
    except OSError:
        pass
    return data


def changed_since(before, after):
    """Rutas cuya firma cambio, o que aparecieron, entre dos instantaneas."""
    return sorted(rel for rel, sig in after.items() if before.get(rel, "nuevo") != sig)
