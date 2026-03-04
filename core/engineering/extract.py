from __future__ import annotations

import os
import re
from typing import Dict, List

from core.portable.paths import detect_base_dir, default_workspace_dir
from core.security.secrets import SecretsManager
from core.engineering import model as eng_model, limits, rules, risk, explain


_RE_NUMBER = r"(-?\d+(?:\.\d+)?)"

_AR = {
    "material": "\u062e\u0627\u0645\u0629",
    "tolerance": "\u062a\u0644\u0631\u0627\u0646\u0633",
    "load": "\u062a\u062d\u0645\u064a\u0644",
    "safe": "\u0622\u0645\u0646",
    "works": "\u064a\u0646\u0641\u0639",
    "choose_material": "\u0627\u062e\u062a\u0631 \u062e\u0627\u0645\u0629",
    "design": "\u062a\u0635\u0645\u064a\u0645",
    "engineering": "\u0647\u0646\u062f\u0633\u064a",
    "steel": "\u0641\u0648\u0644\u0627\u0630",
    "iron": "\u062d\u062f\u064a\u062f",
    "stainless": "\u0633\u062a\u0627\u0646\u0644\u0633",
    "aluminum": "\u0627\u0644\u0648\u0645\u0646\u064a\u0648\u0645",
    "aluminum_alt": "\u0623\u0644\u0645\u0646\u064a\u0648\u0645",
    "brass": "\u0628\u0631\u0627\u0633",
    "plastic": "\u0628\u0644\u0627\u0633\u062a\u064a\u0643",
    "nylon": "\u0646\u0627\u064a\u0644\u0648\u0646",
    "rubber": "\u0645\u0637\u0627\u0637",
    "light": "\u062e\u0641\u064a\u0641",
    "rust": "\u0635\u062f\u0623",
    "strong": "\u0642\u0648\u064a",
    "temp": "\u062d\u0631\u0627\u0631\u0629",
    "economy": "\u0627\u0642\u062a\u0635\u0627\u062f\u064a",
    "outdoor": "\u062e\u0627\u0631\u062c\u064a",
    "humidity": "\u0631\u0637\u0648\u0628\u0629",
    "safety_factor": "\u0639\u0627\u0645\u0644 \u0623\u0645\u0627\u0646",
    "diameter": "\u0642\u0637\u0631",
    "length": "\u0637\u0648\u0644",
    "height": "\u0627\u0631\u062a\u0641\u0627\u0639",
    "newton": "\u0646\u064a\u0648\u062a\u0646",
    "kilo": "\u0643\u064a\u0644\u0648",
    "fixed": "\u062b\u0627\u0628\u062a",
    "fixed2": "\u0645\u062b\u0628\u062a",
    "pinned": "\u0645\u0641\u0635\u0644",
    "roller": "\u0645\u0633\u0646\u062f",
    "bolts": "\u0645\u0633\u0627\u0645\u064a\u0631",
    "weld": "\u0644\u062d\u0627\u0645",
    "print": "\u0637\u0628\u0627\u0639\u0629",
    "lathe": "\u062e\u0631\u0627\u0637\u0629",
    "delta_t": "\u0641\u0631\u0642 \u062d\u0631\u0627\u0631\u0629",
}


def is_engineering_query(text: str) -> bool:
    low = (text or "").lower()
    keys = [
        "material",
        _AR["material"],
        _AR["tolerance"],
        "tolerance",
        "fit",
        _AR["load"],
        "load",
        "force",
        "torque",
        "pressure",
        "safety",
        _AR["safe"],
        "safe",
        _AR["works"],
        _AR["choose_material"],
        _AR["design"],
        _AR["engineering"],
    ]
    return any(k in low for k in keys)


