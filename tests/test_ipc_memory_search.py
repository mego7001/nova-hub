from __future__ import annotations

import os
from pathlib import Path

from core.ingest.ingest_manager import IngestManager
from core.ipc.service import NovaCoreService


def test_ipc_memory_search_returns_hits(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    doc = tmp_path / "input" / "ipc_search.txt"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("IPC memory search checks extracted content.", encoding="utf-8")

    mgr = IngestManager(workspace_root=str(workspace_root))
    mgr.ingest_general("chat_ipc", [str(doc)])

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")
    try:
        service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
        payload = {
            "query": "extracted content",
            "scope": "general",
            "scope_id": "chat_ipc",
            "limit": 10,
            "offset": 0,
        }
        result = service.dispatch("memory.search", payload, {})
        assert result["status"] == "ok"
        assert int(result["total"]) >= 1
        assert isinstance(result.get("hits"), list) and result["hits"]
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
