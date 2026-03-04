from __future__ import annotations
import re
from typing import Dict

from core.chat.intents import extract_goal, extract_diff_path, extract_suggestion_number


_HIGH_VERBS = [
    r"^analyze\b",
    r"^scan\b",
    r"^verify\b",
    r"^search\b",
    r"^plan\b",
    r"^apply\b",
    r"^pipeline\b",
    r"^حلل\b",
    r"^افحص\b",
    r"^تحقق\b",
    r"^نفّذ\b",
    r"^نفذ\b",
    r"^طبق\b",
]

_LOW_HINTS = [
    "maybe",
    "could you",
    "can you",
    "ممكن",
    "عايز",
    "عايزك",
    "لو سمحت",
]


def parse_intent_soft(message: str) -> Dict[str, str]:
    text = (message or "").strip()
    low = text.lower()

    intent = "unknown"
    if any(k in low for k in ["analyze", "analysis", "حلل", "تحليل"]):
        intent = "analyze"
    elif any(k in low for k in ["verify", "تحقق", "اختبر", "تاكد"]):
        intent = "verify"
    elif any(k in low for k in ["search", "hotspot", "ابحث", "بحث"]):
        intent = "search"
    elif any(k in low for k in ["plan", "خطة", "خطط", "اصلاح", "تصليح", "fix"]):
        intent = "plan"
    elif any(k in low for k in ["apply", "طبق", "تطبيق", "تنفيذ"]):
        intent = "apply"
    elif any(k in low for k in ["pipeline", "بايبلاين", "تشغيل كامل"]):
        intent = "pipeline"
    num = extract_suggestion_number(text)
    if num is not None:
        intent = "execute"

    confidence = "NONE"
    if intent != "unknown":
        if any(re.search(pat, low) for pat in _HIGH_VERBS):
            confidence = "HIGH"
        elif any(h in low for h in _LOW_HINTS):
            confidence = "LOW"
        else:
            confidence = "MEDIUM"

    data: Dict[str, str] = {"intent": intent, "confidence": confidence}
    if intent == "plan":
        data["goal"] = extract_goal(text)
    if intent == "apply":
        data["diff_path"] = extract_diff_path(text) or ""
    if intent == "pipeline":
        data["goal"] = extract_goal(text)
    if intent == "execute" and num is not None:
        data["number"] = str(num)
    return data
