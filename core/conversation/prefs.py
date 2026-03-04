from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from core.portable.paths import detect_base_dir, default_workspace_dir


@dataclass
class ConversationPrefs:
    explanation_level: str = "normal"  # short | normal | detailed
    style: str = "egyptian_practical"
    risk_posture: str = "balanced"  # conservative | balanced | aggressive
    online_enabled: bool = False
    last_recapped_at: str = ""
    pinned_goal: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def prefs_path(project_id: str, workspace_root: Optional[str] = None) -> str:
    base = detect_base_dir()
    workspace = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
    return os.path.join(workspace, "projects", project_id, "conversation_prefs.json")


def load_prefs(project_id: str, workspace_root: Optional[str] = None) -> ConversationPrefs:
    path = prefs_path(project_id, workspace_root)
    if not os.path.exists(path):
        return ConversationPrefs()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f) or {}
        return ConversationPrefs(
            explanation_level=str(raw.get("explanation_level") or "normal"),
            style=str(raw.get("style") or "egyptian_practical"),
            risk_posture=str(raw.get("risk_posture") or "balanced"),
            online_enabled=bool(raw.get("online_enabled") or False),
            last_recapped_at=str(raw.get("last_recapped_at") or ""),
            pinned_goal=str(raw.get("pinned_goal") or ""),
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return ConversationPrefs()


def save_prefs(project_id: str, prefs: ConversationPrefs, writer=None, workspace_root: Optional[str] = None) -> None:
    path = prefs_path(project_id, workspace_root)
    payload = json.dumps(prefs.to_dict(), indent=2, ensure_ascii=True)
    if writer:
        writer(path, payload)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)


def update_recapped(prefs: ConversationPrefs) -> ConversationPrefs:
    prefs.last_recapped_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return prefs

