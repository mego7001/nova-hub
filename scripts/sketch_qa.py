from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.portable.paths import default_workspace_dir, detect_base_dir
from core.sketch import parser as sketch_parser
from core.sketch import store as sketch_store
from core.sketch.dxf import export_dxf


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_tests() -> list[dict]:
    results: list[dict] = []
    base = detect_base_dir()
    ws = os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
    project_id = "sketch_qa"
    proj_root = os.path.join(ws, "projects", project_id)
    os.makedirs(proj_root, exist_ok=True)

    # Test Arabic circle
    ops1 = sketch_parser.parse_ops("ارسم دائرة قطرها 200 في المنتصف")
    ok1 = len(ops1) >= 1 and ops1[0].get("op") == "add_circle" and abs(float(ops1[0].get("r")) - 100.0) < 0.01
    results.append({"name": "Arabic circle", "passed": ok1, "detail": f"ops={ops1}"})

    # Test English rect
    ops2 = sketch_parser.parse_ops("draw rectangle 300x150")
    ok2 = len(ops2) >= 1 and ops2[0].get("op") == "add_rect"
    results.append({"name": "English rect", "passed": ok2, "detail": f"ops={ops2}"})

    # Apply ops
    all_ops = ops1 + ops2
    applied = sketch_store.apply_ops(project_id, all_ops, workspace_root=ws)
    ok3 = applied.get("count", 0) >= 2
    results.append({"name": "Apply ops", "passed": ok3, "detail": f"count={applied.get('count')}"})

    # Export DXF
    dxf_text = export_dxf(applied.get("entities") or [])
    ok4 = ("CIRCLE" in dxf_text) and ("LWPOLYLINE" in dxf_text)
    out_dir = os.path.join(ws, "projects", project_id, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{project_id}_sketch.dxf")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dxf_text)
    results.append({"name": "Export DXF", "passed": ok4, "detail": f"path={out_path}"})

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
        "limitations": ["Rule-based parser only; no online fallback tested."],
    }
    with open(os.path.join(reports_dir, "sketch_qa.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Sketch QA",
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
    with open(os.path.join(reports_dir, "sketch_qa.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    results = run_tests()
    write_reports(results)
    return 1 if any(not r["passed"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
