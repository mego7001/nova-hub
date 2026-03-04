from pathlib import Path

from core.telemetry.db import TelemetryDB
from core.telemetry.queries import provider_scoreboard, provider_stats, tool_scoreboard
from core.telemetry.recorders import TelemetryRecorder


def test_telemetry_record_and_scoreboard_query(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = TelemetryDB(workspace_root=str(workspace))
    recorder = TelemetryRecorder(db)

    recorder.record_llm_call(
        session_id="s1",
        project_id="p1",
        mode="general",
        provider="deepseek",
        model="deepseek-chat",
        profile="engineering",
        request_kind="chat",
        input_tokens=100,
        output_tokens=60,
        cost_usd=0.02,
        latency_ms=180,
        status="ok",
    )
    recorder.record_llm_call(
        session_id="s1",
        project_id="p1",
        mode="general",
        provider="gemini",
        model="gemini-1.5-pro",
        profile="engineering",
        request_kind="chat",
        input_tokens=95,
        output_tokens=55,
        cost_usd=0.01,
        latency_ms=120,
        status="error",
        error_kind="rate_limit",
        error_msg="429 too many requests",
    )
    recorder.record_tool_call(
        session_id="s1",
        project_id="p1",
        mode="general",
        tool_name="conversation.chat",
        latency_ms=210,
        status="ok",
    )
    recorder.record_tool_call(
        session_id="s1",
        project_id="p1",
        mode="general",
        tool_name="conversation.chat",
        latency_ms=310,
        status="error",
        error_kind="timeout",
        error_msg="timeout while waiting",
    )

    scoreboard = provider_scoreboard(db, mode="general")
    assert len(scoreboard) == 2
    deepseek = next(item for item in scoreboard if item["provider"] == "deepseek")
    gemini = next(item for item in scoreboard if item["provider"] == "gemini")
    assert deepseek["calls"] == 1
    assert deepseek["success_rate"] == 1.0
    assert gemini["calls"] == 1
    assert gemini["success_rate"] == 0.0
    assert gemini["last_error_kind"] == "rate_limit"

    stats = provider_stats(db, mode="general", request_kind="chat")
    assert len(stats) == 2
    assert {item["provider"] for item in stats} == {"deepseek", "gemini"}

    tool_rows = tool_scoreboard(db, mode="general")
    assert len(tool_rows) == 1
    row = tool_rows[0]
    assert row["tool_name"] == "conversation.chat"
    assert row["calls"] == 2
    assert row["ok_calls"] == 1
    assert row["error_calls"] == 1
