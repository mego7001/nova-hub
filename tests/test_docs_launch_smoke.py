from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "args",
    [
        ["main.py", "--help"],
        ["main.py", "core", "--help"],
        ["main.py", "call", "--help"],
        ["main.py", "cli", "--help"],
        ["run_hud_qml.py", "--help"],
        ["run_quick_panel.py", "--help"],
        ["run_quick_panel_v2.py", "--help"],
        ["run_whatsapp.py", "--help"],
        ["run_chat.py", "--help"],
        ["run_ui.py", "--help"],
        ["run_core_service.py", "--help"],
        ["run_ipc_cli.py", "--help"],
    ],
)
def test_documented_launch_commands_smoke(args: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QSG_RHI_BACKEND", "software")

    proc = subprocess.run(
        [sys.executable, *args],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
