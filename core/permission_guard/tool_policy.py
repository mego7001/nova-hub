from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import os
import yaml

@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    matched: List[str]

class ToolPolicy:
    def __init__(self, policy_yaml_path: str, active_profile: str, ui_mode: bool = False):
        self.policy_yaml_path = policy_yaml_path
        self.active_profile = active_profile
        self.ui_mode = ui_mode
        self._raw: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.policy_yaml_path):
            raise FileNotFoundError(f"Tool policy not found: {self.policy_yaml_path}")
        with open(self.policy_yaml_path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f) or {}
        profiles = self._raw.get("profiles") or {}
        if self.active_profile not in profiles:
            raise ValueError(f"Unknown profile '{self.active_profile}'. Available: {list(profiles.keys())}")

    def get_group_base_risk(self, group: str) -> float:
        g = (self._raw.get("tool_groups") or {}).get(group) or {}
        return float(g.get("base_risk", 0.50))

    def evaluate_group(self, group: str) -> ToolPolicyDecision:
        defaults = self._raw.get("defaults") or {}
        deny_by_default = bool(defaults.get("deny_by_default", True))
        p = (self._raw.get("profiles") or {}).get(self.active_profile) or {}
        allow = set(p.get("allow") or [])
        require_approval = set(p.get("require_approval") or [])

        matched: List[str] = []
        if group in allow:
            matched.append(f"profile:{self.active_profile}:allow:{group}")
            if group in require_approval:
                matched.append(f"profile:{self.active_profile}:require_approval:{group}")
            return ToolPolicyDecision(True, group in require_approval, "Allowed by profile", matched)

        if deny_by_default:
            if self.ui_mode and group == "process_exec":
                matched.append("ui_mode:process_exec:require_approval")
                return ToolPolicyDecision(True, True, "UI override: require approval", matched)
            matched.append("defaults:deny_by_default")
            return ToolPolicyDecision(False, False, "Denied by default (not in allowlist)", matched)

        matched.append("defaults:permissive_fallback")
        return ToolPolicyDecision(True, group in require_approval, "Permissive fallback", matched)
