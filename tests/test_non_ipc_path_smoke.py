from __future__ import annotations

import os
from pathlib import Path

from core.ipc.service import NovaCoreService


def test_local_chat_path_works_when_ipc_env_disabled(tmp_path: Path, monkeypatch) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")
    try:
        monkeypatch.setenv("NH_IPC_ENABLED", "0")
        service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
        result = service.dispatch(
            "chat.send",
            {
                "text": "hello local path",
                "mode": "general",
                "session_id": "non-ipc-smoke",
                "project_path": "",
                "write_reports": False,
            },
            {},
        )
        assert isinstance(result.get("assistant"), dict)
        assert result.get("source") == "core.local"
        assert isinstance(result.get("response"), str)
    finally:
        os.chdir(prev_cwd)
        if prev_base is None:
            os.environ.pop("NH_BASE_DIR", None)
        else:
            os.environ["NH_BASE_DIR"] = prev_base
        if prev_workspace is None:
            os.environ.pop("NH_WORKSPACE", None)
        else:
            os.environ["NH_WORKSPACE"] = prev_workspace
