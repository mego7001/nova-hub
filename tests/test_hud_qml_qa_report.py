from pathlib import Path
import json
import tempfile

from ui.hud_qml.controller import HUDController


def _write_sample_report(workspace: str) -> Path:
    report_path = Path(workspace) / "reports" / "qa" / "latest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "QAReportV1",
        "run_id": "run-123456",
        "timestamp_utc": "2026-02-07T00:00:00Z",
        "project_id": "p-test",
        "summary": {"status": "warn", "findings_total": 2, "warn": 1, "fail": 0},
        "dxf_metrics": {"entities_seen": 12, "bulge_segments_expanded": 3},
        "clip_metrics": {"closed_inputs": 2, "closed_outputs": 2},
        "findings": [
            {"severity": "info", "code": "DXF_OK", "message": "ok", "context": {}},
            {"severity": "warn", "code": "CLIP_WARN", "message": "warn", "context": {"count": 1}},
        ],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def test_hud_controller_refreshes_qa_report_models():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        report_path = _write_sample_report(workspace)
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )

        controller.refreshQaReport()

        assert Path(controller.qaLatestPath).name == "latest.json"
        assert "reports" in controller.qaLatestPath.lower()
        assert "QA=WARN" in controller.qaStatusChip
        assert "project=p-test" in controller.qaReportText
        assert controller.qaFindingsModel.count() == 2
        assert controller.qaMetricsModel.count() >= 2

        first = controller.qaFindingsModel.get(0)
        assert "severity" in first
        assert "code" in first
        assert report_path.exists()
