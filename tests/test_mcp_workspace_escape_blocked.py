from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any

import pytest

from core.mcp.client import McpClientError, StdioJsonRpcClient
from core.plugin_engine.registry import PluginRegistration, PluginRegistry, ToolRegistration
from core.tooling.invoker import InvokeContext, invoke_tool


class _Runner:
    def execute_registered_tool(self, tool, **kwargs):
        return tool.handler(**kwargs)


def _build_registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register_plugin(
        PluginRegistration(
            plugin_id="escape_test",
            kind="test",
            name="Escape Test",
            version="1.0",
            entrypoint="tests.fake",
            tool_groups=["fs_write"],
            config={},
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="patch.plan",
            plugin_id="escape_test",
            tool_group="fs_write",
            op="patch_plan",
            handler=lambda **_: {"source": "local"},
            default_target="patches",
            description="patch plan",
        )
    )
    return reg


def _write_enabled_cfg(path: Path, *, cmd: str) -> None:
    path.write_text(
        "\n".join(
            [
                "enabled: true",
                "servers:",
                "  patch:",
                f"    cmd: ['{cmd}', '-m', 'mcp_servers.patch_server']",
                "    tools: ['patch.plan', 'patch.apply']",
                "    timeout_sec: 20",
                "    env: {}",
            ]
        ),
        encoding="utf-8",
    )


def test_invoker_blocks_workspace_escape_before_transport(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "mcp_servers.yaml"
    # Intentionally invalid interpreter token to ensure preflight runs before spawn.
    _write_enabled_cfg(cfg_path, cmd="python")
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir(parents=True, exist_ok=True)
    outside.mkdir(parents=True, exist_ok=True)
    escaped_target = workspace / ".." / "outside"

    monkeypatch.setenv("NH_MCP_CONFIG", str(cfg_path))
    monkeypatch.setenv("NH_WORKSPACE", str(workspace))
    monkeypatch.setenv("NH_BASE_DIR", str(Path(__file__).resolve().parents[1]))

    with pytest.raises(PermissionError):
        invoke_tool(
            "patch.plan",
            {"target_root": str(escaped_target), "goal": "x", "write_reports": False},
            InvokeContext(runner=_Runner(), registry=_build_registry()),
        )


def test_patch_server_rejects_workspace_escape_with_remote_error(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir(parents=True, exist_ok=True)
    outside.mkdir(parents=True, exist_ok=True)

    client = StdioJsonRpcClient(
        cmd=[sys.executable, "-m", "mcp_servers.patch_server"],
        env={"NH_WORKSPACE": str(workspace)},
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    try:
        client.start_server()
        client.initialize(timeout_sec=3.0)
        with pytest.raises(McpClientError) as err:
            client.call_tool(
                "patch.plan",
                {"target_root": str(outside), "goal": "escape", "write_reports": False},
                timeout_sec=3.0,
            )
        assert err.value.error_kind == "remote_error"
    finally:
        client.shutdown()


def test_invoker_blocks_symlink_escape_when_supported(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir(parents=True, exist_ok=True)
    outside.mkdir(parents=True, exist_ok=True)
    link_path = workspace / "link_out"
    try:
        os.symlink(str(outside), str(link_path), target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this host")

    cfg_path = tmp_path / "mcp_servers.yaml"
    _write_enabled_cfg(cfg_path, cmd="python")
    monkeypatch.setenv("NH_MCP_CONFIG", str(cfg_path))
    monkeypatch.setenv("NH_WORKSPACE", str(workspace))
    monkeypatch.setenv("NH_BASE_DIR", str(Path(__file__).resolve().parents[1]))

    with pytest.raises(PermissionError):
        invoke_tool(
            "patch.plan",
            {"target_root": str(link_path), "goal": "via-link", "write_reports": False},
            InvokeContext(runner=_Runner(), registry=_build_registry()),
        )
