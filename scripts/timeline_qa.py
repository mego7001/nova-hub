from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.audit_spine import ProjectAuditSpine
from core.portable.paths import default_workspace_dir, detect_base_dir


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_tests() -> list[dict]:
    results: list[dict] = []
    base = detect_base_dir()
    ws = os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
    project_id = "timeline_qa"
    os.makedirs(os.path.join(ws, "projects", project_id), exist_ok=True)
    spine = ProjectAuditSpine(project_id, workspace_root=ws)

    spine.emit("message.user", {"text": "token=SECRET123"})
    spine.emit("tool.start", {"url": "https://example.com?token=abc"})
    events = spine.read_events(limit=10)
    ok1 = len(events) >= 2
    results.append({"name": "Append-only", "passed": ok1, "detail": f"count={len(events)}"})

    # redaction check
    last = events[-1] if events else {}
    payload = json.dumps(last)
    ok2 = "SECRET123" not in payload and "token=abc" not in payload
    results.append({"name": "Redaction", "passed": ok2, "detail": "Secrets redacted"})

    # tamper-evident chain check
    ok3 = False
    detail3 = "missing events"
    if len(events) >= 2:
        first = events[-2]
        last = events[-1]
        ok3 = bool(first.get("hash")) and bool(last.get("hash"))
        ok3 = ok3 and last.get("prev_hash") == first.get("hash")
        ok3 = ok3 and first.get("prev_hash") == "GENESIS"
        detail3 = f"prev_hash={last.get('prev_hash')}"
    results.append({"name": "Tamper-evident chain", "passed": ok3, "detail": detail3})

    return results


def write_reports(results: list[dict]) -> None:
    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    total = len(results)
    passed = len([r for r in results if r["passed"]])
    failed = total - passed
    payload = {
        "generated_at": _now_iso(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": results,
        "limitations": ["QA uses file reads; UI timeline not exercised."],
    }
    with open(os.path.join(reports_dir, "timeline_qa.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Timeline QA",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Summary: {passed} passed / {failed} failed",
        "",
        "## Tests",
    ]
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"- [{status}] {r['name']}: {r['detail']}")
    lines.append("")
    lines.append("## Limitations")
    for lim in payload["limitations"]:
        lines.append(f"- {lim}")
    with open(os.path.join(reports_dir, "timeline_qa.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    results = run_tests()
    write_reports(results)
    return 1 if any(not r["passed"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
