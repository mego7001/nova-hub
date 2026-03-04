from __future__ import annotations

from core.plugin_engine.registry import PluginRegistry
from core.ux.task_modes import allowed_user_task_modes, auto_fallback_mode, is_auto_mode


def test_auto_mode_helpers_and_row():
    reg = PluginRegistry()
    rows = allowed_user_task_modes(reg, include_unavailable=False)
    assert rows
    assert str(rows[0].get("id") or "") == "auto"
    assert is_auto_mode("AUTO") is True


def test_auto_mode_fallback_prefers_build_software_in_project_context():
    reg = PluginRegistry()
    reg.tools["conversation.chat"] = object()  # type: ignore[index]
    picked = auto_fallback_mode(reg, project_context=True)
    assert picked == "build_software"


def test_auto_mode_fallback_defaults_to_general_without_tools():
    reg = PluginRegistry()
    picked = auto_fallback_mode(reg, project_context=False)
    assert picked == "general"
