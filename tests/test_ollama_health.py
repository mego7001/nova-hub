from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import requests

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
        key = (str(method).upper(), str(url))
        result = self.mapping.get(key)
        if isinstance(result, Exception):
            raise result
        if result is None:
            return _FakeResponse(404, {"error": "not found"})
        return result


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


def test_ollama_health_ping_ok_with_tags_probe() -> None:
    session = _FakeSession(
        {
            ("GET", "http://127.0.0.1:11434/api/version"): _FakeResponse(200, {"version": "0.5.7"}),
            ("GET", "http://127.0.0.1:11434/api/tags"): _FakeResponse(
                200,
                {"models": [{"name": "gemma3:4b"}, {"name": "qwen2.5-coder:7b-instruct"}]},
            ),
        }
    )
    client = OllamaHttpClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    out = client.health_ping()

    assert out.get("status") == "ok"
    assert out.get("provider") == "ollama"
    assert out.get("base_url") == "http://127.0.0.1:11434"
    details = out.get("details")
    assert isinstance(details, dict)
    assert details.get("model_count") == 2


def test_ollama_health_ping_unavailable_when_tags_fails() -> None:
    session = _FakeSession(
        {
            ("GET", "http://127.0.0.1:11434/api/version"): _FakeResponse(200, {"version": "0.5.7"}),
            ("GET", "http://127.0.0.1:11434/api/tags"): requests.RequestException("connection refused"),
        }
    )
    client = OllamaHttpClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    out = client.health_ping()

    assert out.get("status") == "unavailable"
    assert out.get("provider") == "ollama"
    assert "127.0.0.1:11434" in str(out.get("base_url") or "")

