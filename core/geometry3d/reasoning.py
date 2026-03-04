from __future__ import annotations

import math
from typing import Dict, List, Tuple

from core.geometry3d import primitives


_DENSITY = {
    "steel": 7850.0,
    "aluminum": 2700.0,
    "concrete": 2400.0,
    "wood": 600.0,
}


def analyze(model: Dict, assumptions: List[str] | None = None) -> Tuple[List[Dict], str]:
    entities = model.get("entities") or []
    warnings: List[Dict] = []
    notes: List[str] = []
    total_vol = 0.0
    weighted_center = [0.0, 0.0, 0.0]

    for e in entities:
        typ = str(e.get("type") or "").lower()
        dims = e.get("dims") or {}
        vol = primitives.entity_volume(e)
        total_vol += vol
        cx, cy, cz = primitives.entity_center(e)
        weighted_center[0] += cx * vol
        weighted_center[1] += cy * vol
        weighted_center[2] += cz * vol

        # slenderness
        height = float(dims.get("height", dims.get("z", 0.0)))
        if typ == "box":
            min_dim = min(float(dims.get("x", 0.0)), float(dims.get("y", 0.0))) or 1.0
        else:
            min_dim = float(dims.get("diameter", 0.0)) or 1.0
        if height > 0:
            slenderness = height / min_dim
            if slenderness > 20:
                warnings.append(_warn("CRITICAL", "Slenderness", "الشكل طويل ورفيع جدًا وقد يتعرض لانبعاج."))
            elif slenderness > 10:
                warnings.append(_warn("WARNING", "Slenderness", "الشكل طويل ورفيع؛ في احتمال انبعاج أو اهتزاز."))

        # cantilever / support
        support = (e.get("support") or "").lower()
        if support in ("cantilever", "unsupported"):
            warnings.append(_warn("WARNING", "Support", "النموذج كابولي أو غير مدعوم؛ المخاطر عالية بدون تثبيت واضح."))
        if not support:
            warnings.append(_warn("WARNING", "Support", "الدعم غير محدد؛ النتائج تقريبية ومحتاجة توضيح."))

        # thin wall
        if typ == "cylinder" and e.get("hollow") and float(e.get("thickness", 0.0)) > 0:
            t = float(e.get("thickness", 0.0))
            d = float(dims.get("diameter", 0.0))
            if d > 0 and (t < d / 20 or (height > 0 and t < height / 50)):
                warnings.append(_warn("WARNING", "Thin wall", "سمك الجدار صغير مقارنة بالأبعاد؛ قد يحتاج تدعيم."))

    if total_vol > 0:
        cg = (weighted_center[0] / total_vol, weighted_center[1] / total_vol, weighted_center[2] / total_vol)
    else:
        cg = (0.0, 0.0, 0.0)

    mat = _material_from_entities(entities)
    density = _DENSITY.get(mat, _DENSITY["steel"])
    mass = (total_vol / 1e9) * density
    notes.append(f"تقدير الكتلة التقريبي: ~{mass:.2f} كجم (تقريبي جدًا).")
    notes.append(f"مركز الكتلة التقريبي: ({cg[0]:.1f}, {cg[1]:.1f}, {cg[2]:.1f}) مم.")
    if assumptions:
        notes.append("افتراضات: " + " | ".join(assumptions))
    notes.append("تنبيه: ده تصور هندسي مبدئي، مش حساب نهائي.")

    text = "\n".join(notes)
    return warnings, text


def _warn(sev: str, title: str, detail: str) -> Dict:
    return {"severity": sev, "title": title, "detail": detail}


def _material_from_entities(entities: List[Dict]) -> str:
    for e in entities:
        mat = e.get("material") or ""
        if mat:
            return str(mat)
    return "steel"
