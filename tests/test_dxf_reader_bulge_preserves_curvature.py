from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from core.cad_pipeline.dxf_handler import PatternDXFReader


def _distance_point_to_line(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    vx = end[0] - start[0]
    vy = end[1] - start[1]
    wx = point[0] - start[0]
    wy = point[1] - start[1]
    line_len_sq = vx * vx + vy * vy
    if line_len_sq <= 0.0:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    projection = (wx * vx + wy * vy) / line_len_sq
    closest_x = start[0] + projection * vx
    closest_y = start[1] + projection * vy
    return math.hypot(point[0] - closest_x, point[1] - closest_y)


def test_dxf_reader_bulge_preserves_curvature(tmp_path: Path) -> None:
    dxf_path = tmp_path / "bulge_arc.dxf"
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Quarter-circle arc bulge from (1,0) to (0,1).
    bulge = math.tan(math.radians(90.0) / 4.0)
    msp.add_lwpolyline(
        [(1.0, 0.0, 0.0, 0.0, bulge), (0.0, 1.0, 0.0, 0.0, 0.0)],
        format="xyseb",
    )
    doc.saveas(dxf_path)

    reader = PatternDXFReader(
        str(dxf_path),
        pattern_config={"pattern": {"arc_segments": 32}},
    )
    polylines = reader.get_polylines()

    assert len(polylines) == 1
    points = polylines[0].points
    assert len(points) > 2

    midpoint = points[len(points) // 2]
    deviation = _distance_point_to_line(midpoint, points[0], points[-1])
    assert deviation > 0.05
