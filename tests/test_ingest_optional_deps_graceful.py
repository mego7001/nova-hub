from __future__ import annotations

from core.ingest.parsers import docx_parser, image_parser, pdf_parser, xlsx_parser


def test_docx_parser_reports_missing_dependency(monkeypatch) -> None:
    monkeypatch.setattr(docx_parser, "require", lambda *a, **k: (False, "Feature disabled: missing dependency 'docx'"))
    result = docx_parser.parse_docx("dummy.docx")
    assert "missing dependency" in str(result.get("error") or "").lower()


def test_pdf_parser_reports_missing_dependency(monkeypatch) -> None:
    monkeypatch.setattr(pdf_parser, "require", lambda *a, **k: (False, "Feature disabled: missing dependency 'fitz'"))
    result = pdf_parser.parse_pdf("dummy.pdf")
    assert "missing dependency" in str(result.get("error") or "").lower()


def test_xlsx_parser_reports_missing_dependency(monkeypatch) -> None:
    monkeypatch.setattr(xlsx_parser, "require", lambda *a, **k: (False, "Feature disabled: missing dependency 'openpyxl'"))
    result = xlsx_parser.parse_xlsx("dummy.xlsx")
    assert "missing dependency" in str(result.get("error") or "").lower()


def test_image_parser_reports_missing_dependency(monkeypatch) -> None:
    monkeypatch.setattr(image_parser, "require", lambda *a, **k: (False, "Feature disabled: missing dependency 'PIL'"))
    result = image_parser.parse_image("dummy.png")
    assert str(result.get("ocr_status") or "") == "missing_dependency"
    assert "missing dependency" in str(result.get("error") or "").lower()
