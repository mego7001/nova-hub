from __future__ import annotations
from typing import Dict


def parse_text(path: str, max_bytes: int = 500_000) -> Dict:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(max_bytes)
        return {"text": text, "error": None}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        return {"text": "", "error": str(e)}
