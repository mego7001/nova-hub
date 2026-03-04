from __future__ import annotations
import os
import re
from typing import Dict, Optional, Callable

from core.portable.paths import detect_base_dir, default_workspace_dir


class SecretsManager:
    def __init__(self, env_path: Optional[str] = None, workspace_root: Optional[str] = None):
        self.env_path = env_path or self._default_env_path(workspace_root)
        self._memory: Dict[str, str] = {}
        self._persisted: Dict[str, str] = {}
        self._load_persisted()

    def get(self, key: str) -> Optional[str]:
        v = os.environ.get(key)
        if v:
            return v
        return self._memory.get(key)

    def set_temp(self, key: str, value: str) -> None:
        self._memory[key] = value
        os.environ[key] = value
        if key == "TELEGRAM_CHAT_ID" and "TELEGRAM_DEFAULT_CHAT_ID" not in self._memory:
            self._memory["TELEGRAM_DEFAULT_CHAT_ID"] = value
            os.environ.setdefault("TELEGRAM_DEFAULT_CHAT_ID", value)

    def clear_temp(self, key: str) -> None:
        val = self._memory.pop(key, None)
        if key not in self._persisted and val is not None:
            if os.environ.get(key) == val:
                os.environ.pop(key, None)
        if key == "TELEGRAM_CHAT_ID" and "TELEGRAM_DEFAULT_CHAT_ID" in self._memory:
            if "TELEGRAM_DEFAULT_CHAT_ID" not in self._persisted:
                dv = self._memory.pop("TELEGRAM_DEFAULT_CHAT_ID", None)
                if dv is not None and os.environ.get("TELEGRAM_DEFAULT_CHAT_ID") == dv:
                    os.environ.pop("TELEGRAM_DEFAULT_CHAT_ID", None)

    def temp_keys(self) -> Dict[str, str]:
        return dict(self._memory)

    def has_persisted(self, key: str) -> bool:
        return key in self._persisted

    def has_temp_only(self, key: str) -> bool:
        return key in self._memory and key not in self._persisted

    def set_persist(self, key: str, value: str, writer: Optional[Callable[[str, str], None]] = None) -> None:
        if writer is None:
            raise ValueError("Persisting secrets requires an approved writer callback")
        new_content = self._update_env_content({key: value})
        writer(self.env_path, new_content)
        os.environ[key] = value
        self._memory[key] = value
        self._persisted[key] = value

    def set_persist_bulk(self, values: Dict[str, str], writer: Optional[Callable[[str, str], None]] = None) -> None:
        if writer is None:
            raise ValueError("Persisting secrets requires an approved writer callback")
        new_content = self._update_env_content(values)
        writer(self.env_path, new_content)
        for k, v in values.items():
            os.environ[k] = v
            self._memory[k] = v
            self._persisted[k] = v

    def _update_env_content(self, values: Dict[str, str]) -> str:
        if os.path.exists(self.env_path):
            with open(self.env_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            text = ""
        lines = text.splitlines()
        seen = set()
        out = []
        for line in lines:
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                out.append(line)
                continue
            k, _v = line.split("=", 1)
            k = k.strip()
            if k in values:
                out.append(f"{k}={values[k]}")
                seen.add(k)
            else:
                out.append(line)
        for k, v in values.items():
            if k not in seen:
                out.append(f"{k}={v}")
        return "\n".join(out) + ("\n" if text.endswith("\n") or not text else "")

    def _default_env_path(self, workspace_root: Optional[str]) -> str:
        base = detect_base_dir()
        workspace = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
        return os.path.join(workspace, "secrets", ".env")

    def _load_persisted(self) -> None:
        if not os.path.exists(self.env_path):
            return
        try:
            with open(self.env_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return
        for line in lines:
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                self._memory[k] = v
                os.environ.setdefault(k, v)
                self._persisted[k] = v
        if "TELEGRAM_CHAT_ID" in self._memory and "TELEGRAM_DEFAULT_CHAT_ID" not in self._memory:
            v = self._memory["TELEGRAM_CHAT_ID"]
            self._memory["TELEGRAM_DEFAULT_CHAT_ID"] = v
            os.environ.setdefault("TELEGRAM_DEFAULT_CHAT_ID", v)
            self._persisted["TELEGRAM_DEFAULT_CHAT_ID"] = v

    @staticmethod
    def redact_value(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "****"
        return "****" + value[-4:]

    @staticmethod
    def redact_text(text: str, keys: Optional[Dict[str, str]] = None) -> str:
        redacted = text
        if keys:
            for k, v in keys.items():
                if not v:
                    continue
                redacted = redacted.replace(v, SecretsManager.redact_value(v))
        for key in [
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_DEFAULT_CHAT_ID",
            "GEMINI_API_KEY",
            "DEEPSEEK_API_KEY",
        ]:
            redacted = re.sub(rf"({key}\s*=\s*)([^\s]+)", r"\1[REDACTED]", redacted)
        return redacted
