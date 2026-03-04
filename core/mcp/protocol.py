from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional, Tuple


class JsonRpcProtocolError(ValueError):
    pass


def build_request(method: str, params: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None) -> Dict[str, Any]:
    m = str(method or "").strip()
    if not m:
        raise JsonRpcProtocolError("JSON-RPC method is required")
    rid = str(request_id or uuid.uuid4().hex)
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": m}
    if params is not None:
        payload["params"] = params
    return payload


def dump_message(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def parse_line(line: str | bytes) -> Dict[str, Any]:
    text = line.decode("utf-8", errors="replace") if isinstance(line, (bytes, bytearray)) else str(line or "")
    text = text.strip()
    if not text:
        raise JsonRpcProtocolError("Empty JSON-RPC line")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JsonRpcProtocolError(f"Invalid JSON-RPC line: {exc}") from exc
    if not isinstance(raw, dict):
        raise JsonRpcProtocolError("JSON-RPC payload must be an object")
    return raw


def validate_response(payload: Dict[str, Any], expected_id: str) -> Tuple[Any, Optional[Dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise JsonRpcProtocolError("JSON-RPC response must be an object")
    if str(payload.get("jsonrpc") or "") != "2.0":
        raise JsonRpcProtocolError("JSON-RPC version must be 2.0")
    if str(payload.get("id")) != str(expected_id):
        raise JsonRpcProtocolError(f"JSON-RPC response id mismatch: expected={expected_id} got={payload.get('id')}")

    has_result = "result" in payload
    has_error = "error" in payload
    if has_result == has_error:
        raise JsonRpcProtocolError("JSON-RPC response must include exactly one of result or error")

    if has_error:
        error_obj = payload.get("error")
        if not isinstance(error_obj, dict):
            raise JsonRpcProtocolError("JSON-RPC error must be an object")
        return None, error_obj
    return payload.get("result"), None
