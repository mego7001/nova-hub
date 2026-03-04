from __future__ import annotations
import json
import os
from typing import Any, Callable, Optional

from core.portable.paths import detect_base_dir, default_workspace_dir
from core.fs.safe_workspace_writer import SafeWorkspaceWriter
from core.tooling.invoker import InvokeContext, invoke_tool


class ReportWriter:
    def __init__(self, runner=None, registry=None, workspace_root: Optional[str] = None, base_dir: Optional[str] = None):
        self.runner = runner
        self.registry = registry
        self.base_dir = base_dir or detect_base_dir()
        self.workspace_root = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(self.base_dir)
        self.safe_writer = SafeWorkspaceWriter(self.workspace_root)

    def write_report_md(self, path_under_reports: str, content: str, redact: Optional[Callable[[str], str]] = None) -> str:
        text = redact(content) if redact else content
        path = self._resolve_path(path_under_reports)
        self._write_text(path, text)
        return path

    def write_report_json(self, path_under_reports: str, obj: Any, redact: Optional[Callable[[str], str]] = None) -> str:
        text = json.dumps(obj, indent=2, ensure_ascii=True)
        if redact:
            text = redact(text)
        path = self._resolve_path(path_under_reports)
        self._write_text(path, text)
        return path

    def _write_text(self, path: str, text: str) -> None:
        if self.safe_writer.write_text(path, text):
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tool = None
        if self.registry is not None:
            tool = self.registry.tools.get("fs.write_text")
        if tool is not None and self.runner is not None:
            invoke_tool(
                "fs.write_text",
                {"path": path, "text": text, "target": path},
                InvokeContext(runner=self.runner, registry=self.registry, mode=""),
            )
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _resolve_path(self, path_under_reports: str) -> str:
        rel = path_under_reports.replace("/", os.sep).replace("\\", os.sep)
        if rel.startswith(os.sep) or ":" in rel:
            raise ValueError("Report path must be relative")
        reports_dirs = [
            os.path.join(self.workspace_root, "reports"),
            os.path.join(self.base_dir, "reports"),
        ]
        for rd in reports_dirs:
            os.makedirs(rd, exist_ok=True)
            path = os.path.abspath(os.path.join(rd, rel))
            if path.startswith(os.path.abspath(rd) + os.sep) or path == os.path.abspath(rd):
                return path
        raise ValueError("Report path is outside allowed reports directories")
