from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.llm.ollama_config import (
    DEFAULT_OLLAMA_MODEL_GENERAL,
    load_ollama_settings,
)
from core.llm.providers.ollama_http import OllamaHttpClient
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    settings = load_ollama_settings(config)
    client = OllamaHttpClient(settings=settings)
    default_model = str(settings.model_general or DEFAULT_OLLAMA_MODEL_GENERAL).strip()

    def chat(
        prompt: str,
        system: Optional[str] = None,
        images: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> Dict[str, Any]:
        selected_model = str(model or default_model or "").strip()
        return client.chat(
            prompt=prompt,
            system=system,
            images=images,
            temperature=temperature,
            model=selected_model,
            timeout_sec=timeout_sec,
        )

    def health_ping() -> Dict[str, Any]:
        return client.health_ping()

    def models_list() -> Dict[str, Any]:
        return client.list_models()

    registry.register_tool(
        ToolRegistration(
            "ollama.health.ping",
            manifest.id,
            "ollama",
            "ollama_health_ping",
            health_ping,
            "Ollama local health ping",
            settings.base_url,
        )
    )
    registry.register_tool(
        ToolRegistration(
            "ollama.models.list",
            manifest.id,
            "ollama",
            "ollama_models_list",
            models_list,
            "Ollama local model list",
            settings.base_url,
        )
    )
    registry.register_tool(
        ToolRegistration(
            "ollama.chat",
            manifest.id,
            "ollama",
            "ollama_chat",
            chat,
            f"Ollama local chat (model={default_model})",
            default_model,
        )
    )
