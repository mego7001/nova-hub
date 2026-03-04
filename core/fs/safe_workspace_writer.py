from __future__ import annotations
import os
from typing import Optional

from core.portable.paths import detect_base_dir, default_workspace_dir


class SafeWorkspaceWriter:
    def __init__(self, workspace_root: Optional[str] = None):
        base = detect_base_dir()
        self.workspace_root = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)

    def write_text(self, path: str, content: str) -> bool:
        if not self._is_allowed(path):
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def _is_allowed(self, path: str) -> bool:
        if not path:
            return False
        ws = os.path.abspath(self.workspace_root)
        ap = os.path.abspath(path)
        if not (ap.startswith(ws + os.sep) or ap == ws):
            return False

        # workspace root markers
        if os.path.dirname(ap) == ws:
            if os.path.basename(ap).lower() in (".first_run_done", ".api_setup_skipped"):
                return True

        # workspace/projects/<id>/(state.json|chat.md)
        projects_root = os.path.join(ws, "projects")
        if ap.startswith(os.path.abspath(projects_root) + os.sep):
            rel = os.path.relpath(ap, projects_root)
            parts = rel.split(os.sep)
            if len(parts) >= 2:
                filename = parts[-1].lower()
                if filename in ("state.json", "chat.md", "conversation_prefs.json"):
                    return True
                if filename == "audit_spine.jsonl" and "audit" in [p.lower() for p in parts]:
                    return True
                if "geometry3d" in [p.lower() for p in parts]:
                    if filename in ("model.json", "assumptions.json", "warnings.json", "reasoning.md", "preview.stl"):
                        return True
                    if "exports" in [p.lower() for p in parts] and filename.endswith(".stl"):
                        return True
                if "engineering" in [p.lower() for p in parts]:
                    if filename in (
                        "engineering_state.json",
                        "engineering_assumptions.json",
                        "engineering_warnings.json",
                        "engineering_report.md",
                    ):
                        return True

        # workspace/reports/session_latest.{md,json} and UI logs
        reports_root = os.path.join(ws, "reports")
        if ap.startswith(os.path.abspath(reports_root) + os.sep):
            filename = os.path.basename(ap).lower()
            if filename in ("session_latest.md", "session_latest.json", "ui.log", "ui_chat.log"):
                return True

        return False
