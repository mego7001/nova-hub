from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


class SketchView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self._zoom = 1.0
        self._grid_size = 50
        self._grid_extent = 2000
        self._draw_grid()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.2 if delta > 0 else 0.85
        self._zoom = max(0.1, min(5.0, self._zoom * factor))
        self.setTransform(self.transform().scale(factor, factor))

    def set_entities(self, entities: List[Dict[str, Any]]) -> None:
        self._scene.clear()
        self._draw_grid()
        for e in entities or []:
            self._draw_entity(e)

    def _draw_grid(self) -> None:
        pen = QPen(QColor("#e5e7eb"))
        pen.setWidthF(0.0)
        extent = self._grid_extent
        step = self._grid_size
        for x in range(-extent, extent + step, step):
            self._scene.addLine(x, -extent, x, extent, pen)
        for y in range(-extent, extent + step, step):
            self._scene.addLine(-extent, y, extent, y, pen)
        axis_pen = QPen(QColor("#9ca3af"))
        axis_pen.setWidthF(0.0)
        self._scene.addLine(-extent, 0, extent, 0, axis_pen)
        self._scene.addLine(0, -extent, 0, extent, axis_pen)

    def _draw_entity(self, e: Dict[str, Any]) -> None:
        typ = str(e.get("type") or "").lower()
        pen = QPen(QColor("#111827"))
        pen.setWidthF(1.2)
        if typ == "circle":
            cx = float(e.get("cx", 0.0))
            cy = float(e.get("cy", 0.0))
            r = float(e.get("r", 0.0))
            self._scene.addEllipse(cx - r, cy - r, 2 * r, 2 * r, pen)
        elif typ == "rect":
            cx = float(e.get("cx", 0.0))
            cy = float(e.get("cy", 0.0))
            w = float(e.get("w", 0.0))
            h = float(e.get("h", 0.0))
            self._scene.addRect(cx - w / 2.0, cy - h / 2.0, w, h, pen)
        elif typ == "line":
            x1 = float(e.get("x1", 0.0))
            y1 = float(e.get("y1", 0.0))
            x2 = float(e.get("x2", 0.0))
            y2 = float(e.get("y2", 0.0))
            self._scene.addLine(x1, y1, x2, y2, pen)
