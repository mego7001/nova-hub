from __future__ import annotations

from pathlib import Path

from core.ingest.index_store import IndexStore
from core.ingest.ingest_manager import IngestManager
from core.projects.manager import ProjectManager


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_migration_lossless_moves_docs_extracted_and_metadata(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    src_file = _write(tmp_path / "input" / "alpha.txt", "hello alpha")
    ingest = mgr.ingest_general("chat_lossless", [src_file])
    assert ingest.get("accepted")

    seed = tmp_path / "seed_project"
    _write(seed / "main.py", "print('seed')\n")
    pm = ProjectManager(workspace_root=str(tmp_path))
    project_id = pm.add_project_from_folder(str(seed))

    migrated = mgr.migrate_general_to_project("chat_lossless", project_id, remove_source=False)

    assert migrated["status"] == "ok"
    assert int(migrated["migrated_records"]) >= 1
    manifest = Path(str(migrated["manifest_path"]))
    assert manifest.exists()

    project_paths = pm.get_project_paths(project_id)
    docs = IndexStore(project_paths.index_path).load()
    assert any(str(item.get("migrated_from_chat_id") or "") == "chat_lossless" for item in docs if isinstance(item, dict))
