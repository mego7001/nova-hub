from pathlib import Path

from core.telemetry.db import SCHEMA_VERSION, TelemetryDB


def test_telemetry_db_migrations_create_required_tables(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    db = TelemetryDB(workspace_root=str(workspace))
    assert db.schema_version() == SCHEMA_VERSION
    assert Path(db.path).exists()
    assert db.path.replace("\\", "/").endswith("workspace/runtime/telemetry/nova_telemetry.sqlite3")
    assert db.wal_enabled() is True

    rows = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    names = {str(row.get("name") or "") for row in rows}
    assert "schema_meta" in names
    assert "llm_calls" in names
    assert "tool_calls" in names
    assert "task_runs" in names
