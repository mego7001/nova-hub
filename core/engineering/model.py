from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.engineering import materials


def _prop(value: Optional[float], unit: str) -> Dict[str, Optional[float | str]]:
    return {"value": value, "unit": unit}


@dataclass
class ProjectContext:
    industry: str = ""
    standards: List[str] = field(default_factory=list)
    units: str = "mm"
    environment: str = "indoor"

    def to_dict(self) -> dict:
        return {
            "industry": self.industry,
            "standards": self.standards,
            "units": self.units,
            "environment": self.environment,
        }


@dataclass
class Part:
    part_id: str
    name: str
    role: str
    geometry_link: str = ""
    geometry_hint: Dict[str, str | float] | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.part_id,
            "name": self.name,
            "role": self.role,
            "geometry_link": self.geometry_link,
            "geometry_hint": self.geometry_hint or {},
        }


@dataclass
class MaterialsState:
    selected_material: str
    candidates: List[str]
    properties: Dict[str, Dict[str, float | str | None]]

    def to_dict(self) -> dict:
        return {
            "selected_material": self.selected_material,
            "candidates": self.candidates,
            "properties": self.properties,
        }


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
            "magnitude": _prop(self.magnitude, self.unit),
            "direction": self.direction,
            "duration": self.duration,
        }


@dataclass
class Support:
    support_type: str
    description: str

    def to_dict(self) -> dict:
        return {"type": self.support_type, "description": self.description}


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
            "nominal": _prop(self.nominal, self.unit),
            "tolerance": {"plus": self.tol_plus, "minus": self.tol_minus, "unit": self.unit},
            "fit": self.fit,
        }


@dataclass
class ToleranceStackup:
    features: List[str]
    total: float
    unit: str

    def to_dict(self) -> dict:
        return {"features": self.features, "total": _prop(self.total, self.unit)}


@dataclass
class SafetyState:
    safety_factor_target: float = 2.0
    reliability: str = "medium"

    def to_dict(self) -> dict:
        return {"safety_factor_target": self.safety_factor_target, "reliability": self.reliability}


@dataclass
class Evidence:
    path: str
    line: Optional[int] = None
    excerpt: str = ""

    def to_dict(self) -> dict:
        return {"path": self.path, "line": self.line, "excerpt": self.excerpt}


@dataclass
class Assumptions:
    missing_fields: List[str] = field(default_factory=list)
    assumed_values: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"missing_fields": self.missing_fields, "assumed_values": self.assumed_values}


@dataclass
class EngineeringState:
    context: ProjectContext
    parts: List[Part]
    materials: MaterialsState
    loads: List[LoadCase]
    supports: List[Support]
    tolerances: List[ToleranceFeature]
    stackups: List[ToleranceStackup]
    safety: SafetyState
    evidence: List[Evidence]
    assumptions: Assumptions

    def to_dict(self) -> dict:
        return {
            "context": self.context.to_dict(),
            "parts": [p.to_dict() for p in self.parts],
            "materials": self.materials.to_dict(),
            "loads": [l.to_dict() for l in self.loads],
            "supports": [s.to_dict() for s in self.supports],
            "tolerances": [t.to_dict() for t in self.tolerances],
            "stackups": [s.to_dict() for s in self.stackups],
            "safety": self.safety.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "assumptions": self.assumptions.to_dict(),
        }


def build_state(signals: Dict, message: str = "", geometry_link: str = "") -> EngineeringState:
    env = signals.get("environment") or "indoor"
    standards = signals.get("standards") or []
    context = ProjectContext(
        industry=signals.get("industry") or "",
        standards=standards,
        units=signals.get("units") or "mm",
        environment=env,
    )

    geometry_hint = signals.get("geometry") or {}
    parts = [Part(part_id="part-1", name="Main Part", role=signals.get("role") or "structural", geometry_link=geometry_link, geometry_hint=geometry_hint)]

    material_name = signals.get("material") or ""
    candidates = []
    if not material_name:
        requirements = signals.get("material_requirements") or {}
        ranked = materials.select_material(requirements)
        candidates = [r["material"] for r in ranked]
        material_name = candidates[0] if candidates else "Steel (Generic)"
    props = materials.material_properties(material_name)
    mat_state = MaterialsState(selected_material=material_name, candidates=candidates, properties=props)

    loads = [LoadCase(**l) for l in signals.get("loads", [])]
    supports = [Support(**s) for s in signals.get("supports", [])]
    tolerances = [ToleranceFeature(**t) for t in signals.get("tolerances", [])]
    stackups = signals.get("stackups", [])

    safety_factor = signals.get("safety_factor") or 2.0
    reliability = signals.get("reliability") or "medium"
    safety = SafetyState(safety_factor_target=float(safety_factor), reliability=reliability)

    evidence = [Evidence(**e) for e in signals.get("evidence", [])]

    missing = []
    assumed = []
    if not signals.get("material"):
        missing.append("material")
        assumed.append({"field": "material", "value": material_name, "rationale": "Assumed based on common practice"})
    if not supports:
        missing.append("supports")
        assumed.append({"field": "supports", "value": "unspecified", "rationale": "Support not provided"})
    if not loads:
        missing.append("loads")
        assumed.append({"field": "loads", "value": "unspecified", "rationale": "Load not provided"})
    if not tolerances:
        missing.append("tolerances")
        assumed.append({"field": "tolerances", "value": "unspecified", "rationale": "Tolerance not provided"})

    assumptions = Assumptions(missing_fields=missing, assumed_values=assumed)

    stackups_obj = []
    for st in stackups:
        stackups_obj.append(ToleranceStackup(**st))

    return EngineeringState(
        context=context,
        parts=parts,
        materials=mat_state,
        loads=loads,
        supports=supports,
        tolerances=tolerances,
        stackups=stackups_obj,
        safety=safety,
        evidence=evidence,
        assumptions=assumptions,
    )
