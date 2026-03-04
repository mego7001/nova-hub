from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.engineering import extract as eng_extract
from core.security.secrets import SecretsManager


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_tests() -> list[dict]:
    results: list[dict] = []

    # 1) Material selection
    res1 = eng_extract.run_engineering_brain("\u0639\u0627\u064a\u0632 \u062e\u0627\u0645\u0629 \u062e\u0641\u064a\u0641\u0629 \u0648\u0645\u0642\u0627\u0648\u0645\u0629 \u0644\u0644\u0635\u062f\u0623")
    mat = (res1.get("state") or {}).get("materials", {}).get("selected_material", "")
    ok1 = "Aluminum" in mat or "Stainless" in mat
    results.append({"name": "Material selection", "passed": ok1, "detail": f"selected={mat}"})

    # 2) Load warning (slenderness)
    res2 = eng_extract.run_engineering_brain("\u0639\u0645\u0648\u062f \u0642\u0637\u0631\u0647 20 \u0648\u0637\u0648\u0644\u0647 1500 \u0634\u0627\u064a\u0644 200 \u0643\u064a\u0644\u0648")
    findings2 = res2.get("findings") or []
    ok2 = any(f.get("check_id") == "SLENDERNESS_WARNING" for f in findings2)
    results.append({"name": "Slenderness warning", "passed": ok2, "detail": f"findings={findings2}"})

    # 3) Tolerance warning
    res3 = eng_extract.run_engineering_brain("\u062a\u0644\u0631\u0627\u0646\u0633 \u00b10.01 \u0639\u0644\u0649 \u0642\u0637\u0639\u0629 \u0645\u0637\u0628\u0648\u0639\u0629 3D")
    findings3 = res3.get("findings") or []
    ok3 = any(f.get("check_id") == "TOLERANCE_TOO_TIGHT" for f in findings3)
    results.append({"name": "Tolerance warning", "passed": ok3, "detail": f"findings={findings3}"})

    # 4) Missing supports -> question
    res4 = eng_extract.run_engineering_brain("\u0639\u0627\u064a\u0632\u0647 \u064a\u062a\u062d\u0645\u0644 500N")
    question = res4.get("question") or ""
    ok4 = bool(question)
    results.append({"name": "Missing supports question", "passed": ok4, "detail": f"question={question}"})

    # 5) Redaction
    msg = "my key is sk-TEST-SECRET and api_key=SECRET"
    res5 = eng_extract.run_engineering_brain(msg)
    report = res5.get("report") or ""
    redacted = SecretsManager.redact_text(report)
    ok5 = "sk-TEST-SECRET" not in redacted and "api_key=SECRET" not in redacted
    results.append({"name": "Redaction", "passed": ok5, "detail": "secrets redacted"})

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
        "limitations": ["QA uses offline extraction; UI panel not exercised."],
    }
    with open(os.path.join(reports_dir, "engineering_qa.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Engineering Brain QA",
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
    with open(os.path.join(reports_dir, "engineering_qa.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    results = run_tests()
    write_reports(results)
    return 1 if any(not r["passed"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
