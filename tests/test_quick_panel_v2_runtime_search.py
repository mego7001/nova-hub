from __future__ import annotations

from pathlib import Path


def test_quick_panel_v2_exposes_voice_readiness_and_memory_search_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    qml = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellCompact.qml").read_text(encoding="utf-8")
    tools_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelTools.qml").read_text(encoding="utf-8")
    attach_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelAttach.qml").read_text(encoding="utf-8")
    health_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelHealth.qml").read_text(encoding="utf-8")
    history_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelHistory.qml").read_text(encoding="utf-8")
    voice_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelVoice.qml").read_text(encoding="utf-8")
    top_header = (root / "ui" / "hud_qml_v2" / "components" / "TopHeader.qml").read_text(encoding="utf-8")
    drawer_selector = (root / "ui" / "hud_qml_v2" / "components" / "DrawerSelector.qml").read_text(encoding="utf-8")

    assert 'if (action === "open_drawer")' in qml
    assert "_openDrawer(drawerName)" in qml

    assert "DrawerSelector" in qml
    assert '"Drawer"' in drawer_selector
    assert '"Button"' in drawer_selector
    assert "objectPrefix: \"quickPanelV2\"" in qml

    assert "PanelTools" in qml
    assert "PanelAttach" in qml
    assert "PanelHealth" in qml
    assert "PanelHistory" in qml
    assert "PanelVoice" in qml

    assert "ToolsCatalogList" in tools_panel
    assert "AttachSummaryLabel" in attach_panel
    assert "TimelineList" in history_panel

    assert "VoiceDrawerReadinessButton" in voice_panel
    assert "refreshVoiceReadiness()" in qml

    assert "VoiceDeviceCombo" in voice_panel
    assert "VoiceRefreshDevicesButton" in voice_panel

    assert "OllamaModelCombo" in health_panel
    assert "setOllamaSessionModel(selected)" in qml

    assert "MemorySearchInput" in history_panel
    assert "MemorySearchScopeCombo" in history_panel
    assert "MemorySearchButton" in history_panel
    assert "MemorySearchResultsList" in history_panel
    assert "MemorySearchPrevButton" in history_panel
    assert "MemorySearchNextButton" in history_panel
    assert "memorySearchPage(" in qml
    assert "Memory search returned no results." in qml
    assert "Memory search failed:" in qml
    assert "TopHeader" in qml
    assert "compactMode: true" in qml
    assert '"TopMinimizeButton"' in top_header
    assert '"TopCloseButton"' in top_header
