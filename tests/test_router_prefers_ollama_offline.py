from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from core.llm.router import LLMRouter


@dataclass
class _DummyTool:
    tool_id: str
    handler: Callable[..., Dict[str, Any]]
    default_target: str | None = None


class _DummyRegistry:
    def __init__(self, tools: Dict[str, _DummyTool]) -> None:
        self.tools = tools


class _DummyRunner:
    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

    def execute_registered_tool(self, tool: _DummyTool, **kwargs):
        self.calls.append({"tool_id": tool.tool_id, "kwargs": dict(kwargs)})
        return tool.handler(**kwargs)


def test_router_prefers_ollama_when_online_disabled_and_need_online_true() -> None:
    runner = _DummyRunner()
    registry = _DummyRegistry(
        {
            "deepseek.chat": _DummyTool("deepseek.chat", lambda **_: {"choices": [{"message": {"content": "deepseek"}}]}),
            "gemini.prompt": _DummyTool("gemini.prompt", lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini"}]}}]}),
            "openai.chat": _DummyTool("openai.chat", lambda **_: {"choices": [{"message": {"content": "openai"}}]}),
            "ollama.chat": _DummyTool("ollama.chat", lambda **_: {"status": "ok", "text": "local ollama response", "model": "gemma3:4b"}),
        }
    )
    router = LLMRouter(
        runner=runner,
        registry=registry,
        config={
            "local_first": True,
            "external_backup_only": True,
            "task_model_map": {"conversation": "gemma3:4b"},
        },
    )

    out = router.route(
        "conversation",
        prompt="please explain deeply",
        online_enabled=False,
        offline_confidence="low",
        request_kind="chat",
        session_id="offline-prefers-ollama",
    )

    assert out.get("provider") == "ollama"
    assert out.get("mode") == "offline"
    assert out.get("text") == "local ollama response"
    assert len(runner.calls) == 1
    assert runner.calls[0]["tool_id"] == "ollama.chat"

