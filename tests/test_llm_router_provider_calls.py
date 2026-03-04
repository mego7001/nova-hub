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


def _build_registry(
    *,
    deepseek_handler: Callable[..., Dict[str, Any]],
    gemini_handler: Callable[..., Dict[str, Any]],
    openai_handler: Callable[..., Dict[str, Any]],
    ollama_handler: Callable[..., Dict[str, Any]],
) -> _DummyRegistry:
    return _DummyRegistry(
        {
            "deepseek.chat": _DummyTool("deepseek.chat", deepseek_handler),
            "gemini.prompt": _DummyTool("gemini.prompt", gemini_handler),
            "openai.chat": _DummyTool("openai.chat", openai_handler),
            "ollama.chat": _DummyTool("ollama.chat", ollama_handler),
        }
    )


def test_router_calls_openai_when_selected_and_local_first_disabled() -> None:
    runner = _DummyRunner()
    registry = _build_registry(
        deepseek_handler=lambda **_: {"choices": [{"message": {"content": "deepseek ok"}}]},
        gemini_handler=lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini ok"}]}}]},
        openai_handler=lambda **_: {"choices": [{"message": {"content": "openai ok"}}]},
        ollama_handler=lambda **_: {"message": {"content": "ollama ok"}},
    )
    router = LLMRouter(
        runner=runner,
        registry=registry,
        config={"default_provider": "openai", "local_first": False, "external_backup_only": False},
    )

    out = router.route(
        "conversation",
        prompt="route this online",
        online_enabled=True,
        offline_confidence="low",
        request_kind="chat",
        session_id="router-openai",
    )

    assert out.get("provider") == "openai"
    assert out.get("text") == "openai ok"
    assert runner.calls
    assert runner.calls[0]["tool_id"] == "openai.chat"


def test_router_fallbacks_to_next_provider_on_error_when_local_first_disabled() -> None:
    runner = _DummyRunner()

    def _deepseek_fail(**_):
        raise RuntimeError("deepseek down")

    registry = _build_registry(
        deepseek_handler=_deepseek_fail,
        gemini_handler=lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini fallback"}]}}]},
        openai_handler=lambda **_: {"choices": [{"message": {"content": "openai ok"}}]},
        ollama_handler=lambda **_: {"message": {"content": "ollama ok"}},
    )
    router = LLMRouter(
        runner=runner,
        registry=registry,
        config={"default_provider": "deepseek", "local_first": False, "external_backup_only": False},
    )

    out = router.route(
        "conversation",
        prompt="need online fallback",
        online_enabled=True,
        offline_confidence="low",
        request_kind="chat",
        session_id="router-fallback",
    )

    assert out.get("provider") == "ollama"
    assert out.get("text") == "ollama ok"
    assert len(runner.calls) >= 2
    assert runner.calls[0]["tool_id"] == "deepseek.chat"
    assert runner.calls[1]["tool_id"] == "ollama.chat"
    routing = out.get("_routing")
    assert isinstance(routing, dict)
    attempts = routing.get("attempts")
    assert isinstance(attempts, list)
    assert attempts[0].get("provider") == "deepseek"
    assert attempts[0].get("status") == "error"


def test_router_uses_local_ollama_path_when_online_not_required() -> None:
    runner = _DummyRunner()
    registry = _build_registry(
        deepseek_handler=lambda **_: {"choices": [{"message": {"content": "deepseek ok"}}]},
        gemini_handler=lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini ok"}]}}]},
        openai_handler=lambda **_: {"choices": [{"message": {"content": "openai ok"}}]},
        ollama_handler=lambda **_: {"message": {"content": "ollama local ok"}},
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
        prompt="hello",
        online_enabled=False,
        offline_confidence="high",
        request_kind="chat",
        session_id="router-ollama-local",
    )

    assert out.get("provider") == "ollama"
    assert out.get("mode") == "offline"
    assert out.get("text") == "ollama local ok"
    assert runner.calls
    assert runner.calls[0]["tool_id"] == "ollama.chat"
    assert runner.calls[0]["kwargs"]["model"] == "gemma3:4b"