def run_engineering_brain(
    message: str,
    project_id: str = "",
    workspace_root: str | None = None,
    project_path: str | None = None,
    online_enabled: bool = False,
    router=None,
) -> Dict:
    blocked, reason = limits.check_limits(message)
    if blocked:
        return {
            "reply": reason,
            "state": {},
            "findings": [],
            "risk": {"risk_posture": "HIGH", "risk_score": 0.0},
            "question": "",
            "blocked": True,
        }

    signals = extract_signals(message, project_id=project_id, workspace_root=workspace_root, project_path=project_path)

    confidence = signals.get("confidence", 0.7)
    if confidence < 0.5 and online_enabled and router:
        routed = router.route(
            "engineering_extract",
            prompt=message,
            system=_engineering_system_prompt(),
            online_enabled=True,
            project_id=project_id,
            offline_confidence="low",
            parser_ok=False,
        )
        if routed.get("text"):
            signals.update(_parse_engineering_json(routed.get("text") or ""))

    state = eng_model.build_state(signals, message=message, geometry_link=_geometry_link(project_id, workspace_root))
    state_dict = state.to_dict()
    findings = rules.evaluate(state_dict, signals)
    questions = rules.next_questions(findings)
    question = questions[0] if questions else ""
    risk_result = risk.score(findings, state.assumptions.missing_fields, confidence=signals.get("confidence", 0.7))
    reply = explain.build_response(state_dict, findings, risk_result, question=question)
    report = explain.build_report(state_dict, findings, risk_result)
    return {
        "reply": reply,
        "state": state_dict,
        "findings": findings,
        "risk": risk_result,
        "question": question,
        "report": report,
        "signals": signals,
        "blocked": False,
    }


def extract_signals(
    message: str,
    project_id: str = "",
    workspace_root: str | None = None,
    project_path: str | None = None,
) -> Dict:
    ws = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(detect_base_dir())
    signals: Dict = {
        "loads": [],
        "supports": [],
        "tolerances": [],
        "stackups": [],
        "evidence": [],
        "confidence": 0.7,
        "material_requirements": _extract_material_requirements(message),
    }

    text = message or ""
    low = text.lower()

    material = _extract_material(low)
    if material:
        signals["material"] = material

    env = _extract_environment(low)
    if env:
        signals["environment"] = env
        signals["environment_evidence"] = {"path": "chat", "line": None, "excerpt": SecretsManager.redact_text(message[:200])}

    safety = _extract_safety(low)
    if safety:
        signals["safety_factor"] = safety

    geometry = _extract_geometry(low)
    if geometry:
        signals["geometry"] = geometry
        signals["geometry_evidence"] = {"path": "chat", "line": None, "excerpt": SecretsManager.redact_text(message[:200])}

    loads = _extract_loads(low)
    if loads:
        signals["loads"].extend(loads)

    supports = _extract_supports(low)
    if supports:
        signals["supports"].extend(supports)

    toler = _extract_tolerances(text)
    if toler:
        signals["tolerances"].extend(toler)
        signals["stackups"] = _build_stackups(toler)
        signals["tolerance_evidence"] = {"path": "chat", "line": None, "excerpt": SecretsManager.redact_text(message[:200])}

    process = _extract_process(low)
    if process:
        signals["process"] = process

    if "bolt" in low or "bolted" in low or _AR["bolts"] in low:
        signals["fastener"] = True
    if "grade" in low:
        signals["bolt_grade"] = True
    if "weld" in low or _AR["weld"] in low:
        signals["welded"] = True
    delta_t = _extract_delta_t(low)
    if delta_t:
        signals["delta_t"] = delta_t

    if project_id:
        docs = _scan_docs(project_id, ws)
        repo = _scan_repo(project_path or "")
        signals["evidence"].extend(docs.get("evidence", []))
        signals["evidence"].extend(repo.get("evidence", []))
        if not material and docs.get("material"):
            signals["material"] = docs.get("material")
        if not signals.get("standards") and docs.get("standards"):
            signals["standards"] = docs.get("standards")

    if not (signals.get("material") or signals.get("loads") or signals.get("tolerances") or signals.get("supports") or signals.get("geometry")):
        signals["confidence"] = 0.4

    return signals


def _extract_material(low: str) -> str:
    mat_map = {
        "steel": "Steel (Generic)",
        "stainless": "Stainless 304",
        "304": "Stainless 304",
        "aluminum": "Aluminum 6061",
        "aluminium": "Aluminum 6061",
        "6061": "Aluminum 6061",
        "5052": "Aluminum 5052",
        "brass": "Brass",
        "abs": "ABS",
        "pla": "PLA",
        "nylon": "Nylon",
        "rubber": "Rubber",
        _AR["steel"]: "Steel (Generic)",
        _AR["iron"]: "Steel (Generic)",
        _AR["stainless"]: "Stainless 304",
        _AR["aluminum"]: "Aluminum 6061",
        _AR["aluminum_alt"]: "Aluminum 6061",
        _AR["brass"]: "Brass",
        _AR["plastic"]: "ABS",
        _AR["nylon"]: "Nylon",
        _AR["rubber"]: "Rubber",
    }
    for k, v in mat_map.items():
        if k in low:
            return v
    return ""


