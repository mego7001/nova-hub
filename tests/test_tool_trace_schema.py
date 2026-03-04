from __future__ import annotations

from core.tooling.trace import ToolCallTrace, ToolTraceRecorder


def test_tool_call_trace_schema_fields() -> None:
    trace = ToolCallTrace(
        trace_id="t-1",
        request_id="r-1",
        tool_id="patch.plan",
        provider="local",
        server_name="",
        start_ts="2026-02-27T00:00:00Z",
        end_ts="2026-02-27T00:00:01Z",
        latency_ms=1000,
        ok=True,
        error_kind="",
        error_msg="",
        session_id="s-1",
        project_id="p-1",
        mode="build_software",
    )
    payload = trace.to_dict()
    assert payload["tool_id"] == "patch.plan"
    assert isinstance(payload["latency_ms"], int)
    assert isinstance(payload["ok"], bool)
    assert "start_ts" in payload
    assert "end_ts" in payload


def test_tool_trace_ring_buffer_tail_behavior() -> None:
    recorder = ToolTraceRecorder(capacity=2)
    recorder.append(
        ToolCallTrace(
            trace_id="t-1",
            request_id="r-1",
            tool_id="a",
            provider="local",
            server_name="",
            start_ts="2026-02-27T00:00:00Z",
            end_ts="2026-02-27T00:00:00Z",
            latency_ms=1,
            ok=True,
            error_kind="",
            error_msg="",
            session_id="s",
            project_id="p",
            mode="m",
        )
    )
    recorder.append(
        ToolCallTrace(
            trace_id="t-2",
            request_id="r-2",
            tool_id="b",
            provider="local",
            server_name="",
            start_ts="2026-02-27T00:00:00Z",
            end_ts="2026-02-27T00:00:00Z",
            latency_ms=2,
            ok=True,
            error_kind="",
            error_msg="",
            session_id="s",
            project_id="p",
            mode="m",
        )
    )
    recorder.append(
        ToolCallTrace(
            trace_id="t-3",
            request_id="r-3",
            tool_id="c",
            provider="local",
            server_name="",
            start_ts="2026-02-27T00:00:00Z",
            end_ts="2026-02-27T00:00:00Z",
            latency_ms=3,
            ok=False,
            error_kind="other",
            error_msg="x",
            session_id="s",
            project_id="p",
            mode="m",
        )
    )

    tail = recorder.tail(10)
    assert len(tail) == 2
    assert [item.trace_id for item in tail] == ["t-2", "t-3"]
    assert all(isinstance(item.latency_ms, int) and item.latency_ms >= 0 for item in tail)

