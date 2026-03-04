from __future__ import annotations
from dataclasses import dataclass
from .policies import ToolRequest

@dataclass(frozen=True)
class RiskResult:
    score: float
    reason: str

class RiskScorer:
    def __init__(self, group_base_risk_getter):
        self._get_base = group_base_risk_getter

    def score(self, req: ToolRequest) -> RiskResult:
        base = float(self._get_base(req.tool_group))
        bump = 0.0
        why = [f"base({req.tool_group})={base:.2f}"]
        target = (req.target or "").lower()

        if req.tool_group == "fs_write":
            bump += 0.10; why.append("bump:fs_write")
        if req.tool_group == "process_exec":
            bump += 0.10; why.append("bump:process_exec")
            if any(k in target for k in ["rm ", "del ", "format", "mkfs", "shutdown", "reboot", "diskpart"]):
                bump += 0.25; why.append("bump:destructive_keywords")
        if req.tool_group in ("network", "gemini", "deepseek", "telegram"):
            bump += 0.08; why.append("bump:external_call")

        score = max(0.0, min(1.0, base + bump))
        return RiskResult(score, "; ".join(why))