def _extract_material_requirements(text: str) -> Dict[str, bool]:
    low = (text or "").lower()
    return {
        "lightweight": any(k in low for k in [_AR["light"], "lightweight", "light weight"]),
        "corrosion": any(k in low for k in [_AR["rust"], "corrosion", "corrosive"]),
        "strength": any(k in low for k in [_AR["strong"], "strong", "strength"]),
        "temperature": any(k in low for k in [_AR["temp"], "temperature", "hot"]),
        "cost": any(k in low for k in ["cheap", _AR["economy"], "low cost"]),
    }


def _extract_environment(low: str) -> str:
    if any(k in low for k in ["outdoor", _AR["outdoor"]]):
        return "outdoor"
    if any(k in low for k in ["corrosive", _AR["humidity"], _AR["rust"]]):
        return "corrosive"
    if any(k in low for k in ["hot", "temperature", _AR["temp"]]):
        return "temp"
    return ""


def _extract_safety(low: str) -> float:
    m = re.search(r"(?:safety factor|sf|" + _AR["safety_factor"] + r")\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        try:
            return float(m.group(1))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return 2.0
    return 0.0


def _extract_geometry(low: str) -> Dict:
    geo: Dict[str, float] = {}
    m = re.search(r"(?:diameter|dia|" + _AR["diameter"] + r"(?:\u0647|\u0647\u0627)?)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        geo["diameter"] = float(m.group(1))
    m = re.search(r"(?:height|length|" + _AR["length"] + r"(?:\u0647|\u0647\u0627)?|" + _AR["height"] + r"(?:\u0647|\u0647\u0627)?)\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        geo["height"] = float(m.group(1))
        geo["length"] = float(m.group(1))
    return geo


def _extract_loads(low: str) -> List[Dict]:
    loads = []
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kn|n|newton|" + _AR["newton"] + r")", low)
    if m:
        loads.append({"load_type": "axial", "magnitude": float(m.group(1)), "unit": m.group(2).upper(), "direction": "unknown", "duration": "static"})
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|" + _AR["kilo"] + r"|kgf)", low)
    if m:
        loads.append({"load_type": "weight", "magnitude": float(m.group(1)), "unit": "kg", "direction": "down", "duration": "static"})
    m = re.search(r"(\d+(?:\.\d+)?)\s*(nm|n.m)", low)
    if m:
        loads.append({"load_type": "torque", "magnitude": float(m.group(1)), "unit": "N.m", "direction": "twist", "duration": "static"})
    m = re.search(r"(\d+(?:\.\d+)?)\s*(mpa|bar|pa)", low)
    if m:
        loads.append({"load_type": "pressure", "magnitude": float(m.group(1)), "unit": m.group(2).upper(), "direction": "normal", "duration": "static"})
    return loads


def _extract_supports(low: str) -> List[Dict]:
    supports = []
    if "fixed" in low or _AR["fixed"] in low or _AR["fixed2"] in low:
        supports.append({"support_type": "fixed", "description": "fixed support"})
    if "pinned" in low or _AR["pinned"] in low:
        supports.append({"support_type": "pinned", "description": "pinned support"})
    if "roller" in low or _AR["roller"] in low:
        supports.append({"support_type": "roller", "description": "roller support"})
    if "bolted" in low or _AR["bolts"] in low:
        supports.append({"support_type": "bolted", "description": "bolted joint"})
    if "weld" in low or _AR["weld"] in low:
        supports.append({"support_type": "welded", "description": "welded joint"})
    return supports


def _extract_tolerances(text: str) -> List[Dict]:
    tolerances_list = []
    m = re.search(r"\u00b1\s*(\d+(?:\.\d+)?)", text)
    if m:
        tol = float(m.group(1))
        tolerances_list.append({
            "feature_type": "dimension",
            "nominal": 0.0,
            "tol_plus": tol,
            "tol_minus": -tol,
            "unit": "mm",
            "fit": "unspecified",
        })
    if "tel" in text.lower() or _AR["tolerance"] in text:
        if not tolerances_list:
            tolerances_list.append({
                "feature_type": "dimension",
                "nominal": 0.0,
                "tol_plus": 0.1,
                "tol_minus": -0.1,
                "unit": "mm",
                "fit": "unspecified",
            })
    return tolerances_list


def _build_stackups(tolerances_list: List[Dict]) -> List[Dict]:
    features = []
    total = 0.0
    for t in tolerances_list:
        features.append(t.get("feature_type"))
        total += abs(float(t.get("tol_plus", 0))) + abs(float(t.get("tol_minus", 0)))
    if not features:
        return []
    return [{"features": features, "total": total, "unit": "mm"}]


def _extract_process(low: str) -> str:
    if "3d" in low or "print" in low or _AR["print"] in low:
        return "3d_print"
    if "cnc" in low or "machining" in low or _AR["lathe"] in low:
        return "cnc"
    return ""


def _extract_delta_t(low: str) -> float:
    m = re.search(r"(?:delta\s*t|\u0394t|" + _AR["delta_t"] + r")\s*[:=]?\s*" + _RE_NUMBER, low)
    if m:
        try:
            return float(m.group(1))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return 0.0
    return 0.0


def _scan_docs(project_id: str, workspace_root: str) -> Dict:
    evidence = []
    material = ""
    standards = []
    docs_dir = os.path.join(workspace_root, "projects", project_id, "extracted")
    if not os.path.isdir(docs_dir):
        return {"evidence": [], "material": "", "standards": []}
    for root, _, files in os.walk(docs_dir):
        for name in files[:20]:
            path = os.path.join(root, name)
            try:
                text = open(path, "r", encoding="utf-8", errors="replace").read(2000)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                continue
            low = text.lower()
            if not material:
                material = _extract_material(low)
            if "astm" in low or "iso" in low or "din" in low:
                standards.extend([s for s in ["ASTM", "ISO", "DIN"] if s.lower() in low])
            if material or standards:
                excerpt = SecretsManager.redact_text(text[:200])
                evidence.append({"path": path, "line": None, "excerpt": excerpt})
    return {"evidence": evidence, "material": material, "standards": list(set(standards))}


def _scan_repo(project_path: str) -> Dict:
    evidence = []
    if not project_path or not os.path.isdir(project_path):
        return {"evidence": []}
    scanned = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "node_modules", "__pycache__")]
        for name in files:
            if scanned > 30:
                break
            if not name.endswith((".py", ".json", ".yaml", ".yml", ".txt")):
                continue
            path = os.path.join(root, name)
            try:
                text = open(path, "r", encoding="utf-8", errors="replace").read(800)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                continue
            low = text.lower()
            if any(k in low for k in ["material", "tolerance", "load", "force"]):
                evidence.append({"path": path, "line": None, "excerpt": SecretsManager.redact_text(text[:200])})
                scanned += 1
    return {"evidence": evidence}


def _geometry_link(project_id: str, workspace_root: str | None) -> str:
    if not project_id:
        return ""
    ws = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(detect_base_dir())
    path = os.path.join(ws, "projects", project_id, "geometry3d", "model.json")
    return path if os.path.exists(path) else ""


def _engineering_system_prompt() -> str:
    return (
        "Return JSON only. Format: {\"material\":\"Aluminum 6061\",\"loads\":[{\"load_type\":\"axial\",\"magnitude\":200,\"unit\":\"N\"," 
        "\"direction\":\"down\",\"duration\":\"static\"}],\"supports\":[{\"support_type\":\"fixed\",\"description\":\"fixed\"}],"
        "\"tolerances\":[{\"feature_type\":\"dimension\",\"nominal\":0,\"tol_plus\":0.05,\"tol_minus\":-0.05,\"unit\":\"mm\",\"fit\":\"clearance\"}]}"
    )


def _parse_engineering_json(text: str) -> Dict:
    import json
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}
    out = {}
    if isinstance(data, dict):
        out.update(data)
    return out
