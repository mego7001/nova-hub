from __future__ import annotations

import math
from typing import Dict, List, Tuple

Point3 = Tuple[float, float, float]


def combine(entities: List[Dict], operations: List[Dict] | None = None) -> Dict:
    return {
        "entities": entities or [],
        "operations": operations or [],
    }


def rotate_point(p: Point3, rot: Dict[str, float]) -> Point3:
    rx = math.radians(float(rot.get("x", 0.0)))
    ry = math.radians(float(rot.get("y", 0.0)))
    rz = math.radians(float(rot.get("z", 0.0)))
    x, y, z = p
    # rotate around x
    cy = math.cos(rx)
    sy = math.sin(rx)
    y, z = y * cy - z * sy, y * sy + z * cy
    # rotate around y
    cx = math.cos(ry)
    sx = math.sin(ry)
    x, z = x * cx + z * sx, -x * sx + z * cx
    # rotate around z
    cz = math.cos(rz)
    sz = math.sin(rz)
    x, y = x * cz - y * sz, x * sz + y * cz
    return (x, y, z)


def apply_transform(p: Point3, pos: Dict[str, float], rot: Dict[str, float] | None = None) -> Point3:
    rp = rotate_point(p, rot or {})
    return (rp[0] + float(pos.get("x", 0.0)), rp[1] + float(pos.get("y", 0.0)), rp[2] + float(pos.get("z", 0.0)))
