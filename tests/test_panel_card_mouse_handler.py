from __future__ import annotations

from pathlib import Path


def test_panel_card_click_handler_declares_mouse_parameter() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "ui" / "hud_qml" / "qml" / "components" / "PanelCard.qml").read_text(encoding="utf-8")

    assert "onClicked: function(mouse)" in text
    assert "mouse.x > parent.width - 60" in text
