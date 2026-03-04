from __future__ import annotations

import os
from pathlib import Path

from core.ipc.service import NovaCoreService


def test_chat_send_test_mode_fastpath_skips_brain_and_includes_routing(tmp_path: Path, monkeypatch) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")

    monkeypatch.setenv("NH_TEST_MODE", "1")
    service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
    monkeypatch.setattr(service.brain, "respond", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("brain must not be called")))

    try:
        out = service.dispatch(
            "chat.send",
            {
                "text": "test deterministic route",
                "mode": "general",
                "session_id": "fastpath-session",
                "project_path": "",
                "write_reports": False,
                "debug_routing": True,
            },
            {},
        )
        assistant = out.get("assistant")
        assert isinstance(assistant, dict)
        assert str(assistant.get("text") or "").strip()
        assert out.get("source") == "core.local"
        routing = out.get("routing")
        assert isinstance(routing, dict)
        decision = routing.get("decision")
        assert isinstance(decision, dict)
        assert bool(routing.get("test_mode")) is True

        history = service.dispatch(
            "conversation.history.get",
            {"session_id": "fastpath-session", "project_id": "", "limit": 10},
            {},
        )
        msgs = history.get("messages")
        assert isinstance(msgs, list)
        roles = [str(item.get("role") or "") for item in msgs if isinstance(item, dict)]
        assert "user" in roles
        assert "assistant" in roles
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
