from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.plugin_engine.loader import PluginLoader
from core.permission_guard.tool_policy import ToolPolicy
from core.permission_guard.approval_flow import ApprovalFlow
from core.task_engine.runner import Runner


def _abs_path(path: str) -> str:
    if not path:
        raise ValueError("path is required")
    return os.path.abspath(path)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _approval_callback(req, res):
    print("\n=== APPROVAL REQUIRED ===")
    print("ToolGroup:", req.tool_group)
    print("Op:", req.op)
    print("Target:", req.target)
    print("Reason:", res.reason)
    print("Risk:", res.risk_score)
    ans = input("Approve? (y/n): ").strip().lower()
    return ans == "y"


def _tool_by_id(registry: PluginRegistry, tool_id: str):
    tool = registry.tools.get(tool_id)
    if not tool:
        raise ValueError(f"Tool not found: {tool_id}")
    return tool


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def pipeline_run(
        target_root: str = ".",
        goal: str = "",
        apply_diff: bool = False,
        max_files: int = 10,
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        if not goal or not str(goal).strip():
            raise ValueError("goal is required and must be non-empty")

        root = _abs_path(target_root)
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Target root not found: {root}")

        profile = os.environ.get("NH_PROFILE", "engineering")
        tool_policy = ToolPolicy(os.path.join(root, "configs", "tool_policy.yaml"), active_profile=profile)
        approvals = ApprovalFlow(tool_policy, os.path.join(root, "configs", "approvals.yaml"))
        runner = Runner(approval_flow=approvals, approval_callback=_approval_callback)

        reg = PluginRegistry()
        PluginLoader(root).load_enabled(os.path.join(root, "configs", "plugins_enabled.yaml"), reg)

        steps: List[Dict[str, Any]] = []
        ok = True

        def run_step(tool_id: str, **kwargs) -> Dict[str, Any]:
            nonlocal ok
            tool = _tool_by_id(reg, tool_id)
            try:
                result = runner.execute_registered_tool(tool, **kwargs)
                steps.append({
                    "tool_id": tool_id,
                    "status": "success",
                    "result": _summarize_result(result),
                })
                return result
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                steps.append({
                    "tool_id": tool_id,
                    "status": "failed",
                    "error": str(e),
                })
                ok = False
                raise

        def run_step_no_raise(tool_id: str, **kwargs) -> Optional[Dict[str, Any]]:
            try:
                return run_step(tool_id, **kwargs)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return None

        def ensure_reports_dir() -> str:
            reports_dir = os.path.join(root, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            return reports_dir

        run_step_no_raise("project.scan_repo", root_path=root, write_reports=True)
        run_step_no_raise("repo.search", root_path=root, query=None, write_reports=True)
        plan_result = run_step_no_raise("patch.plan", target_root=root, goal=goal, max_files=max_files, write_reports=True)

        diff_path = None
        if plan_result and isinstance(plan_result, dict):
            diff_path = plan_result.get("diff_path")

        if apply_diff:
            if not diff_path:
                steps.append({
                    "tool_id": "patch.apply",
                    "status": "failed",
                    "error": "No diff_path returned from patch.plan",
                })
                ok = False
            else:
                diff_abs = diff_path
                if not os.path.isabs(diff_abs):
                    diff_abs = os.path.join(root, diff_abs)
                run_step_no_raise("patch.apply", diff_path=diff_abs, target_root=root, write_reports=True)

        run_step_no_raise("verify.smoke", target_root=root, write_reports=True)

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "target_root": root,
            "goal": goal,
            "apply_diff": bool(apply_diff),
            "steps": steps,
            "final_verdict": "PASS" if ok else "FAIL",
        }

        report_paths: List[str] = []
        if write_reports:
            reports_dir = ensure_reports_dir()
            json_path = os.path.join(reports_dir, "pipeline_run.json")
            md_path = os.path.join(reports_dir, "pipeline_run.md")
            _write_json(json_path, payload)

            lines = []
            lines.append("# Pipeline Run Report")
            lines.append("")
            lines.append(f"Timestamp: {payload['timestamp']}")
            lines.append(f"Goal: {goal}")
            lines.append(f"Apply Diff: {apply_diff}")
            lines.append("")
            lines.append("## Steps")
            for s in steps:
                lines.append(f"- {s.get('tool_id')}: {s.get('status')}")
                if s.get("error"):
                    lines.append(f"  - error: {s.get('error')}")
            lines.append("")
            lines.append("## Final Verdict")
            lines.append(payload["final_verdict"])

            _write_text(md_path, "\n".join(lines) + "\n")
            report_paths = [json_path, md_path]

        payload["report_paths"] = report_paths
        if report_paths:
            payload["artifact_ref"] = report_paths[0]
        return payload

    def _summarize_result(result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return {"value": str(result)}
        summary: Dict[str, Any] = {}
        for k in ["report_paths", "diff_path", "selected_files", "totals", "results", "files"]:
            if k in result:
                summary[k] = result.get(k)
        return summary

    registry.register_tool(
        ToolRegistration(
            tool_id="pipeline.run",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="pipeline_run",
            handler=pipeline_run,
            description="Run scan->search->plan->(apply)->verify pipeline",
            default_target=None,
        )
    )

