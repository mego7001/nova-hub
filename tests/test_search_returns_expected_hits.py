from __future__ import annotations

from pathlib import Path

from core.ingest.ingest_manager import IngestManager
from core.memory.search_service import MemorySearchService


def test_search_returns_expected_hits_for_general_scope(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    doc = tmp_path / "input" / "searchable.txt"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("Nova memory search should find this phrase quickly.", encoding="utf-8")
    mgr.ingest_general("chat_search", [str(doc)])

    svc = MemorySearchService(str(tmp_path))
    result = svc.search("phrase quickly", scope="general", scope_id="chat_search", limit=10, offset=0)

    assert result["status"] == "ok"
    assert int(result["total"]) >= 1
    hits = result.get("hits") or []
    assert hits
    assert "phrase quickly" in str(hits[0].get("snippet") or "").lower()
