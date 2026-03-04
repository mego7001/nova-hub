from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.geometry3d import intent as geom_intent
from core.geometry3d import reasoning as geom_reasoning


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_tests() -> list[dict]:
    results: list[dict] = []

    # 1) Simple box
    r1 = geom_intent.parse_intent("make a box 100x80x60")
    ok1 = bool(r1.get("entities")) and r1["entities"][0].get("type") == "box"
    results.append({"name": "Simple box", "passed": ok1, "detail": str(r1.get("entities"))})

    # 2) Cylinder with height/diameter
    r2 = geom_intent.parse_intent("cylinder diameter 200 height 1200")
    ok2 = bool(r2.get("entities")) and r2["entities"][0].get("type") == "cylinder"
    results.append({"name": "Cylinder dims", "passed": ok2, "detail": str(r2.get("entities"))})

    # 3) Unsupported cantilever warning
    r3 = geom_intent.parse_intent("cantilever cylinder diameter 50 height 1000 unsupported")
    model3 = {"entities": r3.get("entities") or [], "operations": []}
    warnings3, _ = geom_reasoning.analyze(model3, r3.get("assumptions") or [])
    ok3 = any("كابولي" in (w.get("detail") or "") or "غير مدعوم" in (w.get("detail") or "") or "كابولي" in (w.get("detail") or "") for w in warnings3)
    results.append({"name": "Cantilever warning", "passed": ok3, "detail": f"warnings={warnings3}"})

    # 4) Ambiguous description -> clarification needed
    r4 = geom_intent.parse_intent("3d shape")
    ok4 = (r4.get("confidence", 0.0) < 0.6) or (not r4.get("entities"))
    results.append({"name": "Ambiguous description", "passed": ok4, "detail": f"confidence={r4.get('confidence')}"})

    # 5) Arabic + English mixed input
    r5 = geom_intent.parse_intent("ارسم cylinder قطر 120 وارتفاع 500")
    ok5 = bool(r5.get("entities"))
    results.append({"name": "Arabic+English input", "passed": ok5, "detail": str(r5.get("entities"))})

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
        "limitations": ["QA uses offline parser only; UI preview not exercised."],
    }
    with open(os.path.join(reports_dir, "geometry3d_qa.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Geometry3D QA",
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
    with open(os.path.join(reports_dir, "geometry3d_qa.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    results = run_tests()
    write_reports(results)
    return 1 if any(not r["passed"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
