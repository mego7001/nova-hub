from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "QAReportV1"
SCHEMA_COMPAT_ID = "nh.dxf_clip_qa.v1"

_SEVERITY_RANK = {"error": 0, "fail": 1, "warn": 2, "warning": 2, "info": 3}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(temp_path, path)


def resolve_workspace_root(path_hint: Optional[str] = None) -> str:
    """
    Best-effort workspace root discovery.
    Expected structure includes a folder named `workspace`.
    """
    candidates: List[Path] = []
    if path_hint:
        candidates.append(Path(path_hint).resolve(strict=False))
    env_workspace = os.environ.get("NH_WORKSPACE", "").strip()
    if env_workspace:
        candidates.append(Path(env_workspace).resolve(strict=False))
    candidates.append(Path.cwd().resolve(strict=False))
    candidates.append(Path(__file__).resolve(strict=False))

    for candidate in candidates:
        current = candidate if candidate.is_dir() else candidate.parent
        for parent in (current, *current.parents):
            if parent.name.lower() == "workspace":
                return str(parent)
            if (parent / "workspace").is_dir():
                return str(parent / "workspace")

    return str(Path.cwd().resolve(strict=False))


def _normalize_finding(item: Dict[str, Any]) -> Dict[str, Any]:
    hints = item.get("hints")
    if not isinstance(hints, list):
        hints_list: List[str] = []
    else:
        hints_list = sorted({str(x) for x in hints if str(x).strip()})

    out = {
        "severity": str(item.get("severity") or "info").lower(),
        "code": str(item.get("code") or ""),
        "message": str(item.get("message") or ""),
        "entity_ref": str(item.get("entity_ref") or ""),
        "file": str(item.get("file") or ""),
        "hints": hints_list,
    }
    context = item.get("context")
    out["context"] = dict(context) if isinstance(context, dict) else {}
    return out


def _normalize_risk(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "risk_code": str(item.get("risk_code") or ""),
        "level": str(item.get("level") or ""),
        "rationale": str(item.get("rationale") or ""),
        "suggested_action": str(item.get("suggested_action") or ""),
    }


