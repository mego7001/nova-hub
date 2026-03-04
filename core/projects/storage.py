from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

from .models import ProjectMeta, ProjectState


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def load_project_meta(path: str) -> Optional[ProjectMeta]:
    data = _read_json(path)
    if not data:
        return None
    return ProjectMeta.from_dict(data)


def save_project_meta(path: str, meta: ProjectMeta) -> None:
    _write_json(path, meta.to_dict())


def load_project_state(path: str) -> ProjectState:
    data = _read_json(path)
    return ProjectState.from_dict(data)


def save_project_state(path: str, state: ProjectState) -> None:
    _write_json(path, state.to_dict())


def list_project_dirs(projects_root: str) -> List[str]:
    if not os.path.isdir(projects_root):
        return []
    out: List[str] = []
    for name in os.listdir(projects_root):
        if name.startswith("."):
            continue
        p = os.path.join(projects_root, name)
        if os.path.isdir(p):
            out.append(p)
    return out
