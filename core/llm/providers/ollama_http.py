from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import requests

from core.llm.ollama_config import OllamaSettings, load_ollama_settings


class OllamaHttpClient:
    def __init__(
        self,
        *,
        settings: Optional[OllamaSettings] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.settings = settings or load_ollama_settings()
        self.base_url = str(self.settings.base_url).rstrip("/")
        self.session = session or requests.Session()

    def health_ping(self) -> Dict[str, Any]:
        details: Dict[str, Any] = {}
        version_payload: Dict[str, Any] = {}
        try:
            version_res = self._request("GET", "/api/version", read_timeout=5.0)
            if version_res.status_code == 200:
                version_payload = self._json_or_none(version_res)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            details["version_probe"] = str(exc)

        try:
            tags_res = self._request("GET", "/api/tags", read_timeout=8.0)
            if tags_res.status_code != 200:
                detail = self._response_detail(tags_res)
                return {
                    "status": "unavailable",
                    "provider": "ollama",
                    "base_url": self.base_url,
                    "details": detail or f"HTTP {tags_res.status_code}",
                }
            payload = self._json_dict(tags_res, context="tags")
            models = payload.get("models")
            model_count = len(models) if isinstance(models, list) else 0
            if version_payload:
                details["version"] = version_payload
            details["model_count"] = model_count
            return {
                "status": "ok",
                "provider": "ollama",
                "base_url": self.base_url,
                "details": details,
            }
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": self.base_url,
                "details": str(exc),
            }

    def list_models(self) -> Dict[str, Any]:
        try:
            res = self._request("GET", "/api/tags", read_timeout=8.0)
            if res.status_code != 200:
                return {
                    "status": "unavailable",
                    "provider": "ollama",
                    "base_url": self.base_url,
                    "models": [],
                    "details": self._response_detail(res) or f"HTTP {res.status_code}",
                }
            payload = self._json_dict(res, context="tags")
            out: List[Dict[str, Any]] = []
            for item in payload.get("models") or []:
                if not isinstance(item, dict):
                    continue
                out.append(
                    {
                        "name": str(item.get("name") or ""),
                        "size": item.get("size"),
                        "modified": str(item.get("modified_at") or item.get("modified") or ""),
                    }
                )
            return {
                "status": "ok",
                "provider": "ollama",
                "base_url": self.base_url,
                "models": out,
            }
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": self.base_url,
                "models": [],
                "details": str(exc),
            }

    def chat(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        images: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> Dict[str, Any]:
        prompt_text = str(prompt or "").strip()
        if not prompt_text:
            raise ValueError("prompt required")

        selected_model = str(model or "").strip()
        if not selected_model:
            raise ValueError("ollama model is required")

        request_read_timeout = float(self.settings.read_timeout_sec)
        if timeout_sec is not None:
            request_read_timeout = max(1.0, float(timeout_sec))
        meta: Dict[str, Any] = {}

        chat_messages: List[Dict[str, Any]] = []
        if system and str(system).strip():
            chat_messages.append({"role": "system", "content": str(system).strip()})
        user_msg: Dict[str, Any] = {"role": "user", "content": prompt_text}
        if images:
            user_msg["images"] = images
        chat_messages.append(user_msg)

        body: Dict[str, Any] = {"model": selected_model, "messages": chat_messages, "stream": False}
        if temperature is not None:
            body["options"] = {"temperature": float(temperature)}

        chat_payload, chat_err = self._try_endpoint(
            "/api/chat",
            body,
            read_timeout=request_read_timeout,
        )
        if chat_payload is not None:
            text = self._extract_text(chat_payload)
            if text:
                return self._ok_result(
                    text=text,
                    model=selected_model,
                    endpoint="/api/chat",
                    payload=chat_payload,
                )
            meta["chat_error"] = "empty response content"
        if chat_err:
            meta["chat_error"] = chat_err

        generate_body: Dict[str, Any] = {"model": selected_model, "prompt": prompt_text, "stream": False}
        if system and str(system).strip():
            generate_body["system"] = str(system).strip()
        if images:
            generate_body["images"] = images
        if temperature is not None:
            generate_body["options"] = {"temperature": float(temperature)}

        gen_payload, gen_err = self._try_endpoint(
            "/api/generate",
            generate_body,
            read_timeout=request_read_timeout,
        )
        if gen_payload is not None:
            text = self._extract_text(gen_payload)
            if text:
                return self._ok_result(
                    text=text,
                    model=selected_model,
                    endpoint="/api/generate",
                    payload=gen_payload,
                )
            meta["generate_error"] = "empty response content"
        if gen_err:
            meta["generate_error"] = gen_err

        detail = self._first_error(meta) or "Ollama response was empty"
        if self._model_not_found(detail):
            detail = f"Ollama model not available: {selected_model}. Run: ollama pull {selected_model}"

        return {
            "status": "unavailable",
            "provider": "ollama",
            "model": selected_model,
            "text": "",
            "raw_meta": {"base_url": self.base_url, **meta},
            "details": detail,
        }

    def _timeout(self, read_timeout: Optional[float] = None) -> Tuple[float, float]:
        connect_sec = max(0.1, float(self.settings.connect_timeout_sec))
        read_sec = max(1.0, float(read_timeout if read_timeout is not None else self.settings.read_timeout_sec))
        return (connect_sec, read_sec)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        read_timeout: Optional[float] = None,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        try:
            return self.session.request(
                method=str(method or "GET").upper(),
                url=url,
                json=payload,
                timeout=self._timeout(read_timeout),
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama service unreachable at {self.base_url}: {exc}") from exc

    def _try_endpoint(
        self,
        path: str,
        payload: Dict[str, Any],
        *,
        read_timeout: float,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        try:
            res = self._request("POST", path, payload=payload, read_timeout=read_timeout)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            return None, str(exc)

        if res.status_code != 200:
            return None, self._response_detail(res) or f"HTTP {res.status_code}"

        try:
            return self._json_dict(res, context=path), ""
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            return None, str(exc)

    def _ok_result(self, *, text: str, model: str, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "ok",
            "provider": "ollama",
            "model": str(model or "").strip(),
            "text": str(text or "").strip(),
            "raw_meta": {
                "base_url": self.base_url,
                "endpoint": endpoint,
                "done": payload.get("done"),
                "prompt_eval_count": payload.get("prompt_eval_count"),
                "eval_count": payload.get("eval_count"),
                "total_duration": payload.get("total_duration"),
            },
        }

    def _json_dict(self, response: requests.Response, *, context: str) -> Dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama returned invalid JSON for {context}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"Ollama returned unexpected payload for {context}")
        return payload

    def _json_or_none(self, response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _extract_text(self, payload: Dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return ""
        direct = str(payload.get("text") or "").strip()
        if direct:
            return direct
        message = payload.get("message")
        if isinstance(message, dict):
            content = str(message.get("content") or "").strip()
            if content:
                return content
        return str(payload.get("response") or "").strip()

    def _response_detail(self, response: requests.Response) -> str:
        text = str(response.text or "").strip()
        if text:
            return text
        try:
            payload = response.json()
        except ValueError:
            return ""
        return str(payload or "").strip()

    def _first_error(self, meta: Dict[str, Any]) -> str:
        for key in ("generate_error", "chat_error"):
            val = str(meta.get(key) or "").strip()
            if val:
                return val
        return ""

    def _model_not_found(self, detail: str) -> bool:
        low = str(detail or "").lower()
        return "model" in low and ("not found" in low or "pull" in low or "unknown model" in low)

