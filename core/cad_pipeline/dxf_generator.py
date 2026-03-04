from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
import math
import os
import re

import ezdxf

from core.utils.optional_deps import require


@dataclass(frozen=True)
class DxfGenerationResult:
    output_path: str
    shape: str
    units: str
    layer: str
    warnings: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "out_dxf": self.output_path,
            "shape": self.shape,
            "units": self.units,
            "layer": self.layer,
            "warnings": list(self.warnings),
        }


_UNITS_MAP = {
    "unitless": 0,
    "in": 1,
    "ft": 2,
    "mm": 4,
    "cm": 5,
    "m": 6,
}


def _safe_float(raw: Any, fallback: float) -> float:
    try:
        value = float(raw)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return float(fallback)
    if not math.isfinite(value):
        return float(fallback)
    return float(value)


def _extract_first_number(text: str, fallback: float) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)", str(text or ""))
    if not match:
        return float(fallback)
    return _safe_float(match.group(1), fallback)


def _normalize_shape(spec_text: str, params: Mapping[str, Any]) -> str:
    shape = str(params.get("shape") or "").strip().lower()
    if shape in ("rectangle", "rect", "circle", "line"):
        return "rectangle" if shape == "rect" else shape
    text = str(spec_text or "").lower()
    if any(token in text for token in ("circle", "دائرة")):
        return "circle"
    if any(token in text for token in ("rectangle", "rect", "box", "مستطيل")):
        return "rectangle"
    if any(token in text for token in ("line", "segment", "خط")):
        return "line"
    return "rectangle"


def _prepare_output_path(output_path: str) -> str:
    raw = str(output_path or "outputs/generated_shape.dxf").strip()
    if not raw:
        raw = "outputs/generated_shape.dxf"
    out = Path(raw)
    if not out.suffix:
        out = out.with_suffix(".dxf")
    out.parent.mkdir(parents=True, exist_ok=True)
    return str(out.resolve())


def _closed_polyline_points(width: float, height: float) -> List[Tuple[float, float]]:
    return [
        (0.0, 0.0),
        (max(1e-6, width), 0.0),
        (max(1e-6, width), max(1e-6, height)),
        (0.0, max(1e-6, height)),
        (0.0, 0.0),
    ]


def _validate_closed(points: List[Tuple[float, float]], warnings: List[str]) -> None:
    if not points:
        warnings.append("No geometry points were generated.")
        return
    if points[0] != points[-1]:
        warnings.append("Polyline was open; auto-closing shape.")


def _line_self_intersection_best_effort(points: List[Tuple[float, float]], warnings: List[str]) -> None:
    ok, _msg = require(
        "shapely",
        "pip install -r requirements-cad.txt",
        "DXF geometry validation",
    )
    if not ok:
        return
    from shapely.geometry import LineString  # type: ignore
    try:
        line = LineString(points)
        if not line.is_simple:
            warnings.append("Detected possible self-intersection in generated profile.")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return


def generate_dxf(
    *,
    spec_text: str = "",
    params: Optional[Mapping[str, Any]] = None,
    output_path: str = "outputs/generated_shape.dxf",
    units: str = "mm",
    layer: str = "OUTLINE",
) -> Dict[str, Any]:
    data = dict(params or {})
    shape = _normalize_shape(spec_text, data)
    out_path = _prepare_output_path(output_path)
    normalized_units = str(units or "mm").strip().lower()
    if normalized_units not in _UNITS_MAP:
        normalized_units = "mm"

    warnings: List[str] = []
    doc = ezdxf.new("R2010")
    doc.units = _UNITS_MAP.get(normalized_units, _UNITS_MAP["mm"])
    model = doc.modelspace()
    layer_name = str(layer or "OUTLINE").strip() or "OUTLINE"
    if layer_name not in doc.layers:
        doc.layers.new(name=layer_name)

    if shape == "circle":
        radius = _safe_float(data.get("radius"), _extract_first_number(spec_text, 50.0))
        radius = max(1e-6, radius)
        model.add_circle((0.0, 0.0), radius=radius, dxfattribs={"layer": layer_name})
    elif shape == "line":
        length = _safe_float(data.get("length"), _extract_first_number(spec_text, 100.0))
        length = max(1e-6, length)
        model.add_line((0.0, 0.0), (length, 0.0), dxfattribs={"layer": layer_name})
    else:
        width = _safe_float(data.get("width"), 120.0)
        height = _safe_float(data.get("height"), 80.0)
        pts = _closed_polyline_points(width, height)
        _validate_closed(pts, warnings)
        _line_self_intersection_best_effort(pts, warnings)
        model.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer_name})

    doc.saveas(out_path)
    return DxfGenerationResult(
        output_path=out_path,
        shape=shape,
        units=normalized_units,
        layer=layer_name,
        warnings=tuple(warnings),
    ).to_dict()
