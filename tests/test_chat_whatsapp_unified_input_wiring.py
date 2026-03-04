from pathlib import Path


def test_chat_wires_mode_routing_and_general_ingest():
    root = Path(__file__).resolve().parents[1]
    src = (root / "ui" / "chat" / "app.py").read_text(encoding="utf-8")

    assert "route_message_for_mode(" in src
    assert "user_message=routed" in src
    assert "ingest_general(" in src
    assert "ingest_project(" in src
    assert "task_mode_combo" in src
    assert "tools_button" in src


def test_quick_panel_wires_mode_routing_and_general_ingest():
    root = Path(__file__).resolve().parents[1]
    quick_panel_src = (root / "ui" / "quick_panel" / "app.py").read_text(encoding="utf-8")
    legacy_src = (root / "ui" / "whatsapp" / "app.py").read_text(encoding="utf-8")

    assert "QuickPanelWindow" in quick_panel_src

    assert "route_message_for_mode(" in quick_panel_src
    assert "user_message=routed_message" in quick_panel_src
    assert "ingest_general(" in quick_panel_src
    assert "ingest_project(" in quick_panel_src
    assert "task_mode_combo" in quick_panel_src
    assert "tools_button" in quick_panel_src

    assert "from ui.quick_panel.app import QuickPanelWindow" in legacy_src
    assert "WhatsAppWindow = QuickPanelWindow" in legacy_src
