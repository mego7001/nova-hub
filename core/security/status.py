from __future__ import annotations
import re
from typing import Dict, Iterable

from core.security.secrets import SecretsManager

_PATTERNS = {
    "DEEPSEEK_API_KEY": re.compile(r"^sk-[A-Za-z0-9\-_]{16,}$"),
    "GEMINI_API_KEY": re.compile(r"^AIza[\w-]{10,}$"),
    "TELEGRAM_BOT_TOKEN": re.compile(r"^\d{6,12}:[\w-]{20,}$"),
    "TELEGRAM_CHAT_ID": re.compile(r"^-?\d{4,}$"),
    "TELEGRAM_DEFAULT_CHAT_ID": re.compile(r"^-?\d{4,}$"),
    "OPENAI_API_KEY": re.compile(r"^sk-[A-Za-z0-9\-_]{16,}$"),
}


def get_key_status(secrets: SecretsManager, required_keys: Iterable[str]) -> Dict[str, str]:
    status: Dict[str, str] = {}
    for key in required_keys:
        val = secrets.get(key)
        if not val:
            status[key] = "missing"
            continue
        pat = _PATTERNS.get(key)
        if pat and not pat.match(val):
            status[key] = "invalid_pattern"
        else:
            status[key] = "present"
    return status


def provider_ready(secrets: SecretsManager, provider: str) -> bool:
    if provider == "deepseek":
        return get_key_status(secrets, ["DEEPSEEK_API_KEY"]).get("DEEPSEEK_API_KEY") == "present"
    if provider == "gemini":
        return get_key_status(secrets, ["GEMINI_API_KEY"]).get("GEMINI_API_KEY") == "present"
    if provider == "telegram":
        st = get_key_status(secrets, ["TELEGRAM_BOT_TOKEN"])
        return st.get("TELEGRAM_BOT_TOKEN") == "present"
    return False
