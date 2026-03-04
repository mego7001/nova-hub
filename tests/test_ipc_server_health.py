import socket
import time

from core.ipc.client import IpcClient
from core.ipc.server import LocalIpcServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_ipc_server_health_roundtrip() -> None:
    port = _free_port()
    token = "ipc-health-test-token"

    def dispatch(op: str, _payload: dict, _ctx: dict) -> dict:
        if op == "health.ping":
            return {"ok": True, "pong": True}
        raise ValueError(f"unexpected op: {op}")

    server = LocalIpcServer(host="127.0.0.1", port=port, dispatcher=dispatch, token=token)
    server.start_in_thread()
    try:
        client = IpcClient(host="127.0.0.1", port=port, token=token, timeout_s=1.0)
        deadline = time.time() + 2.0
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                result = client.call_ok("health.ping", {})
                break
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:  # pragma: no cover - retry path
                last_error = exc
                time.sleep(0.05)
        else:  # pragma: no cover - fail with context
            raise AssertionError(f"IPC health ping did not succeed: {last_error}")

        assert result["ok"] is True
        assert result["pong"] is True
    finally:
        server.shutdown()
