from __future__ import annotations

import math
from typing import Dict, List, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


Point3 = Tuple[float, float, float]


def make_box(width: float, depth: float, height: float, center: Point3 = (0.0, 0.0, 0.0)) -> Dict:
    return {
        "type": "box",
        "dims": {"x": float(width), "y": float(depth), "z": float(height)},
        "position": {"x": float(center[0]), "y": float(center[1]), "z": float(center[2])},
    }


def make_cylinder(diameter: float, height: float, center: Point3 = (0.0, 0.0, 0.0), hollow: bool = False, thickness: float = 0.0) -> Dict:
    return {
        "type": "cylinder",
        "dims": {"diameter": float(diameter), "height": float(height)},
        "position": {"x": float(center[0]), "y": float(center[1]), "z": float(center[2])},
        "hollow": bool(hollow),
        "thickness": float(thickness),
    }


def make_sphere(diameter: float, center: Point3 = (0.0, 0.0, 0.0)) -> Dict:
    return {
        "type": "sphere",
        "dims": {"diameter": float(diameter)},
        "position": {"x": float(center[0]), "y": float(center[1]), "z": float(center[2])},
    }


def make_cone(diameter: float, height: float, center: Point3 = (0.0, 0.0, 0.0)) -> Dict:
    return {
        "type": "cone",
        "dims": {"diameter": float(diameter), "height": float(height)},
        "position": {"x": float(center[0]), "y": float(center[1]), "z": float(center[2])},
    }


def entity_center(entity: Dict) -> Point3:
    pos = entity.get("position") or {}
    return (float(pos.get("x", 0.0)), float(pos.get("y", 0.0)), float(pos.get("z", 0.0)))


def entity_bbox(entity: Dict) -> Tuple[Point3, Point3]:
    typ = str(entity.get("type") or "").lower()
    cx, cy, cz = entity_center(entity)
    if typ == "box":
        d = entity.get("dims") or {}
        x = float(d.get("x", 0.0))
        y = float(d.get("y", 0.0))
        z = float(d.get("z", 0.0))
        return (cx - x / 2, cy - y / 2, cz - z / 2), (cx + x / 2, cy + y / 2, cz + z / 2)
    if typ in ("cylinder", "cone"):
        d = entity.get("dims") or {}
        diameter = float(d.get("diameter", 0.0))
        height = float(d.get("height", 0.0))
        r = diameter / 2.0
        return (cx - r, cy - r, cz - height / 2), (cx + r, cy + r, cz + height / 2)
    if typ == "sphere":
        d = entity.get("dims") or {}
        diameter = float(d.get("diameter", 0.0))
        r = diameter / 2.0
        return (cx - r, cy - r, cz - r), (cx + r, cy + r, cz + r)
    return (cx, cy, cz), (cx, cy, cz)


def entity_volume(entity: Dict) -> float:
    typ = str(entity.get("type") or "").lower()
    d = entity.get("dims") or {}
    if typ == "box":
        return float(d.get("x", 0.0)) * float(d.get("y", 0.0)) * float(d.get("z", 0.0))
    if typ == "cylinder":
        r = float(d.get("diameter", 0.0)) / 2.0
        h = float(d.get("height", 0.0))
        vol = math.pi * r * r * h
        if entity.get("hollow"):
            t = float(entity.get("thickness", 0.0))
            r2 = max(r - t, 0.0)
            vol = math.pi * (r * r - r2 * r2) * h
        return vol
    if typ == "sphere":
        r = float(d.get("diameter", 0.0)) / 2.0
        return (4.0 / 3.0) * math.pi * r * r * r
    if typ == "cone":
        r = float(d.get("diameter", 0.0)) / 2.0
        h = float(d.get("height", 0.0))
        return (1.0 / 3.0) * math.pi * r * r * h
    return 0.0


