from __future__ import annotations

import json
import os
from typing import Dict

from core.fs.safe_workspace_writer import SafeWorkspaceWriter
from core.portable.paths import detect_base_dir, default_workspace_dir
from core.security.secrets import SecretsManager


def _workspace_root() -> str:
    base = detect_base_dir()
    return os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)


def engineering_dir(project_id: str, workspace_root: str | None = None) -> str:
    ws = workspace_root or _workspace_root()
    return os.path.join(ws, "projects", project_id, "engineering")


def save_state(
    project_id: str,
    state: Dict,
    assumptions: Dict,
    warnings: Dict,
    report: str,
    workspace_root: str | None = None,
) -> Dict:
    ws = workspace_root or _workspace_root()
    base = engineering_dir(project_id, ws)
    writer = SafeWorkspaceWriter(ws)
    os.makedirs(base, exist_ok=True)

    state_path = os.path.join(base, "engineering_state.json")
    assumptions_path = os.path.join(base, "engineering_assumptions.json")
    warnings_path = os.path.join(base, "engineering_warnings.json")
    report_path = os.path.join(base, "engineering_report.md")

    state_text = _redact_json(state)
    assumptions_text = _redact_json(assumptions)
    warnings_text = _redact_json(warnings)
    report_text = SecretsManager.redact_text(report or "")

    if not writer.write_text(state_path, state_text):
        raise RuntimeError("Workspace writer blocked engineering_state.json")
    if not writer.write_text(assumptions_path, assumptions_text):
        raise RuntimeError("Workspace writer blocked engineering_assumptions.json")
    if not writer.write_text(warnings_path, warnings_text):
        raise RuntimeError("Workspace writer blocked engineering_warnings.json")
    if not writer.write_text(report_path, report_text):
        raise RuntimeError("Workspace writer blocked engineering_report.md")

    return {
        "state_path": state_path,
        "assumptions_path": assumptions_path,
        "warnings_path": warnings_path,
        "report_path": report_path,
    }


def load_state(project_id: str, workspace_root: str | None = None) -> Dict:
    ws = workspace_root or _workspace_root()
    base = engineering_dir(project_id, ws)
    def _read(path: str, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                if path.endswith(".json"):
                    return json.load(f)
                return f.read()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return default

    return {
        "state": _read(os.path.join(base, "engineering_state.json"), {}),
        "assumptions": _read(os.path.join(base, "engineering_assumptions.json"), {}),
        "warnings": _read(os.path.join(base, "engineering_warnings.json"), {}),
        "report": _read(os.path.join(base, "engineering_report.md"), ""),
    }


def _redact_json(payload: Dict) -> str:
    def _redact_val(v):
        if isinstance(v, str):
            return SecretsManager.redact_text(v)
        if isinstance(v, dict):
            return {k: _redact_val(vv) for k, vv in v.items()}
        if isinstance(v, list):
            return [_redact_val(vv) for vv in v]
        return v

    red = _redact_val(payload or {})
    return json.dumps(red, indent=2, ensure_ascii=False)
