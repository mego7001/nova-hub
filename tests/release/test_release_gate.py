from __future__ import annotations

import json
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_findings(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_release_artifacts_exist() -> None:
    root = _root()
    required = [
        root / "configs" / "release_scope.yaml",
        root / "reports" / "audit" / "index.json",
        root / "reports" / "audit" / "findings.jsonl",
        root / "reports" / "audit" / "line_review_matrix.csv",
        root / "reports" / "audit" / "test_gap_matrix.json",
        root / "reports" / "audit" / "release_freeze_manifest.json",
        root / "reports" / "FINAL_RELEASE_READINESS_AR.md",
        root / "reports" / "final_findings_summary.json",
        root / "reports" / "release_gate_results.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Missing required release artifacts: {missing}"


def test_release_gate_no_open_p0_p1_findings() -> None:
    root = _root()
    findings = _read_findings(root / "reports" / "audit" / "findings.jsonl")
    blocked = [
        item
        for item in findings
        if str(item.get("status") or "").lower() == "open"
        and str(item.get("priority") or "").upper() in {"P0", "P1"}
    ]
    assert not blocked, f"Open P0/P1 findings exist: {len(blocked)}"


def test_release_gate_no_open_p2_findings() -> None:
    root = _root()
    findings = _read_findings(root / "reports" / "audit" / "findings.jsonl")
    blocked = [
        item
        for item in findings
        if str(item.get("status") or "").lower() == "open"
        and str(item.get("priority") or "").upper() == "P2"
    ]
    assert not blocked, f"Open P2 findings exist: {len(blocked)}"


def test_release_gate_reports_pass_state() -> None:
    root = _root()
    gate = _read_json(root / "reports" / "release_gate_results.json")
    assert bool((gate.get("checks") or {}).get("no_open_p2")) is True
    assert bool(gate.get("passed")) is True
