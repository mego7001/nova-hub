from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading
from typing import Any, Deque, Dict, List


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ToolCallTrace:
    trace_id: str
    request_id: str
    tool_id: str
    provider: str
    server_name: str
    start_ts: str
    end_ts: str
    latency_ms: int
    ok: bool
    error_kind: str
    error_msg: str
    session_id: str
    project_id: str
    mode: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ToolTraceRecorder:
    def __init__(self, *, capacity: int = 512) -> None:
        self.capacity = max(1, int(capacity))
        self._items: Deque[ToolCallTrace] = deque(maxlen=self.capacity)
        self._lock = threading.Lock()

    def append(self, trace: ToolCallTrace) -> None:
        with self._lock:
            self._items.append(trace)

    def tail(self, limit: int = 20) -> List[ToolCallTrace]:
        take = max(1, int(limit or 1))
        with self._lock:
            if take >= len(self._items):
                return list(self._items)
            return list(self._items)[-take:]

