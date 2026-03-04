from __future__ import annotations
from typing import Dict

from core.utils.optional_deps import require


def parse_docx(path: str) -> Dict:
    ok, msg = require(
        "docx",
        "pip install python-docx",
        "DOCX ingest",
    )
    if not ok:
        return {"text": "", "error": msg}
    import docx  # python-docx
    try:
        doc = docx.Document(path)
        parts = [p.text for p in doc.paragraphs if p.text]
        return {"text": "\n".join(parts), "error": None}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        return {"text": "", "error": str(e)}
