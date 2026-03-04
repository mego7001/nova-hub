from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


_RE_NUMBER = r"(-?\d+(?:\.\d+)?)"


def _find_center(text: str) -> Tuple[float, float] | None:
    low = text.lower()
    # center at x,y
    m = re.search(r"(?:center|centre|مركزها|المركز)\s*(?:at|=|:)?\s*\(?\s*" + _RE_NUMBER + r"\s*[, ]\s*" + _RE_NUMBER + r"\s*\)?", low)
    if m:
        return float(m.group(1)), float(m.group(2))
    if any(k in low for k in ["center", "centre", "المنتصف", "في المنتصف", "المركز"]):
        return 0.0, 0.0
    return None


def _parse_circle(text: str) -> List[Dict[str, Any]]:
    ops: List[Dict[str, Any]] = []
    low = text.lower()
    if "circle" not in low and "دائرة" not in low:
        return ops
    center = _find_center(text) or (0.0, 0.0)
    # diameter
    m = re.search(r"(?:diameter|dia|قطرها|قطر)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        d = float(m.group(1))
        r = abs(d) / 2.0
        ops.append({"op": "add_circle", "cx": center[0], "cy": center[1], "r": r})
        return ops
    # radius
    m = re.search(r"(?:radius|r|نصف\s*قطر(?:ها)?)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        r = abs(float(m.group(1)))
        ops.append({"op": "add_circle", "cx": center[0], "cy": center[1], "r": r})
        return ops
    # default radius if mentioned
    m = re.search(r"(?:circle|دائرة)\s*" + _RE_NUMBER, low)
    if m:
        r = abs(float(m.group(1)))
        ops.append({"op": "add_circle", "cx": center[0], "cy": center[1], "r": r})
    return ops


def _parse_rect(text: str) -> List[Dict[str, Any]]:
    ops: List[Dict[str, Any]] = []
    low = text.lower()
    if "rect" not in low and "rectangle" not in low and "مستطيل" not in low:
        return ops
    center = _find_center(text) or (0.0, 0.0)
    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×\*]\s*(\d+(?:\.\d+)?)", low)
    if m:
        w = abs(float(m.group(1)))
        h = abs(float(m.group(2)))
        ops.append({"op": "add_rect", "cx": center[0], "cy": center[1], "w": w, "h": h})
        return ops
    m = re.search(r"(?:width|w|عرض)\s*[:=]?\s*" + _RE_NUMBER + r".*?(?:height|h|ارتفاع)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        w = abs(float(m.group(1)))
        h = abs(float(m.group(2)))
        ops.append({"op": "add_rect", "cx": center[0], "cy": center[1], "w": w, "h": h})
    return ops


def _parse_line(text: str) -> List[Dict[str, Any]]:
    ops: List[Dict[str, Any]] = []
    low = text.lower()
    if "line" not in low and "خط" not in low:
        return ops
    m = re.search(
        r"(?:line|خط)\s*(?:from|من)?\s*\(?\s*" + _RE_NUMBER + r"\s*[, ]\s*" + _RE_NUMBER +
        r"\s*\)?\s*(?:to|الى|إلى)?\s*\(?\s*" + _RE_NUMBER + r"\s*[, ]\s*" + _RE_NUMBER + r"\s*\)?",
        low,
    )
    if m:
        ops.append({
            "op": "add_line",
            "x1": float(m.group(1)),
            "y1": float(m.group(2)),
            "x2": float(m.group(3)),
            "y2": float(m.group(4)),
        })
    return ops


def parse_ops(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    low = text.lower()
    if any(k in low for k in ["clear", "امسح", "مسح", "حذف الرسم"]):
        return [{"op": "clear"}]

    ops: List[Dict[str, Any]] = []
    ops.extend(_parse_circle(text))
    ops.extend(_parse_rect(text))
    ops.extend(_parse_line(text))
    return ops


def summarize_ops(ops: List[Dict[str, Any]]) -> str:
    if not ops:
        return ""
    lines = []
    for op in ops:
        typ = op.get("op")
        if typ == "add_circle":
            lines.append(f"- دائرة نصف قطر {op.get('r')} عند ({op.get('cx')},{op.get('cy')})")
        elif typ == "add_rect":
            lines.append(f"- مستطيل {op.get('w')}x{op.get('h')} عند ({op.get('cx')},{op.get('cy')})")
        elif typ == "add_line":
            lines.append(f"- خط من ({op.get('x1')},{op.get('y1')}) إلى ({op.get('x2')},{op.get('y2')})")
        elif typ == "clear":
            lines.append("- مسح الرسم")
    return "\n".join(lines)


def parse_ops_from_json(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    import json
    # extract json array or object
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not m:
        return []
    blob = m.group(1)
    try:
        data = json.loads(blob)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return []
    if isinstance(data, dict):
        data = data.get("ops") or []
    if isinstance(data, list):
        return [op for op in data if isinstance(op, dict)]
    return []
