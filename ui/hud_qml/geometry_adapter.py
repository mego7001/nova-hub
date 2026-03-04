from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.geometry3d import primitives
from core.geometry3d import store as geometry_store


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return float(default)


class GeometryAdapter:
    """Reads project geometry data and maps it to HUD viewport entities."""

    def load_entities(self, project_id: str, workspace_root: Optional[str] = None) -> List[Dict[str, Any]]:
        pid = str(project_id or "").strip()
        if not pid:
            return []
        payload = geometry_store.load_model(pid, workspace_root=workspace_root)
        model = payload.get("model") if isinstance(payload, dict) else {}
        entities = model.get("entities") if isinstance(model, dict) else []
        if not isinstance(entities, list):
            return []

        out: List[Dict[str, Any]] = []
        for i, raw in enumerate(entities):
            if not isinstance(raw, dict):
                continue
            typ = str(raw.get("type") or "shape").lower()
            eid = str(raw.get("id") or f"{typ}_{i+1}")
            pos = raw.get("position") or {}
            x = _f(pos.get("x", 0.0))
            y = _f(pos.get("y", 0.0))
            z = _f(pos.get("z", 0.0))
            bmin, bmax = primitives.entity_bbox(raw)
            sx = max(2.0, abs(_f(bmax[0]) - _f(bmin[0])))
            sy = max(2.0, abs(_f(bmax[1]) - _f(bmin[1])))
            sz = max(2.0, abs(_f(bmax[2]) - _f(bmin[2])))
            out.append(
                {
                    "entity_id": eid,
                    "name": str(raw.get("name") or eid),
                    "visible": bool(raw.get("visible", True)),
                    "x": x,
                    "y": y,
                    "z": z,
                    "size_x": sx,
                    "size_y": sy,
                    "size_z": sz,
                    "size": max(sx, sy, sz),
                    "category": typ,
                    "color": "",
                }
            )
        return out

    def sample_entities(self) -> List[Dict[str, Any]]:
        return [
            {
                "entity_id": "sample_box_1",
                "name": "Sample Box 1",
                "visible": True,
                "x": -60.0,
                "y": 20.0,
                "z": 0.0,
                "size_x": 44.0,
                "size_y": 44.0,
                "size_z": 44.0,
                "size": 44.0,
                "category": "box",
                "color": "",
            },
            {
                "entity_id": "sample_box_2",
                "name": "Sample Box 2",
                "visible": True,
                "x": 42.0,
                "y": 25.0,
                "z": -54.0,
                "size_x": 34.0,
                "size_y": 52.0,
                "size_z": 34.0,
                "size": 52.0,
                "category": "box",
                "color": "",
            },
        ]
