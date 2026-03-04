from __future__ import annotations
from typing import Any, Dict, List


def build_suggestions(
    scan_res: Dict[str, Any],
    search_res: Dict[str, Any],
    verify_res: Dict[str, Any],
    doc_index: List[Dict[str, Any]],
    risk_posture: str = "balanced",
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []

    # Verify failures
    totals = (verify_res or {}).get("totals") or {}
    failed = totals.get("failed_count", 0)
    if failed:
        suggestions.append({
            "title": "Fix failing smoke checks",
            "rationale": f"verify.smoke reported {failed} failing checks",
            "impact": "high",
            "risk": "low",
            "effort": "medium",
            "evidence": [{"type": "report", "path": p} for p in (verify_res or {}).get("report_paths", [])],
            "goal": "Fix failing smoke checks and get verify.smoke to pass",
        })

    # Hotspots from repo.search
    hotspots = (search_res or {}).get("hotspots") or {}
    top_files = hotspots.get("files_with_most_hits") or []
    if top_files:
        top = ", ".join([f"{h.get('path')} ({h.get('hits')})" for h in top_files[:3]])
        suggestions.append({
            "title": "Address task-marker hotspots",
            "rationale": f"Top files with task markers: {top}",
            "impact": "medium",
            "risk": "medium",
            "effort": "medium",
            "evidence": _evidence_from_matches(search_res, max_items=5),
            "goal": "Resolve task-marker hotspots in the top files",
        })

    # Config hotspots if present
    config_hotspots = hotspots.get("config_hotspots") or []
    if config_hotspots:
        suggestions.append({
            "title": "Review configuration hotspots",
            "rationale": "Repo search found configuration-related hotspots",
            "impact": "medium",
            "risk": "low",
            "effort": "low",
            "evidence": [{"type": "config", "path": p} for p in config_hotspots[:5]],
            "goal": "Normalize or document configuration hotspots",
        })

    # Large/complex files from scan
    stats = (scan_res or {}).get("stats") or {}
    largest = (scan_res or {}).get("largest_files") or []
    if stats and largest:
        largest_names = ", ".join([f.get("path") for f in largest[:3] if f.get("path")])
        suggestions.append({
            "title": "Refactor or review large files",
            "rationale": f"Large files detected: {largest_names}",
            "impact": "medium",
            "risk": "medium",
            "effort": "high",
            "evidence": [{"type": "large_file", "path": f.get("path"), "bytes": f.get("bytes")} for f in largest[:5]],
            "goal": "Review largest files for modularization or cleanup",
        })

    # Ingested docs
    if doc_index:
        suggestions.append({
            "title": "Convert ingested requirements into checklist",
            "rationale": f"{len(doc_index)} ingested documents found",
            "impact": "medium",
            "risk": "low",
            "effort": "medium",
            "evidence": [{"type": "doc", "path": d.get("stored_path")} for d in doc_index[:5]],
            "goal": "Summarize ingested requirements into a checklist report",
        })

    return _rank_suggestions(suggestions, risk_posture)


def _evidence_from_matches(search_res: Dict[str, Any], max_items: int = 5) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in (search_res or {}).get("matches") or []:
        if m.get("type") != "todo":
            continue
        out.append({"type": "match", "path": m.get("path"), "line": m.get("line"), "excerpt": m.get("excerpt")})
        if len(out) >= max_items:
            break
    return out


def _rank_suggestions(items: List[Dict[str, Any]], risk_posture: str) -> List[Dict[str, Any]]:
    def _score(s: Dict[str, Any]) -> float:
        impact = _lvl(s.get("impact"))
        risk = _lvl(s.get("risk"))
        effort = _lvl(s.get("effort"))
        if risk_posture == "conservative":
            return (impact * 2) - (risk * 3) - effort
        if risk_posture == "aggressive":
            return (impact * 3) - (effort * 0.5)
        return (impact * 2) - (risk * 1.5) - (effort * 0.5)

    return sorted(items, key=_score, reverse=True)


def _lvl(v: Any) -> float:
    if isinstance(v, str):
        if v.lower() == "high":
            return 3.0
        if v.lower() == "medium":
            return 2.0
        if v.lower() == "low":
            return 1.0
    return 1.0
