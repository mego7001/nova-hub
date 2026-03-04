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


def test_ipc_chat_send_returns_assistant_payload(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    token = "ipc-chat-smoke-token"

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")

    service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
    server = LocalIpcServer(host="127.0.0.1", port=port, dispatcher=service.dispatch, token=token)
    server.start_in_thread()
    try:
        client = IpcClient(host="127.0.0.1", port=port, token=token, timeout_s=3.0)
        result = client.call_ok(
            "chat.send",
            {
                "text": "hello nova",
                "mode": "general",
                "session_id": "ipc_chat_smoke",
                "project_path": "",
                "write_reports": False,
                "ui": "pytest",
            },
        )

        assistant = result.get("assistant")
        assert isinstance(assistant, dict)
        assert assistant.get("role") == "assistant"
        assert isinstance(assistant.get("text"), str)
        assert "response" in result
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
