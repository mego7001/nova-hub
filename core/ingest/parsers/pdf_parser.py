from __future__ import annotations
from typing import Dict

from core.utils.optional_deps import require


def parse_pdf(path: str) -> Dict:
    ok, msg = require(
        "fitz",
        "pip install pymupdf",
        "PDF ingest",
    )
    if not ok:
        return {"text": "", "error": msg}
    import fitz  # PyMuPDF
    try:
        doc = fitz.open(path)
        parts = []
        for page in doc:
            parts.append(page.get_text("text"))
        return {"text": "\n".join(parts), "error": None, "pages": doc.page_count}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        return {"text": "", "error": str(e)}
