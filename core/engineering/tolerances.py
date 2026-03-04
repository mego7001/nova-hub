from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ToleranceFeature:
    feature_type: str
    nominal: float
    tol_plus: float
    tol_minus: float
    unit: str
    fit: str

    def to_dict(self) -> dict:
        return {
            "feature": self.feature_type,
            "nominal": {"value": self.nominal, "unit": self.unit},
            "tolerance": {"plus": self.tol_plus, "minus": self.tol_minus, "unit": self.unit},
            "fit": self.fit,
        }


@dataclass
class ToleranceStackup:
    features: List[str]
    total: float
    unit: str

    def to_dict(self) -> dict:
        return {"features": self.features, "total": {"value": self.total, "unit": self.unit}}


def worst_case_stackup(features: List[ToleranceFeature]) -> ToleranceStackup:
    total = 0.0
    unit = "mm"
    names = []
    for f in features:
        total += abs(f.tol_plus) + abs(f.tol_minus)
        unit = f.unit
        names.append(f.feature_type)
    return ToleranceStackup(features=names, total=total, unit=unit)


def process_capability(process: str) -> float:
    low = (process or "").lower()
    if "3d" in low or "print" in low or "طباعة" in low:
        return 0.1
    if "cnc" in low or "machining" in low or "خراطة" in low:
        return 0.02
    if "laser" in low:
        return 0.05
    return 0.05