def entity_edges(entity: Dict, segments: int = 24) -> List[Tuple[Point3, Point3]]:
    typ = str(entity.get("type") or "").lower()
    edges: List[Tuple[Point3, Point3]] = []
    cx, cy, cz = entity_center(entity)
    if typ == "box":
        d = entity.get("dims") or {}
        x = float(d.get("x", 0.0)) / 2.0
        y = float(d.get("y", 0.0)) / 2.0
        z = float(d.get("z", 0.0)) / 2.0
        corners = [
            (cx - x, cy - y, cz - z),
            (cx + x, cy - y, cz - z),
            (cx + x, cy + y, cz - z),
            (cx - x, cy + y, cz - z),
            (cx - x, cy - y, cz + z),
            (cx + x, cy - y, cz + z),
            (cx + x, cy + y, cz + z),
            (cx - x, cy + y, cz + z),
        ]
        idx_edges = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        ]
        for a, b in idx_edges:
            edges.append((corners[a], corners[b]))
        return edges
    if typ in ("cylinder", "cone", "sphere"):
        d = entity.get("dims") or {}
        diameter = float(d.get("diameter", 0.0))
        height = float(d.get("height", 0.0))
        r = diameter / 2.0
        seg = max(8, segments)
        if typ == "cylinder":
            if HAS_NUMPY:
                angs = np.linspace(0, 2 * np.pi, seg, endpoint=False)
                xs = cx + r * np.cos(angs)
                ys = cy + r * np.sin(angs)
                z1, z2 = cz - height / 2.0, cz + height / 2.0
                pts1 = [(float(x), float(y), float(z1)) for x, y in zip(xs, ys)]
                pts2 = [(float(x), float(y), float(z2)) for x, y in zip(xs, ys)]
            else:
                z1 = cz - height / 2.0
                z2 = cz + height / 2.0
                pts1, pts2 = [], []
                for i in range(seg):
                    ang = 2 * math.pi * i / seg
                    x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
                    pts1.append((x, y, z1))
                    pts2.append((x, y, z2))
            
            for i in range(seg):
                edges.append((pts1[i], pts1[(i + 1) % seg]))
                edges.append((pts2[i], pts2[(i + 1) % seg]))
                edges.append((pts1[i], pts2[i]))
            return edges
        if typ == "cone":
            z1, z2 = cz - height / 2.0, cz + height / 2.0
            apex = (cx, cy, z2)
            if HAS_NUMPY:
                angs = np.linspace(0, 2 * np.pi, seg, endpoint=False)
                xs = cx + r * np.cos(angs)
                ys = cy + r * np.sin(angs)
                pts = [(float(x), float(y), float(z1)) for x, y in zip(xs, ys)]
            else:
                pts = []
                for i in range(seg):
                    ang = 2 * math.pi * i / seg
                    pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang), z1))
            for i in range(seg):
                edges.append((pts[i], pts[(i + 1) % seg]))
                edges.append((pts[i], apex))
            return edges
        if typ == "sphere":
            if HAS_NUMPY:
                seg = max(12, segments)
                for axis in ("xy", "xz", "yz"):
                    angs = np.linspace(0, 2 * np.pi, seg, endpoint=False)
                    if axis == "xy":
                        xs, ys, zs = cx + r * np.cos(angs), cy + r * np.sin(angs), np.full(seg, cz)
                    elif axis == "xz":
                        xs, ys, zs = cx + r * np.cos(angs), np.full(seg, cy), cz + r * np.sin(angs)
                    else:
                        xs, ys, zs = np.full(seg, cx), cy + r * np.cos(angs), cz + r * np.sin(angs)
                    pts = [(float(x), float(y), float(z)) for x, y, z in zip(xs, ys, zs)]
                    for i in range(seg):
                        edges.append((pts[i], pts[(i + 1) % seg]))
            else:
                seg = max(12, segments)
                for axis in ("xy", "xz", "yz"):
                    pts = []
                    for i in range(seg):
                        ang = 2 * math.pi * i / seg
                        if axis == "xy":
                            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang), cz))
                        elif axis == "xz":
                            pts.append((cx + r * math.cos(ang), cy, cz + r * math.sin(ang)))
                        else:
                            pts.append((cx, cy + r * math.cos(ang), cz + r * math.sin(ang)))
                    for i in range(seg):
                        edges.append((pts[i], pts[(i + 1) % seg]))
            return edges
    return edges


