#!/bin/sh
# Diagnóstico del plugin: comprueba el intérprete y cede a doctor.py para los
# scripts y los hooks.
#
#   sh doctor.sh            diagnóstico completo; sale con 0 si el plugin está
#                           listo, 1 si no y 2 si el uso es incorrecto
#   sh doctor.sh --skill    lo mismo, pero sale siempre con 0 (lo usa la skill)
#   sh doctor.sh session    hook SessionStart: calla si el intérprete está bien;
#                           si no, avisa una vez por sesión. Sale siempre con 0
#
# Está en shell, no en Python, porque su trabajo es avisar cuando Python falta o
# no sirve. Solo usa utilidades POSIX: nada de bashismos (en Linux, sh es dash).
#
# Copia idéntica en los cinco plugins de la serie: plugins/sdd/scripts/doctor.sh
# (el original), plugins/discovery/scripts/doctor.sh,
# plugins/architecture/scripts/doctor.sh, plugins/release/scripts/doctor.sh y
# plugins/operate/scripts/doctor.sh. Los plugins no comparten código: un cambio
# en una se replica en las otras, y el selftest de cada plugin lo comprueba.

# Versión mínima de la constitución.
MIN_MAJOR=3
MIN_MINOR=8

# Solo para las pruebas: sustituye al intérprete. Los hooks usan siempre python3.
PY=${DOCTOR_PYTHON:-python3}

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$HERE")

plugin_name() {
    name=$(sed -n 's/^[[:space:]]*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
        "$ROOT/.claude-plugin/plugin.json" 2>/dev/null | head -n 1)
    if [ -n "$name" ]; then printf '%s' "$name"; else printf 'doctor'; fi
}

# Deja en STATE uno de: falta, no-ejecuta, antigua, bien. Rellena PYPATH,
# VERSION y, si no se ejecuta, DETAIL. La versión se pide con una sintaxis que
# vale incluso en Python 2 y se compara aquí, sin fiarse del intérprete.
check_interpreter() {
    PYPATH=$(command -v "$PY" 2>/dev/null)
    VERSION=""
    DETAIL=""
    if [ -z "$PYPATH" ]; then
        STATE=falta
        return
    fi
    out=$("$PY" -c 'import sys; print("%d.%d.%d" % tuple(sys.version_info[:3]))' 2>&1)
    rc=$?
    VERSION=$(printf '%s\n' "$out" \
        | sed -n '/^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$/p' | head -n 1)
    if [ "$rc" -ne 0 ] || [ -z "$VERSION" ]; then
        STATE=no-ejecuta
        DETAIL=$(printf '%s\n' "$out" | sed -n '1p')
        return
    fi
    major=${VERSION%%.*}
    rest=${VERSION#*.}
    minor=${rest%%.*}
    if [ "$major" -gt "$MIN_MAJOR" ] \
        || { [ "$major" -eq "$MIN_MAJOR" ] && [ "$minor" -ge "$MIN_MINOR" ]; }; then
        STATE=bien
    else
        STATE=antigua
    fi
}

# Cómo instalarlo, según el sistema.
fix_hint() {
    case "$(uname -s 2>/dev/null)" in
        Darwin)
            printf '%s' "Instala Python con Homebrew (brew install python@3.12)" \
                " o desde python.org." ;;
        Linux)
            printf '%s' "Instala Python con el gestor de paquetes de tu distribución" \
                " (por ejemplo, sudo apt install python3)." ;;
        MINGW*|MSYS*|CYGWIN*)
            printf '%s' "Instala Python desde python.org y comprueba que python3 está" \
                " en el PATH de Git Bash; si lo intercepta el alias de la Microsoft" \
                " Store, desactívalo." ;;
        *)
            printf '%s' "Instala Python $MIN_MAJOR.$MIN_MINOR o posterior" \
                " desde python.org." ;;
    esac
}

