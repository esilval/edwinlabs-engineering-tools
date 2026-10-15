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
    print(f"  {'ok  ' if ok else 'FALLA'} {nombre}" + (f" :: {detalle}" if detalle and not ok else ""))
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
    for malo in ("../fuera.md", "../specs/spec.md", "/tmp/absoluta.md", "sources/../../x.md"):
        try:
            discovery.write_product(root, malo, "x\n")
            escapo = True
        except discovery.OutsideProduct:
            escapo = False
        expect(not escapo, f"rechaza escribir en {malo}")
    expect(not (root / "fuera.md").exists() and not (root / "specs").exists(),
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
    sellado, ok = discovery.set_status(texto, f"Approved · {discovery.content_digest(texto)}")
    assert ok
    return sellado


def test_F001_R016_huella_ignora_formato():
    a = "# T\n\nUna  linea\n\n\n| a |  b |\n"
    b = "# T\nUna linea\n|a|b|\n"
    expect(discovery.text_digest(a) == discovery.text_digest(b),
           "espacios, lineas en blanco y relleno de tablas no cambian la huella")
    sellado = _aprobar(BACKLOG_APROBADO)
    expect(discovery.is_approved(sellado) and not discovery.is_stale(sellado),
           "recien aprobado: aprobado y no cambiado")
    reformateado = sellado.replace("\n\n### B01", "\n\n\n### B01").replace("el usuario", "el  usuario")
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


def test_F001_R002_huella_de_texto_igual_con_otro_formato():
    # F001-R002: la deteccion de duplicados compara esta huella
    expect(discovery.text_digest("# Vision\n\nTexto.\n") == discovery.text_digest("# Vision\nTexto.\n"),
           "el mismo contenido con otro formato tiene la misma huella")
    expect(discovery.text_digest("# Vision\nTexto.\n") != discovery.text_digest("# Vision\nOtro.\n"),
           "contenido distinto, huella distinta")


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
