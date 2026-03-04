import json
import os
from pathlib import Path

from core.ipc.service import NovaCoreService


def test_doctor_report_shape_and_secret_safety(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")
    prev_token = os.environ.get("NH_IPC_TOKEN")
    os.environ["NH_IPC_TOKEN"] = "super-secret-token-for-test"

    try:
        service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
        service.telemetry.record_llm_call(
            session_id="doc",
            project_id="doc",
            mode="general",
            provider="deepseek",
            model="deepseek-chat",
            request_kind="chat",
            status="error",
            latency_ms=100,
            error_kind="auth",
            error_msg="api_key=SUPER_SECRET sk-12345678901234567890",
        )
        report = service.dispatch("doctor.report", {}, {})

        assert isinstance(report, dict)
        for key in ("db", "recent_errors", "best_provider_by_mode", "voice", "ipc", "remediation"):
            assert key in report
        assert isinstance(report["db"], dict)
        assert report["db"]["schema_version"] >= 1
        assert isinstance(report["recent_errors"], list)
        assert isinstance(report["best_provider_by_mode"], dict)
        assert isinstance(report["remediation"], list)
        assert report["ipc"]["token_enabled"] is True

        blob = json.dumps(report, ensure_ascii=False)
        assert "super-secret-token-for-test" not in blob
        assert "sk-12345678901234567890" not in blob
    finally:
        os.chdir(prev_cwd)
        if prev_base is None:
            os.environ.pop("NH_BASE_DIR", None)
        else:
            os.environ["NH_BASE_DIR"] = prev_base
        if prev_workspace is None:
            os.environ.pop("NH_WORKSPACE", None)
        else:
            os.environ["NH_WORKSPACE"] = prev_workspace
        if prev_token is None:
            os.environ.pop("NH_IPC_TOKEN", None)
        else:
            os.environ["NH_IPC_TOKEN"] = prev_token
