from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import fnmatch, os, re
import yaml
from .policies import ToolRequest, ApprovalDecision, PolicyCheckResult
from .tool_policy import ToolPolicy
from .risk import RiskScorer

@dataclass(frozen=True)
class ApprovalRuleMatch:
    decision: ApprovalDecision
    rule_id: str
    reason: str

class ApprovalFlow:
    def __init__(self, tool_policy: ToolPolicy, approvals_yaml_path: str):
        self.tool_policy = tool_policy
        self.approvals_yaml_path = approvals_yaml_path
        self._raw: Dict[str, Any] = {}
        self._load()
        self.risk = RiskScorer(self.tool_policy.get_group_base_risk)

    def _load(self) -> None:
        if not os.path.exists(self.approvals_yaml_path):
            raise FileNotFoundError(f"Approvals config not found: {self.approvals_yaml_path}")
        with open(self.approvals_yaml_path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f) or {}

    def check(self, req: ToolRequest) -> PolicyCheckResult:
        tp = self.tool_policy.evaluate_group(req.tool_group)
        rr = self.risk.score(req)
        if not tp.allowed:
            return PolicyCheckResult(False, False, f"[ToolPolicy] {tp.reason}", rr.score, tp.matched + [rr.reason])

        match = self._match_rules(req)
        matched = tp.matched + [rr.reason]
        if match:
            matched.append(f"approvals:{match.decision}:{match.rule_id}")
            if match.decision == ApprovalDecision.DENY:
                return PolicyCheckResult(False, False, f"[Approvals] {match.reason}", rr.score, matched)
            if match.decision == ApprovalDecision.AUTO_ALLOW:
                return PolicyCheckResult(True, tp.requires_approval, "[Approvals] auto_allow", rr.score, matched)
            return PolicyCheckResult(True, True, f"[Approvals] {match.reason}", rr.score, matched)

        mode = ((self._raw.get("defaults") or {}).get("mode") or "require_approval").strip().lower()
        if tp.requires_approval:
            return PolicyCheckResult(True, True, "[Fallback] ToolPolicy requires approval", rr.score, matched + ["fallback:tool_policy_requires_approval"])
        if mode == "auto_allow":
            return PolicyCheckResult(True, False, "[Fallback] auto_allow", rr.score, matched + ["fallback:auto_allow"])
        return PolicyCheckResult(True, True, "[Fallback] require_approval", rr.score, matched + ["fallback:require_approval"])

    def _match_rules(self, req: ToolRequest) -> Optional[ApprovalRuleMatch]:
        for bucket, decision in [
            ("always_deny", ApprovalDecision.DENY),
            ("auto_allow", ApprovalDecision.AUTO_ALLOW),
            ("require_approval", ApprovalDecision.REQUIRE_APPROVAL),
        ]:
            for idx, rule in enumerate(self._raw.get(bucket) or []):
                if self._rule_matches(rule, req):
                    rid = rule.get("id") or f"{bucket}#{idx}"
                    return ApprovalRuleMatch(decision, rid, rule.get("reason") or bucket)
        return None

    def _rule_matches(self, rule: Dict[str, Any], req: ToolRequest) -> bool:
        rtype = (rule.get("type") or "").strip()
        if not rtype:
            return False

        cond = rule.get("condition")
        if cond and not self._condition_matches(cond, req):
            return False

        if rtype == "tool_group":
            return rule.get("group") == req.tool_group
        if rtype == "path_glob":
            return fnmatch.fnmatch(req.target or "", rule.get("pattern") or "")
        if rtype == "command_regex":
            pat = rule.get("pattern") or ""
            return bool(pat) and re.search(pat, req.target or "") is not None
        if rtype == "op_equals":
            return str(rule.get("op") or "") == str(req.op or "")
        if rtype == "op_regex":
            pat = rule.get("pattern") or ""
            return bool(pat) and re.search(pat, req.op or "") is not None
        return False

    def _condition_matches(self, cond: Dict[str, Any], req: ToolRequest) -> bool:
        op = cond.get("op")
        unless_glob = cond.get("unless_path_glob")
        if op and req.tool_group != op:
            return False
        if unless_glob and fnmatch.fnmatch(req.target or "", unless_glob):
            return False
        return True
