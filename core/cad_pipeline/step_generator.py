from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional
import math
import re

from core.utils.optional_deps import require


def _safe_float(raw: Any, fallback: float) -> float:
    try:
        value = float(raw)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return float(fallback)
    if not math.isfinite(value):
        return float(fallback)
    return float(value)


def _first_number(text: str, fallback: float) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)", str(text or ""))
    if not match:
        return float(fallback)
    return _safe_float(match.group(1), fallback)


def _normalize_shape(spec_text: str, params: Mapping[str, Any]) -> str:
    shape = str(params.get("shape") or "").strip().lower()
    if shape in ("box", "cylinder"):
        return shape
    text = str(spec_text or "").lower()
    if "cylinder" in text or "اسطوانة" in text:
        return "cylinder"
    return "box"


def _prepare_output(output_path: str) -> str:
    raw = str(output_path or "outputs/generated_part.step").strip() or "outputs/generated_part.step"
    out = Path(raw)
    if not out.suffix:
        out = out.with_suffix(".step")
    out.parent.mkdir(parents=True, exist_ok=True)
    return str(out.resolve())


def generate_step(
    *,
    spec_text: str = "",
    params: Optional[Mapping[str, Any]] = None,
    output_path: str = "outputs/generated_part.step",
) -> Dict[str, Any]:
    data = dict(params or {})
    shape = _normalize_shape(spec_text, data)
    out_path = _prepare_output(output_path)

    ok, msg = require(
        "cadquery",
        "pip install -r requirements-3d.txt",
        "STEP export",
    )
    if not ok:
        return {
            "ok": False,
            "shape": shape,
            "out_step": out_path,
            "error": msg,
        }
    import cadquery as cq  # type: ignore
    from cadquery import exporters  # type: ignore

    if shape == "cylinder":
        radius = max(1e-6, _safe_float(data.get("radius"), _first_number(spec_text, 20.0)))
        height = max(1e-6, _safe_float(data.get("height"), 50.0))
        part = cq.Workplane("XY").circle(radius).extrude(height)
    else:
        width = max(1e-6, _safe_float(data.get("width"), 60.0))
        depth = max(1e-6, _safe_float(data.get("depth"), 40.0))
        height = max(1e-6, _safe_float(data.get("height"), 20.0))
        part = cq.Workplane("XY").box(width, depth, height)

    exporters.export(part, out_path)
    if not Path(out_path).exists():
        return {
            "ok": False,
            "shape": shape,
            "out_step": out_path,
            "error": "STEP export reported success but output file was not created.",
        }
    return {
        "ok": True,
        "shape": shape,
        "out_step": out_path,
    }
