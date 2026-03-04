from __future__ import annotations

from ui.hud_qml import controller as controller_mod
from ui.hud_qml import controller_core, controller_ingest, controller_tools, controller_voice


def test_hud_controller_split_modules_importable():
    assert hasattr(controller_mod, "HUDController")
    assert callable(controller_core.now_utc)
    assert callable(controller_ingest.build_attach_rows)
    assert callable(controller_tools.preferred_user_mode)
    assert callable(controller_voice.latency_summary)
