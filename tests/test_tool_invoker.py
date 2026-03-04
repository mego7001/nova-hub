from __future__ import annotations

from typing import Any, Dict, Optional

from core.plugin_engine.registry import PluginRegistration, PluginRegistry, ToolRegistration
from core.tooling.invoker import InvokeContext, invoke_tool
from core.tooling.trace import ToolTraceRecorder


class _Runner:
    def __init__(self, *, fail_with: Optional[Exception] = None) -> None:
        self.fail_with = fail_with
        self.calls: list[dict[str, Any]] = []

    def execute_registered_tool(self, tool, **kwargs):
        self.calls.append({"tool_id": str(tool.tool_id), "kwargs": dict(kwargs)})
        if self.fail_with is not None:
            raise self.fail_with
        return tool.handler(**kwargs)


def _registry_with_tool(*, tool_id: str, handler, default_target: str | None = None) -> PluginRegistry:
    reg = PluginRegistry()
    reg.register_plugin(
        PluginRegistration(
            plugin_id="test_plugin",
            kind="test",
            name="Test Plugin",
            version="1.0.0",
            entrypoint="tests.fake",
            tool_groups=["fs_read"],
            config={},
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id=tool_id,
            plugin_id="test_plugin",
            tool_group="fs_read",
            op="test_op",
            handler=handler,
            description="test",
            default_target=default_target,
        )
    )
    return reg


def test_invoke_tool_returns_raw_result_passthrough() -> None:
    def _handler(value: str) -> Dict[str, Any]:
        return {"ok": True, "value": value}

    reg = _registry_with_tool(tool_id="test.echo", handler=_handler)
    runner = _Runner()
    out = invoke_tool(
        "test.echo",
        {"value": "hello"},
        InvokeContext(runner=runner, registry=reg, session_id="s1", project_id="p1", mode="general"),
    )
    assert out == {"ok": True, "value": "hello"}
    assert runner.calls and runner.calls[0]["kwargs"] == {"value": "hello"}


def test_invoke_tool_missing_tool_raises_value_error() -> None:
    reg = _registry_with_tool(tool_id="test.echo", handler=lambda: {"ok": True})
    runner = _Runner()
    try:
        invoke_tool("missing.tool", {}, InvokeContext(runner=runner, registry=reg))
    except ValueError as exc:
        assert "Tool not found: missing.tool" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing tool")


def test_invoke_tool_propagates_permission_error_unchanged() -> None:
    reg = _registry_with_tool(tool_id="test.secure", handler=lambda **_: {"ok": True})
    runner = _Runner(fail_with=PermissionError("User rejected approval."))
    try:
        invoke_tool("test.secure", {}, InvokeContext(runner=runner, registry=reg))
    except PermissionError as exc:
        assert str(exc) == "User rejected approval."
    else:
        raise AssertionError("Expected PermissionError")


def test_invoke_tool_records_trace_success_and_failure_without_exact_timing_assertions() -> None:
    reg = _registry_with_tool(tool_id="test.echo", handler=lambda: {"ok": True})
    recorder = ToolTraceRecorder(capacity=8)

    ok_runner = _Runner()
    invoke_tool(
        "test.echo",
        {},
        InvokeContext(runner=ok_runner, registry=reg, trace_recorder=recorder, request_id="req-ok"),
    )

    bad_runner = _Runner(fail_with=RuntimeError("boom"))
    try:
        invoke_tool(
            "test.echo",
            {},
            InvokeContext(runner=bad_runner, registry=reg, trace_recorder=recorder, request_id="req-bad"),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError")

    tail = recorder.tail(8)
    assert len(tail) == 2
    assert [t.request_id for t in tail] == ["req-ok", "req-bad"]
    assert tail[0].ok is True
    assert tail[1].ok is False
    assert all(isinstance(t.latency_ms, int) and t.latency_ms >= 0 for t in tail)
    assert all(isinstance(t.start_ts, str) and isinstance(t.end_ts, str) for t in tail)


def test_invoke_tool_injects_default_target_only_when_missing() -> None:
    def _handler(path: str, target: str | None = None) -> Dict[str, Any]:
        return {"path": path, "target": target}

    reg = _registry_with_tool(tool_id="test.write", handler=_handler, default_target="outputs/default.txt")
    runner = _Runner()
    out = invoke_tool(
        "test.write",
        {"path": "tmp/file.txt"},
        InvokeContext(runner=runner, registry=reg),
    )
    assert out.get("target") == "outputs/default.txt"
    assert runner.calls and runner.calls[0]["kwargs"].get("target") == "outputs/default.txt"

