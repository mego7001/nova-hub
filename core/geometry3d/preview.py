from __future__ import annotations

import math
from typing import Dict, List, Tuple

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

from core.geometry3d import primitives

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


Point3 = Tuple[float, float, float]


def build_preview_edges(model: Dict, segments: int = 24) -> Dict:
    entities = model.get("entities") or []
    edges_by_id: Dict[str, List[Tuple[Point3, Point3]]] = {}
    bounds_min = [float("inf"), float("inf"), float("inf")]
    bounds_max = [float("-inf"), float("-inf"), float("-inf")]
    for e in entities:
        eid = str(e.get("id") or "")
        edges = primitives.entity_edges(e, segments=segments)
        edges_by_id[eid] = edges
        for a, b in edges:
            for p in (a, b):
                bounds_min[0] = min(bounds_min[0], p[0])
                bounds_min[1] = min(bounds_min[1], p[1])
                bounds_min[2] = min(bounds_min[2], p[2])
                bounds_max[0] = max(bounds_max[0], p[0])
                bounds_max[1] = max(bounds_max[1], p[1])
                bounds_max[2] = max(bounds_max[2], p[2])
    if bounds_min[0] == float("inf"):
        bounds_min = [0.0, 0.0, 0.0]
        bounds_max = [0.0, 0.0, 0.0]
    return {"edges": edges_by_id, "bounds_min": bounds_min, "bounds_max": bounds_max}


class Geometry3DView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._edges: Dict[str, List[Tuple[Point3, Point3]]] = {}
        self._visible: Dict[str, bool] = {}
        self._bounds_min = (0.0, 0.0, 0.0)
        self._bounds_max = (0.0, 0.0, 0.0)
        self._yaw = 0.6
        self._pitch = 0.4
        self._zoom = 1.0
        self._last_pos = QPoint()
        self.setMinimumHeight(240)

    def set_model(self, model: Dict) -> None:
        preview = build_preview_edges(model)
        self._edges = preview.get("edges", {})
        self._bounds_min = tuple(preview.get("bounds_min", (0.0, 0.0, 0.0)))
        self._bounds_max = tuple(preview.get("bounds_max", (0.0, 0.0, 0.0)))
        if not self._visible:
            self._visible = {k: True for k in self._edges.keys()}
        else:
            for k in self._edges.keys():
                self._visible.setdefault(k, True)
        self.update()

    def set_visibility(self, entity_id: str, visible: bool) -> None:
        self._visible[str(entity_id)] = bool(visible)
        self.update()

    def clear(self) -> None:
        self._edges = {}
        self._visible = {}
        self.update()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 0.87
        self._zoom = max(0.2, min(4.0, self._zoom * factor))
        self.update()

    def mousePressEvent(self, event) -> None:
        self._last_pos = event.position().toPoint()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        dx = pos.x() - self._last_pos.x()
        dy = pos.y() - self._last_pos.y()
        self._yaw += dx * 0.01
        self._pitch += dy * 0.01
        self._last_pos = pos
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0b1220"))
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#38bdf8"))
        pen.setWidthF(1.2)
        painter.setPen(pen)

        center = (
            (self._bounds_min[0] + self._bounds_max[0]) / 2.0,
            (self._bounds_min[1] + self._bounds_max[1]) / 2.0,
            (self._bounds_min[2] + self._bounds_max[2]) / 2.0,
        )
        max_dim = max(
            abs(self._bounds_max[0] - self._bounds_min[0]),
            abs(self._bounds_max[1] - self._bounds_min[1]),
            abs(self._bounds_max[2] - self._bounds_min[2]),
            1.0,
        )
        distance = max_dim * 2.5
        w = self.width()
        h = self.height()

        if HAS_NUMPY and self._edges:
            # Batch projection for performance
            all_pts = []
            edge_groups = []
            for eid, edges in self._edges.items():
                if self._visible.get(eid, True):
                    start_idx = len(all_pts)
                    for a, b in edges:
                        all_pts.extend([a, b])
                    edge_groups.append((start_idx, len(edges)))
            
            if all_pts:
                pts_np = np.array(all_pts, dtype=np.float32)
                projected = _project_batch(pts_np, center, self._yaw, self._pitch, self._zoom, distance, w, h)
                
                for start, count in edge_groups:
                    for i in range(count):
                        p1 = projected[start + i*2]
                        p2 = projected[start + i*2 + 1]
                        painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
        else:
            # Fallback to per-point projection
            for eid, edges in self._edges.items():
                if not self._visible.get(eid, True):
                    continue
                for a, b in edges:
                    pa = _project(a, center, self._yaw, self._pitch, self._zoom, distance, w, h)
                    pb = _project(b, center, self._yaw, self._pitch, self._zoom, distance, w, h)
                    painter.drawLine(int(pa[0]), int(pa[1]), int(pb[0]), int(pb[1]))


def _project(p: Point3, center: Point3, yaw: float, pitch: float, zoom: float, distance: float, w: int, h: int) -> Tuple[float, float]:
    x = p[0] - center[0]
    y = p[1] - center[1]
    z = p[2] - center[2]

    # rotate around y
    cyop, syop = math.cos(yaw), math.sin(yaw)
    x, z = x * cyop + z * syop, -x * syop + z * cyop
    # rotate around x
    cxop, sxop = math.cos(pitch), math.sin(pitch)
    y, z = y * cxop - z * sxop, y * sxop + z * cxop

    scale = zoom * 120.0
    denom = (distance + z) if (distance + z) != 0 else 1.0
    return (x * scale) / denom + w / 2.0, (-y * scale) / denom + h / 2.0


def _project_batch(points: np.ndarray, center: Point3, yaw: float, pitch: float, zoom: float, distance: float, w: int, h: int) -> np.ndarray:
    pts = points - np.array(center)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]

    # rotate around y
    cy, sy = np.cos(yaw), np.sin(yaw)
    x_new = x * cy + z * sy
    z_new = -x * sy + z * cy
    x, z = x_new, z_new

    # rotate around x
    cp, sp = np.cos(pitch), np.sin(pitch)
    y_new = y * cp - z * sp
    z_new = y * sp + z * cp
    y, z = y_new, z_new

    scale = zoom * 120.0
    denom = distance + z
    denom[denom == 0] = 1.0
    
    px = (x * scale) / denom + w / 2.0
    py = (-y * scale) / denom + h / 2.0
    return np.column_stack((px, py))
