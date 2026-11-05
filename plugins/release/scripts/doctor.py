#!/usr/bin/env python3
"""
Diagnóstico del plugin: los scripts arrancan y los hooks responden. Lo lanza
doctor.sh solo cuando el intérprete es válido:

    python3 doctor.py <plugin>

Escribe una línea por comprobación y un resumen, y sale con 0 si el plugin está
listo y con 1 si no. No toca el proyecto: los scripts se cargan y los hooks se
lanzan contra un proyecto temporal que se borra al terminar.

Copia en los cinco plugins de la serie: plugins/sdd/scripts/doctor.py (el
original), plugins/discovery/scripts/doctor.py,
plugins/architecture/scripts/doctor.py, plugins/release/scripts/doctor.py y
plugins/operate/scripts/doctor.py. Solo cambia el bloque CASE; lo que hay bajo
la línea «común a las cinco copias» es idéntico, y el selftest de cada plugin
lo comprueba. Los plugins no comparten código: un cambio en una copia se
replica en las otras.
"""

# Peticiones de prueba de este plugin: los directorios que el guardrail necesita
# para actuar y una escritura que lo aprueba, que tiene que denegar.
CASE = {
    "dirs": ["releases"],
    "approval": {
        "file_path": "releases/v0.0.1.md",
        "content": "# Prueba del diagnóstico\n\n"
                   "| Campo  | Valor    |\n| ------ | -------- |\n| Estado | Approved |\n",
    },
}

# --- común a las cinco copias ---

import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# Exento de la compuerta de sdd (*.md) y fuera de lo que protegen los demás.
INNOCUOUS = "notas.md"
GUARDRAILS = ("guard", "audit")
SESSION = "doctor"

# Carga un script por ruta sin ejecutar su main, que va tras __name__.
LOADER = (
    "import importlib.util, sys\n"
    "sys.path.insert(0, sys.argv[2])\n"
    "name = sys.argv[3]\n"
    "spec = importlib.util.spec_from_file_location(name, sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "sys.modules[name] = module\n"
    "spec.loader.exec_module(module)\n"
)


def child_env(project):
    """Entorno del hijo: el proyecto temporal y ningún escape de guardrail."""
    env = {k: v for k, v in os.environ.items() if not k.endswith("_BYPASS")}
    env.update(CLAUDE_PROJECT_DIR=str(project), CLAUDE_PLUGIN_ROOT=str(ROOT),
               PYTHONDONTWRITEBYTECODE="1")
    return env


def last_error(text):
    """La última línea con texto: en una traza, la del tipo de excepción."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else "sin mensaje de error"


def check_scripts(project):
    """(nombre, ok, detalle) por cada script de scripts/ salvo este."""
    out = []
    for script in sorted(HERE.glob("*.py")):
        if script.name == Path(__file__).name:
            continue
        try:
            r = subprocess.run(
                [sys.executable, "-c", LOADER, str(script), str(HERE), script.stem],
                capture_output=True, text=True, cwd=str(project), env=child_env(project),
                timeout=30)
        except subprocess.TimeoutExpired:
            out.append((f"script {script.name}", False, "no terminó de cargar en 30 s"))
            continue
        if r.returncode == 0:
            out.append((f"script {script.name}", True, "arranca"))
        else:
            out.append((f"script {script.name}", False,
                        f"no arranca: {last_error(r.stderr)}"))
    return out


def payload(event, project, tool=None, **tool_input):
    data = {"session_id": SESSION, "hook_event_name": event, "cwd": str(project)}
    if tool:
        data.update(tool_name=tool, tool_input=tool_input)
        if event == "PostToolUse":
            data["tool_response"] = {}
    if event == "SessionStart":
        data["source"] = "startup"
    return data


def run_hook(argv, data, project, timeout):
    """(salida, error) del hook; error es None si salió con 0 a tiempo."""
    try:
        r = subprocess.run([sys.executable, *argv], input=json.dumps(data),
                           capture_output=True, text=True, cwd=str(project),
                           env=child_env(project), timeout=timeout)
    except subprocess.TimeoutExpired:
        return "", f"no respondió en {timeout} s"
    except OSError as exc:
        return "", f"no se pudo lanzar: {exc}"
    if r.returncode != 0:
        return r.stdout, f"salió con {r.returncode}: {last_error(r.stderr)}"
    return r.stdout, None


def denies(stdout):
    try:
        out = json.loads(stdout)
    except ValueError:
        return False
    specific = out.get("hookSpecificOutput") if isinstance(out, dict) else None
    return isinstance(specific, dict) and specific.get("permissionDecision") == "deny"


def check_hook(event, matcher, argv, project, timeout):
    """(ok, detalle) de un hook frente a sus peticiones de prueba."""
    tools = matcher.split("|") if matcher else []
    write = {"file_path": str(project / INNOCUOUS), "content": "notas\n"}
    if event in ("PreToolUse", "PostToolUse"):
        inocua = (payload(event, project, "Write", **write) if "Write" in tools
                  else payload(event, project, "Bash", command="true"))
    else:
        inocua = payload(event, project)
    stdout, error = run_hook(argv, inocua, project, timeout)
    if error:
        return False, error
    if '"allow"' in stdout:
        return False, "concede permisos (allow), y un guardrail nunca debe hacerlo"
    if denies(stdout):
        return False, "bloquea una operación inocua"
    if not (event == "PreToolUse" and argv[-1] == "guard"):
        return True, "responde"
    target = project / CASE["approval"]["file_path"]
    approval = dict(CASE["approval"], file_path=str(target))
    stdout, error = run_hook(argv, payload(event, project, "Write", **approval), project,
                             timeout)
    if error:
        return False, error
    if '"allow"' in stdout:
        return False, "concede permisos (allow), y un guardrail nunca debe hacerlo"
    if not denies(stdout):
        return False, "no impide una aprobación de prueba: no protege"
    return True, "impide una aprobación de prueba y deja pasar una escritura inocua"


def check_hooks(project):
    """(nombre, ok, detalle) por cada hook de python3 de hooks.json."""
    try:
        conf = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [("hooks", False, f"hooks.json no se puede leer: {exc}")]
    out = []
    for event, groups in (conf.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                # Los de sh son el propio diagnóstico.
                if hook.get("type") != "command" or hook.get("command") != "python3":
                    continue
                argv = [a.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT))
                        for a in hook.get("args", [])]
                name = Path(argv[-1]).stem if argv else "?"
                kind = "guardrail" if name in GUARDRAILS else "hook"
                ok, detail = check_hook(event, group.get("matcher", ""), argv, project,
                                        hook.get("timeout", 60))
                out.append((f"{kind} {name} ({event})", ok, detail))
    return out


def main(argv):
    plugin = argv[1] if len(argv) > 1 else ROOT.name
    project = Path(tempfile.mkdtemp(prefix="doctor-"))
    try:
        for d in CASE["dirs"]:
            (project / d).mkdir(parents=True, exist_ok=True)
        results = check_scripts(project) + check_hooks(project)
    finally:
        shutil.rmtree(str(project), ignore_errors=True)
    for name, ok, detail in results:
        print(f"[{'ok' if ok else 'falla'}] {name}: {detail}")
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print(f"Resumen: {plugin} no está listo: {', '.join(failed)}.")
        return 1
    print(f"Resumen: {plugin} está listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
