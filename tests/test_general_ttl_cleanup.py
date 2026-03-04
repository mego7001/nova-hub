from __future__ import annotations

import os
import time
from pathlib import Path

from core.ingest.ingest_manager import IngestManager


def _touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_general_ttl_cleanup_removes_only_expired_sessions(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    root = tmp_path / "chat" / "sessions"
    old_session = root / "old"
    new_session = root / "new"
    _touch(old_session / "docs" / "a.txt")
    _touch(new_session / "docs" / "b.txt")

    old_ts = time.time() - (20 * 24 * 60 * 60)
    os.utime(old_session / "docs" / "a.txt", (old_ts, old_ts))
    os.utime(old_session / "docs", (old_ts, old_ts))
    os.utime(old_session, (old_ts, old_ts))

    summary = mgr.cleanup_general_storage()

    assert summary["removed_sessions"] >= 1
    assert not old_session.exists()
    assert new_session.exists()
