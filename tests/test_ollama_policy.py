from __future__ import annotations

from pathlib import Path

from core.permission_guard.approval_flow import ApprovalFlow
from core.permission_guard.policies import ToolRequest
from core.permission_guard.tool_policy import ToolPolicy


def _paths() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[1]
    return (
        str(root / "configs" / "tool_policy.yaml"),
        str(root / "configs" / "approvals.yaml"),
    )


def test_tool_policy_allows_ollama_without_approval_in_engineering() -> None:
    tool_policy_path, _ = _paths()
    policy = ToolPolicy(tool_policy_path, active_profile="engineering", ui_mode=True)
    decision = policy.evaluate_group("ollama")
    assert decision.allowed is True
    assert decision.requires_approval is False


def test_approval_flow_auto_allows_ollama_group() -> None:
    tool_policy_path, approvals_path = _paths()
    policy = ToolPolicy(tool_policy_path, active_profile="engineering", ui_mode=True)
    flow = ApprovalFlow(policy, approvals_path)
    req = ToolRequest(tool_group="ollama", op="ollama_chat", target="llm:ollama")
    result = flow.check(req)
    assert result.allowed is True
    assert result.requires_approval is False


def test_approval_flow_still_requires_external_llm_approval() -> None:
    tool_policy_path, approvals_path = _paths()
    policy = ToolPolicy(tool_policy_path, active_profile="engineering", ui_mode=True)
    flow = ApprovalFlow(policy, approvals_path)
    req = ToolRequest(tool_group="deepseek", op="deepseek_chat", target="llm:deepseek")
    result = flow.check(req)
    assert result.allowed is True
    assert result.requires_approval is True

