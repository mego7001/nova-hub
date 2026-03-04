from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

class ApprovalDecision(str, Enum):
    AUTO_ALLOW = "auto_allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"

@dataclass(frozen=True)
class ToolRequest:
    tool_group: str
    op: str
    target: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

@dataclass(frozen=True)
class PolicyCheckResult:
    allowed: bool
    requires_approval: bool
    reason: str
    risk_score: float
    matched_rules: List[str]
