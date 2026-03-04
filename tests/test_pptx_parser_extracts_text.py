from __future__ import annotations

import types
import sys
from pathlib import Path

from core.ingest.parsers.pptx_parser import parse_pptx


class _FakeShape:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeNotesFrame:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeNotesSlide:
    def __init__(self, text: str) -> None:
        self.notes_text_frame = _FakeNotesFrame(text)


class _FakeSlide:
    def __init__(self, text: str, notes: str = "") -> None:
        self.shapes = [_FakeShape(text)]
        self.notes_slide = _FakeNotesSlide(notes)


class _FakePresentation:
    def __init__(self, _path: str) -> None:
        self.slides = [
            _FakeSlide("slide one text", "note one"),
            _FakeSlide("slide two text", ""),
        ]


def test_parse_pptx_extracts_slide_text_and_notes(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("core.ingest.parsers.pptx_parser.require", lambda *_args, **_kwargs: (True, ""))
    monkeypatch.setitem(sys.modules, "pptx", types.SimpleNamespace(Presentation=_FakePresentation))
    dummy = tmp_path / "sample.pptx"
    dummy.write_text("x", encoding="utf-8")

    result = parse_pptx(str(dummy))

    assert result.get("error") is None
    text = str(result.get("text") or "")
    assert "slide one text" in text
    assert "slide two text" in text
    assert "[notes] note one" in text
    assert int(result.get("slides") or 0) == 2
    assert int(result.get("notes_found") or 0) == 1
