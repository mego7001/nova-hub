from __future__ import annotations

import pytest
from shapely.geometry import Polygon
from core.cad_pipeline.dxf_handler import PolylinePath
from core.cad_pipeline.geometry_engine import PanelFlatPattern
from core.cad_pipeline.pattern_mapper import PatternProjector


def _make_projector(PanelFlatPattern, PatternProjector):
    panel = PanelFlatPattern(
        panel_id=2,
        r_outer=100.0,
        r_inner=50.0,
        arc_angle=90.0,
        sheet_width_flat=50.0,
        sheet_length_flat=120.0,
        safe_zone=10.0,
        overlap=0.0,
        panel_type="normal",
    )
    return PatternProjector(
        panel_flat=panel,
        pattern_width=10.0,
        pattern_height=10.0,
        min_x=0.0,
        min_y=0.0,
        interpolation_density=1,
    )


def test_pattern_projector_closed_inside_safe_zone_unchanged() -> None:
    projector = _make_projector(PanelFlatPattern, PatternProjector)
    source_points = [(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0), (4.0, 4.0)]
    source_poly = PolylinePath(points=source_points, closed=True)

    mapped = projector.map_polylines([source_poly])

    assert len(mapped) == 1
    ring = mapped[0]
    assert ring.closed is True
    assert ring.points[0] == pytest.approx(ring.points[-1], abs=1e-7)

    expected_points = [projector._map_point(point, clamp=False) for point in source_points]
    expected_area = Polygon(expected_points).area
    actual_area = Polygon(ring.points).area

    assert actual_area == pytest.approx(expected_area, rel=1e-6, abs=1e-6)
