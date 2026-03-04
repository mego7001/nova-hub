from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ui.hud_qml.controller import HUDController


def test_is_ui_action_allowed_respects_contract_defaults() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        assert controller.isUiActionAllowed("switch_mode") is True
        assert controller.isUiActionAllowed("app_close") is True
        assert controller.isUiActionAllowed("definitely_unknown_action") is False


def test_record_ui_event_writes_workspace_log() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.recordUiEvent("ui.command.execute", "test_case", "42")

        log_path = Path(workspace) / "runtime" / "logs" / "ui_events.jsonl"
        assert log_path.exists()
        line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
        payload = json.loads(line)
        assert payload["event_key"] == "ui.command.execute"
        assert payload["source"] == "test_case"
        assert payload["value"] == "42"