def entity_triangles(entity: Dict, segments: int = 24) -> List[Tuple[Point3, Point3, Point3]]:
    typ = str(entity.get("type") or "").lower()
    tris: List[Tuple[Point3, Point3, Point3]] = []
    cx, cy, cz = entity_center(entity)
    if typ == "box":
        d = entity.get("dims") or {}
        x = float(d.get("x", 0.0)) / 2.0
        y = float(d.get("y", 0.0)) / 2.0
        z = float(d.get("z", 0.0)) / 2.0
        v = [
            (cx - x, cy - y, cz - z),
            (cx + x, cy - y, cz - z),
            (cx + x, cy + y, cz - z),
            (cx - x, cy + y, cz - z),
            (cx - x, cy - y, cz + z),
            (cx + x, cy - y, cz + z),
            (cx + x, cy + y, cz + z),
            (cx - x, cy + y, cz + z),
        ]
        faces = [
            (0, 1, 2), (0, 2, 3),
            (4, 5, 6), (4, 6, 7),
            (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6),
            (3, 0, 4), (3, 4, 7),
        ]
        for a, b, c in faces:
            tris.append((v[a], v[b], v[c]))
        return tris
    if typ == "cylinder":
        d = entity.get("dims") or {}
        diameter = float(d.get("diameter", 0.0))
        height = float(d.get("height", 0.0))
        r = diameter / 2.0
        seg = max(12, segments)
        z1, z2 = cz - height / 2.0, cz + height / 2.0
        
        if HAS_NUMPY:
            angs = np.linspace(0, 2 * np.pi, seg, endpoint=False)
            xs = cx + r * np.cos(angs)
            ys = cy + r * np.sin(angs)
            pts1 = [(float(x), float(y), float(z1)) for x, y in zip(xs, ys)]
            pts2 = [(float(x), float(y), float(z2)) for x, y in zip(xs, ys)]
        else:
            pts1, pts2 = [], []
            for i in range(seg):
                ang = 2 * math.pi * i / seg
                x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
                pts1.append((x, y, z1))
                pts2.append((x, y, z2))
                
        for i in range(seg):
            a, b, c, d2 = pts1[i], pts1[(i + 1) % seg], pts2[(i + 1) % seg], pts2[i]
            tris.append((a, b, c))
            tris.append((a, c, d2))
        c1, c2 = (cx, cy, z1), (cx, cy, z2)
        for i in range(seg):
            tris.append((c1, pts1[(i + 1) % seg], pts1[i]))
            tris.append((c2, pts2[i], pts2[(i + 1) % seg]))
        return tris
    if typ == "cone":
        z1, z2 = cz - height / 2.0, cz + height / 2.0
        apex = (cx, cy, z2)
        if HAS_NUMPY:
            angs = np.linspace(0, 2 * np.pi, seg, endpoint=False)
            xs, ys = cx + r * np.cos(angs), cy + r * np.sin(angs)
            pts = [(float(x), float(y), float(z1)) for x, y in zip(xs, ys)]
        else:
            pts = []
            for i in range(seg):
                ang = 2 * math.pi * i / seg
                pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang), z1))
        for i in range(seg):
            tris.append((pts[i], pts[(i + 1) % seg], apex))
        center = (cx, cy, z1)
        for i in range(seg):
            tris.append((center, pts[(i + 1) % seg], pts[i]))
        return tris
    if typ == "sphere":
        seg = max(8, segments // 2)
        if HAS_NUMPY:
            thetas = np.linspace(0, np.pi, seg + 1)
            phis = np.linspace(0, 2 * np.pi, seg * 2 + 1)
            # This could be further vectorized but for now, structured generation is safer
            for i in range(seg):
                t1, t2 = thetas[i], thetas[i+1]
                for j in range(seg * 2):
                    p1_ang, p2_ang = phis[j], phis[j+1]
                    v1 = (float(cx + r * np.sin(t1) * np.cos(p1_ang)), float(cy + r * np.sin(t1) * np.sin(p1_ang)), float(cz + r * np.cos(t1)))
                    v2 = (float(cx + r * np.sin(t2) * np.cos(p1_ang)), float(cy + r * np.sin(t2) * np.sin(p1_ang)), float(cz + r * np.cos(t2)))
                    v3 = (float(cx + r * np.sin(t2) * np.cos(p2_ang)), float(cy + r * np.sin(t2) * np.sin(p2_ang)), float(cz + r * np.cos(t2)))
                    v4 = (float(cx + r * np.sin(t1) * np.cos(p2_ang)), float(cy + r * np.sin(t1) * np.sin(p2_ang)), float(cz + r * np.cos(t1)))
                    tris.append((v1, v2, v3))
                    tris.append((v1, v3, v4))
        else:
            for i in range(seg):
                theta1, theta2 = math.pi * i / seg, math.pi * (i + 1) / seg
                for j in range(seg * 2):
                    phi1, phi2 = 2 * math.pi * j / (seg * 2), 2 * math.pi * (j + 1) / (seg * 2)
                    p1 = (cx + r * math.sin(theta1) * math.cos(phi1), cy + r * math.sin(theta1) * math.sin(phi1), cz + r * math.cos(theta1))
                    p2 = (cx + r * math.sin(theta2) * math.cos(phi1), cy + r * math.sin(theta2) * math.sin(phi1), cz + r * math.cos(theta2))
                    p3 = (cx + r * math.sin(theta2) * math.cos(phi2), cy + r * math.sin(theta2) * math.sin(phi2), cz + r * math.cos(theta2))
                    p4 = (cx + r * math.sin(theta1) * math.cos(phi2), cy + r * math.sin(theta1) * math.sin(phi2), cz + r * math.cos(theta1))
                    tris.append((p1, p2, p3))
                    tris.append((p1, p3, p4))
        return tris
    return tris
