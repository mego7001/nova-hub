from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from core.portable.paths import detect_base_dir, default_workspace_dir
from .model import normalize_entity


def _workspace_root(workspace_root: Optional[str] = None) -> str:
    base = detect_base_dir()
    return workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)


def _sketch_path(project_id: str, workspace_root: Optional[str] = None) -> str:
    ws = _workspace_root(workspace_root)
    return os.path.join(ws, "projects", project_id, "sketch", "sketch.json")


def load_sketch(project_id: str, workspace_root: Optional[str] = None) -> Dict[str, Any]:
    path = _sketch_path(project_id, workspace_root)
    if not os.path.exists(path):
        return {"entities": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        entities = [normalize_entity(e) for e in data.get("entities") or []]
        return {"entities": [e for e in entities if e]}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {"entities": []}


def save_sketch(project_id: str, data: Dict[str, Any], workspace_root: Optional[str] = None) -> str:
    path = _sketch_path(project_id, workspace_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "entities": [normalize_entity(e) for e in (data.get("entities") or []) if normalize_entity(e)],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)
    return path


def apply_ops(project_id: str, ops: List[Dict[str, Any]], workspace_root: Optional[str] = None) -> Dict[str, Any]:
    state = load_sketch(project_id, workspace_root)
    entities = list(state.get("entities") or [])

    for op in ops or []:
        typ = op.get("op")
        if typ == "clear":
            entities = []
            continue
        if typ == "add_circle":
            entities.append({
                "type": "circle",
                "cx": float(op.get("cx", 0.0)),
                "cy": float(op.get("cy", 0.0)),
                "r": float(op.get("r", 0.0)),
            })
        elif typ == "add_rect":
            entities.append({
                "type": "rect",
                "cx": float(op.get("cx", 0.0)),
                "cy": float(op.get("cy", 0.0)),
                "w": float(op.get("w", 0.0)),
                "h": float(op.get("h", 0.0)),
            })
        elif typ == "add_line":
            entities.append({
                "type": "line",
                "x1": float(op.get("x1", 0.0)),
                "y1": float(op.get("y1", 0.0)),
                "x2": float(op.get("x2", 0.0)),
                "y2": float(op.get("y2", 0.0)),
            })

    path = save_sketch(project_id, {"entities": entities}, workspace_root)
    return {"entities": entities, "path": path, "count": len(entities)}
