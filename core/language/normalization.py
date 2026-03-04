from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List


@dataclass
class NormalizedInput:
    normalized_input: str
    detected_languages: List[str]
    input_style: str


_AR_RE = re.compile(r"[\u0600-\u06FF]")


def normalize_input(text: str) -> NormalizedInput:
    raw = (text or "").strip()
    # normalize whitespace without altering semantics
    norm = re.sub(r"\s+", " ", raw)
    languages: List[str] = []
    if _AR_RE.search(norm):
        languages.append("ar")
    if not languages:
        languages.append("en")
    return NormalizedInput(
        normalized_input=norm,
        detected_languages=languages,
        input_style="plain",
    )

