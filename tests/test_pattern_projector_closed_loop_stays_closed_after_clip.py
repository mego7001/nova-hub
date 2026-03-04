from __future__ import annotations

import math

import pytest
from core.cad_pipeline.dxf_handler import PolylinePath
from core.cad_pipeline.geometry_engine import PanelFlatPattern
from core.cad_pipeline.pattern_mapper import PatternProjector


def _make_projector(PanelFlatPattern, PatternProjector):
    panel = PanelFlatPattern(
        panel_id=1,
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


def test_pattern_projector_closed_loop_stays_closed_after_clip() -> None:
    projector = _make_projector(PanelFlatPattern, PatternProjector)
    source_poly = PolylinePath(
        points=[(-2.0, -2.0), (12.0, -2.0), (12.0, 12.0), (-2.0, 12.0), (-2.0, -2.0)],
        closed=True,
    )

    mapped = projector.map_polylines([source_poly])

    assert mapped
    theta_limit = math.radians(projector.panel_flat.arc_angle)
    for ring in mapped:
        assert ring.closed is True
        assert len(ring.points) >= 4
        assert ring.points[0] == pytest.approx(ring.points[-1], abs=1e-7)

        for x, y in ring.points[:-1]:
            radius = math.hypot(x, y)
            theta = math.atan2(y, x)
            if theta < 0.0:
                theta += 2.0 * math.pi
            assert projector.r_inner_eff - 1e-4 <= radius <= projector.r_outer_eff + 1e-4
            assert -1e-6 <= theta <= theta_limit + 1e-6
