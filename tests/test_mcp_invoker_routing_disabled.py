from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from core.plugin_engine.registry import PluginRegistration, PluginRegistry, ToolRegistration
from core.tooling.invoker import InvokeContext, invoke_tool


class _Runner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute_registered_tool(self, tool, **kwargs):
        self.calls.append({"tool_id": str(tool.tool_id), "kwargs": dict(kwargs)})
        return tool.handler(**kwargs)


def _write_cfg(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "enabled: false",
                "servers:",
                "  patch:",
                "    cmd: ['python', '-m', 'mcp_servers.patch_server']",
                "    tools: ['patch.plan', 'patch.apply']",
                "    timeout_sec: 90",
                "    env: {}",
            ]
        ),
        encoding="utf-8",
    )


def _registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register_plugin(
        PluginRegistration(
            plugin_id="test_patch",
            kind="test",
            name="Test Patch",
            version="1.0",
            entrypoint="tests.fake",
            tool_groups=["fs_write"],
            config={},
        )
    )

    def _patch_plan(goal: str, target_root: str = ".", write_reports: bool = False) -> Dict[str, Any]:
        return {"ok": True, "goal": goal, "target_root": target_root, "write_reports": write_reports, "source": "local"}

    reg.register_tool(
        ToolRegistration(
            tool_id="patch.plan",
            plugin_id="test_patch",
            tool_group="fs_write",
            op="patch_plan",
            handler=_patch_plan,
            default_target="patches",
            description="local patch plan",
        )
    )
    return reg


def test_invoker_routes_to_local_when_mcp_disabled(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "mcp_servers.yaml"
    _write_cfg(cfg_path)
    monkeypatch.setenv("NH_MCP_CONFIG", str(cfg_path))

    reg = _registry()
    runner = _Runner()
    out = invoke_tool(
        "patch.plan",
        {"goal": "Harden gitignore", "target_root": str(tmp_path), "write_reports": False},
        InvokeContext(runner=runner, registry=reg),
    )
    assert out == {
        "ok": True,
        "goal": "Harden gitignore",
        "target_root": str(tmp_path),
        "write_reports": False,
        "source": "local",
    }
    assert runner.calls
    assert runner.calls[0]["tool_id"] == "patch.plan"
