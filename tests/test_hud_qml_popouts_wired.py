from pathlib import Path


def test_popout_wiring_files_and_references_exist():
    root = Path(__file__).resolve().parents[1]

    main_qml = root / "ui" / "hud_qml" / "qml" / "Main.qml"
    panel_card_qml = root / "ui" / "hud_qml" / "qml" / "components" / "PanelCard.qml"
    popout_window_qml = root / "ui" / "hud_qml" / "qml" / "components" / "PopoutWindow.qml"
    diff_panel_qml = root / "ui" / "hud_qml" / "qml" / "panels" / "DiffPreviewPanel.qml"
    timeline_panel_qml = root / "ui" / "hud_qml" / "qml" / "panels" / "TimelinePanel.qml"
    threed_panel_qml = root / "ui" / "hud_qml" / "qml" / "panels" / "ThreeDPanel.qml"

    assert main_qml.exists()
    assert panel_card_qml.exists()
    assert popout_window_qml.exists()
    assert diff_panel_qml.exists()
    assert timeline_panel_qml.exists()
    assert threed_panel_qml.exists()

    main_text = main_qml.read_text(encoding="utf-8")
    panel_card_text = panel_card_qml.read_text(encoding="utf-8")
    diff_text = diff_panel_qml.read_text(encoding="utf-8")
    timeline_text = timeline_panel_qml.read_text(encoding="utf-8")
    threed_text = threed_panel_qml.read_text(encoding="utf-8")

    assert "property bool diffPoppedOut" in main_text
    assert "property bool timelinePoppedOut" in main_text
    assert "property bool threeDPoppedOut" in main_text
    assert "PopoutWindow" in main_text
    assert "_popOutPanel(" in main_text
    assert "_restorePanel(" in main_text

    assert "property string panelId" in panel_card_text
    assert "signal popOutRequested(string panelId)" in panel_card_text

    assert "controller.diffStatsText" in diff_text
    assert "controller.timelineModel" in timeline_text
    assert "controller.activateThreeD()" in threed_text
    assert "controller.entitiesModel" in threed_text
