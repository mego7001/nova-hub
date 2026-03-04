from __future__ import annotations
from typing import Dict


_CONFIRM_WORDS = {
    "yes",
    "y",
    "ok",
    "okay",
    "sure",
    "confirm",
    "do it",
    "go ahead",
    "اه",
    "آه",
    "تمام",
    "نفّذ",
    "نفذ",
    "اعمل كده",
    "نفّذها",
    "ماشي",
    "ابدأ",
    "أيوه",
}

_REJECT_WORDS = {
    "no",
    "n",
    "cancel",
    "stop",
    "don't",
    "لا",
    "لأ",
    "إلغاء",
    "الغاء",
}


def is_confirmation(text: str) -> bool:
    low = (text or "").strip().lower()
    return low in _CONFIRM_WORDS


def is_rejection(text: str) -> bool:
    low = (text or "").strip().lower()
    return low in _REJECT_WORDS


def build_prompt(action: Dict[str, str]) -> str:
    typ = action.get("type") or "action"
    desc = action.get("description") or typ
    return f"تمام. أبدأ {desc}؟"


def action_labels(action: Dict[str, str]) -> Dict[str, str]:
    typ = (action.get("type") or "").lower()
    if typ == "analyze":
        return {"confirm": "ابدأ التحليل", "cancel": "مش دلوقتي"}
    if typ == "suggestions":
        return {"confirm": "طلع اقتراحات", "cancel": "إلغاء"}
    if typ == "plan":
        return {"confirm": "اعمل Plan", "cancel": "إلغاء"}
    if typ == "apply":
        return {"confirm": "طبّق التعديل", "cancel": "إلغاء"}
    if typ == "verify":
        return {"confirm": "شغّل التحقق", "cancel": "إلغاء"}
    if typ == "search":
        return {"confirm": "ابدأ البحث", "cancel": "إلغاء"}
    if typ == "pipeline":
        return {"confirm": "شغّل البايبلاين", "cancel": "إلغاء"}
    if typ == "execute":
        return {"confirm": "نفّذ الاقتراح", "cancel": "إلغاء"}
    if typ == "sketch_apply":
        return {"confirm": "طبّق الرسم", "cancel": "إلغاء"}
    if typ == "sketch_parse_online":
        return {"confirm": "استخدم Online AI", "cancel": "إلغاء"}
    if typ == "sketch_export":
        return {"confirm": "صدّر DXF", "cancel": "إلغاء"}
    if typ == "geometry3d_apply":
        return {"confirm": "Confirm 3D", "cancel": "Cancel"}
    if typ == "geometry3d_parse_online":
        return {"confirm": "Use Online AI", "cancel": "Cancel"}
    if typ == "geometry3d_export":
        return {"confirm": "Export STL", "cancel": "Cancel"}
    return {"confirm": "Confirm", "cancel": "Cancel"}