def test_router_local_first_uses_ollama_and_does_not_call_external_on_success() -> None:
    runner = _DummyRunner()
    registry = _build_registry(
        deepseek_handler=lambda **_: {"choices": [{"message": {"content": "deepseek should not run"}}]},
        gemini_handler=lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini should not run"}]}}]},
        openai_handler=lambda **_: {"choices": [{"message": {"content": "openai should not run"}}]},
        ollama_handler=lambda **_: {"message": {"content": "local success"}},
    )
    router = LLMRouter(
        runner=runner,
        registry=registry,
        config={
            "default_provider": "auto",
            "local_first": True,
            "external_backup_only": True,
            "task_model_map": {
                "conversation": "gemma3:4b",
            },
        },
    )

    out = router.route(
        "conversation",
        prompt="need online local-first",
        online_enabled=True,
        offline_confidence="low",
        request_kind="chat",
        session_id="router-local-first-success",
    )

    assert out.get("provider") == "ollama"
    assert out.get("text") == "local success"
    assert len(runner.calls) == 1
    assert runner.calls[0]["tool_id"] == "ollama.chat"
    assert runner.calls[0]["kwargs"]["model"] == "gemma3:4b"


def test_router_local_first_falls_back_to_external_on_ollama_failure() -> None:
    runner = _DummyRunner()

    def _ollama_fail(**_):
        raise RuntimeError("ollama timeout")

    registry = _build_registry(
        deepseek_handler=lambda **_: {"choices": [{"message": {"content": "deepseek fallback ok"}}]},
        gemini_handler=lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini fallback"}]}}]},
        openai_handler=lambda **_: {"choices": [{"message": {"content": "openai fallback"}}]},
        ollama_handler=_ollama_fail,
    )
    router = LLMRouter(
        runner=runner,
        registry=registry,
        config={
            "default_provider": "auto",
            "local_first": True,
            "external_backup_only": True,
            "task_model_map": {
                "conversation": "gemma3:4b",
            },
        },
    )

    out = router.route(
        "conversation",
        prompt="need online local-first fallback",
        online_enabled=True,
        offline_confidence="low",
        request_kind="chat",
        session_id="router-local-first-fallback",
    )

    assert out.get("provider") in {"deepseek", "gemini", "openai"}
    assert "fallback" in str(out.get("text") or "")
    assert len(runner.calls) >= 2
    assert runner.calls[0]["tool_id"] == "ollama.chat"


def test_router_build_software_uses_coder_model_mapping() -> None:
    runner = _DummyRunner()
    registry = _build_registry(
        deepseek_handler=lambda **_: {"choices": [{"message": {"content": "deepseek"}}]},
        gemini_handler=lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini"}]}}]},
        openai_handler=lambda **_: {"choices": [{"message": {"content": "openai"}}]},
        ollama_handler=lambda **_: {"message": {"content": "coder run"}},
    )
    router = LLMRouter(
        runner=runner,
        registry=registry,
        config={
            "local_first": True,
            "external_backup_only": True,
            "task_model_map": {
                "build_software": "qwen2.5-coder:7b-instruct",
                "conversation": "gemma3:4b",
            },
        },
    )

    out = router.route(
        "conversation",
        prompt="implement a parser and tests",
        online_enabled=True,
        offline_confidence="low",
        mode="build_software",
        request_kind="chat",
        session_id="router-build-mode-coder",
    )

    assert out.get("provider") == "ollama"
    assert out.get("text") == "coder run"
    assert runner.calls
    assert runner.calls[0]["tool_id"] == "ollama.chat"
    assert runner.calls[0]["kwargs"]["model"] == "qwen2.5-coder:7b-instruct"


def test_router_vision_uses_llava_model_mapping() -> None:
    runner = _DummyRunner()
    registry = _build_registry(
        deepseek_handler=lambda **_: {"choices": [{"message": {"content": "deepseek"}}]},
        gemini_handler=lambda **_: {"candidates": [{"content": {"parts": [{"text": "gemini"}]}}]},
        openai_handler=lambda **_: {"choices": [{"message": {"content": "openai"}}]},
        ollama_handler=lambda **_: {"message": {"content": "vision run"}},
    )
    router = LLMRouter(
        runner=runner,
        registry=registry,
        config={
            "local_first": True,
            "external_backup_only": True,
            "task_model_map": {
                "vision": "llava",
            },
        },
    )

    out = router.route(
        "vision",
        prompt="extract dimensions from image",
        online_enabled=True,
        offline_confidence="low",
        request_kind="vision_geometry",
        session_id="router-vision-llava",
        images=["ZmFrZS1pbWFnZS1kYXRh"],
    )

    assert out.get("provider") == "ollama"
    assert out.get("text") == "vision run"
    assert runner.calls
    assert runner.calls[0]["tool_id"] == "ollama.chat"
    assert runner.calls[0]["kwargs"]["model"] == "llava"
