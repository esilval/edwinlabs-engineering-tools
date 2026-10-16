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
