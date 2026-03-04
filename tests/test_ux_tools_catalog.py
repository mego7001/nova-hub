from pathlib import Path

from core.permission_guard.tool_policy import ToolPolicy
from core.plugin_engine.registry import PluginRegistration, PluginRegistry, ToolRegistration
from core.ux.tools_catalog import build_tools_catalog


def _build_registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register_plugin(
        PluginRegistration(
            plugin_id="test.plugin",
            kind="python",
            name="Test Plugin",
            version="1.0.0",
            entrypoint="tests.stub",
            tool_groups=["fs_read", "process_exec", "fs_write"],
            config={},
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="conversation.chat",
            plugin_id="test.plugin",
            tool_group="fs_read",
            op="conversation_chat",
            handler=lambda **_: {"ok": True},
            description="Chat boundary",
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="verify.smoke",
            plugin_id="test.plugin",
            tool_group="process_exec",
            op="verify",
            handler=lambda **_: {"ok": True},
            description="Run verification",
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="patch.plan",
            plugin_id="test.plugin",
            tool_group="fs_write",
            op="plan",
            handler=lambda **_: {"ok": True},
            description="Create patch candidate",
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="openai.chat",
            plugin_id="test.plugin",
            tool_group="openai",
            op="openai_chat",
            handler=lambda **_: {"ok": True},
            description="OpenAI chat",
        )
    )
    return reg


def test_tools_catalog_groups_and_curated_entries():
    reg = _build_registry()
    policy_path = Path(__file__).resolve().parents[1] / "configs" / "tool_policy.yaml"
    policy = ToolPolicy(str(policy_path), active_profile="engineering", ui_mode=True)
    catalog = build_tools_catalog(reg, policy=policy, project_context=True, task_mode="build_software")

    assert str(catalog.get("task_mode")) == "build_software"
    curated_ids = [str(item.get("id")) for item in catalog.get("curated", [])]
    assert "conversation.chat" in curated_ids
    assert "verify.smoke" in curated_ids
    assert "patch.plan" in curated_ids

    grouped = catalog.get("groups") or []
    group_names = {str(g.get("group")) for g in grouped if isinstance(g, dict)}
    assert "Read" in group_names
    assert "Execution" in group_names
    assert "Write" in group_names


def test_tools_catalog_badges_reflect_policy():
    reg = _build_registry()
    policy_path = Path(__file__).resolve().parents[1] / "configs" / "tool_policy.yaml"
    policy = ToolPolicy(str(policy_path), active_profile="engineering", ui_mode=True)
    catalog = build_tools_catalog(reg, policy=policy, project_context=True, task_mode="build_software")
    by_id = {str(item.get("id")): item for item in catalog.get("advanced", []) if isinstance(item, dict)}

    assert str(by_id["conversation.chat"]["badge"]) == "available"
    assert str(by_id["verify.smoke"]["badge"]) == "approval"
    assert str(by_id["patch.plan"]["badge"]) == "available"
    assert "mode_tags" in by_id["conversation.chat"]


def test_tools_catalog_curated_changes_with_mode():
    reg = _build_registry()
    policy_path = Path(__file__).resolve().parents[1] / "configs" / "tool_policy.yaml"
    policy = ToolPolicy(str(policy_path), active_profile="engineering", ui_mode=True)

    catalog = build_tools_catalog(reg, policy=policy, project_context=True, task_mode="gen_2d_dxf")
    curated_ids = [str(item.get("id")) for item in catalog.get("curated", [])]

    assert "conversation.chat" in curated_ids
    assert "patch.plan" not in curated_ids
    assert "verify.smoke" not in curated_ids


def test_tools_catalog_flags_missing_secret_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reg = _build_registry()
    policy_path = Path(__file__).resolve().parents[1] / "configs" / "tool_policy.yaml"
    policy = ToolPolicy(str(policy_path), active_profile="engineering", ui_mode=True)
    catalog = build_tools_catalog(reg, policy=policy, project_context=True, task_mode="general")
    by_id = {str(item.get("id")): item for item in catalog.get("advanced", []) if isinstance(item, dict)}

    assert str(by_id["openai.chat"]["badge"]) == "unavailable"
    assert str(by_id["openai.chat"]["reason"]).lower().startswith("missing secret/env")
