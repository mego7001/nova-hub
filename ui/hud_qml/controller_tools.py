from __future__ import annotations

from typing import Any, Dict, List


def preferred_user_mode(rows: List[Dict[str, Any]], current: str) -> str:
    allowed_ids = {str(row.get("id") or "") for row in rows if isinstance(row, dict)}
    if str(current or "") in allowed_ids:
        return str(current or "")
    for row in rows:
        if not isinstance(row, dict):
            continue
        mode_id = str(row.get("id") or "")
        if mode_id and mode_id.lower() != "auto":
            return mode_id
    return "general"
