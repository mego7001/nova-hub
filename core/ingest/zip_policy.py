from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

from core.ingest.file_types import DOCX_EXT, IMAGE_EXT, PDF_EXT, PPTX_EXT, TEXT_EXT, XLSX_EXT


@dataclass(frozen=True)
class ZipPolicy:
    max_files: int = 500
    max_total_uncompressed_bytes: int = 50_000_000
    max_member_bytes: int = 10_000_000
    allow_nested_zip: bool = False
    allowed_extensions: frozenset[str] = frozenset()


def default_allowed_extensions() -> Set[str]:
    exts: Set[str] = set()
    exts.update(TEXT_EXT)
    exts.update(PDF_EXT)
    exts.update(DOCX_EXT)
    exts.update(XLSX_EXT)
    exts.update(PPTX_EXT)
    exts.update(IMAGE_EXT)
    return exts


def default_zip_policy() -> ZipPolicy:
    return ZipPolicy(allowed_extensions=frozenset(default_allowed_extensions()))


def rejection(path: str, reason: str, reason_code: str) -> Dict[str, str]:
    return {
        "path": str(path or ""),
        "reason": str(reason or "").strip(),
        "reason_code": str(reason_code or "policy_rejected").strip() or "policy_rejected",
    }
