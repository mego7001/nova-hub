from __future__ import annotations
from typing import Any, Callable
from core.permission_guard.policies import ToolRequest
from core.permission_guard.approval_flow import ApprovalFlow

class Runner:
    def __init__(self, approval_flow: ApprovalFlow, approval_callback: Callable[[ToolRequest, Any], bool]):
        self.approval_flow = approval_flow
        self.approval_callback = approval_callback

    def execute_registered_tool(self, tool, **kwargs):
        target = kwargs.get("target") or tool.default_target
        req = ToolRequest(tool_group=tool.tool_group, op=tool.op, target=target, meta={"tool_id": tool.tool_id})
        res = self.approval_flow.check(req)

        if not res.allowed:
            raise PermissionError(f"Denied: {res.reason}\nRules: {res.matched_rules}")
        if res.requires_approval and not self.approval_callback(req, res):
            raise PermissionError("User rejected approval.")

        return tool.handler(**kwargs)
