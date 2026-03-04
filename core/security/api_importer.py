from __future__ import annotations
import json
import re
from typing import Dict, Any, Optional

from core.security.secrets import SecretsManager
from core.tooling.invoker import InvokeContext, invoke_tool

_ALLOWED = {
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_DEFAULT_CHAT_ID",
}


class ApiImporter:
    def __init__(self, secrets: SecretsManager, runner=None, registry=None):
        self.secrets = secrets
        self.runner = runner
        self.registry = registry

    def import_from_text(self, text: str) -> int:
        data = self.detect_keys(text)
        count = 0
        for k, v in data.items():
            if k in _ALLOWED and v:
                self.secrets.set_temp(k, v)
                count += 1
        return count

    def detect_keys(self, text: str) -> Dict[str, str]:
        return self._parse_text(text)

    def persist_keys(self, data: Dict[str, str]) -> None:
        tool = self.registry.tools.get("fs.write_text") if self.registry else None
        if tool and self.runner:
            invoke_ctx = InvokeContext(runner=self.runner, registry=self.registry, mode="")

            def _writer(path: str, text: str) -> None:
                invoke_tool("fs.write_text", {"path": path, "text": text, "target": path}, invoke_ctx)

            self.secrets.set_persist_bulk(data, writer=_writer)
            return
        raise RuntimeError("fs.write_text tool required to persist keys")

    def _parse_text(self, text: str) -> Dict[str, str]:
        found: Dict[str, str] = {}
        # JSON object
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in _ALLOWED and isinstance(v, str):
                        found[k] = v
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

        # KEY=VALUE or KEY: VALUE lines
        for line in text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
            elif ":" in line:
                k, v = line.split(":", 1)
            else:
                continue
            k = k.strip()
            v = v.strip().strip("\"").strip("'")
            if k in _ALLOWED and v:
                found[k] = v


        # Heuristic detections (unlabeled)
        if "OPENAI_API_KEY" not in found:
            m = re.search(r"sk-[A-Za-z0-9\-_]{16,}", text)
            if m and "DEEPSEEK_API_KEY" not in found:
                found["DEEPSEEK_API_KEY"] = m.group(0)
        m2 = re.search(r"AIza[\w-]{10,}", text)
        if m2 and "GEMINI_API_KEY" not in found:
            found["GEMINI_API_KEY"] = m2.group(0)
        m3 = re.search(r"\b\d{6,12}:[\w-]{20,}\b", text)
        if m3 and "TELEGRAM_BOT_TOKEN" not in found:
            found["TELEGRAM_BOT_TOKEN"] = m3.group(0)

        if "TELEGRAM_CHAT_ID" in found and "TELEGRAM_DEFAULT_CHAT_ID" not in found:
            found["TELEGRAM_DEFAULT_CHAT_ID"] = found["TELEGRAM_CHAT_ID"]
        return found

    @staticmethod
    def redact_map(values: Dict[str, str]) -> Dict[str, str]:
        return {k: SecretsManager.redact_value(v) for k, v in values.items()}
