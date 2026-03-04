from __future__ import annotations
import re
from typing import Dict, Optional


_AR = {
    "scan": ["حلل", "تحليل", "افحص", "فحص", "اسكان", "scan"],
    "analyze": ["analyze", "analysis", "حلل", "تحليل"],
    "search": ["ابحث", "بحث", "hotspot", "hotspots", "بحث عن"],
    "plan": ["plan", "خطة", "اعمل plan", "خطط", "اصلاح", "تصليح", "fix"],
    "apply": ["apply", "طبق", "تنفيذ", "تطبيق"],
    "execute": ["تنفيذ", "نفّذ", "نفذ", "execute", "apply"],
    "verify": ["verify", "تحقق", "اختبر", "تاكد"],
    "pipeline": ["pipeline", "بايبلاين", "run full pipeline", "تشغيل كامل"],
}


def extract_goal(message: str) -> str:
    m = re.search(r"goal\s*[:=]\s*(.+)$", message, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"هدف\s*[:=]\s*(.+)$", message, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if message.lower().startswith("plan "):
        return message[5:].strip()
    if message.lower().startswith("pipeline "):
        return message[9:].strip()
    return ""


def extract_diff_path(message: str) -> Optional[str]:
    m = re.search(r"\S+\.diff", message)
    if m:
        return m.group(0)
    return None




def extract_suggestion_token(message: str) -> Optional[int]:
    m = re.search(r"suggestion[:=](\d+)", message, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None
    return None


def extract_project_path(message: str) -> Optional[str]:
    m = re.search(r"([A-Za-z]:\\[^\s]+)", message)
    if m:
        return m.group(1)
    m = re.search(r"(/[^\s]+)", message)
    if m:
        return m.group(1)
    return None


def extract_suggestion_number(message: str) -> Optional[int]:
    m = re.search(r"(?:apply|execute|نفّذ|نفذ)\s+(\d+)", message, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None
    if "نفذ" in message or "نفّذ" in message:
        m2 = re.search(r"\b(\d+)\b", message)
        if m2:
            try:
                return int(m2.group(1))
            except (TypeError, ValueError):
                return None
    return None


def parse_intent(message: str) -> Dict[str, str]:
    low = message.lower().strip()

    if low in ("help", "help me", "مساعدة", "ساعدني"):
        return {"intent": "help"}

    if "project" in low or "folder" in low or "مجلد" in low or "مشروع" in low:
        p = extract_project_path(message)
        if p:
            return {"intent": "set_project", "project_path": p}
        return {"intent": "set_project"}

    if any(k in low for k in _AR["pipeline"]):
        return {"intent": "pipeline", "goal": extract_goal(message)}

    if any(k in low for k in _AR["analyze"]):
        return {"intent": "analyze"}

    if any(k in low for k in _AR["verify"]):
        return {"intent": "verify"}

    token = extract_suggestion_token(message)
    if token is not None and extract_diff_path(message):
        return {"intent": "apply", "diff_path": extract_diff_path(message) or "", "suggestion_number": str(token)}

    num = extract_suggestion_number(message)
    if num is not None:
        return {"intent": "execute", "number": str(num)}

    if any(k in low for k in _AR["apply"]):
        return {"intent": "apply", "diff_path": extract_diff_path(message) or ""}

    if any(k in low for k in _AR["plan"]):
        return {"intent": "plan", "goal": extract_goal(message)}

    if any(k in low for k in _AR["search"]):
        return {"intent": "search"}

    if any(k in low for k in _AR["scan"]):
        return {"intent": "scan"}

    return {"intent": "unknown"}
