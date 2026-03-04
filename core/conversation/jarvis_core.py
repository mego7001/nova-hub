from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Dict, Optional, Tuple

from core.conversation.intent_parser import parse_intent_soft


@dataclass
class IntentResult:
    intent_type: str
    confidence: str
    needs_confirm: bool
    proposed_action: Dict[str, Any]
    conflict: bool
    topic_hash: str
    risk_signal: str


def _hash_topic(text: str) -> str:
    val = (text or "").strip().lower()
    return hashlib.sha256(val.encode("utf-8")).hexdigest()[:16]


def _get_jarvis_state(context: Dict[str, Any]) -> Dict[str, Any]:
    return dict((context or {}).get("jarvis") or {})


def _conflicts_with_goal(message: str, pinned_goal: str) -> bool:
    if not pinned_goal:
        return False
    low = (message or "").lower()
    conflict_terms = [
        "ignore",
        "forget",
        "skip",
        "drop",
        "cancel",
        "delete",
        "remove",
        "ØªØ¬Ø§Ù‡Ù„",
        "Ø§Ù†Ø³",
        "Ø³ÙŠØ¨",
        "Ø§Ù„ØºØ§Ø¡",
        "Ø¥Ù„ØºØ§Ø¡",
    ]
    return any(t in low for t in conflict_terms)


def _risk_from_intent(intent_type: str) -> str:
    if intent_type in ("apply", "pipeline", "execute"):
        return "high"
    if intent_type in ("verify",):
        return "medium"
    return "low"


def assess_intent(message: str, context: Dict[str, Any]) -> IntentResult:
    intent = parse_intent_soft(message)
    intent_type = str(intent.get("intent") or "unknown")
    confidence = str(intent.get("confidence") or "NONE")
    pinned_goal = str((_get_jarvis_state(context).get("pinned_goal") or "")).strip()
    conflict = _conflicts_with_goal(message, pinned_goal)
    proposed_action = _action_from_intent(intent)
    needs_confirm = bool(proposed_action) and confidence == "HIGH" and not conflict
    topic_hash = _hash_topic(f"{intent_type}:{message}")
    risk_signal = _risk_from_intent(intent_type)
    return IntentResult(
        intent_type=intent_type,
        confidence=confidence,
        needs_confirm=needs_confirm,
        proposed_action=proposed_action,
        conflict=conflict,
        topic_hash=topic_hash,
        risk_signal=risk_signal,
    )


def generate_reply(message: str, context: Dict[str, Any]) -> str:
    # Simple, natural reply (Egyptian Arabic tone) when no stronger guidance applies.
    text = (message or "").strip()
    if not text:
        return "Ø£Ù†Ø§ Ù…Ø¹Ø§Ùƒ. Ù‚ÙˆÙ„ÙŠ Ù…Ø­ØªØ§Ø¬ Ø¥ÙŠÙ‡ Ø¨Ø§Ù„Ø¸Ø¨Ø·ØŸ"
    intent = parse_intent_soft(text)
    if intent.get("intent") in ("analyze", "search", "verify", "plan", "apply", "pipeline", "execute"):
        return "ØªÙ…Ø§Ù…. Ø£Ù‚Ø¯Ø± Ø£Ø¨Ø¯Ø£ Ø¨Ø¹Ø¯ ØªØ£ÙƒÙŠØ¯Ùƒ."
    return "ØªÙ…Ø§Ù…. ØªØ­Ø¨ Ø£Ø³Ø§Ø¹Ø¯Ùƒ Ø¥Ø²Ø§ÙŠØŸ"


def manage_disagreement(context: Dict[str, Any], proposal: Dict[str, Any], user_preference: str = "") -> Tuple[str, str]:
    jarvis = _get_jarvis_state(context)
    goal = str(jarvis.get("pinned_goal") or "").strip()
    reason = f"Ø¯Ù‡ Ù…ØªØ¹Ø§Ø±Ø¶ Ù…Ø¹ Ø§Ù„Ù‡Ø¯Ù Ø§Ù„Ù…Ø«Ø¨Ù‘Øª: {goal}." if goal else "Ø¯Ù‡ Ù…Ø®Ø§Ù„Ù Ù„Ù„ØªÙˆØ¬ÙŠÙ‡ Ø§Ù„Ø­Ø§Ù„ÙŠ."
    disagree = f"Ø£Ù†Ø§ Ù…Ø´ Ù…ÙˆØ§ÙÙ‚. {reason}"
    question = "ØªØ­Ø¨ Ù†ÙƒÙ…Ù‘Ù„ ÙÙŠ Ø§ØªØ¬Ø§Ù‡Ùƒ ÙˆÙ„Ø§ Ù†Ø¹Ø¯Ù‘Ù„ Ø§Ù„Ù…Ø³Ø§Ø±ØŸ"
    return disagree, question


