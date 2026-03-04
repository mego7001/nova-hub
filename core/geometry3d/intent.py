from __future__ import annotations

import json
import re
from typing import Dict, List, Tuple

from core.geometry3d import limits


_RE_NUMBER = r"(-?\d+(?:\.\d+)?)"

_SHAPE_KEYWORDS = {
    "box": ["box", "cube", "rectangular prism", "صندوق", "مكعب", "متوازي"],
    "cylinder": ["cylinder", "cyl", "اسطوانة", "أسطوانة"],
    "sphere": ["sphere", "ball", "كرة"],
    "cone": ["cone", "مخروط"],
}

_MATERIALS = {
    "steel": ["steel", "stainless", "حديد", "فولاذ"],
    "aluminum": ["aluminum", "aluminium", "الومنيوم", "ألومنيوم"],
    "concrete": ["concrete", "خرسانة"],
    "wood": ["wood", "خشب"],
}

_SUPPORTS = {
    "fixed_base": ["fixed base", "fixed", "clamped", "مثبت", "ثابت"],
    "cantilever": ["cantilever", "كابولي", "كانتليفر"],
    "simple": ["simply supported", "supported", "مسند", "مدعوم"],
}

_LOADS = {
    "axial": ["axial", "محوري"],
    "lateral": ["lateral", "جانبي"],
    "bending": ["bending", "عزم", "انحناء"],
    "torsion": ["torsion", "لي"],
    "compression": ["compression", "ضغط"],
    "tension": ["tension", "شد"],
}


