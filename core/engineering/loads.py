from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LoadCase:
    load_type: str
    magnitude: float
    unit: str
    direction: str
    duration: str

    def to_dict(self) -> dict:
        return {
            "type": self.load_type,
            "magnitude": {"value": self.magnitude, "unit": self.unit},
            "direction": self.direction,
            "duration": self.duration,
        }


@dataclass
class Support:
    support_type: str
    description: str

    def to_dict(self) -> dict:
        return {"type": self.support_type, "description": self.description}


def cantilever_moment_nmm(force_n: float, length_mm: float) -> float:
    """Return cantilever moment in N·mm."""
    return force_n * length_mm


def axial_stress(force_n: float, area_mm2: float) -> Optional[float]:
    if area_mm2 <= 0:
        return None
    return force_n / area_mm2


def bending_stress(moment_nmm: float, c_mm: float, inertia_mm4: float) -> Optional[float]:
    if inertia_mm4 <= 0:
        return None
    return moment_nmm * c_mm / inertia_mm4
