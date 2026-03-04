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
        return self.mapping[(str(method).upper(), str(url))]


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


def test_ollama_models_list_parses_names_and_metadata() -> None:
    session = _FakeSession(
        {
            ("GET", "http://127.0.0.1:11434/api/tags"): _FakeResponse(
                200,
                {
                    "models": [
                        {
                            "name": "qwen2.5-coder:7b-instruct",
                            "size": 4681000000,
                            "modified_at": "2026-02-22T01:00:00Z",
                        },
                        {
                            "name": "gemma3:4b",
                            "size": 3100000000,
                            "modified_at": "2026-02-22T02:00:00Z",
                        },
                    ]
                },
            )
        }
    )
    client = OllamaHttpClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    out = client.list_models()

    assert out.get("status") == "ok"
    models = out.get("models")
    assert isinstance(models, list)
    names = [str(item.get("name") or "") for item in models if isinstance(item, dict)]
    assert "qwen2.5-coder:7b-instruct" in names
    assert "gemma3:4b" in names

