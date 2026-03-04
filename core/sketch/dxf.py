from __future__ import annotations

from typing import Any, Dict, List


def export_dxf(entities: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    _section(lines, "HEADER")
    _endsec(lines)
    _section(lines, "TABLES")
    _endsec(lines)
    _section(lines, "ENTITIES")
    for e in entities:
        typ = str(e.get("type") or "").lower()
        if typ == "circle":
            _circle(lines, e)
        elif typ == "line":
            _line(lines, e)
        elif typ == "rect":
            _rect(lines, e)
    _endsec(lines)
    lines.append("0")
    lines.append("EOF")
    return "\n".join(lines) + "\n"


def _section(lines: List[str], name: str) -> None:
    lines.append("0")
    lines.append("SECTION")
    lines.append("2")
    lines.append(name)


def _endsec(lines: List[str]) -> None:
    lines.append("0")
    lines.append("ENDSEC")


def _circle(lines: List[str], e: Dict[str, Any]) -> None:
    lines.extend([
        "0", "CIRCLE",
        "8", "0",
        "10", _fmt(e.get("cx", 0.0)),
        "20", _fmt(e.get("cy", 0.0)),
        "30", "0.0",
        "40", _fmt(e.get("r", 0.0)),
    ])


def _line(lines: List[str], e: Dict[str, Any]) -> None:
    lines.extend([
        "0", "LINE",
        "8", "0",
        "10", _fmt(e.get("x1", 0.0)),
        "20", _fmt(e.get("y1", 0.0)),
        "30", "0.0",
        "11", _fmt(e.get("x2", 0.0)),
        "21", _fmt(e.get("y2", 0.0)),
        "31", "0.0",
    ])


def _rect(lines: List[str], e: Dict[str, Any]) -> None:
    cx = float(e.get("cx", 0.0))
    cy = float(e.get("cy", 0.0))
    w = float(e.get("w", 0.0))
    h = float(e.get("h", 0.0))
    x1 = cx - w / 2.0
    y1 = cy - h / 2.0
    x2 = cx + w / 2.0
    y2 = cy + h / 2.0
    # draw as closed polyline
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    lines.extend([
        "0", "LWPOLYLINE",
        "8", "0",
        "90", str(len(points)),
        "70", "1",
    ])
    for x, y in points:
        lines.append("10")
        lines.append(_fmt(x))
        lines.append("20")
        lines.append(_fmt(y))


def _fmt(val: Any) -> str:
    try:
        return f"{float(val):.3f}"
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return "0.0"
