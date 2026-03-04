from __future__ import annotations

"""Conical helix / spiral generator.

DXF is 2D, so we export the XY projection of a helix that advances along the
cone axis. For a cone with height H, bottom radius rb and top radius rt:

  z(theta) = (pitch / (2*pi)) * theta
  r(z) = rb + (rt-rb) * (z/H)
  x = r(theta) * cos(theta), y = r(theta) * sin(theta)

This produces a true conical spiral in XY with linear radius change vs z.
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.utils.dxf_min import polyline, write_dxf


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _conical_helix_xy(
    r_bottom: float,
    r_top: float,
    height: float,
    pitch: float,
    turns: float,
    segments_per_turn: int,
) -> List[Tuple[float, float]]:
    if height <= 0:
        raise ValueError("height must be > 0")
    if pitch <= 0:
        raise ValueError("pitch must be > 0")
    if turns <= 0:
        raise ValueError("turns must be > 0")
    if segments_per_turn < 16:
        segments_per_turn = 16

    theta_max = 2.0 * math.pi * turns
    n = max(32, int(math.ceil(turns * segments_per_turn)))
    pts: List[Tuple[float, float]] = []

    for i in range(n + 1):
        theta = (i / n) * theta_max
        z = (pitch / (2.0 * math.pi)) * theta
        # if user provided turns that implies z > height, clamp to height
        zc = _clamp(z, 0.0, height)
        r = r_bottom + (r_top - r_bottom) * (zc / height)
        pts.append((r * math.cos(theta), r * math.sin(theta)))
    return pts


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    # Defaults tuned for sheet-metal patterning use
    rb = float(config.get("r_bottom", 200.0))
    rt = float(config.get("r_top", 80.0))
    pitch = float(config.get("pitch", 30.0))
    turns = float(config.get("turns", 6.0))
    # If height is not provided, we assume height = turns * pitch (one pitch per turn)
    height = float(config.get("height", turns * pitch))
    spt = int(config.get("segments_per_turn", 160))

    def generate_helix(
        turns: Optional[float] = None,
        pitch: Optional[float] = None,
        r_bottom: Optional[float] = None,
        r_top: Optional[float] = None,
        height: Optional[float] = None,
        segments_per_turn: Optional[int] = None,
        out_dxf: str = "outputs/conical_helix_xy.dxf",
        layer: str = "CONICAL_HELIX",
    ) -> Dict[str, Any]:
        _turns = float(turns if turns is not None else config.get("turns", 6.0))
        _pitch = float(pitch if pitch is not None else config.get("pitch", 30.0))
        _rb = float(r_bottom if r_bottom is not None else config.get("r_bottom", 200.0))
        _rt = float(r_top if r_top is not None else config.get("r_top", 80.0))
        _height = float(height if height is not None else config.get("height", _turns * _pitch))
        _spt = int(segments_per_turn if segments_per_turn is not None else config.get("segments_per_turn", 160))

        pts = _conical_helix_xy(_rb, _rt, _height, _pitch, _turns, _spt)
        ents = [polyline(pts, layer=layer, closed=False)]
        write_dxf(out_dxf, ents)
        return {
            "tool": "conical.generate_helix",
            "r_bottom": _rb,
            "r_top": _rt,
            "height": _height,
            "pitch": _pitch,
            "turns": _turns,
            "segments_per_turn": _spt,
            "out_dxf": os.path.abspath(out_dxf),
            "points": len(pts),
        }

    # Important: this tool writes a DXF => declare it as fs_write so approvals guard file targets.
    registry.register_tool(
        ToolRegistration(
            tool_id="conical.generate_helix",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="conical_generate_helix",
            handler=generate_helix,
            description="Generate a conical helix (XY projection) and export DXF to outputs/",
            default_target="outputs/conical_helix_xy.dxf",
        )
    )
