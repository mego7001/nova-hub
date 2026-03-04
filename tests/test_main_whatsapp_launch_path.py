from __future__ import annotations

from pathlib import Path


def test_launch_whatsapp_defaults_to_quick_panel_v2_path() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "main.py").read_text(encoding="utf-8")

    assert "def _legacy_whatsapp_enabled() -> bool:" in text
    assert "NH_UI_LEGACY_WHATSAPP" in text
    assert "return _launch_quick_panel_v2()" in text
    assert "Warning: legacy quick panel path enabled via NH_UI_LEGACY_WHATSAPP=1." in text
    assert "from ui.quick_panel.app import QuickPanelWindow" in text
