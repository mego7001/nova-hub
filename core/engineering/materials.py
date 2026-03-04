from __future__ import annotations

from typing import Dict, List


MATERIAL_LIBRARY: Dict[str, Dict[str, float]] = {
    "Steel (Generic)": {"density": 7850, "E": 200, "yield": 250, "alpha": 12},
    "Stainless 304": {"density": 8000, "E": 193, "yield": 215, "alpha": 17},
    "Aluminum 6061": {"density": 2700, "E": 69, "yield": 275, "alpha": 23},
    "Aluminum 5052": {"density": 2680, "E": 70, "yield": 193, "alpha": 24},
    "Brass": {"density": 8500, "E": 100, "yield": 200, "alpha": 19},
    "ABS": {"density": 1040, "E": 2.1, "yield": 40, "alpha": 90},
    "PLA": {"density": 1250, "E": 3.5, "yield": 60, "alpha": 70},
    "Nylon": {"density": 1150, "E": 2.7, "yield": 70, "alpha": 80},
    "Rubber": {"density": 1100, "E": 0.01, "yield": 5, "alpha": 120},
}


def material_properties(name: str) -> Dict[str, Dict[str, float | str]]:
    props = MATERIAL_LIBRARY.get(name, {})
    return {
        "E": {"value": props.get("E"), "unit": "GPa"},
        "yield_strength": {"value": props.get("yield"), "unit": "MPa"},
        "density": {"value": props.get("density"), "unit": "kg/m^3"},
        "thermal_expansion": {"value": props.get("alpha"), "unit": "1e-6/K"},
        "hardness": {"value": None, "unit": "HB"},
    }


def select_material(requirements: Dict[str, bool]) -> List[Dict[str, str]]:
    results = []
    for name, props in MATERIAL_LIBRARY.items():
        score = 0.0
        reasons = []
        density = props.get("density", 0)
        yield_strength = props.get("yield", 0)

        if requirements.get("lightweight"):
            if density and density < 3000:
                score += 2.0
                reasons.append("خفيف الوزن")
            else:
                score -= 1.0
        if requirements.get("corrosion"):
            if "stainless" in name.lower() or "aluminum" in name.lower() or name in ("Brass", "ABS", "PLA", "Nylon"):
                score += 2.0
                reasons.append("مقاومة للتآكل")
            elif "steel" in name.lower():
                score -= 1.5
        if requirements.get("strength"):
            if yield_strength and yield_strength >= 200:
                score += 1.5
                reasons.append("قوة مناسبة")
        if requirements.get("temperature"):
            if name in ("Steel (Generic)", "Stainless 304", "Aluminum 6061", "Aluminum 5052"):
                score += 1.0
                reasons.append("ملائم للحرارة")
            else:
                score -= 0.5
        if requirements.get("cost"):
            if name in ("Steel (Generic)", "Aluminum 5052", "ABS", "PLA"):
                score += 1.0
                reasons.append("تكلفة معقولة")

        results.append({"material": name, "score": score, "reason": "، ".join(reasons) or "خواص متوازنة"})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:5]
