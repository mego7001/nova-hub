from pathlib import Path
import tempfile

from ui.hud_qml.controller import HUDController


def test_hud_main_qml_wires_tools_and_attach_panels():
    root = Path(__file__).resolve().parents[1]
    main_qml = root / "ui" / "hud_qml" / "qml" / "Main.qml"
    text = main_qml.read_text(encoding="utf-8")

    assert "Tools Menu" in text
    assert "Attach Summary" in text
    assert "Health / Stats" in text
    assert "toolsMenuPanelComponent" in text
    assert "attachSummaryPanelComponent" in text
    assert "healthStatsPanelComponent" in text
    assert "attachDialog.open()" in text
    assert "hudController.setTaskMode(modeId)" in text
    assert "hudController.toggleToolsMenu()" in text
    assert "hudController.attachFiles(selectedFiles)" in text


def test_hud_controller_exposes_unified_ux_contract():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        assert hasattr(controller, "taskModesModel")
        assert hasattr(controller, "currentTaskMode")
        assert hasattr(controller, "toolsCatalogModel")
        assert hasattr(controller, "attachSummaryModel")
        assert hasattr(controller, "healthStatsModel")
        assert hasattr(controller, "healthStatsSummary")
        assert hasattr(controller, "setTaskMode")
        assert hasattr(controller, "openToolsMenu")
        assert hasattr(controller, "toggleToolsMenu")
        assert hasattr(controller, "refreshHealthStats")
        assert hasattr(controller, "attachFiles")
        assert hasattr(controller, "migrateGeneralToProject")
