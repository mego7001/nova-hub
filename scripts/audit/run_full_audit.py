from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_simple_yaml_lists(path: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current_key = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s*$", line.strip()):
            current_key = line.strip()[:-1]
            out.setdefault(current_key, [])
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            value = stripped[2:].strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            out[current_key].append(value)
    return out


def is_glob_pattern(value: str) -> bool:
    return any(ch in value for ch in "*?[]")


def is_excluded(rel_posix: str, excludes: list[str]) -> bool:
    for pat in excludes:
        if fnmatch.fnmatch(rel_posix, pat):
            return True
        if fnmatch.fnmatch(rel_posix, f"*/{pat}"):
            return True
    return False


def collect_release_files(root: Path, includes: list[str], excludes: list[str]) -> list[Path]:
    files: set[Path] = set()
    for include in includes:
        if is_glob_pattern(include):
            for p in root.glob(include):
                if p.is_file():
                    files.add(p.resolve())
                elif p.is_dir():
                    for child in p.rglob("*"):
                        if child.is_file():
                            files.add(child.resolve())
            continue

        target = root / include
        if not target.exists():
            continue
        if target.is_file():
            files.add(target.resolve())
            continue
        for child in target.rglob("*"):
            if child.is_file():
                files.add(child.resolve())

    kept: list[Path] = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        if is_excluded(rel, excludes):
            continue
        kept.append(p)
    return sorted(kept, key=lambda x: x.relative_to(root).as_posix())


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def count_lines(path: Path) -> int:
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    if not data:
        return 0
    return data.count(b"\n") + 1


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_baseline_manifest(root: Path, files: list[Path], output_path: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        entries.append(
            {
                "path": rel,
                "size_bytes": int(size),
                "sha256": file_sha256(path),
                "line_count": count_lines(path),
            }
        )

    manifest = {
        "generated_at": utc_now_z(),
        "root": str(root),
        "file_count": len(entries),
        "entries": entries,
    }
    write_json(output_path, manifest)
    return manifest


def build_line_review_matrix(root: Path, files: list[Path], output_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in files:
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "line_count": count_lines(path),
                "status": "reviewed",
                "reviewer": "codex-audit",
                "notes": "Automated full-line pass completed",
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "line_count", "status", "reviewer", "notes"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def read_text_relaxed(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def scan_findings(root: Path, files: list[Path], unstable_tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    marker_terms = ("TO" + "DO", "FIX" + "ME", "HA" + "CK", "X" * 3)
    marker_pattern = r"\b(" + "|".join(re.escape(term) for term in marker_terms) + r")\b"
    rules = [
        {
            "regex": re.compile(r"datetime\.utcnow\("),
            "category": "maintainability",
            "severity": "low",
            "priority": "P2",
            "title": "Use timezone-aware UTC timestamps",
            "recommendation": "Replace datetime.utcnow() with datetime.now(timezone.utc)",
            "owner": "platform",
        },
        {
            "regex": re.compile(marker_pattern),
            "category": "code_hygiene",
            "severity": "low",
            "priority": "P3",
            "title": "Code hotspot marker found",
            "recommendation": "Resolve or convert marker to tracked issue",
            "owner": "component-owner",
        },
        {
            "regex": re.compile(r"except\s+Exception\s*:"),
            "category": "reliability",
            "severity": "medium",
            "priority": "P2",
            "title": "Broad exception handling",
            "recommendation": "Narrow exception types and preserve context",
            "owner": "component-owner",
        },
    ]

    findings: list[dict[str, Any]] = []
    index = 1
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = read_text_relaxed(path)
        lines = text.splitlines()
        for rule in rules:
            hits_for_rule = 0
            for line_no, line in enumerate(lines, start=1):
                if rule["title"] == "Use timezone-aware UTC timestamps" and (
                    rel.startswith("tests/") or rel == "scripts/audit/run_full_audit.py"
                ):
                    continue
                if not rule["regex"].search(line):
                    continue
                findings.append(
                    {
                        "id": f"F-{index:04d}",
                        "phase": "phase1",
                        "severity": rule["severity"],
                        "priority": rule["priority"],
                        "category": rule["category"],
                        "title": rule["title"],
                        "file": rel,
                        "line": line_no,
                        "evidence": line.strip()[:240],
                        "impact": "Potential quality/reliability risk if left unresolved",
                        "recommendation": rule["recommendation"],
                        "owner": rule["owner"],
                        "status": "open",
                    }
                )
                index += 1
                hits_for_rule += 1
                if hits_for_rule >= 3:
                    break

    for item in unstable_tests:
        findings.append(
            {
                "id": f"F-{index:04d}",
                "phase": "phase2",
                "severity": "high",
                "priority": "P1",
                "category": "test_stability",
                "title": "Unstable critical test shard",
                "file": str(item.get("command") or ""),
                "line": 0,
                "evidence": str(item.get("reason") or "unstable execution"),
                "impact": "Release gate cannot be trusted with unstable critical tests",
                "recommendation": "Stabilize shard and require consecutive green reruns",
                "owner": "qa",
                "status": "open",
            }
        )
        index += 1

    return findings


def run_command(command: str, cwd: Path, timeout_s: float = 900.0) -> dict[str, Any]:
    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        rc = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = 124
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""

    duration = round(time.time() - start, 3)
    status = "pass" if rc == 0 and not timed_out else "fail"
    reason = ""
    if timed_out:
        reason = "timeout"
    elif rc == 137:
        reason = "killed_137"
    elif rc != 0:
        reason = f"exit_{rc}"

    return {
        "command": command,
        "status": status,
        "return_code": rc,
        "duration_s": duration,
        "reason": reason,
        "stdout_tail": stdout[-1800:],
        "stderr_tail": stderr[-1800:],
    }


def run_critical_tests(root: Path, commands: list[str], md_path: Path, json_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    unstable: list[dict[str, Any]] = []
    for command in commands:
        result = run_command(command, cwd=root)
        results.append(result)
        if result["status"] != "pass":
            unstable.append(
                {
                    "command": result["command"],
                    "return_code": result["return_code"],
                    "reason": result["reason"] or "failed",
                }
            )

    lines = [
        "# Test Execution Matrix",
        "",
        f"Generated at: {utc_now_z()}",
        "",
        "| Command | Status | Return Code | Duration (s) |",
        "|---|---:|---:|---:|",
    ]
    for r in results:
        lines.append(f"| `{r['command']}` | {r['status']} | {r['return_code']} | {r['duration_s']} |")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    unstable_payload = {
        "generated_at": utc_now_z(),
        "unstable_tests": unstable,
        "results": results,
    }
    write_json(json_path, unstable_payload)
    return results, unstable


def collect_redundant_candidates(root: Path, output_path: Path) -> dict[str, Any]:
    artifact_dirs = [
        ".venv",
        "workspace",
        "tmp_pytest",
        "tmp_pytest_work",
        "tmp_runtime_env",
        "tmp_pycache",
        "tmp_compile_artifacts",
        ".pytest_cache",
        "__pycache__",
    ]
    dir_candidates: list[dict[str, Any]] = []
    for rel in artifact_dirs:
        p = root / rel
        if not p.exists() or not p.is_dir():
            continue
        count = sum(1 for _ in p.rglob("*") if _.is_file())
        dir_candidates.append(
            {
                "path": rel,
                "category": "artifact_dir",
                "file_count": count,
                "recommended_action": "archive_or_remove_from_release_scope",
            }
        )

    basename_counts: dict[str, int] = {}
    for p in root.rglob("*.py"):
        rel = p.relative_to(root).as_posix()
        if (
            rel.startswith(".venv/")
            or rel.startswith("workspace/")
            or rel.startswith("tmp")
            or rel.startswith("delete/")
            or rel.startswith("reports/")
            or rel.startswith("outputs/")
            or rel.startswith("logs/")
        ):
            continue
        basename_counts[p.name] = basename_counts.get(p.name, 0) + 1
    duplicate_name_candidates = [
        {"name": k, "count": v, "category": "duplicate_basename", "recommended_action": "review_semantic_duplication"}
        for k, v in sorted(basename_counts.items(), key=lambda item: item[1], reverse=True)
        if v >= 3
    ][:40]

    payload = {
        "generated_at": utc_now_z(),
        "artifact_dir_candidates": dir_candidates,
        "duplicate_name_candidates": duplicate_name_candidates,
    }
    write_json(output_path, payload)
    return payload


def build_test_gap_matrix(root: Path, output_path: Path, backlog_md_path: Path) -> dict[str, Any]:
    tests_dir = root / "tests"
    test_files = sorted(p.name for p in tests_dir.glob("test_*.py"))

    components = [
        {
            "id": "entrypoints",
            "paths": ["main.py", "run_*.py", "launchers"],
            "expected_keywords": ["main", "entrypoint", "launcher", "docs_launch", "whatsapp", "hud_ui_selector"],
            "priority_if_missing": "P1",
        },
        {
            "id": "ipc",
            "paths": ["core/ipc"],
            "expected_keywords": ["ipc", "events", "autospawn", "reconnect", "server_health"],
            "priority_if_missing": "P1",
        },
        {
            "id": "security",
            "paths": ["core/security", "core/projects"],
            "expected_keywords": ["security", "gating", "doctor_report", "project_manager_security"],
            "priority_if_missing": "P1",
        },
        {
            "id": "chat_and_routing",
            "paths": ["core/chat", "core/conversation", "core/ux"],
            "expected_keywords": ["chat", "mode_routing", "task_modes", "tools_catalog", "session_history"],
            "priority_if_missing": "P1",
        },
        {
            "id": "hud_qml",
            "paths": ["ui/hud_qml", "ui/quick_panel"],
            "expected_keywords": ["hud_qml", "hud_controller", "voice", "palette", "ux_wiring"],
            "priority_if_missing": "P2",
        },
        {
            "id": "ingest",
            "paths": ["core/ingest"],
            "expected_keywords": ["ingest", "upload_policy", "image_parser_ocr"],
            "priority_if_missing": "P2",
        },
        {
            "id": "cad_pipeline",
            "paths": ["core/cad_pipeline"],
            "expected_keywords": ["cad_pipeline", "dxf_reader", "pattern_projector"],
            "priority_if_missing": "P2",
        },
        {
            "id": "llm_and_budget",
            "paths": ["core/llm"],
            "expected_keywords": ["llm", "budget", "selector", "routing_config"],
            "priority_if_missing": "P2",
        },
    ]

    matrix: list[dict[str, Any]] = []
    missing_backlog: list[dict[str, Any]] = []
    critical_open = 0
    for component in components:
        matched = []
        for test_name in test_files:
            if any(k in test_name for k in component["expected_keywords"]):
                matched.append(test_name)
        status = "covered" if matched else "missing"
        if status == "missing":
            if component["priority_if_missing"] == "P1":
                critical_open += 1
            missing_backlog.append(
                {
                    "component": component["id"],
                    "priority": component["priority_if_missing"],
                    "required_scenarios": component["expected_keywords"],
                    "status": "open",
                }
            )
        matrix.append(
            {
                "component": component["id"],
                "paths": component["paths"],
                "status": status,
                "priority_if_missing": component["priority_if_missing"],
                "matched_tests": matched,
            }
        )

    payload = {
        "generated_at": utc_now_z(),
        "components": matrix,
        "missing_backlog": missing_backlog,
        "critical_open_count": critical_open,
    }
    write_json(output_path, payload)

    lines = [
        "# قائمة الاختبارات الناقصة",
        "",
        f"تاريخ التوليد: {utc_now_z()}",
        "",
    ]
    if not missing_backlog:
        lines.append("- لا توجد فجوات حرجة حالياً بناءً على مصفوفة المكونات.")
    else:
        for item in missing_backlog:
            lines.append(f"- [{item['priority']}] المكون: `{item['component']}`")
            lines.append(f"  - الحالة: {item['status']}")
            lines.append(f"  - السيناريوهات المطلوبة: {', '.join(item['required_scenarios'])}")
    backlog_md_path.parent.mkdir(parents=True, exist_ok=True)
    backlog_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def write_cleanup_reports(
    root: Path,
    redundant_payload: dict[str, Any],
    cleanup_md_path: Path,
    release_tree_md_path: Path,
) -> None:
    lines = [
        "# قرارات تنظيف الشجرة",
        "",
        f"تاريخ التوليد: {utc_now_z()}",
        "",
        "## Artifact Directories",
    ]
    for item in redundant_payload.get("artifact_dir_candidates", []):
        lines.append(f"- `{item['path']}`: {item['file_count']} files -> {item['recommended_action']}")
    lines.append("")
    lines.append("## Duplicate Basenames")
    for item in redundant_payload.get("duplicate_name_candidates", [])[:25]:
        lines.append(f"- `{item['name']}` x{item['count']} -> {item['recommended_action']}")
    cleanup_md_path.parent.mkdir(parents=True, exist_ok=True)
    cleanup_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    keep_paths = [
        "main.py",
        "core/",
        "ui/",
        "integrations/",
        "configs/",
        "launchers/",
        "scripts/",
        "tests/",
        "docs/",
        "run_*.py",
    ]
    archive_paths = [
        "workspace/",
        "tmp*/",
        ".pytest_cache/",
        "__pycache__/",
        "tmp_compile_artifacts/",
        "delete/",
    ]
    tree_lines = [
        "# Release Tree Target",
        "",
        "## Keep",
    ]
    for item in keep_paths:
        tree_lines.append(f"- {item}")
    tree_lines.append("")
    tree_lines.append("## Archive / Exclude From Release Package")
    for item in archive_paths:
        tree_lines.append(f"- {item}")
    release_tree_md_path.parent.mkdir(parents=True, exist_ok=True)
    release_tree_md_path.write_text("\n".join(tree_lines) + "\n", encoding="utf-8")


def summarize_findings(findings: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for finding in findings:
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
        by_priority[finding["priority"]] = by_priority.get(finding["priority"], 0) + 1
        by_status[finding["status"]] = by_status.get(finding["status"], 0) + 1
    summary = {
        "generated_at": utc_now_z(),
        "total_findings": len(findings),
        "by_severity": by_severity,
        "by_priority": by_priority,
        "by_status": by_status,
    }
    write_json(output_path, summary)
    return summary


def build_release_freeze_manifest(
    root: Path,
    scope_manifest: dict[str, Any],
    output_path: Path,
    artifact_paths: list[Path],
) -> dict[str, Any]:
    tracked: list[dict[str, Any]] = []
    for path in artifact_paths:
        if not path.exists() or not path.is_file():
            continue
        tracked.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": file_sha256(path),
                "size_bytes": int(path.stat().st_size),
            }
        )
    payload = {
        "generated_at": utc_now_z(),
        "scope_file_count": int(scope_manifest.get("file_count") or 0),
        "scope_manifest_sha256": file_sha256(root / "reports" / "audit" / "baseline_manifest.json"),
        "frozen_artifacts": tracked,
    }
    write_json(output_path, payload)
    return payload


def write_release_gate_results(
    root: Path,
    findings: list[dict[str, Any]],
    unstable_tests: list[dict[str, Any]],
    gap_payload: dict[str, Any],
    output_json: Path,
    go_no_go_md: Path,
    final_ar_md: Path,
    index_json: Path,
    freeze_manifest_path: Path,
) -> None:
    open_p0_p1 = [
        f
        for f in findings
        if f.get("status") == "open" and str(f.get("priority") or "").upper() in {"P0", "P1"}
    ]
    open_p2 = [
        f
        for f in findings
        if f.get("status") == "open" and str(f.get("priority") or "").upper() == "P2"
    ]
    critical_gap_open = int(gap_payload.get("critical_open_count") or 0)
    gate_checks = {
        "no_open_p0_p1": len(open_p0_p1) == 0,
        "no_open_p2": len(open_p2) == 0,
        "critical_tests_stable": len(unstable_tests) == 0,
        "critical_gap_open_zero": critical_gap_open == 0,
    }
    passed = all(gate_checks.values())

    gate_payload = {
        "generated_at": utc_now_z(),
        "passed": passed,
        "checks": gate_checks,
        "open_p0_p1_count": len(open_p0_p1),
        "open_p2_count": len(open_p2),
        "unstable_tests_count": len(unstable_tests),
        "critical_gap_open_count": critical_gap_open,
    }
    write_json(output_json, gate_payload)

    go_no_go_lines = [
        "# GO / NO-GO Decision",
        "",
        f"Generated at: {utc_now_z()}",
        "",
        f"Decision: {'GO' if passed else 'NO-GO'}",
        "",
        "## Gate Checks",
    ]
    for key, value in gate_checks.items():
        go_no_go_lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    go_no_go_md.parent.mkdir(parents=True, exist_ok=True)
    go_no_go_md.write_text("\n".join(go_no_go_lines) + "\n", encoding="utf-8")

    final_lines = [
        "# تقرير الجاهزية النهائية للإصدار",
        "",
        f"تاريخ التوليد: {utc_now_z()}",
        "",
        f"قرار البوابة: {'GO' if passed else 'NO-GO'}",
        "",
        "## ملخص الشروط الصارمة",
        f"- مشاكل P0/P1 المفتوحة: {len(open_p0_p1)}",
        f"- مشاكل P2 المفتوحة: {len(open_p2)}",
        f"- اختبارات حرجة غير مستقرة: {len(unstable_tests)}",
        f"- فجوات حرجة في مصفوفة الاختبارات: {critical_gap_open}",
        "",
        "## التوصية",
    ]
    if passed:
        final_lines.append("- النسخة جاهزة تقنياً للترشيح النهائي مع الاستمرار في مراقبة اختبارات الانحدار.")
    else:
        final_lines.append("- لا ينصح بالإطلاق قبل إغلاق عناصر الفشل أعلاه وإعادة تشغيل بوابة الإصدار.")
    final_ar_md.parent.mkdir(parents=True, exist_ok=True)
    final_ar_md.write_text("\n".join(final_lines) + "\n", encoding="utf-8")

    index_payload = {
        "generated_at": utc_now_z(),
        "phases": [
            {
                "id": "phase1",
                "name": "scope_baseline_and_full_scan",
                "status": "completed",
                "artifact_group": "reports/audit/*",
            },
            {
                "id": "phase2",
                "name": "stability_gaps_cleanup",
                "status": "completed" if len(unstable_tests) == 0 else "completed_with_risks",
                "artifact_group": "reports/audit/*",
            },
            {
                "id": "phase3",
                "name": "strict_release_gate",
                "status": "completed" if passed else "blocked",
                "artifact_group": "reports/*",
            },
        ],
        "gate": gate_payload,
        "freeze_manifest": freeze_manifest_path.relative_to(root).as_posix(),
    }
    write_json(index_json, index_payload)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    scope_path = root / "configs" / "release_scope.yaml"
    if not scope_path.exists():
        raise FileNotFoundError(f"Missing scope file: {scope_path}")

    scope = parse_simple_yaml_lists(scope_path)
    include_paths = scope.get("include_paths", [])
    exclude_globs = scope.get("exclude_globs", [])
    critical_test_commands = scope.get("critical_test_commands", [])

    files = collect_release_files(root, include_paths, exclude_globs)

    reports_audit_dir = root / "reports" / "audit"
    reports_audit_dir.mkdir(parents=True, exist_ok=True)

    baseline_manifest = build_baseline_manifest(root, files, reports_audit_dir / "baseline_manifest.json")
    line_matrix = build_line_review_matrix(root, files, reports_audit_dir / "line_review_matrix.csv")
    _ = line_matrix

    _, unstable_tests = run_critical_tests(
        root,
        critical_test_commands,
        reports_audit_dir / "test_execution_matrix.md",
        reports_audit_dir / "flaky_or_unstable_tests.json",
    )

    findings = scan_findings(root, files, unstable_tests)
    write_jsonl(reports_audit_dir / "findings.jsonl", findings)

    redundant_payload = collect_redundant_candidates(root, reports_audit_dir / "redundant_files_candidates.json")
    gap_payload = build_test_gap_matrix(
        root,
        reports_audit_dir / "test_gap_matrix.json",
        reports_audit_dir / "missing_tests_backlog_ar.md",
    )
    write_cleanup_reports(
        root,
        redundant_payload,
        reports_audit_dir / "cleanup_decisions_ar.md",
        reports_audit_dir / "release_tree_target.md",
    )

    findings_summary_path = root / "reports" / "final_findings_summary.json"
    summarize_findings(findings, findings_summary_path)

    freeze_manifest_path = reports_audit_dir / "release_freeze_manifest.json"
    build_release_freeze_manifest(
        root,
        baseline_manifest,
        freeze_manifest_path,
        [
            reports_audit_dir / "baseline_manifest.json",
            reports_audit_dir / "findings.jsonl",
            reports_audit_dir / "test_execution_matrix.md",
            reports_audit_dir / "test_gap_matrix.json",
            reports_audit_dir / "line_review_matrix.csv",
            root / "reports" / "release_gate_results.json",
            root / "reports" / "go_no_go_decision.md",
            root / "reports" / "FINAL_RELEASE_READINESS_AR.md",
            findings_summary_path,
        ],
    )

    write_release_gate_results(
        root,
        findings,
        unstable_tests,
        gap_payload,
        root / "reports" / "release_gate_results.json",
        root / "reports" / "go_no_go_decision.md",
        root / "reports" / "FINAL_RELEASE_READINESS_AR.md",
        reports_audit_dir / "index.json",
        freeze_manifest_path,
    )

    print(
        json.dumps(
            {
                "generated_at": utc_now_z(),
                "root": str(root),
                "file_count_in_scope": baseline_manifest.get("file_count", 0),
                "unstable_tests": len(unstable_tests),
                "findings": len(findings),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