def is_3d_prompt(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    keys = ["3d", "solid", "model", "مجسم", "ثلاثي", "جسم"]
    for group in _SHAPE_KEYWORDS.values():
        keys.extend(group)
    return any(k in low for k in keys)


def parse_intent(text: str) -> Dict:
    blocked, reason = limits.check_limits(text or "")
    if blocked:
        return {
            "entities": [],
            "operations": [],
            "confidence": 0.0,
            "missing_info": [],
            "assumptions": [],
            "disallowed": True,
            "reason": reason,
        }

    entities: List[Dict] = []
    low = (text or "").lower()

    pos = _parse_position(text)
    material = _parse_material(low)
    support = _parse_support(low)
    load = _parse_load(low)
    hollow, thickness = _parse_hollow(low)

    if _has_shape(low, "box"):
        dims = _parse_box_dims(low)
        if dims:
            entities.append(_make_entity("box", dims, pos, material, support, load, hollow, thickness))
    if _has_shape(low, "cylinder"):
        dims = _parse_cylinder_dims(low)
        if dims:
            entities.append(_make_entity("cylinder", dims, pos, material, support, load, hollow, thickness))
    if _has_shape(low, "sphere"):
        dims = _parse_sphere_dims(low)
        if dims:
            entities.append(_make_entity("sphere", dims, pos, material, support, load, hollow, thickness))
    if _has_shape(low, "cone"):
        dims = _parse_cone_dims(low)
        if dims:
            entities.append(_make_entity("cone", dims, pos, material, support, load, hollow, thickness))

    confidence = _compute_confidence(low, entities)
    missing = _missing_info(material, support, load)
    assumptions = _assumptions_from_missing(missing)
    return {
        "entities": entities,
        "operations": [],
        "confidence": confidence,
        "missing_info": missing,
        "assumptions": assumptions,
        "disallowed": False,
        "reason": "",
    }


def parse_intent_from_json(text: str) -> Dict:
    if not text:
        return {
            "entities": [],
            "operations": [],
            "confidence": 0.0,
            "missing_info": [],
            "assumptions": [],
            "disallowed": False,
            "reason": "",
        }
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not m:
        return {
            "entities": [],
            "operations": [],
            "confidence": 0.0,
            "missing_info": [],
            "assumptions": [],
            "disallowed": False,
            "reason": "",
        }
    try:
        data = json.loads(m.group(1))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {
            "entities": [],
            "operations": [],
            "confidence": 0.0,
            "missing_info": [],
            "assumptions": [],
            "disallowed": False,
            "reason": "",
        }
    entities = []
    if isinstance(data, dict):
        entities = data.get("entities") or []
    elif isinstance(data, list):
        entities = data
    confidence = float(data.get("confidence", 0.7)) if isinstance(data, dict) else 0.7
    missing = data.get("missing_info") or []
    assumptions = data.get("assumptions") or []
    return {
        "entities": entities if isinstance(entities, list) else [],
        "operations": data.get("operations") if isinstance(data, dict) else [],
        "confidence": max(0.0, min(1.0, confidence)),
        "missing_info": missing if isinstance(missing, list) else [],
        "assumptions": assumptions if isinstance(assumptions, list) else [],
        "disallowed": False,
        "reason": "",
    }


def _has_shape(low: str, shape: str) -> bool:
    return any(k in low for k in _SHAPE_KEYWORDS.get(shape, []))


def _parse_position(text: str) -> Tuple[float, float, float]:
    if not text:
        return (0.0, 0.0, 0.0)
    low = text.lower()
    m = re.search(r"(?:center|at|مركز|في)\s*(?:=|:)?\s*\(?\s*" + _RE_NUMBER + r"\s*[, ]\s*" + _RE_NUMBER + r"\s*[, ]\s*" + _RE_NUMBER + r"\s*\)?", low)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    return (0.0, 0.0, 0.0)


def _parse_material(low: str) -> str:
    for mat, keys in _MATERIALS.items():
        if any(k in low for k in keys):
            return mat
    return ""


def _parse_support(low: str) -> str:
    for sup, keys in _SUPPORTS.items():
        if any(k in low for k in keys):
            return sup
    if "unsupported" in low or "غير مدعوم" in low:
        return "unsupported"
    return ""


def _parse_load(low: str) -> str:
    for load, keys in _LOADS.items():
        if any(k in low for k in keys):
            return load
    return ""


def _parse_hollow(low: str) -> Tuple[bool, float]:
    hollow = any(k in low for k in ["hollow", "pipe", "tube", "مجوّف", "أنبوب", "ماسورة"])
    m = re.search(r"(?:thickness|t|سمك)\s*[:=]?\s*" + _RE_NUMBER, low)
    t = float(m.group(1)) if m else 0.0
    return hollow, abs(t)


def _parse_box_dims(low: str) -> Dict:
    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×\*]\s*(\d+(?:\.\d+)?)\s*[x×\*]\s*(\d+(?:\.\d+)?)", low)
    if m:
        return {"x": float(m.group(1)), "y": float(m.group(2)), "z": float(m.group(3))}
    m = re.search(r"(?:cube|مكعب)\s*" + _RE_NUMBER, low)
    if m:
        v = float(m.group(1))
        return {"x": v, "y": v, "z": v}
    m = re.search(r"(?:width|w|عرض)\s*[:=]?\s*" + _RE_NUMBER + r".*?(?:depth|d|عمق)\s*[:=]?\s*" + _RE_NUMBER + r".*?(?:height|h|ارتفاع)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        return {"x": float(m.group(1)), "y": float(m.group(2)), "z": float(m.group(3))}
    return {}


def _parse_cylinder_dims(low: str) -> Dict:
    m = re.search(r"(?:diameter|dia|قطر)\s*[:=]?\s*" + _RE_NUMBER + r".*?(?:height|h|ارتفاع|طول)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        return {"diameter": float(m.group(1)), "height": float(m.group(2))}
    m = re.search(r"(?:radius|r|نصف قطر)\s*[:=]?\s*" + _RE_NUMBER + r".*?(?:height|h|ارتفاع|طول)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        return {"diameter": float(m.group(1)) * 2.0, "height": float(m.group(2))}
    return {}


def _parse_sphere_dims(low: str) -> Dict:
    m = re.search(r"(?:diameter|dia|قطر)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        return {"diameter": float(m.group(1))}
    m = re.search(r"(?:radius|r|نصف قطر)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        return {"diameter": float(m.group(1)) * 2.0}
    return {}


def _parse_cone_dims(low: str) -> Dict:
    m = re.search(r"(?:diameter|dia|قطر)\s*[:=]?\s*" + _RE_NUMBER + r".*?(?:height|h|ارتفاع|طول)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        return {"diameter": float(m.group(1)), "height": float(m.group(2))}
    return {}


def _make_entity(typ: str, dims: Dict, pos: Tuple[float, float, float], material: str, support: str, load: str, hollow: bool, thickness: float) -> Dict:
    return {
        "id": f"{typ}_{len(dims)}_{abs(hash(str(dims))) % 9999}",
        "type": typ,
        "dims": dims,
        "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
        "material": material or "",
        "support": support or "",
        "load": load or "",
        "hollow": hollow,
        "thickness": thickness,
    }


def _compute_confidence(low: str, entities: List[Dict]) -> float:
    if not entities:
        return 0.1 if any(_has_shape(low, s) for s in _SHAPE_KEYWORDS.keys()) else 0.0
    score = 0.2
    score += 0.5
    if all((e.get("dims") for e in entities)):
        score += 0.2
    if _parse_position(low) != (0.0, 0.0, 0.0):
        score += 0.1
    return min(score, 0.95)


def _missing_info(material: str, support: str, load: str) -> List[str]:
    missing = []
    if not material:
        missing.append("material")
    if not support:
        missing.append("support")
    if not load:
        missing.append("load")
    return missing


def _assumptions_from_missing(missing: List[str]) -> List[str]:
    assumptions = []
    if "material" in missing:
        assumptions.append("Material assumed: steel")
    if "support" in missing:
        assumptions.append("Support assumed: unspecified")
    if "load" in missing:
        assumptions.append("Load assumed: unknown")
    return assumptions
