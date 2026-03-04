from __future__ import annotations

from pathlib import Path
import sys

import pytest

from core.mcp.client import McpClientError, StdioJsonRpcClient


def _echo_server_cmd() -> list[str]:
    root = Path(__file__).resolve().parents[1]
    script = root / "tests" / "helpers" / "mcp_echo_server.py"
    return [sys.executable, str(script)]


def test_mcp_stdio_client_success_roundtrip_uses_mcp_methods() -> None:
    client = StdioJsonRpcClient(cmd=_echo_server_cmd())
    try:
        client.start_server()
        init = client.initialize(timeout_sec=3.0)
        assert isinstance(init, dict)
        assert isinstance(init.get("capabilities"), dict)

        tools = client.list_tools(timeout_sec=3.0)
        assert tools == ["echo", "sleep", "error", "bad_json"]

        out = client.call_tool("echo", {"value": "ok"}, timeout_sec=3.0)
        assert isinstance(out, dict)
        assert out.get("name") == "echo"
        assert out.get("arguments") == {"value": "ok"}
        # Verifies wire method names are MCP-spec names.
        assert out.get("seen_methods")[:3] == ["initialize", "tools/list", "tools/call"]
    finally:
        client.shutdown()


def test_mcp_stdio_client_timeout_raises_timeout_error() -> None:
    client = StdioJsonRpcClient(cmd=_echo_server_cmd())
    try:
        client.start_server()
        client.initialize(timeout_sec=2.0)
        with pytest.raises(TimeoutError):
            client.call_tool("sleep", {"seconds": 0.5}, timeout_sec=0.05)
    finally:
        client.shutdown()


def test_mcp_stdio_client_remote_error_mapping() -> None:
    client = StdioJsonRpcClient(cmd=_echo_server_cmd())
    try:
        client.start_server()
        client.initialize(timeout_sec=2.0)
        with pytest.raises(McpClientError) as err:
            client.call_tool("error", {}, timeout_sec=2.0)
        assert err.value.error_kind == "remote_error"
        assert "forced error" in str(err.value)
    finally:
        client.shutdown()


def test_mcp_stdio_client_protocol_error_mapping() -> None:
    client = StdioJsonRpcClient(cmd=_echo_server_cmd())
    try:
        client.start_server()
        client.initialize(timeout_sec=2.0)
        with pytest.raises(McpClientError) as err:
            client.call_tool("bad_json", {}, timeout_sec=2.0)
        assert err.value.error_kind == "protocol_error"
    finally:
        client.shutdown()


def test_mcp_stdio_client_shutdown_is_graceful() -> None:
    client = StdioJsonRpcClient(cmd=_echo_server_cmd())
    client.start_server()
    client.initialize(timeout_sec=2.0)
    client.shutdown(grace_sec=0.2)
    # Idempotent shutdown should remain safe.
    client.shutdown(grace_sec=0.1)
