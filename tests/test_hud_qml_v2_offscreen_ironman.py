from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_hud_qml_v2_offscreen_ironman_autoclose_exits_zero() -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QSG_RHI_BACKEND", "software")
    env["NH_HUD_AUTOCLOSE_MS"] = "200"
    env["NH_UI_VERSION"] = "v2"

    proc = subprocess.run(
        [sys.executable, "run_hud_qml.py"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