def normalize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a deterministic QA report payload with stable ordering.
    """
    src = dict(report or {})

    findings_src = src.get("findings")
    findings: List[Dict[str, Any]] = []
    if isinstance(findings_src, list):
        for item in findings_src:
            if isinstance(item, dict):
                findings.append(_normalize_finding(item))
    findings.sort(
        key=lambda x: (
            _SEVERITY_RANK.get(str(x.get("severity") or "").lower(), 99),
            str(x.get("code") or ""),
            str(x.get("message") or ""),
            str(x.get("entity_ref") or ""),
            str(x.get("file") or ""),
        )
    )

    risks_src = src.get("manufacturing_risks")
    risks: List[Dict[str, Any]] = []
    if isinstance(risks_src, list):
        for item in risks_src:
            if isinstance(item, dict):
                risks.append(_normalize_risk(item))
    risks.sort(
        key=lambda x: (
            str(x.get("level") or ""),
            str(x.get("risk_code") or ""),
            str(x.get("rationale") or ""),
        )
    )

    dxf_metrics = src.get("dxf_metrics")
    clip_metrics = src.get("clip_metrics")
    if not isinstance(dxf_metrics, dict):
        dxf_metrics = dict(src.get("dxf") or {})
    if not isinstance(clip_metrics, dict):
        clip_metrics = dict(src.get("clip") or {})

    artifacts = src.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    debug_paths = artifacts.get("debug_paths")
    if not isinstance(debug_paths, list):
        debug_paths = []

    determinism = src.get("determinism")
    if not isinstance(determinism, dict):
        determinism = {}

    out = {
        "schema_version": str(src.get("schema_version") or SCHEMA_VERSION),
        "schema": str(src.get("schema") or SCHEMA_COMPAT_ID),
        "run_id": str(src.get("run_id") or uuid.uuid4().hex),
        "timestamp_utc": str(src.get("timestamp_utc") or src.get("generated_at") or _utc_iso()),
        "generated_at": str(src.get("generated_at") or src.get("timestamp_utc") or _utc_iso()),
        "project_id": str(src.get("project_id") or "unknown"),
        "input_files": sorted({str(x) for x in (src.get("input_files") or []) if str(x).strip()}),
        "source": dict(src.get("source") or {}),
        "dxf_metrics": dict(dxf_metrics),
        "clip_metrics": dict(clip_metrics),
        "dxf": dict(dxf_metrics),
        "clip": dict(clip_metrics),
        "findings": findings,
        "manufacturing_risks": risks,
        "artifacts": {
            "latest_json_path": str(artifacts.get("latest_json_path") or ""),
            "latest_hud_summary": str(artifacts.get("latest_hud_summary") or ""),
            "debug_paths": sorted({str(x) for x in debug_paths if str(x).strip()}),
        },
        "determinism": {
            "ordering_rule": str(determinism.get("ordering_rule") or "stable-sort by severity/code/message + normalized rings"),
            "rounding": str(determinism.get("rounding") or "float string preserved; comparisons use epsilon"),
            "epsilon": float(determinism.get("epsilon") or 1e-8),
        },
    }

    warn = sum(1 for x in findings if x.get("severity") in ("warn", "warning"))
    fail = sum(1 for x in findings if x.get("severity") in ("fail", "error"))
    status = "fail" if fail else ("warn" if warn else "ok")
    out["summary"] = {
        "status": status,
        "findings_total": len(findings),
        "warn": warn,
        "fail": fail,
    }
    return out


def validate_report(report: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(report, dict):
        return False, ["report must be a dict"]

    required_str = ["schema_version", "run_id", "timestamp_utc", "project_id"]
    for key in required_str:
        value = report.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"missing or invalid string: {key}")

    for key in ["dxf_metrics", "clip_metrics", "summary", "artifacts", "determinism"]:
        if not isinstance(report.get(key), dict):
            errors.append(f"missing or invalid dict: {key}")

    if not isinstance(report.get("findings"), list):
        errors.append("missing or invalid list: findings")
    if not isinstance(report.get("manufacturing_risks"), list):
        errors.append("missing or invalid list: manufacturing_risks")

    status = str((report.get("summary") or {}).get("status") or "")
    if status not in ("ok", "warn", "fail"):
        errors.append("summary.status must be one of: ok, warn, fail")

    return len(errors) == 0, errors


class QACollector:
    """
    Lightweight counters/findings API for pipeline modules.
    """

    def __init__(self, report: "QAReportV1"):
        self.report = report
        self.report.ensure_schema_defaults()

    def inc(self, section: str, key: str, amount: int = 1) -> None:
        bucket = self._section(section)
        bucket[key] = int(bucket.get(key) or 0) + int(amount)

    def set_metric(self, section: str, key: str, value: Any) -> None:
        bucket = self._section(section)
        bucket[key] = value

    def add_finding(
        self,
        severity: str,
        code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        entity_ref: str = "",
        file: str = "",
        hints: Optional[List[str]] = None,
    ) -> None:
        self.report.add(
            severity=severity,
            code=code,
            message=message,
            context=context,
            entity_ref=entity_ref,
            file=file,
            hints=hints,
        )

    def add_risk(self, risk_code: str, level: str, rationale: str, suggested_action: str) -> None:
        self.report.add_risk(risk_code, level, rationale, suggested_action)

    def finalize(self) -> Dict[str, Any]:
        return self.report.to_dict()

    def _section(self, section: str) -> Dict[str, Any]:
        if section in ("dxf", "dxf_metrics"):
            return self.report.dxf
        if section in ("clip", "clip_metrics"):
            return self.report.clip
        raise ValueError(f"unsupported section: {section}")


@dataclass
class QAReportV1:
    project_id: str
    dxf_path: str = ""
    pattern_id: str = ""
    units: str = "mm"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    input_files: List[str] = field(default_factory=list)
    dxf: Dict[str, Any] = field(default_factory=dict)
    clip: Dict[str, Any] = field(default_factory=dict)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    manufacturing_risks: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    determinism: Dict[str, Any] = field(default_factory=dict)

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        entity_ref: str = "",
        file: str = "",
        hints: Optional[List[str]] = None,
    ) -> None:
        self.findings.append(
            {
                "severity": str(severity),
                "code": str(code),
                "message": str(message),
                "context": dict(context or {}),
                "entity_ref": str(entity_ref or ""),
                "file": str(file or ""),
                "hints": list(hints or []),
            }
        )

    def add_unique(
        self,
        severity: str,
        code: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        entity_ref: str = "",
        file: str = "",
        hints: Optional[List[str]] = None,
    ) -> None:
        for item in self.findings:
            if str(item.get("code") or "") == str(code):
                return
        self.add(severity, code, message, context, entity_ref=entity_ref, file=file, hints=hints)

    def add_risk(self, risk_code: str, level: str, rationale: str, suggested_action: str) -> None:
        self.manufacturing_risks.append(
            {
                "risk_code": str(risk_code),
                "level": str(level),
                "rationale": str(rationale),
                "suggested_action": str(suggested_action),
            }
        )

    def ensure_schema_defaults(self) -> None:
        dxf_defaults = {
            "entities_seen": 0,
            "entity_counts": {},
            "polylines_seen": 0,
            "lwpolylines_seen": 0,
            "bulge_segments_seen": 0,
            "bulge_segments_expanded": 0,
            "bulge_segments_failed": 0,
            "arc_segments_default": 96,
            "closed_loops_seen": 0,
            "closed_loops_enforced": 0,
            "degenerate_segments_dropped": 0,
            "invalid_entities_skipped": 0,
        }
        clip_defaults = {
            "safe_zone": {"minx": 0.0, "miny": 0.0, "maxx": 0.0, "maxy": 0.0},
            "closed_inputs": 0,
            "open_inputs": 0,
            "closed_outputs": 0,
            "open_outputs": 0,
            "fragmentation_events": 0,
            "geometry_collections": 0,
            "multi_geometries": 0,
            "ring_closure_repairs": 0,
            "num_inputs": 0,
            "num_clipped": 0,
            "geom_types_seen": {},
        }
        for key, value in dxf_defaults.items():
            if key not in self.dxf:
                self.dxf[key] = value
        for key, value in clip_defaults.items():
            if key not in self.clip:
                self.clip[key] = value

        if not self.input_files and self.dxf_path:
            self.input_files = [self.dxf_path]

        self.artifacts.setdefault("latest_json_path", "")
        self.artifacts.setdefault("latest_hud_summary", "")
        self.artifacts.setdefault("debug_paths", [])

        self.determinism.setdefault("ordering_rule", "stable-sort by severity/code/message + normalized rings")
        self.determinism.setdefault("rounding", "float string preserved; comparisons use epsilon")
        self.determinism.setdefault("epsilon", 1e-8)

    def _status(self) -> str:
        has_fail = any(str(x.get("severity") or "").lower() in ("fail", "error") for x in self.findings)
        if has_fail:
            return "fail"
        has_warn = any(str(x.get("severity") or "").lower() in ("warn", "warning") for x in self.findings)
        if has_warn:
            return "warn"
        return "ok"

    def to_dict(self) -> Dict[str, Any]:
        self.ensure_schema_defaults()
        payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "schema": SCHEMA_COMPAT_ID,
            "run_id": str(self.run_id or uuid.uuid4().hex),
            "timestamp_utc": _utc_iso(),
            "project_id": str(self.project_id or "unknown"),
            "input_files": list(self.input_files or ([] if not self.dxf_path else [self.dxf_path])),
            "source": {
                "dxf_path": str(self.dxf_path or ""),
                "pattern_id": str(self.pattern_id or ""),
                "units": str(self.units or "mm"),
            },
            "dxf_metrics": dict(self.dxf),
            "clip_metrics": dict(self.clip),
            "findings": list(self.findings),
            "manufacturing_risks": list(self.manufacturing_risks),
            "artifacts": dict(self.artifacts),
            "determinism": dict(self.determinism),
            "generated_at": _utc_iso(),
            "dxf": dict(self.dxf),
            "clip": dict(self.clip),
        }

        normalized = normalize_report(payload)
        return normalized

    def write_latest(self, workspace_root: str) -> str:
        root = resolve_workspace_root(workspace_root)
        out_path = os.path.join(root, "reports", "qa", "latest.json")
        legacy_path = os.path.join(root, "reports", "dxf_clip_qa", "latest.json")

        payload = self.to_dict()
        artifacts = dict(payload.get("artifacts") or {})
        artifacts["latest_json_path"] = out_path
        debug_paths = [str(x) for x in (artifacts.get("debug_paths") or []) if str(x).strip()]
        if legacy_path not in debug_paths:
            debug_paths.append(legacy_path)
        artifacts["debug_paths"] = sorted(set(debug_paths))
        payload["artifacts"] = artifacts
        payload["summary"] = payload.get("summary") or {}
        payload["summary"]["status"] = payload["summary"].get("status") or self._status()

        normalized = normalize_report(payload)
        ok, errors = validate_report(normalized)
        if not ok:
            normalized.setdefault("findings", []).append(
                {
                    "severity": "error",
                    "code": "QA_SCHEMA_INVALID",
                    "message": "QA report failed validation before write.",
                    "context": {"errors": errors},
                    "entity_ref": "",
                    "file": "",
                    "hints": [],
                }
            )
            normalized = normalize_report(normalized)

        _atomic_write_json(out_path, normalized)
        _atomic_write_json(legacy_path, normalized)

        self.artifacts = dict(normalized.get("artifacts") or {})
        return out_path
