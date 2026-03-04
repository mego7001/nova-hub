from pathlib import Path


def test_qa_panel_files_and_main_wiring_exist():
    root = Path(__file__).resolve().parents[1]
    main_qml = root / "ui" / "hud_qml" / "qml" / "Main.qml"
    qa_panel_qml = root / "ui" / "hud_qml" / "qml" / "panels" / "QAReportPanel.qml"

    assert main_qml.exists()
    assert qa_panel_qml.exists()

    main_text = main_qml.read_text(encoding="utf-8")
    qa_text = qa_panel_qml.read_text(encoding="utf-8")

    assert "DXF/Clip QA" in main_text
    assert "qaReportPanelComponent" in main_text
    assert "QAReportPanel" in main_text

    assert "controller.qaReportText" in qa_text
    assert "controller.qaStatusChip" in qa_text
    assert "controller.qaFindingsModel" in qa_text
    assert "controller.qaMetricsModel" in qa_text
    assert "controller.refreshQaReport()" in qa_text
