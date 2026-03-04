from __future__ import annotations
from dataclasses import dataclass


@dataclass
class OnlineModeState:
    online_enabled: bool = False
    scope: str = "session"  # session | project

    def is_enabled(self, project_pref_enabled: bool) -> bool:
        if self.scope == "project":
            return bool(project_pref_enabled)
        return bool(self.online_enabled)
