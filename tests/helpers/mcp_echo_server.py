from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, Optional


def _write(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _ok(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "error": {"code": int(code), "message": str(message)}}
    if data is not None:
        payload["error"]["data"] = data
    return payload


def main() -> int:
    seen_methods: list[str] = []
    for raw in sys.stdin:
        line = str(raw or "").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _write(_err(None, -32700, "Parse error"))
            continue
        if not isinstance(req, dict):
            _write(_err(None, -32600, "Invalid Request"))
            continue

        req_id = req.get("id")
        if str(req.get("jsonrpc") or "") != "2.0":
            _write(_err(req_id, -32600, "Invalid Request"))
            continue

        method = str(req.get("method") or "").strip()
        seen_methods.append(method)

        if method == "initialize":
            _write(
                _ok(
                    req_id,
                    {
                        "serverInfo": {"name": "mcp-echo-server", "version": "1"},
                        "capabilities": {"tools": {"supported": ["echo", "sleep", "error", "bad_json"]}},
                    },
                )
            )
            continue
        if method == "tools/list":
            _write(_ok(req_id, ["echo", "sleep", "error", "bad_json"]))
            continue
        if method == "tools/call":
            params = req.get("params")
            if not isinstance(params, dict):
                _write(_err(req_id, -32602, "Invalid params"))
                continue
            name = str(params.get("name") or "")
            args = params.get("arguments")
            if not isinstance(args, dict):
                _write(_err(req_id, -32602, "arguments must be object"))
                continue
            if name == "sleep":
                time.sleep(max(0.0, float(args.get("seconds") or 0.0)))
                _write(_ok(req_id, {"ok": True}))
                continue
            if name == "error":
                _write(_err(req_id, -32010, "forced error"))
                continue
            if name == "bad_json":
                sys.stdout.write("not-json\n")
                sys.stdout.flush()
                continue
            _write(_ok(req_id, {"name": name, "arguments": args, "seen_methods": list(seen_methods)}))
            continue

        _write(_err(req_id, -32601, "Method not found"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
