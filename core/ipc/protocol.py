from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17840
DEFAULT_EVENTS_PORT = DEFAULT_PORT + 1
MAX_MESSAGE_BYTES = 2 * 1024 * 1024


def ipc_enabled() -> bool:
    raw = str(os.environ.get("NH_IPC_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def resolve_ipc_port(port: int | None = None) -> int:
    if port is not None:
        return int(port)
    raw = str(os.environ.get("NH_IPC_PORT") or "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        value = int(raw)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return DEFAULT_PORT
    return value if value > 0 else DEFAULT_PORT


def resolve_ipc_events_port(port: int | None = None, *, rpc_port: int | None = None) -> int:
    if port is not None:
        return int(port)
    raw = str(os.environ.get("NH_IPC_EVENTS_PORT") or "").strip()
    if raw:
        try:
            value = int(raw)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            value = 0
        if value > 0:
            return value
    resolved_rpc = resolve_ipc_port(rpc_port)
    fallback = resolved_rpc + 1
    return fallback if fallback > 0 else DEFAULT_EVENTS_PORT


def resolve_ipc_token() -> str:
    return str(os.environ.get("NH_IPC_TOKEN") or "").strip()


def make_request(op: str, payload: Dict[str, Any] | None = None, req_id: str | None = None) -> Dict[str, Any]:
    return {
        "type": "request",
        "id": str(req_id or uuid.uuid4().hex),
        "op": str(op or ""),
        "payload": dict(payload or {}),
    }


def make_response(
    req_id: str,
    *,
    ok: bool,
    result: Dict[str, Any] | None = None,
    error: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "type": "response",
        "id": str(req_id or ""),
        "ok": bool(ok),
    }
    if ok:
        out["result"] = dict(result or {})
    else:
        out["error"] = dict(error or {"message": "unknown error"})
    return out


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_event(
    topic: str,
    data: Dict[str, Any] | None = None,
    *,
    session_id: str = "",
    project_id: str = "",
) -> Dict[str, Any]:
    return {
        "type": "event",
        "ts": _now_iso(),
        "session_id": str(session_id or ""),
        "project_id": str(project_id or ""),
        "topic": str(topic or ""),
        "data": dict(data or {}),
    }


def parse_message_line(raw: bytes, *, max_bytes: int = MAX_MESSAGE_BYTES) -> Dict[str, Any]:
    if len(raw) > max_bytes:
        raise ValueError("message too large")
    line = raw.decode("utf-8", errors="strict").strip()
    if not line:
        raise ValueError("empty message")
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise ValueError("message must be a JSON object")
    return payload


def serialize_message(message: Dict[str, Any], *, max_bytes: int = MAX_MESSAGE_BYTES) -> bytes:
    blob = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(blob) > max_bytes:
        raise ValueError("message too large")
    return blob
