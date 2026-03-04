import os
from pathlib import Path
import socket
import threading
import time

from core.ipc.client import EventsClient, IpcClient
from core.ipc.server import LocalEventsServer, LocalIpcServer
from core.ipc.service import NovaCoreService


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_chat_send_emits_thinking_and_progress_events(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    rpc_port = _free_port()
    events_port = _free_port()
    token = "ipc-chat-events-token"

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")

    service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
    rpc_server = LocalIpcServer(host="127.0.0.1", port=rpc_port, dispatcher=service.dispatch, token=token)
    events_server = LocalEventsServer(host="127.0.0.1", port=events_port, token=token)
    service.set_event_publisher(
        lambda session_id, project_id, topic, data: events_server.publish_event(
            session_id=session_id, project_id=project_id, topic=topic, data=data
        )
    )

    rpc_server.start_in_thread()
    events_server.start_in_thread()

    received: list[dict] = []
    connected = threading.Event()
    got_thinking_start = threading.Event()
    got_thinking_end = threading.Event()
    got_progress = threading.Event()

    def _on_event(evt: dict) -> None:
        received.append(evt)
        topic = str(evt.get("topic") or "")
        data = evt.get("data")
        if not isinstance(data, dict):
            data = {}
        if topic == "thinking" and str(data.get("state") or "") == "start":
            got_thinking_start.set()
        if topic == "thinking" and str(data.get("state") or "") == "end":
            got_thinking_end.set()
        if topic == "progress":
            got_progress.set()

    events_client = EventsClient(host="127.0.0.1", port=events_port, token=token, timeout_s=2.0, reconnect=False)
    events_client.start(
        session_id="chat-events-session",
        project_id="",
        on_event=_on_event,
        on_connected=lambda: connected.set(),
        on_disconnected=lambda _reason: None,
    )
    try:
        assert connected.wait(timeout=2.0), "events client did not connect"
        rpc_client = IpcClient(host="127.0.0.1", port=rpc_port, token=token, timeout_s=3.0)
        result = rpc_client.call_ok(
            "chat.send",
            {
                "text": "hello from events",
                "mode": "general",
                "session_id": "chat-events-session",
                "project_path": "",
                "write_reports": False,
            },
        )
        assert isinstance(result.get("assistant"), dict)
        assert got_thinking_start.wait(timeout=3.0)
        assert got_progress.wait(timeout=3.0)
        assert got_thinking_end.wait(timeout=3.0)
        assert any(str(e.get("topic") or "") == "thinking" for e in received)
        assert any(str(e.get("topic") or "") == "progress" for e in received)
    finally:
        events_client.stop()
        rpc_server.shutdown()
        events_server.shutdown()
        os.chdir(prev_cwd)
        if prev_base is None:
            os.environ.pop("NH_BASE_DIR", None)
        else:
            os.environ["NH_BASE_DIR"] = prev_base
        if prev_workspace is None:
            os.environ.pop("NH_WORKSPACE", None)
        else:
            os.environ["NH_WORKSPACE"] = prev_workspace
