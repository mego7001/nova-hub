from __future__ import annotations

import inspect
import os
import time
from types import SimpleNamespace
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.mcp.client import StdioJsonRpcClient
from core.mcp.config import McpServerConfig, load_mcp_servers_config
from core.mcp.security import resolve_workspace_root, validate_patch_workspace_constraints
from core.telemetry.recorders import classify_error_kind
from core.tooling.trace import ToolCallTrace, ToolTraceRecorder, utc_now_iso


@dataclass(frozen=True)
class InvokeContext:
    runner: Any
    registry: Any
    trace_recorder: Optional[ToolTraceRecorder] = None
    request_id: str = ""
    session_id: str = ""
    project_id: str = ""
    mode: str = ""
    provider: str = "local"
    server_name: str = ""


def _supports_target(handler: Any) -> bool:
    try:
        sig = inspect.signature(handler)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False
    if "target" in sig.parameters:
        return True
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return False


def _prepare_payload(tool: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})
    if "target" in out:
        return out
    default_target = getattr(tool, "default_target", None)
    if default_target is None:
        return out
    handler = getattr(tool, "handler", None)
    if handler is None:
        return out
    if _supports_target(handler):
        out["target"] = default_target
    return out


def _resolve_recorder(ctx: InvokeContext) -> Optional[ToolTraceRecorder]:
    if ctx.trace_recorder is not None:
        return ctx.trace_recorder
    candidate = getattr(ctx.runner, "_tool_trace_recorder", None)
    return candidate if isinstance(candidate, ToolTraceRecorder) else None


def _resolve_mcp_route(tool_id: str) -> Optional[tuple[str, McpServerConfig]]:
    cfg = load_mcp_servers_config()
    if not cfg.enabled:
        return None
    server_name = str(cfg.tool_to_server.get(tool_id) or "").strip()
    if not server_name:
        return None
    server_cfg = cfg.servers.get(server_name)
    if server_cfg is None:
        raise RuntimeError(f"MCP server mapping missing config: tool={tool_id}, server={server_name}")
    return server_name, server_cfg


def _invoke_via_mcp_with_runner_approvals(
    *,
    tool: Any,
    tool_id: str,
    kwargs: Dict[str, Any],
    ctx: InvokeContext,
    server_name: str,
    server_cfg: McpServerConfig,
) -> Any:
    if not server_cfg.cmd:
        raise RuntimeError(f"MCP server command is empty: {server_name}")
    timeout_sec = max(1, int(server_cfg.timeout_sec))
    workspace_root = resolve_workspace_root(os.environ.get("NH_WORKSPACE"))
    base_dir = str(os.environ.get("NH_BASE_DIR") or os.getcwd())
    mcp_env = dict(server_cfg.env or {})
    mcp_env.setdefault("NH_WORKSPACE", workspace_root)
    if base_dir:
        mcp_env.setdefault("NH_BASE_DIR", base_dir)

    def _proxy_handler(**handler_kwargs: Any) -> Any:
        if tool_id in {"patch.plan", "patch.apply"}:
            validate_patch_workspace_constraints(tool_id, handler_kwargs, workspace_root=workspace_root)
        client = StdioJsonRpcClient(cmd=list(server_cfg.cmd), env=mcp_env, cwd=base_dir)
        try:
            client.start_server()
            client.initialize(timeout_sec=float(timeout_sec))
            return client.call_tool(tool_id, dict(handler_kwargs), timeout_sec=float(timeout_sec))
        finally:
            client.shutdown(grace_sec=min(5.0, max(0.2, float(timeout_sec) / 3.0)))

    proxy_tool = SimpleNamespace(
        tool_id=str(getattr(tool, "tool_id", tool_id)),
        tool_group=str(getattr(tool, "tool_group", "")),
        op=str(getattr(tool, "op", "")),
        default_target=getattr(tool, "default_target", None),
        handler=_proxy_handler,
    )
    return ctx.runner.execute_registered_tool(proxy_tool, **kwargs)


def invoke_tool(tool_id: str, payload: Dict[str, Any], ctx: InvokeContext) -> Any:
    tid = str(tool_id or "").strip()
    tool = ctx.registry.tools.get(tid)
    if tool is None:
        raise ValueError(f"Tool not found: {tid}")

    request_id = str(ctx.request_id or uuid.uuid4().hex)
    trace_id = uuid.uuid4().hex
    start_ts = utc_now_iso()
    started = time.perf_counter()
    recorder = _resolve_recorder(ctx)
    kwargs = _prepare_payload(tool, dict(payload or {}))
    trace_provider = str(ctx.provider or "local")
    trace_server_name = str(ctx.server_name or "")

    try:
        route = _resolve_mcp_route(tid)
        if route is None:
            result = ctx.runner.execute_registered_tool(tool, **kwargs)
        else:
            server_name, server_cfg = route
            trace_provider = "mcp"
            trace_server_name = server_name
            result = _invoke_via_mcp_with_runner_approvals(
                tool=tool,
                tool_id=tid,
                kwargs=kwargs,
                ctx=ctx,
                server_name=server_name,
                server_cfg=server_cfg,
            )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        if recorder is not None:
            recorder.append(
                ToolCallTrace(
                    trace_id=trace_id,
                    request_id=request_id,
                    tool_id=tid,
                    provider=trace_provider,
                    server_name=trace_server_name,
                    start_ts=start_ts,
                    end_ts=utc_now_iso(),
                    latency_ms=latency_ms,
                    ok=False,
                    error_kind=classify_error_kind(exc),
                    error_msg=str(exc),
                    session_id=str(ctx.session_id or ""),
                    project_id=str(ctx.project_id or ""),
                    mode=str(ctx.mode or ""),
                )
            )
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    if recorder is not None:
        recorder.append(
            ToolCallTrace(
                trace_id=trace_id,
                request_id=request_id,
                tool_id=tid,
                provider=trace_provider,
                server_name=trace_server_name,
                start_ts=start_ts,
                end_ts=utc_now_iso(),
                latency_ms=latency_ms,
                ok=True,
                error_kind="",
                error_msg="",
                session_id=str(ctx.session_id or ""),
                project_id=str(ctx.project_id or ""),
                mode=str(ctx.mode or ""),
            )
        )
    return result
