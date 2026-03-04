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


def _write_enabled_cfg(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "enabled: true",
                "servers:",
                "  patch:",
                "    cmd: ['python', '-m', 'mcp_servers.patch_server']",
                "    tools: ['patch.plan', 'patch.apply']",
                "    timeout_sec: 30",
                "    env: {}",
            ]
        ),
        encoding="utf-8",
    )


def _build_registry(local_patch_calls: list[str], local_other_calls: list[str]) -> PluginRegistry:
    reg = PluginRegistry()
    reg.register_plugin(
        PluginRegistration(
            plugin_id="test_mcp_enabled",
            kind="test",
            name="MCP Enabled Test",
            version="1.0",
            entrypoint="tests.fake",
            tool_groups=["fs_write", "fs_read"],
            config={},
        )
    )

    def _local_patch_plan(goal: str, target_root: str = ".", write_reports: bool = False) -> Dict[str, Any]:
        local_patch_calls.append(goal)
        return {"source": "local_patch", "goal": goal, "target_root": target_root, "write_reports": write_reports}

    def _local_other(value: str) -> Dict[str, Any]:
        local_other_calls.append(value)
        return {"source": "local_other", "value": value}

    reg.register_tool(
        ToolRegistration(
            tool_id="patch.plan",
            plugin_id="test_mcp_enabled",
            tool_group="fs_write",
            op="patch_plan",
            handler=_local_patch_plan,
            default_target="patches",
            description="local fallback patch plan",
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="test.local",
            plugin_id="test_mcp_enabled",
            tool_group="fs_read",
            op="local_echo",
            handler=_local_other,
            default_target=None,
            description="non-mapped local tool",
        )
    )
    return reg


def test_invoker_routes_patch_to_mcp_when_enabled_and_keeps_nonmapped_local(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "mcp_servers.yaml"
    _write_enabled_cfg(cfg_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / "projects" / "projA" / "working"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")

    monkeypatch.setenv("NH_MCP_CONFIG", str(cfg_path))
    monkeypatch.setenv("NH_WORKSPACE", str(workspace))
    monkeypatch.setenv("NH_BASE_DIR", str(Path(__file__).resolve().parents[1]))

    patch_local_calls: list[str] = []
    other_local_calls: list[str] = []
    reg = _build_registry(patch_local_calls, other_local_calls)
    runner = _Runner()

    patch_out = invoke_tool(
        "patch.plan",
        {"target_root": str(project_dir), "goal": "Harden gitignore", "write_reports": False},
        InvokeContext(runner=runner, registry=reg),
    )
    assert isinstance(patch_out, dict)
    assert patch_out.get("goal") == "Harden gitignore"
    assert str(patch_out.get("diff_path") or "").strip()
    # MCP route should not execute the local patch handler.
    assert patch_local_calls == []

    local_out = invoke_tool(
        "test.local",
        {"value": "stay-local"},
        InvokeContext(runner=runner, registry=reg),
    )
    assert local_out == {"source": "local_other", "value": "stay-local"}
    assert other_local_calls == ["stay-local"]
