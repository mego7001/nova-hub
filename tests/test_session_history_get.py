import os
from pathlib import Path
import socket

from core.ipc.client import IpcClient
from core.ipc.server import LocalIpcServer
from core.ipc.service import NovaCoreService


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_conversation_history_get_returns_bounded_ordered_messages(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    rpc_port = _free_port()
    token = "ipc-history-token"

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")

    service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
    server = LocalIpcServer(host="127.0.0.1", port=rpc_port, dispatcher=service.dispatch, token=token)
    server.start_in_thread()
    try:
        client = IpcClient(host="127.0.0.1", port=rpc_port, token=token, timeout_s=3.0)
        client.call_ok(
            "chat.send",
            {
                "text": "history message one",
                "mode": "general",
                "session_id": "history-session",
                "project_path": "",
                "write_reports": False,
            },
        )
        client.call_ok(
            "chat.send",
            {
                "text": "history message two",
                "mode": "general",
                "session_id": "history-session",
                "project_path": "",
                "write_reports": False,
            },
        )

        history = client.call_ok(
            "conversation.history.get",
            {"session_id": "history-session", "project_id": "", "limit": 50},
        )
        assert history.get("session_id") == "history-session"
        messages = history.get("messages")
        assert isinstance(messages, list)
        assert len(messages) >= 4
        user_messages = [str(m.get("text") or "") for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        assert "history message one" in user_messages
        assert "history message two" in user_messages
    finally:
        server.shutdown()
        os.chdir(prev_cwd)
        if prev_base is None:
            os.environ.pop("NH_BASE_DIR", None)
        else:
            os.environ["NH_BASE_DIR"] = prev_base
        if prev_workspace is None:
            os.environ.pop("NH_WORKSPACE", None)
        else:
            os.environ["NH_WORKSPACE"] = prev_workspace
