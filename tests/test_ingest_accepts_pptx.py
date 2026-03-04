from __future__ import annotations

from pathlib import Path

from core.ingest.ingest_manager import IngestManager


def test_ingest_accepts_pptx_and_writes_extracted_text(monkeypatch, tmp_path: Path):
    def _fake_parse(_path: str):
        return {"text": "pptx extracted text", "slides": 1, "notes_found": 0, "error": None}

    monkeypatch.setattr("core.ingest.ingest_manager.parse_pptx", _fake_parse)
    mgr = IngestManager(workspace_root=str(tmp_path))

    src = tmp_path / "input" / "deck.pptx"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"pptx-placeholder")

    result = mgr.ingest_general("chat_pptx", [str(src)])

    accepted = result.get("accepted") or []
    assert accepted
    assert any(str(item.get("type") or "") == "pptx" for item in accepted if isinstance(item, dict))
    extracted_paths = [str(item.get("extracted_text_path") or "") for item in accepted if isinstance(item, dict)]
    assert any(path and Path(path).exists() for path in extracted_paths)
