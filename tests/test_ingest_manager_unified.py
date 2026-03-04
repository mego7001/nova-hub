from __future__ import annotations

import os
import time
from pathlib import Path

from core.ingest.index_store import IndexStore
from core.ingest.ingest_manager import IngestManager
from core.projects.manager import ProjectManager


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_ingest_general_uses_chat_scope_and_policy(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    ok_file = _write(tmp_path / "inputs" / "notes.txt", "hello ingest")
    bad_file = _write(tmp_path / "inputs" / "blob.bin", "xxxx")

    result = mgr.ingest_general("chat_abc", [ok_file, bad_file])

    assert result["target"] == "general"
    assert result["scope_id"] == "chat_abc"
    assert len(result["accepted"]) == 1
    assert len(result["rejected"]) == 1
    assert result["accepted"][0]["type"] == "text"
    assert Path(result["index_path"]).exists()
    assert "chat/sessions/chat_abc/docs".replace("/", os.sep) in str(result["docs_dir"])


def test_cleanup_general_storage_removes_stale_sessions(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    stale_root = tmp_path / "chat" / "sessions" / "old_chat"
    _write(stale_root / "docs" / "old.txt", "legacy")
    _write(stale_root / "extracted" / "old.txt", "legacy")

    old_ts = time.time() - (21 * 24 * 60 * 60)
    for p in [stale_root, stale_root / "docs", stale_root / "extracted", stale_root / "docs" / "old.txt", stale_root / "extracted" / "old.txt"]:
        os.utime(p, (old_ts, old_ts))

    summary = mgr.cleanup_general_storage()
    assert summary["removed_sessions"] >= 1
    assert not stale_root.exists()


def test_migrate_general_to_project_moves_docs_and_index(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    src_file = _write(tmp_path / "inputs" / "a.txt", "content from general")
    ingest_result = mgr.ingest_general("chat_to_project", [src_file])
    assert ingest_result["accepted"]

    seed = tmp_path / "seed_project"
    _write(seed / "main.py", "print('seed')\n")
    pm = ProjectManager(workspace_root=str(tmp_path))
    project_id = pm.add_project_from_folder(str(seed))

    migrated = mgr.migrate_general_to_project("chat_to_project", project_id, remove_source=True)
    assert migrated["status"] == "ok"
    assert migrated["migrated_records"] >= 1

    project_paths = pm.get_project_paths(project_id)
    records = IndexStore(project_paths.index_path).load()
    assert any(str(r.get("migrated_from_chat_id") or "") == "chat_to_project" for r in records)
    assert not (tmp_path / "chat" / "sessions" / "chat_to_project").exists()
