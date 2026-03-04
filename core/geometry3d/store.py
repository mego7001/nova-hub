from __future__ import annotations

import json
import os
from typing import Dict, List

from core.fs.safe_workspace_writer import SafeWorkspaceWriter
from core.portable.paths import detect_base_dir, default_workspace_dir
from core.geometry3d import export as geom_export


def _workspace_root() -> str:
    base = detect_base_dir()
    return os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)


def geometry_dir(project_id: str, workspace_root: str | None = None) -> str:
    ws = workspace_root or _workspace_root()
    return os.path.join(ws, "projects", project_id, "geometry3d")


def load_model(project_id: str, workspace_root: str | None = None) -> Dict:
    base = geometry_dir(project_id, workspace_root)
    model_path = os.path.join(base, "model.json")
    assumptions_path = os.path.join(base, "assumptions.json")
    warnings_path = os.path.join(base, "warnings.json")
    reasoning_path = os.path.join(base, "reasoning.md")
    model = {}
    assumptions: List[str] = []
    warnings: List[Dict] = []
    reasoning = ""
    if os.path.exists(model_path):
        try:
            with open(model_path, "r", encoding="utf-8") as f:
                model = json.load(f) or {}
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            model = {}
    if os.path.exists(assumptions_path):
        try:
            with open(assumptions_path, "r", encoding="utf-8") as f:
                assumptions = json.load(f) or []
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            assumptions = []
    if os.path.exists(warnings_path):
        try:
            with open(warnings_path, "r", encoding="utf-8") as f:
                warnings = json.load(f) or []
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            warnings = []
    if os.path.exists(reasoning_path):
        try:
            with open(reasoning_path, "r", encoding="utf-8") as f:
                reasoning = f.read()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            reasoning = ""
    return {
        "model": model,
        "assumptions": assumptions,
        "warnings": warnings,
        "reasoning": reasoning,
    }


def save_model(
    project_id: str,
    model: Dict,
    assumptions: List[str],
    warnings: List[Dict],
    reasoning: str,
    workspace_root: str | None = None,
) -> Dict:
    ws = workspace_root or _workspace_root()
    base = geometry_dir(project_id, ws)
    writer = SafeWorkspaceWriter(ws)

    os.makedirs(base, exist_ok=True)
    model_path = os.path.join(base, "model.json")
    assumptions_path = os.path.join(base, "assumptions.json")
    warnings_path = os.path.join(base, "warnings.json")
    reasoning_path = os.path.join(base, "reasoning.md")
    preview_path = os.path.join(base, "preview.stl")

    if not writer.write_text(model_path, json.dumps(model, indent=2, ensure_ascii=True)):
        raise RuntimeError("Workspace writer blocked model.json")
    if not writer.write_text(assumptions_path, json.dumps(assumptions, indent=2, ensure_ascii=True)):
        raise RuntimeError("Workspace writer blocked assumptions.json")
    if not writer.write_text(warnings_path, json.dumps(warnings, indent=2, ensure_ascii=True)):
        raise RuntimeError("Workspace writer blocked warnings.json")
    if not writer.write_text(reasoning_path, reasoning):
        raise RuntimeError("Workspace writer blocked reasoning.md")

    geom_export.export_stl(model, preview_path, name=project_id)

    return {
        "model_path": model_path,
        "assumptions_path": assumptions_path,
        "warnings_path": warnings_path,
        "reasoning_path": reasoning_path,
        "preview_path": preview_path,
    }
