import socket
import threading
import time

from core.ipc.client import EventsClient
from core.ipc.server import LocalEventsServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_events_channel_subscribe_and_publish() -> None:
    port = _free_port()
    token = "ipc-events-basic-token"
    server = LocalEventsServer(host="127.0.0.1", port=port, token=token)
    server.start_in_thread()

    connected = threading.Event()
    received = threading.Event()
    events: list[dict] = []

    client = EventsClient(host="127.0.0.1", port=port, token=token, timeout_s=1.0, reconnect=False)
    client.start(
        session_id="events-basic-session",
        project_id="",
        on_event=lambda evt: (events.append(evt), received.set()),
        on_connected=lambda: connected.set(),
        on_disconnected=lambda _reason: None,
    )
    try:
        assert connected.wait(timeout=2.0), "events client did not connect"
        sent = server.publish_event(
            session_id="events-basic-session",
            project_id="",
            topic="log",
            data={"level": "info", "msg": "hello events"},
        )
        assert sent >= 1
        assert received.wait(timeout=2.0), "did not receive published event"
        assert events
        event = events[-1]
        assert event.get("type") == "event"
        assert event.get("topic") == "log"
        data = event.get("data")
        assert isinstance(data, dict)
        assert data.get("msg") == "hello events"
    finally:
        client.stop()
        server.shutdown()
