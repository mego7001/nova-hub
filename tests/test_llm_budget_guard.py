from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

from core.llm.router import LLMRouter
from core.telemetry.db import TelemetryDB
from core.telemetry.recorders import TelemetryRecorder


@dataclass
class _DummyTool:
    tool_id: str
    handler: Callable[..., Dict[str, Any]]
    default_target: str | None = None


class _DummyRegistry:
    def __init__(self) -> None:
        self.tools = {
            "deepseek.chat": _DummyTool("deepseek.chat", lambda **_: {"choices": [{"message": {"content": "ok"}}]}),
            "gemini.prompt": _DummyTool("gemini.prompt", lambda **_: {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}),
            "openai.chat": _DummyTool("openai.chat", lambda **_: {"choices": [{"message": {"content": "ok"}}]}),
            "ollama.chat": _DummyTool("ollama.chat", lambda **_: {"message": {"content": "ok"}}),
        }


class _DummyRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute_registered_tool(self, tool: _DummyTool, **kwargs):
        self.calls.append({"tool_id": tool.tool_id, "kwargs": dict(kwargs)})
        return tool.handler(**kwargs)


def test_session_budget_blocks_online_provider_call(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = TelemetryDB(workspace_root=str(workspace))
    recorder = TelemetryRecorder(db)
    recorder.record_llm_call(
        session_id="budget-session",
        project_id="p1",
        mode="general",
        provider="deepseek",
        model="deepseek-chat",
        request_kind="chat",
        input_tokens=120,
        output_tokens=60,
        status="ok",
    )

    monkeypatch.setenv("NH_SESSION_TOKEN_BUDGET", "150")
    monkeypatch.setenv("NH_DAILY_TOKEN_BUDGET", "0")

    runner = _DummyRunner()
    registry = _DummyRegistry()
    router = LLMRouter(runner=runner, registry=registry, telemetry_recorder=recorder, config={"default_provider": "deepseek"})

    out = router.route(
        "conversation",
        prompt="هذه رسالة تحتاج توجيه أونلاين",
        online_enabled=True,
        offline_confidence="low",
        request_kind="chat",
        session_id="budget-session",
    )

    assert out.get("mode") == "offline"
    assert "budget" in str(out.get("reason") or "").lower()
    assert not runner.calls
    routing = out.get("_routing")
    assert isinstance(routing, dict)
    budget = routing.get("token_budget")
    assert isinstance(budget, dict)
    assert budget.get("blocked") is True
