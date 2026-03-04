from __future__ import annotations

from pathlib import Path

from core.ingest.index_store import IndexStore
from core.ingest.ingest_manager import IngestManager
from core.projects.manager import ProjectManager


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_migration_is_idempotent_for_same_chat_and_project(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    src_file = _write(tmp_path / "input" / "doc.txt", "idempotent migration text")
    mgr.ingest_general("chat_idem", [src_file])

    seed = tmp_path / "seed_project"
    _write(seed / "main.py", "print('seed')\n")
    pm = ProjectManager(workspace_root=str(tmp_path))
    project_id = pm.add_project_from_folder(str(seed))

    first = mgr.migrate_general_to_project("chat_idem", project_id, remove_source=False)
    second = mgr.migrate_general_to_project("chat_idem", project_id, remove_source=False)

    assert first["status"] == "ok"
    assert int(first["migrated_records"]) >= 1
    assert int(second["migrated_records"]) == 0

    index = IndexStore(pm.get_project_paths(project_id).index_path).load()
    migrated = [row for row in index if isinstance(row, dict) and str(row.get("migrated_from_chat_id") or "") == "chat_idem"]
    assert len(migrated) == int(first["migrated_records"])
