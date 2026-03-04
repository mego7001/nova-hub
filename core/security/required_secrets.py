from __future__ import annotations
from typing import Dict, Iterable, List, Set

# Tool-level requirements
TOOL_REQUIRED_KEYS: Dict[str, List[str]] = {
    "deepseek.chat": ["DEEPSEEK_API_KEY"],
    "gemini.prompt": ["GEMINI_API_KEY"],
    "openai.chat": ["OPENAI_API_KEY"],
    "telegram.send": ["TELEGRAM_BOT_TOKEN"],
}

# Feature/job recipe requirements
FEATURE_REQUIRED_KEYS: Dict[str, List[str]] = {
    "quick_fix": [],
    "auto_improve": [],
    "pipeline": [],
}


def required_keys_for_tool(tool_id: str) -> List[str]:
    return list(TOOL_REQUIRED_KEYS.get(tool_id, []))


def required_keys_for_feature(feature: str) -> List[str]:
    return list(FEATURE_REQUIRED_KEYS.get(feature, []))


def required_keys_for_tools(tool_ids: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for tid in tool_ids:
        for k in required_keys_for_tool(tid):
            out.add(k)
    return out


def all_known_keys() -> Set[str]:
    keys = set()
    for v in TOOL_REQUIRED_KEYS.values():
        keys.update(v)
    for v in FEATURE_REQUIRED_KEYS.values():
        keys.update(v)
    return keys
