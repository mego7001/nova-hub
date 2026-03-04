from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration


def _key(cfg: Dict[str, Any]) -> str:
    return (cfg.get("api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    model = str(config.get("model") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini")
    base_url = str(config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    timeout = int(config.get("timeout_sec") or 45)

    def chat(prompt: str, system: Optional[str] = None, temperature: Optional[float] = None) -> Dict[str, Any]:
        key = _key(config)
        if not key:
            raise RuntimeError("OPENAI_API_KEY missing")
        if not prompt.strip():
            raise ValueError("prompt required")

        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        messages = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt.strip()})
        body: Dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            body["temperature"] = float(temperature)

        r = requests.post(url, headers=headers, json=body, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI API error {r.status_code}: {r.text}")
        return r.json()

    registry.register_tool(
        ToolRegistration(
            "openai.chat",
            manifest.id,
            "openai",
            "openai_chat",
            chat,
            "OpenAI chat.completions (approval)",
            model,
        )
    )
