from __future__ import annotations

from pathlib import Path

import pytest

from core.ingest.parsers import image_parser


def _make_png(path: Path) -> None:
    pil = pytest.importorskip("PIL.Image")
    img = pil.new("RGB", (16, 16), color=(255, 255, 255))
    img.save(path)


def test_parse_image_ocr_disabled_returns_metadata_only(tmp_path: Path, monkeypatch):
    src = tmp_path / "sample.png"
    _make_png(src)
    monkeypatch.setenv("NH_OCR_ENABLED", "false")

    result = image_parser.parse_image(str(src))

    assert result["ocr_status"] == "disabled"
    assert result.get("text", "") == ""
    assert result["metadata"]["size"] == [16, 16]
    assert result.get("error") is None


def test_parse_image_ocr_missing_dependency_fallback(tmp_path: Path, monkeypatch):
    src = tmp_path / "sample.png"
    _make_png(src)
    monkeypatch.setenv("NH_OCR_ENABLED", "true")
    monkeypatch.setattr(
        image_parser,
        "_perform_ocr",
        lambda _img, _langs: ("", "missing_dependency", "Install pytesseract"),
    )

    result = image_parser.parse_image(str(src))

    assert result["ocr_status"] == "missing_dependency"
    assert "Install pytesseract" in str(result.get("error") or "")
    assert result["metadata"]["size"] == [16, 16]


def test_parse_image_ocr_success_with_mock(tmp_path: Path, monkeypatch):
    src = tmp_path / "sample.png"
    _make_png(src)
    monkeypatch.setenv("NH_OCR_ENABLED", "true")
    monkeypatch.setenv("NH_OCR_LANGS", "ara+eng")
    monkeypatch.setattr(
        image_parser,
        "_perform_ocr",
        lambda _img, _langs: ("recognized text", "ok", ""),
    )

    result = image_parser.parse_image(str(src))

    assert result["ocr_status"] == "ok"
    assert result["text"] == "recognized text"
    assert result["ocr_langs"] == "ara+eng"
