from __future__ import annotations
import os, requests
from typing import Any, Dict, Optional
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration

def _token(cfg: Dict[str,Any])->str:
    return (cfg.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()

def _chat(cfg: Dict[str,Any])->str:
    return (cfg.get("default_chat_id") or os.environ.get("TELEGRAM_DEFAULT_CHAT_ID") or "").strip()

def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    timeout = int(config.get("timeout_sec") or 20)

    def send(text: str, chat_id: Optional[str]=None, parse_mode: Optional[str]=None)->Dict[str,Any]:
        t = _token(config)
        if not t: raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
        cid = (chat_id or _chat(config)).strip()
        if not cid: raise RuntimeError("Telegram chat_id missing")
        if not text.strip(): raise ValueError("text required")
        url = f"https://api.telegram.org/bot{t}/sendMessage"
        payload = {"chat_id": cid, "text": text}
        if parse_mode: payload["parse_mode"]=parse_mode
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"Telegram API error {r.status_code}: {r.text}")
        return r.json()

    registry.register_tool(ToolRegistration("telegram.send", manifest.id, "telegram", "telegram_send", send, "Send Telegram message (approval)", None))
