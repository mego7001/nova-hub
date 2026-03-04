from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "script_name",
    [
        "run_hud_qml.py",
        "run_quick_panel.py",
        "run_quick_panel_v2.py",
        "run_whatsapp.py",
        "run_chat.py",
        "run_ui.py",
        "run_core_service.py",
        "run_ipc_cli.py",
    ],
)
def test_wrapper_help_smoke(script_name: str) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, script_name, "--help"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, output
    assert "usage:" in output.lower()


def test_start_launchers_target_canonical_main_hud() -> None:
    root = Path(__file__).resolve().parents[1]
    ps1_text = (root / "launchers" / "start_novahub.ps1").read_text(encoding="utf-8").lower()
    bat_text = (root / "launchers" / "start_novahub.bat").read_text(encoding="utf-8").lower()

    assert "python main.py hud" in ps1_text
    assert "python main.py hud" in bat_text