def warning_level(context: Dict[str, Any], risk_signal: Dict[str, Any] | str) -> int:
    jarvis = _get_jarvis_state(context)
    state = dict(jarvis.get("warning_state") or {})
    prev_level = int(state.get("level") or 0)
    last_hash = str(state.get("last_topic_hash") or "")
    count = int(state.get("count") or 0)

    if isinstance(risk_signal, dict):
        topic_hash = str(risk_signal.get("topic_hash") or "")
        insist = bool(risk_signal.get("insist"))
        risky = bool(risk_signal.get("risky", True))
    else:
        topic_hash = ""
        insist = False
        risky = bool(risk_signal)

    if not risky:
        return 0

    if topic_hash and topic_hash != last_hash:
        prev_level = 0
        count = 0

    if prev_level == 0:
        level = 1
    elif insist:
        level = min(prev_level + 1, 3)
    else:
        level = prev_level

    state.update({
        "level": level,
        "last_topic_hash": topic_hash or last_hash,
        "count": count + (1 if insist else 0),
    })
    jarvis["warning_state"] = state
    context["jarvis"] = jarvis
    return level


def warning_text(level: int) -> str:
    if level == 1:
        return "ØªÙ†Ø¨ÙŠÙ‡ Ù…Ù†Ø·Ù‚ÙŠ: Ø§Ù„Ø¥Ø¬Ø±Ø§Ø¡ Ø¯Ù‡ Ù…Ù…ÙƒÙ† ÙŠØ³Ø¨Ø¨ Ù…Ø®Ø§Ø·Ø±Ø©. ØªØ­Ø¨ Ù†ÙƒÙ…Ù„ ÙˆÙ„Ø§ Ù†Ø±Ø§Ø¬Ø¹ØŸ"
    if level == 2:
        return "ØªÙ†Ø¨ÙŠÙ‡ Ø¨ØµÙŠØºØ© Ø³ÙŠÙ†Ø§Ø±ÙŠÙˆ: Ù„Ùˆ ÙƒÙ…Ù„Ù†Ø§ ÙƒØ¯Ù‡ ÙˆÙ…Ø´ÙƒÙ„Ø© Ø­ØµÙ„ØªØŒ Ù‡Ù†Ø®Ø³Ø± ÙˆÙ‚Øª ÙÙŠ ØªØµØ­ÙŠØ­Ù‡Ø§ Ø¨Ø¹Ø¯ÙŠÙ†."
    if level >= 3:
        return "ØªÙ†Ø¨ÙŠÙ‡ Ù…Ø®ØªØµØ±: Ø§Ù„Ù‚Ø±Ø§Ø± ØªÙ… Ø±ØºÙ… Ù…Ø®Ø§Ø·Ø±Ø© Ù…ÙˆØ¶Ù‘Ø­Ø© Ø³Ø§Ø¨Ù‚Ù‹Ø§."
    return ""


def documentary_log_note() -> str:
    return "Ø³Ø£Ø³Ø¬Ù‘Ù„ Ø¥Ù† Ø§Ù„Ù‚Ø±Ø§Ø± ØªÙ… Ø±ØºÙ… Ù…Ø®Ø§Ø·Ø±Ø© Ù…ÙˆØ¶Ù‘Ø­Ø© Ø³Ø§Ø¨Ù‚Ù‹Ø§."