# Una frase con el problema del intérprete.
problem() {
    case "$STATE" in
        falta) printf '%s' "falta $PY: no se encuentra en el PATH." ;;
        no-ejecuta) printf '%s' "$PY ($PYPATH) no se ejecuta." ;;
        antigua)
            printf '%s' "Python $VERSION es anterior a $MIN_MAJOR.$MIN_MINOR," \
                " la versión mínima." ;;
    esac
}

run_full() {
    plugin=$(plugin_name)
    echo "Diagnóstico de $plugin"
    check_interpreter
    if [ "$STATE" != bien ]; then
        echo "[falla] intérprete: $(problem)"
        if [ -n "$DETAIL" ]; then
            echo "    $DETAIL"
        fi
        echo "    Sin un Python válido no funcionan las comprobaciones ni" \
            "los guardrails de $plugin: los guardrails dejan pasar todo."
        if [ -f "$HERE/sdd.py" ]; then
            echo "    Tampoco funciona la compuerta: deja escribir código sin" \
                "especificación aprobada."
        fi
        echo "    Cómo resolverlo: $(fix_hint) Después, reinicia la sesión y repite" \
            "/$plugin:doctor."
        echo "[--] scripts: sin comprobar, necesitan el intérprete."
        echo "[--] hooks: sin comprobar, necesitan el intérprete."
        echo "Resumen: $plugin no está listo: intérprete."
        return 1
    fi
    echo "[ok] intérprete: Python $VERSION ($PYPATH)"
    out=$("$PY" "$HERE/doctor.py" "$plugin" 2>&1)
    rc=$?
    if printf '%s\n' "$out" | grep -q '^Resumen: '; then
        printf '%s\n' "$out"
        return "$rc"
    fi
    # doctor.py no llegó a su resumen: no arranca o reventó.
    echo "[falla] scripts: doctor.py no terminó el diagnóstico."
    printf '%s\n' "$out" | sed 's/^/    /'
    echo "Resumen: $plugin no está listo: scripts."
    return 1
}

# Hook SessionStart. Solo comprueba el intérprete: tiene que ser rápido. El
# primero de los plugins instalados que avisa crea una marca por sesión
# (mkdir es atómico) y los demás callan. Sin session_id, o si la marca no se
# puede crear, avisa igual: mejor repetido que callado.
run_session() {
    # Lanzado a mano desde una terminal, no espera una entrada que no llegará.
    payload=""
    if [ ! -t 0 ]; then
        payload=$(cat 2>/dev/null)
    fi
    check_interpreter
    if [ "$STATE" = bien ]; then
        return 0
    fi
    plugin=$(plugin_name)
    id=$(printf '%s\n' "$payload" \
        | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
        | head -n 1 | tr -cd 'A-Za-z0-9_-')
    if [ -n "$id" ]; then
        mark="${TMPDIR:-/tmp}/edwinlabs-doctor.$id"
        if ! mkdir "$mark" 2>/dev/null && [ -d "$mark" ]; then
            return 0
        fi
    fi
    # Sin comillas ni barras invertidas, el texto va al JSON tal cual.
    what=$(problem | tr -d '"\\')
    msg="Python no sirve: $what Los guardrails de los plugins de"
    msg="$msg edwinlabs-engineering-tools no protegen."
    msg="$msg Ejecuta /$plugin:doctor para el detalle."
    ctx="$msg Los hooks de esos plugins fallan abiertos: no impiden que el modelo"
    ctx="$ctx apruebe artefactos y, si está instalado sdd, su compuerta no bloquea."
    ctx="$ctx Díselo al usuario."
    printf '{"systemMessage": "%s", "hookSpecificOutput": {"hookEventName":'\
' "SessionStart", "additionalContext": "%s"}}\n' "$msg" "$ctx"
}

# El modo session sale siempre con 0, aunque reciba argumentos de más.
if [ "$#" -gt 1 ] && [ "$1" != session ]; then
    set -- --uso-incorrecto
fi

case "$1" in
    "")
        run_full
        exit $?
        ;;
    --skill)
        run_full
        exit 0
        ;;
    session)
        run_session 2>/dev/null
        exit 0
        ;;
    *)
        echo "Uso: sh doctor.sh [--skill | session]" >&2
        exit 2
        ;;
esac
