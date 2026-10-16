#!/usr/bin/env python3
"""
architecture.py - utilidades deterministas del plugin architecture.

Todo lo que no requiere criterio vive aqui: identificadores, comprobacion de
coherencia, huellas, aprobacion, revision de decisiones y guardrails. Las
skills solo redactan y preguntan.

El plugin lee product/ (lo deja discovery) y solo escribe en architecture/.
No importa codigo de otros plugins: es una etapa independiente, unida a las
demas por archivos.

Subcomandos:
  init                Crea architecture/ desde las plantillas, si el producto
                      de discovery esta aprobado.
  next-id Q|C|S|ADR   Siguiente atributo (Q3), componente (C2), estandar (S4)
                      o decision (ADR-0005) libre. Nunca se recicla.
  check [--json] [--check]
                      Coherencia de la arquitectura. --json emite
                      architecture.check/v1; --check sale con 1 si hay
                      errores (para CI).
  approve [--skill]   Aprueba el conjunto si check no da errores. Solo lo
                      lanza el usuario, con /architecture:approve.
  review ADR-NNNN aceptar|rechazar [--skill]
                      Decide una decision propuesta. Solo lo lanza el
                      usuario, con /architecture:review.
  guard               Hook PreToolUse: impide que el modelo apruebe.
  audit               Hook PostToolUse sobre Bash: revierte una aprobacion
                      escrita por un comando.
"""

import sys

COMMANDS = {}

# Un hook que revienta nunca debe bloquear al usuario: falla abierto.
HOOKS = {"guard", "audit"}

# Codigos de hallazgo declarados: el selftest exige probar cada uno.
FINDINGS = {}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[1]](argv[2:])
    except Exception as exc:  # noqa: BLE001
        if argv[1] in HOOKS:
            print(f"architecture.py {argv[1]}: {exc}", file=sys.stderr)
            return 0
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv))
