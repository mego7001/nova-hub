from __future__ import annotations
import os
from typing import Any, Dict

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.chat.orchestrator import ChatOrchestrator, OrchestratorFactory, build_default_runner

_UI_CONTEXT: Dict[str, Any] = {}
_FACTORY: OrchestratorFactory | None = None


def set_ui_context(runner, registry, project_root: str) -> None:
    _UI_CONTEXT["runner"] = runner
    _UI_CONTEXT["registry"] = registry
    _UI_CONTEXT["project_root"] = project_root


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def _get_orchestrator() -> ChatOrchestrator:
        global _FACTORY
        if _UI_CONTEXT.get("runner") and _UI_CONTEXT.get("registry") and _UI_CONTEXT.get("project_root"):
            if _FACTORY is None:
                _FACTORY = OrchestratorFactory(_UI_CONTEXT["project_root"])
            return _FACTORY.get(_UI_CONTEXT["runner"], _UI_CONTEXT["registry"])

        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        runner, reg = build_default_runner(root)
        if _FACTORY is None:
            _FACTORY = OrchestratorFactory(root)
        return _FACTORY.get(runner, reg)

    def conversation_chat(
        user_message: str,
        project_path: str,
        session_id: str = "default",
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        orchestrator = _get_orchestrator()
        return orchestrator.handle_message(
            user_message=user_message,
            project_path=project_path,
            session_id=session_id,
            write_reports=write_reports,
        )

    registry.register_tool(
        ToolRegistration(
            tool_id="conversation.chat",
            plugin_id=manifest.id,
            tool_group="fs_read",
            op="conversation_chat",
            handler=conversation_chat,
            description="Rule-based chat assistant for Nova Hub",
            default_target=None,
        )
    )
