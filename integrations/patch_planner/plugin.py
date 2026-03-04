from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration


def _abs_path(path: str) -> str:
    if not path:
        raise ValueError("path is required")
    return os.path.abspath(path)


def _read_json_if_exists(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _is_binary_sample(path: str, max_probe: int = 4096) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(max_probe)
        return b"\x00" in chunk
    except OSError:
        return False


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def _relpath(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return path.replace("\\", "/")


def _diff_additions_for_gitignore(root: str) -> Tuple[Optional[str], Optional[str]]:
    gi = os.path.join(root, ".gitignore")
    if not os.path.exists(gi):
        return None, None
    content = _read_text(gi)
    lines = content.splitlines()
    want = [".env", "reports/", "patches/"]
    missing = [w for w in want if w not in lines]
    if not missing:
        return None, None

    old_lines = content.splitlines()
    new_lines = old_lines + missing
    old_start = 1 if old_lines else 0
    new_start = 1 if new_lines else 0

    diff = []
    diff.append("--- a/.gitignore")
    diff.append("+++ b/.gitignore")
    diff.append(f"@@ -{old_start},{len(old_lines)} +{new_start},{len(new_lines)} @@")
    for line in old_lines:
        diff.append(f" {line}")
    for m in missing:
        diff.append(f"+{m}")
    diff_text = "\n".join(diff) + "\n"
    return diff_text, ".gitignore"


def create_patch_plan_handler(config: Dict[str, Any]):
    default_output_dir = str(config.get("default_output_dir") or "patches")
    default_reports_dir = str(config.get("default_reports_dir") or "reports")

    def patch_plan(
        target_root: str = ".",
        goal: str = "",
        constraints: Optional[str] = None,
        max_files: int = 10,
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        if not goal or not str(goal).strip():
            raise ValueError("goal is required and must be non-empty")

        root = _abs_path(target_root)
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Target root not found: {root}")

        reports_dir = os.path.join(root, default_reports_dir)
        output_dir = os.path.join(root, default_output_dir)
        os.makedirs(reports_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        project_scan = _read_json_if_exists(os.path.join(reports_dir, "project_scan.json"))
        repo_search = _read_json_if_exists(os.path.join(reports_dir, "repo_search.json"))
        audit_python = _read_json_if_exists(os.path.join(reports_dir, "audit_python.json"))

        candidates: List[str] = []
        rationale: Dict[str, str] = {}

        if repo_search:
            hs = repo_search.get("hotspots") or {}
            for item in (hs.get("files_with_most_hits") or []):
                p = item.get("path")
                if p:
                    candidates.append(p)
                    rationale[p] = "hotspot: most hits"
            for item in (hs.get("suspicious_files") or []):
                p = item.get("path")
                if p and p not in rationale:
                    candidates.append(p)
                    rationale[p] = "hotspot: suspicious"
            for p in (hs.get("config_hotspots") or []):
                if p and p not in rationale:
                    candidates.append(p)
                    rationale[p] = "hotspot: config"

        selected: List[str] = []
        for p in candidates:
            if len(selected) >= int(max_files):
                break
            abs_p = os.path.join(root, p)
            if not os.path.exists(abs_p):
                continue
            if os.path.isdir(abs_p):
                continue
            if _is_binary_sample(abs_p):
                continue
            selected.append(p)

        diffs: List[str] = []
        diff_paths: List[str] = []

        gitignore_diff, gi_path = _diff_additions_for_gitignore(root)
        if gitignore_diff:
            diffs.append(gitignore_diff)
            diff_paths.append(gi_path or ".gitignore")

        diff_text = "".join(diffs).strip()
        if diff_text:
            diff_text = diff_text + "\n"

        diff_path = os.path.join(output_dir, "plan_001.diff")
        if diff_text:
            _write_text(diff_path, diff_text)
        else:
            _write_text(diff_path, "")

        steps: List[str] = []
        if gitignore_diff:
            steps.append("Add .env and report/patch output folders to .gitignore to avoid committing local outputs.")
        if not steps:
            steps.append("No safe mechanical patches detected. Review reports and add manual TODOs to patch_plan.md.")

        plan_lines: List[str] = []
        plan_lines.append("# Patch Plan")
        plan_lines.append("")
        plan_lines.append("## Goal")
        plan_lines.append(goal.strip())
        plan_lines.append("")
        plan_lines.append("## Constraints")
        plan_lines.append((constraints or "(none)").strip())
        plan_lines.append("")
        plan_lines.append("## Inputs")
        plan_lines.append(f"- reports/project_scan.json: {'found' if project_scan else 'missing'}")
        plan_lines.append(f"- reports/repo_search.json: {'found' if repo_search else 'missing'}")
        plan_lines.append(f"- reports/audit_python.json: {'found' if audit_python else 'missing'}")
        plan_lines.append("")
        plan_lines.append("## Selected Files")
        if selected:
            for p in selected:
                plan_lines.append(f"- {p} ({rationale.get(p, 'selected')})")
        else:
            plan_lines.append("- (none)")
        plan_lines.append("")
        plan_lines.append("## Proposed Steps")
        for s in steps:
            plan_lines.append(f"- {s}")
        plan_lines.append("")
        plan_lines.append("## Acceptance Checks")
        plan_lines.append("- reports/patch_plan.md exists and describes steps")
        plan_lines.append("- patches/plan_001.diff exists (may be empty if no safe changes)")

        plan_path = os.path.join(reports_dir, "patch_plan.md")
        _write_text(plan_path, "\n".join(plan_lines) + "\n")

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "target_root": root,
            "goal": goal,
            "constraints": constraints,
            "inputs": {
                "project_scan": bool(project_scan),
                "repo_search": bool(repo_search),
                "audit_python": bool(audit_python),
            },
            "selected_files": selected,
            "rationale": rationale,
            "diff_paths": ["patches/plan_001.diff"],
            "report_paths": ["reports/patch_plan.md", "reports/patch_summary.json"],
        }
        summary_path = os.path.join(reports_dir, "patch_summary.json")
        _write_json(summary_path, summary)

        return {
            "timestamp": summary["timestamp"],
            "target_root": root,
            "goal": goal,
            "constraints": constraints,
            "selected_files": selected,
            "diff_path": _relpath(diff_path, root),
            "report_paths": [
                _relpath(plan_path, root),
                _relpath(summary_path, root),
            ],
            "artifact_ref": _relpath(diff_path, root) or _relpath(summary_path, root),
        }

    return patch_plan


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    default_output_dir = str(config.get("default_output_dir") or "patches")
    patch_plan = create_patch_plan_handler(config)
    registry.register_tool(
        ToolRegistration(
            tool_id="patch.plan",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="patch_plan",
            handler=patch_plan,
            description="Plan safe patches and generate unified diffs",
            default_target=default_output_dir,
        )
    )

