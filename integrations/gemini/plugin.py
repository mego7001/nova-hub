from __future__ import annotations
import os, requests
from typing import Any, Dict, Optional
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration

def _key(cfg: Dict[str,Any])->str:
    return (cfg.get("api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()

def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    model = str(config.get("model") or os.environ.get("GEMINI_MODEL") or "gemini-1.5-pro")
    timeout = int(config.get("timeout_sec") or 40)

    def prompt(text: str, system: Optional[str]=None, temperature: Optional[float]=None)->Dict[str,Any]:
        key = _key(config)
        if not key: raise RuntimeError("GEMINI_API_KEY missing")
        if not text.strip(): raise ValueError("text required")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        parts=[]
        if system and system.strip(): parts.append({"text": system.strip()})
        parts.append({"text": text.strip()})
        body={"contents":[{"parts":parts}]}
        if temperature is not None:
            body["generationConfig"]={"temperature": float(temperature)}
        r = requests.post(url, json=body, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"Gemini API error {r.status_code}: {r.text}")
        return r.json()

    registry.register_tool(ToolRegistration("gemini.prompt", manifest.id, "gemini", "gemini_prompt", prompt, "Gemini generateContent (approval)", model))
