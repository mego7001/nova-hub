from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Circle:
    cx: float
    cy: float
    r: float


@dataclass
class Rect:
    cx: float
    cy: float
    w: float
    h: float


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float


def normalize_entity(entity: Dict[str, Any]) -> Dict[str, Any]:
    typ = str(entity.get("type") or "").lower()
    if typ == "circle":
        return {
            "type": "circle",
            "cx": float(entity.get("cx", 0.0)),
            "cy": float(entity.get("cy", 0.0)),
            "r": float(entity.get("r", 0.0)),
        }
    if typ == "rect":
        return {
            "type": "rect",
            "cx": float(entity.get("cx", 0.0)),
            "cy": float(entity.get("cy", 0.0)),
            "w": float(entity.get("w", 0.0)),
            "h": float(entity.get("h", 0.0)),
        }
    if typ == "line":
        return {
            "type": "line",
            "x1": float(entity.get("x1", 0.0)),
            "y1": float(entity.get("y1", 0.0)),
            "x2": float(entity.get("x2", 0.0)),
            "y2": float(entity.get("y2", 0.0)),
        }
    return {}


def entity_summary(entity: Dict[str, Any]) -> str:
    typ = str(entity.get("type") or "").lower()
    if typ == "circle":
        return f"Circle r={entity.get('r')} @ ({entity.get('cx')},{entity.get('cy')})"
    if typ == "rect":
        return f"Rect {entity.get('w')}x{entity.get('h')} @ ({entity.get('cx')},{entity.get('cy')})"
    if typ == "line":
        return f"Line ({entity.get('x1')},{entity.get('y1')}) -> ({entity.get('x2')},{entity.get('y2')})"
    return "Unknown entity"
