from __future__ import annotations

from typing import Dict, List


SEVERITY_WEIGHT = {"OK": 0.0, "WARN": 1.0, "WARNING": 1.0, "CRITICAL": 2.5}


def score(findings: List[Dict], missing_fields: List[str], confidence: float = 0.7) -> Dict:
    score_val = 0.0
    max_sev = "OK"
    for f in findings:
        sev = str(f.get("severity") or "OK").upper()
        if SEVERITY_WEIGHT.get(sev, 0) > SEVERITY_WEIGHT.get(max_sev, 0):
            max_sev = sev
        score_val += SEVERITY_WEIGHT.get(sev, 0)
    score_val += 0.3 * len(missing_fields)
    if confidence < 0.5:
        score_val += 0.7
    if score_val >= 3.5 or max_sev == "CRITICAL":
        posture = "HIGH"
    elif score_val >= 1.5:
        posture = "MED"
    else:
        posture = "LOW"
    return {"risk_score": score_val, "risk_posture": posture, "max_severity": max_sev}
