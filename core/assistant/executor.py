from __future__ import annotations
from typing import Any, Dict, List, Optional


def pick_suggestion(suggestions: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
    if index < 1 or index > len(suggestions):
        raise ValueError("Suggestion number out of range")
    return suggestions[index - 1]


def suggestion_goal(suggestion: Dict[str, Any]) -> str:
    return str(suggestion.get("goal") or suggestion.get("title") or "")


def init_status(suggestions: List[Dict[str, Any]], existing: Dict[str, Any]) -> Dict[str, Any]:
    status: Dict[str, Any] = {}
    for idx, s in enumerate(suggestions, 1):
        key = str(idx)
        prev = existing.get(key) if isinstance(existing, dict) else None
        entry = {
            "status": "ready",
            "last_diff_path": "",
            "last_run_at": "",
            "last_error": "",
            "title": s.get("title") if isinstance(s, dict) else "",
        }
        if isinstance(prev, dict):
            entry["status"] = prev.get("status") or "ready"
            entry["last_diff_path"] = prev.get("last_diff_path") or ""
            entry["last_run_at"] = prev.get("last_run_at") or ""
            entry["last_error"] = prev.get("last_error") or ""
        status[key] = entry
    return status


def update_status(status_map: Dict[str, Any], number: int, status: str, diff_path: str = "", error: Optional[str] = None) -> Dict[str, Any]:
    key = str(number)
    entry = status_map.get(key) if isinstance(status_map, dict) else None
    if not isinstance(entry, dict):
        entry = {}
    entry["status"] = status
    if diff_path:
        entry["last_diff_path"] = diff_path
    if error:
        entry["last_error"] = error
    status_map[key] = entry
    return status_map
