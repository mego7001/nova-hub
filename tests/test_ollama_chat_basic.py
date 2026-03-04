from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.llm.ollama_config import OllamaSettings
from core.llm.providers.ollama_http import OllamaHttpClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: Optional[Dict[str, Any]] = None, text: str = "") -> None:
        self.status_code = int(status_code)
        self._payload = payload
        self.text = text

    def json(self) -> Dict[str, Any]:
        if self._payload is None:
            raise ValueError("invalid json")
        return self._payload


class _FakeSession:
    def __init__(self, mapping: Dict[Tuple[str, str], Any]) -> None:
        self.mapping = mapping

    def request(self, method: str, url: str, json: Any = None, timeout: Any = None):  # noqa: ANN401
        _ = json
        _ = timeout
        key = (str(method).upper(), str(url))
        return self.mapping[key]


def _settings() -> OllamaSettings:
    return OllamaSettings(
        enabled=True,
        base_url="http://127.0.0.1:11434",
        model_general="gemma3:4b",
        model_code="qwen2.5-coder:7b-instruct",
        model_vision="llava",
        model_override="",
        connect_timeout_sec=0.5,
        read_timeout_sec=60.0,
    )


def test_ollama_chat_uses_api_chat_message_content() -> None:
    session = _FakeSession(
        {
            ("POST", "http://127.0.0.1:11434/api/chat"): _FakeResponse(
                200,
                {"message": {"content": "hello from ollama"}, "done": True},
            )
        }
    )
    client = OllamaHttpClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    out = client.chat(prompt="hi", model="gemma3:4b")

    assert out.get("status") == "ok"
    assert out.get("provider") == "ollama"
    assert out.get("model") == "gemma3:4b"
    assert out.get("text") == "hello from ollama"


def test_ollama_chat_falls_back_to_generate_endpoint() -> None:
    session = _FakeSession(
        {
            ("POST", "http://127.0.0.1:11434/api/chat"): _FakeResponse(404, {"error": "chat endpoint not available"}),
            ("POST", "http://127.0.0.1:11434/api/generate"): _FakeResponse(
                200,
                {"response": "fallback response from generate"},
            ),
        }
    )
    client = OllamaHttpClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    out = client.chat(prompt="build parser", model="qwen2.5-coder:7b-instruct")

    assert out.get("status") == "ok"
    assert out.get("text") == "fallback response from generate"
    raw_meta = out.get("raw_meta")
    assert isinstance(raw_meta, dict)
    assert raw_meta.get("endpoint") == "/api/generate"

