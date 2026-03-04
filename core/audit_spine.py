from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import uuid
from typing import Any, Dict, Iterable, List, Optional

from core.security.secrets import SecretsManager
from core.portable.paths import detect_base_dir, default_workspace_dir
from core.utils.jsonl_tail import read_jsonl_page, tail_jsonl_dicts


_SECRET_KEY_HINTS = ("token", "secret", "apikey", "api_key", "password", "key")
_URL_QUERY_RE = re.compile(r"(\?.*)$")


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    recorded_at: str
    mission_id: str
    intent_id: Optional[str]
    decision_id: Optional[str]
    run_id: Optional[str]
    event_type: str
    payload: Dict[str, Any]
    supersedes_event_id: Optional[str] = None
    prev_hash: Optional[str] = None
    hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "recorded_at": self.recorded_at,
            "mission_id": self.mission_id,
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "run_id": self.run_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "supersedes_event_id": self.supersedes_event_id,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


class AuditSpine:
    def __init__(self, mission_id: str, base_dir: str):
        self.mission_id = mission_id
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.path = os.path.join(self.base_dir, f"audit_{_safe_filename(mission_id)}.jsonl")

    def emit(
        self,
        event_type: str,
        payload: Dict[str, Any],
        intent_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        run_id: Optional[str] = None,
        supersedes_event_id: Optional[str] = None,
    ) -> AuditEvent:
        prev_hash = self._read_last_hash()
        evt = AuditEvent(
            event_id=_new_id(),
            recorded_at=_now(),
            mission_id=self.mission_id,
            intent_id=intent_id,
            decision_id=decision_id,
            run_id=run_id,
            event_type=event_type,
            payload=self._sanitize_payload(payload),
            supersedes_event_id=supersedes_event_id,
            prev_hash=prev_hash,
            hash=None,
        )
        evt_dict = evt.to_dict()
        evt_hash = _compute_hash(evt_dict)
        evt = AuditEvent(
            event_id=evt.event_id,
            recorded_at=evt.recorded_at,
            mission_id=evt.mission_id,
            intent_id=evt.intent_id,
            decision_id=evt.decision_id,
            run_id=evt.run_id,
            event_type=evt.event_type,
            payload=evt.payload,
            supersedes_event_id=evt.supersedes_event_id,
            prev_hash=evt.prev_hash,
            hash=evt_hash,
        )
        self._append_event(evt)
        return evt

    def timeline(self) -> List[Dict[str, Any]]:
        return list(self._read_events())

    def run_chain(self, run_id: str) -> List[Dict[str, Any]]:
        return [e for e in self._read_events() if e.get("run_id") == run_id]

    def _append_event(self, evt: AuditEvent) -> None:
        line = json.dumps(evt.to_dict(), ensure_ascii=True)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _read_last_hash(self) -> str:
        if not os.path.exists(self.path):
            return "GENESIS"
        last_line = ""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        last_line = line
        except OSError:
            return "GENESIS"
        if not last_line:
            return "GENESIS"
        try:
            payload = json.loads(last_line)
            return payload.get("hash") or "GENESIS"
        except (TypeError, ValueError, json.JSONDecodeError):
            return "GENESIS"

    def _read_events(self) -> Iterable[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        out: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
        return out

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return _sanitize_payload(payload)


class ProjectAuditSpine:
    def __init__(self, project_id: str, workspace_root: Optional[str] = None):
        self.project_id = project_id
        base = detect_base_dir()
        self.workspace_root = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
        audit_dir = os.path.join(self.workspace_root, "projects", project_id, "audit")
        os.makedirs(audit_dir, exist_ok=True)
        self.path = os.path.join(audit_dir, "audit_spine.jsonl")

    def emit(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        prev_hash = self._read_last_hash()
        evt = {
            "event_id": _new_id(),
            "recorded_at": _now(),
            "project_id": self.project_id,
            "event_type": event_type,
            "payload": _sanitize_payload(payload or {}),
            "prev_hash": prev_hash,
        }
        evt["hash"] = _compute_hash(evt)
        self._append_event(evt)
        return evt

    def read_events(self, limit: int = 200, cursor: Optional[int] = None) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        if cursor is not None:
            items, _next_cursor, _has_more = read_jsonl_page(self.path, cursor=cursor, limit=limit)
            return items
        return tail_jsonl_dicts(self.path, limit=limit)

    def read_events_page(self, limit: int = 200, cursor: int = 0) -> Dict[str, Any]:
        items, next_cursor, has_more = read_jsonl_page(self.path, cursor=cursor, limit=limit)
        return {
            "events": items,
            "cursor": max(0, int(cursor or 0)),
            "next_cursor": int(next_cursor),
            "has_more": bool(has_more),
            "limit": max(1, int(limit or 200)),
        }

    def _append_event(self, evt: Dict[str, Any]) -> None:
        line = json.dumps(evt, ensure_ascii=True)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _read_last_hash(self) -> str:
        if not os.path.exists(self.path):
            return "GENESIS"
        last_line = ""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        last_line = line
        except OSError:
            return "GENESIS"
        if not last_line:
            return "GENESIS"
        try:
            payload = json.loads(last_line)
            return payload.get("hash") or "GENESIS"
        except (TypeError, ValueError, json.JSONDecodeError):
            return "GENESIS"


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def _looks_sensitive_url(val: str) -> bool:
    low = val.lower()
    return any(k in low for k in ("token=", "key=", "apikey=", "secret=", "access_token="))


def _strip_query(val: str) -> str:
    return _URL_QUERY_RE.sub("?REDACTED", val)


def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    def _clean_value(key: str, val: Any) -> Any:
        if isinstance(val, str):
            if any(k in key.lower() for k in _SECRET_KEY_HINTS):
                return "[REDACTED]"
            if "://" in val and _looks_sensitive_url(val):
                return _strip_query(val)
            return SecretsManager.redact_text(val)
        if isinstance(val, dict):
            return {k: _clean_value(k, v) for k, v in val.items()}
        if isinstance(val, list):
            return [_clean_value(key, v) for v in val]
        return val

    return {k: _clean_value(k, v) for k, v in (payload or {}).items()}


def _compute_hash(evt: Dict[str, Any]) -> str:
    data = {k: v for k, v in evt.items() if k != "hash"}
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

