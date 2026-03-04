from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


_DEEP_REASONING_KEYWORDS = [
    "deep",
    "root cause",
    "why",
    "prove",
    "formal",
    "step-by-step",
    "reasoning",
    "analysis",
    "analyze deeply",
    "explain in detail",
    "مفصل",
    "تحليل عميق",
    "سبب جذري",
    "برهن",
    "اشرح بالتفصيل",
]


def _summary_threshold() -> int:
    raw = os.environ.get("NH_ONLINE_SUMMARY_THRESHOLD", "").strip()
    try:
        if raw:
            return max(1000, int(raw))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return 8000


def _looks_deep_reasoning(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in _DEEP_REASONING_KEYWORDS)


def _looks_complex_goal(text: str) -> bool:
    low = (text or "").lower()
    # Heuristic: multi-clause, multiple files, or refactor/architecture cues
    signals = ["refactor", "architecture", "redesign", "migrate", "optimize", "overhaul", "end-to-end", "system-wide"]
    return len(low.split()) >= 20 or any(s in low for s in signals)


@dataclass(frozen=True)
class OnlineDecision:
    need_online: bool
    reason: str


def decide_online(
    task_type: str,
    user_msg: str = "",
    offline_confidence: str = "high",
    extracted_text_len: int = 0,
    parser_ok: bool = True,
    plan_ok: bool = True,
    goal_complex: Optional[bool] = None,
) -> OnlineDecision:
    task = (task_type or "").strip().lower()
    confidence = (offline_confidence or "high").strip().lower()

    if task == "summarize_docs":
        threshold = _summary_threshold()
        if extracted_text_len > threshold:
            return OnlineDecision(True, f"summarization length {extracted_text_len} > {threshold}")
        return OnlineDecision(False, "offline summarization sufficient")

    if task in ("deep_reasoning", "conversation"):
        if _looks_deep_reasoning(user_msg) or confidence in ("low", "none"):
            return OnlineDecision(True, "deep reasoning or low offline confidence")
        return OnlineDecision(False, "offline reasoning sufficient")

    if task in ("sketch_parse", "sketch"):
        if not parser_ok:
            return OnlineDecision(True, "offline sketch parser failed")
        return OnlineDecision(False, "offline sketch parser sufficient")

    if task in ("geometry3d_parse", "geometry3d"):
        if not parser_ok:
            return OnlineDecision(True, "offline geometry3d parser failed")
        return OnlineDecision(False, "offline geometry3d parser sufficient")

    if task in ("engineering_extract", "engineering"):
        if not parser_ok:
            return OnlineDecision(True, "offline engineering extraction insufficient")
        return OnlineDecision(False, "offline extraction sufficient")

    if task in ("patch_planning", "plan"):
        is_complex = _looks_complex_goal(user_msg) if goal_complex is None else bool(goal_complex)
        if is_complex and not plan_ok:
            return OnlineDecision(True, "offline patch plan insufficient for complex goal")
        return OnlineDecision(False, "offline patch plan sufficient")

    # Default: stay offline unless confidence is low and message indicates deep reasoning
    if confidence in ("low", "none") and _looks_deep_reasoning(user_msg):
        return OnlineDecision(True, "low offline confidence with deep reasoning request")

    return OnlineDecision(False, "offline sufficient")
