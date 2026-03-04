from pathlib import Path

from ui.hud_qml.controller import _read_jsonl, _write_jsonl


def test_jsonl_read_and_write_line_counts(tmp_path):
    jsonl_path = tmp_path / "events.jsonl"

    # Pre-seed two JSONL records and verify the reader returns exactly two dicts.
    jsonl_path.write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")
    items = _read_jsonl(str(jsonl_path))
    assert len(items) == 2
    assert items[0]["id"] == 1
    assert items[1]["id"] == 2

    # Two writes should append exactly two lines (no accidental duplication).
    jsonl_path.write_text("", encoding="utf-8")
    _write_jsonl(str(jsonl_path), {"id": "a"})
    _write_jsonl(str(jsonl_path), {"id": "b"})
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    written = _read_jsonl(str(jsonl_path))
    assert len(written) == 2
    assert written[0]["id"] == "a"
    assert written[1]["id"] == "b"
