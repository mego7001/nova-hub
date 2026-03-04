from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.plugin_engine.loader import PluginLoader
from core.plugin_engine.registry import PluginRegistry


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    return int(proc.returncode), out.strip()


def main() -> int:
    root = ROOT
    failures = []

    registry = PluginRegistry()
    PluginLoader(str(root)).load_enabled(str(root / "configs" / "plugins_enabled.yaml"), registry)
    required_tools = {"conversation.chat", "patch.plan", "patch.apply", "verify.smoke"}
    missing = sorted(required_tools - set(registry.tools.keys()))
    if missing:
        failures.append(f"missing tools: {', '.join(missing)}")

    compile_targets = [
        "main.py",
        "run_hud_qml.py",
        "run_chat.py",
        "run_quick_panel.py",
        "ui/hud_qml/controller.py",
    ]
    code, out = _run([sys.executable, "-B", "-m", "py_compile", *compile_targets], root)
    if code != 0:
        failures.append(f"py_compile failed: {out}")

    if failures:
        print("smoke_status: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("smoke_status: PASS")
    print(f"tools_loaded: {len(registry.tools)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
