from __future__ import annotations

import os
from typing import Dict, Tuple

from core.utils.optional_deps import require


def _ocr_enabled() -> bool:
    raw = str(os.environ.get("NH_OCR_ENABLED") or "true").strip().lower()
    return raw not in ("0", "false", "off", "no")


def _ocr_langs() -> str:
    raw = str(os.environ.get("NH_OCR_LANGS") or "ara+eng").strip()
    return raw or "ara+eng"


def _configure_tesseract_cmd() -> None:
    cmd = str(os.environ.get("TESSERACT_CMD") or "").strip()
    if not cmd:
        return
    ok, _msg = require(
        "pytesseract",
        "pip install pytesseract",
        "OCR",
    )
    if not ok:
        return
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = cmd
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return


def _perform_ocr(image, langs: str) -> Tuple[str, str, str]:
    ok, msg = require(
        "pytesseract",
        "pip install pytesseract",
        "OCR",
    )
    if not ok:
        return (
            "",
            "missing_dependency",
            f"{msg} Also install local Tesseract and set TESSERACT_CMD on Windows if needed.",
        )
    import pytesseract

    _configure_tesseract_cmd()
    try:
        text = str(pytesseract.image_to_string(image, lang=langs) or "").strip()
        if text:
            return text, "ok", ""
        return "", "empty", ""
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
        msg = str(exc or "").strip()
        low = msg.lower()
        if "tesseract" in low and ("not found" in low or "is not installed" in low):
            return (
                "",
                "missing_dependency",
                "Tesseract executable not found. Install Tesseract and set TESSERACT_CMD to tesseract.exe.",
            )
        return "", "error", msg or "OCR failed."


def parse_image(path: str) -> Dict:
    ok, msg = require(
        "PIL",
        "pip install pillow",
        "image ingest",
    )
    if not ok:
        return {
            "metadata": {},
            "text": "",
            "ocr_status": "missing_dependency",
            "error": msg,
        }
    from PIL import Image

    try:
        with Image.open(path) as img:
            meta = {
                "format": img.format,
                "mode": img.mode,
                "size": list(img.size),
            }

            if not _ocr_enabled():
                return {
                    "metadata": meta,
                    "text": "",
                    "ocr_status": "disabled",
                    "ocr_langs": _ocr_langs(),
                    "error": None,
                }

            text, status, err = _perform_ocr(img, _ocr_langs())
            return {
                "metadata": meta,
                "text": text,
                "ocr_status": status,
                "ocr_langs": _ocr_langs(),
                "error": err or None,
            }
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        return {
            "metadata": {},
            "text": "",
            "ocr_status": "error",
            "error": str(e),
        }
