from __future__ import annotations

from typing import Any, Dict

from .client import IpcClient
from .protocol import DEFAULT_HOST, resolve_ipc_port


def health_ping(
    *,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    token: str | None = None,
    timeout_s: float = 0.8,
) -> Dict[str, Any]:
    client = IpcClient(host=host, port=resolve_ipc_port(port), token=token, timeout_s=timeout_s)
    return client.call_ok("health.ping", {})