def record_documentary_warning(context: Dict[str, Any], audit: Any | None = None) -> None:
    note = documentary_log_note()
    jarvis = _get_jarvis_state(context)
    jarvis["last_documentary_note"] = {
        "text": note,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    context["jarvis"] = jarvis
    if audit and hasattr(audit, "emit"):
        try:
            audit.emit("jarvis_documentary_warning", {"note": note})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass


def recovery_mode(context: Dict[str, Any], failure_event: Dict[str, Any]) -> Tuple[str, str]:
    ftype = str((failure_event or {}).get("type") or "unknown")
    if ftype in ("verify_failed", "patch_apply_failed", "pipeline_failed"):
        plan = "Ø®Ù„Ù‘ÙŠÙ†Ø§ Ù†ØµÙ„Ù‘Ø­ Ø§Ù„Ø£ÙˆÙ„ Ø¨Ø®Ø·Ø© Ø¢Ù…Ù†Ø© (plan ÙÙ‚Ø·)ØŒ ÙˆØ¨Ø¹Ø¯Ù‡Ø§ Ù†Ø±Ø¬Ù‘Ø¹ Ø§Ù„ØªØ­Ù‚Ù‚."
    elif ftype in ("preview_crashed",):
        plan = "Ø®Ù„Ù‘ÙŠÙ†Ø§ Ù†Ø«Ø¨Øª Ø§Ù„Ø³Ø¨Ø¨: Ù‡Ù†Ø±Ø§Ø¬Ø¹ Ø§Ù„Ù„ÙˆØ¬ ÙˆÙ†Ø¹Ø¯Ù‘Ù„ Ø£Ù‚Ù„ ØªØºÙŠÙŠØ± Ù…Ù…ÙƒÙ† Ø«Ù… Ù†Ø¬Ø±Ø¨ ØªØ§Ù†ÙŠ."
    else:
        plan = "Ø®Ù„Ù‘ÙŠÙ†Ø§ Ù†Ø¨Ø¯Ø£ Ø¨Ø¥ØµÙ„Ø§Ø­ Ø¢Ù…Ù† ÙˆØ®Ø·ÙˆØ© Ø¨Ø®Ø·ÙˆØ©."
    reminder = "Ø¨Ø§Ù„Ù…Ù†Ø§Ø³Ø¨Ø©ØŒ Ø§Ù„Ù†ØªÙŠØ¬Ø© Ø¯ÙŠ ÙƒØ§Ù†Øª Ø¶Ù…Ù† Ø§Ù„Ø³ÙŠÙ†Ø§Ø±ÙŠÙˆ Ø§Ù„Ù„ÙŠ Ø§ØªØ°ÙƒØ± Ù‚Ø¨Ù„ ÙƒØ¯Ù‡."
    return plan, reminder


def update_last_disagreement(context: Dict[str, Any], topic_hash: str, reason: str) -> None:
    jarvis = _get_jarvis_state(context)
    jarvis["last_disagreement"] = {
        "topic_hash": topic_hash,
        "reason": reason,
        "asked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    context["jarvis"] = jarvis


def update_last_outcome(context: Dict[str, Any], outcome_type: str, resolved: bool = False) -> None:
    jarvis = _get_jarvis_state(context)
    jarvis["last_outcome"] = {
        "type": outcome_type,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "resolved": bool(resolved),
    }
    context["jarvis"] = jarvis


def _action_from_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    action = {"type": intent.get("intent"), "description": ""}
    if intent.get("intent") == "analyze":
        action["description"] = "Analyze the current project"
    elif intent.get("intent") == "search":
        action["description"] = "Find task-marker hotspots"
    elif intent.get("intent") == "verify":
        action["description"] = "Run verification checks"
    elif intent.get("intent") == "plan":
        goal = intent.get("goal") or ""
        action["description"] = "Plan fixes" + (f" for: {goal}" if goal else "")
        action["goal"] = goal
    elif intent.get("intent") == "apply":
        diff_path = intent.get("diff_path") or ""
        action["description"] = "Apply planned diff" + (f": {diff_path}" if diff_path else "")
        action["diff_path"] = diff_path
    elif intent.get("intent") == "pipeline":
        goal = intent.get("goal") or ""
        action["description"] = "Run pipeline" + (f" for: {goal}" if goal else "")
        action["goal"] = goal
    elif intent.get("intent") == "execute":
        num = intent.get("number") or ""
        action["description"] = f"Execute suggestion {num}"
        action["number"] = num
    else:
        return {}
    return action


def is_user_insisting(message: str) -> bool:
    low = (message or "").lower()
    return any(k in low for k in ["proceed", "continue", "go ahead", "ÙƒÙ…Ù„", "ÙƒÙ…Ù‘Ù„", "Ø§Ø³ØªÙ…Ø±", "Ø§Ù…Ø´ÙŠ"])


def is_user_adjusting(message: str) -> bool:
    low = (message or "").lower()
    return any(k in low for k in ["adjust", "change", "modify", "Ø¹Ø¯Ù‘Ù„", "ØºÙŠØ±", "ØªØ¹Ø¯ÙŠÙ„", "Ù†Ø¹Ø¯Ù‘Ù„"])

