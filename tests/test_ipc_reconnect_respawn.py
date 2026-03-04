from pathlib import Path
import socket
import threading
import time

from core.ipc.client import EventsClient
from core.ipc.server import LocalEventsServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_events_client_reconnects_and_respawns_core(tmp_path: Path) -> None:
    _ = tmp_path
    _ = Path(__file__).resolve().parents[1]
    events_port = _free_port()
    token = "ipc-reconnect-token"

    connected_count = 0
    connected_lock = threading.Lock()
    reconnect_seen = threading.Event()
    events_seen: list[dict] = []
    server_lock = threading.Lock()
    active_server: list[LocalEventsServer | None] = [None]

    def _start_server() -> LocalEventsServer:
        srv = LocalEventsServer(host="127.0.0.1", port=events_port, token=token)
        srv.start_in_thread()
        with server_lock:
            active_server[0] = srv
        return srv

    def _stop_server() -> None:
        with server_lock:
            srv = active_server[0]
            active_server[0] = None
        if srv is not None:
            srv.shutdown()

    def _publish(topic: str, payload: dict) -> int:
        with server_lock:
            srv = active_server[0]
        if srv is None:
            return 0
        return srv.publish_event(session_id="reconnect-session", project_id="", topic=topic, data=payload)

    def _on_connected() -> None:
        nonlocal connected_count
        with connected_lock:
            connected_count += 1
            if connected_count >= 2:
                reconnect_seen.set()

    client = EventsClient(
        host="127.0.0.1",
        port=events_port,
        token=token,
        timeout_s=1.5,
        reconnect=True,
        backoff_initial_s=0.1,
        backoff_max_s=0.5,
        ensure_running=lambda: _start_server() if active_server[0] is None else None,
    )

    _start_server()
    client.start(
        session_id="reconnect-session",
        project_id="",
        on_event=lambda evt: events_seen.append(evt),
        on_connected=_on_connected,
        on_disconnected=lambda _reason: None,
    )

    try:
        deadline = time.time() + 5.0
        while time.time() < deadline:
            with connected_lock:
                if connected_count >= 1:
                    break
            time.sleep(0.05)
        with connected_lock:
            assert connected_count >= 1

        assert _publish("thinking", {"state": "before-restart"}) >= 1

        _stop_server()

        assert reconnect_seen.wait(timeout=18.0), "events client did not reconnect after core restart"

        assert _publish("thinking", {"state": "after-restart"}) >= 1

        wait_events_deadline = time.time() + 4.0
        while time.time() < wait_events_deadline:
            if any(str(evt.get("topic") or "") == "thinking" for evt in events_seen) and len(events_seen) >= 2:
                break
            time.sleep(0.05)
        assert any(
            str(evt.get("topic") or "") == "thinking"
            and str((evt.get("data") or {}).get("state") or "") == "after-restart"
            for evt in events_seen
        )
    finally:
        client.stop()
        _stop_server()
