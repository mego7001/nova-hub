from __future__ import annotations

import re

DEFAULT_MAX_LEN = 400

_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
]


def _strip_control_chars(text: str) -> str:
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)


def sanitize_text(value: object, *, max_len: int = DEFAULT_MAX_LEN) -> str:
    raw = str(value or "")
    text = _strip_control_chars(raw).replace("\r", " ").replace("\n", " ").strip()
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    if len(text) > max_len:
        text = text[: max(0, max_len - 1)] + "…"
    return text


def sanitize_error_message(value: object, *, max_len: int = 280) -> str:
    return sanitize_text(value, max_len=max_len)


def truncate_text(value: object, *, max_len: int = 280) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[: max(0, max_len - 1)] + "…"
    return text
