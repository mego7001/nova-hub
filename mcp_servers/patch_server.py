from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, Optional

from core.mcp.security import resolve_workspace_root, validate_patch_workspace_constraints
from integrations.patch_apply.plugin import create_patch_apply_handler
from integrations.patch_planner.plugin import create_patch_plan_handler


ToolHandler = Callable[..., Dict[str, Any]]


def _write(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _ok(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "error": {"code": int(code), "message": str(message)}}
    if data is not None:
        payload["error"]["data"] = data
    return payload


def _build_handlers() -> Dict[str, ToolHandler]:
    return {
        "patch.plan": create_patch_plan_handler({}),
        "patch.apply": create_patch_apply_handler({}),
    }


def main() -> int:
    handlers = _build_handlers()
    workspace_root = resolve_workspace_root()

    for raw in sys.stdin:
        line = str(raw or "").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _write(_error(None, -32700, "Parse error"))
            continue
        if not isinstance(req, dict):
            _write(_error(None, -32600, "Invalid Request"))
            continue

        req_id = req.get("id")
        if str(req.get("jsonrpc") or "") != "2.0":
            _write(_error(req_id, -32600, "Invalid Request"))
            continue

        method = str(req.get("method") or "").strip()
        params = req.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            _write(_error(req_id, -32602, "Invalid params"))
            continue

        if method == "initialize":
            _write(
                _ok(
                    req_id,
                    {
                        "serverInfo": {"name": "nova-mcp-patch-server", "version": "1"},
                        "capabilities": {"tools": {"supported": sorted(handlers.keys())}},
                    },
                )
            )
            continue

        if method == "tools/list":
            _write(_ok(req_id, sorted(handlers.keys())))
            continue

        if method != "tools/call":
            _write(_error(req_id, -32601, "Method not found"))
            continue

        name = str(params.get("name") or "").strip()
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            _write(_error(req_id, -32602, "Invalid params: arguments must be an object"))
            continue
        handler = handlers.get(name)
        if handler is None:
            _write(_error(req_id, -32602, f"Unknown tool: {name}"))
            continue

        try:
            validate_patch_workspace_constraints(name, arguments, workspace_root=workspace_root)
            result = handler(**arguments)
        except Exception as exc:  # noqa: BLE001
            _write(_error(req_id, -32000, str(exc)))
            continue
        _write(_ok(req_id, result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
