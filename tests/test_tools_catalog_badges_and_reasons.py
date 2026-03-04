from __future__ import annotations

from core.plugin_engine.registry import PluginRegistration, PluginRegistry, ToolRegistration
from core.ux.tools_catalog import build_tools_catalog


def _registry_with_tools() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register_plugin(
        PluginRegistration(
            plugin_id="t",
            kind="python",
            name="t",
            version="1.0.0",
            entrypoint="tests",
            tool_groups=["fs_read"],
            config={},
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="patch.plan",
            plugin_id="t",
            tool_group="fs_read",
            op="plan",
            handler=lambda **_: {"ok": True},
            description="plan",
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="cad.step.generate",
            plugin_id="t",
            tool_group="fs_read",
            op="step",
            handler=lambda **_: {"ok": True},
            description="step",
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="deepseek.chat",
            plugin_id="t",
            tool_group="fs_read",
            op="deepseek_chat",
            handler=lambda **_: {"ok": True},
            description="deepseek",
        )
    )
    return reg


def test_tools_catalog_reports_context_mismatch_reason():
    catalog = build_tools_catalog(_registry_with_tools(), policy=None, project_context=False, task_mode="general")
    by_id = {str(item.get("id")): item for item in catalog.get("advanced") or [] if isinstance(item, dict)}

    assert str(by_id["patch.plan"]["badge"]) == "unavailable"
    assert "context mismatch" in str(by_id["patch.plan"]["reason"]).lower()


def test_tools_catalog_reports_missing_dependency_reason(monkeypatch):
    monkeypatch.setattr(
        "core.ux.tools_catalog.importlib.util.find_spec",
        lambda name: None if str(name) == "cadquery" else object(),
    )
    catalog = build_tools_catalog(_registry_with_tools(), policy=None, project_context=True, task_mode="gen_3d_step")
    by_id = {str(item.get("id")): item for item in catalog.get("advanced") or [] if isinstance(item, dict)}

    assert str(by_id["cad.step.generate"]["badge"]) == "unavailable"
    assert "missing dependency" in str(by_id["cad.step.generate"]["reason"]).lower()


def test_tools_catalog_reports_missing_secret_reason(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    catalog = build_tools_catalog(_registry_with_tools(), policy=None, project_context=True, task_mode="general")
    by_id = {str(item.get("id")): item for item in catalog.get("advanced") or [] if isinstance(item, dict)}

    assert str(by_id["deepseek.chat"]["badge"]) == "unavailable"
    assert str(by_id["deepseek.chat"]["reason"]).lower().startswith("missing secret/env")
