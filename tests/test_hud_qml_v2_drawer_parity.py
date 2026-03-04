from pathlib import Path


def test_hud_v2_drawers_cover_core_capabilities() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellFull.qml").read_text(encoding="utf-8")
    top_header = (root / "ui" / "hud_qml_v2" / "components" / "TopHeader.qml").read_text(encoding="utf-8")
    drawer_selector = (root / "ui" / "hud_qml_v2" / "components" / "DrawerSelector.qml").read_text(encoding="utf-8")
    tools_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelTools.qml").read_text(encoding="utf-8")
    attach_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelAttach.qml").read_text(encoding="utf-8")
    health_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelHealth.qml").read_text(encoding="utf-8")
    history_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelHistory.qml").read_text(encoding="utf-8")
    voice_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelVoice.qml").read_text(encoding="utf-8")

    assert "{ id: \"tools\", title: \"Tools\" }" in text
    assert "{ id: \"attach\", title: \"Attach\" }" in text
    assert "{ id: \"health\", title: \"Health\" }" in text
    assert "{ id: \"history\", title: \"History\" }" in text
    assert "{ id: \"voice\", title: \"Voice\" }" in text

    assert "PanelTools" in text
    assert "PanelAttach" in text
    assert "PanelHealth" in text
    assert "PanelHistory" in text
    assert "PanelVoice" in text
    assert "TopHeader" in text
    assert "DrawerSelector" in text

    assert "Queue Apply Candidate" in tools_panel
    assert "Confirm Pending" in tools_panel
    assert "Reject Pending" in tools_panel
    assert "Run Security Audit" in tools_panel
    assert "hudController.queue_apply()" in text
    assert "hudController.confirm_pending()" in text
    assert "hudController.reject_pending()" in text
    assert "hudController.run_security_audit()" in text

    assert "Attach Files" in text
    assert "AttachChooseFilesButton" in attach_panel
    assert "hudController.attachFiles(selectedFiles)" in text
    assert "attachLastSummary" in text

    assert "Refresh Health" in health_panel
    assert "Doctor Report" in health_panel
    assert "Local LLM: Ollama" in health_panel
    assert "Refresh Models" in health_panel
    assert "hudController.healthStatsModel" in text
    assert "hudController.healthStatsSummary" in text
    assert "hudController.ollamaHealthSummary" in text
    assert "hudController.ollamaAvailableModels" in text

    assert "Refresh Timeline" in history_panel
    assert "hudController.timelineModel" in text
    assert "hudController.timelineSummary" in text
    assert "Memory Search" in history_panel
    assert "Voice mode: push-to-talk (hold Mic)" in voice_panel
    assert "Capabilities: Chat | Tools | Attach | Health | History | Voice | Security | Timeline" in top_header
    assert '"TopMinimizeButton"' in top_header
    assert '"TopCloseButton"' in top_header
    assert '"DrawerTab_"' in drawer_selector


def test_hud_v2_palette_includes_voice_and_apply_actions() -> None:
    root = Path(__file__).resolve().parents[1]
    palette = (root / "ui" / "hud_qml_v2" / "components" / "CommandPalette.qml").read_text(encoding="utf-8")

    assert "drawer.voice" in palette
    assert "apply.queue" in palette
    assert "apply.confirm" in palette
    assert "apply.reject" in palette
    assert "security.audit" in palette
    assert "voice.toggle" in palette
    assert "voice.mute" in palette
    assert "voice.stop" in palette
    assert "voice.replay" in palette
    assert "app.minimize" in palette
    assert "app.close" in palette
