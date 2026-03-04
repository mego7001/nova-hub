from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.portable.paths import default_workspace_dir, detect_base_dir
from core.security.security_doctor import run_security_audit


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    base = detect_base_dir()
    ws = os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
    reports_dir = os.path.join(ws, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    seed_path = os.path.join(reports_dir, "seed_security_secret.txt")
    with open(seed_path, "w", encoding="utf-8") as f:
        f.write("sk-TESTSECRETTOKEN1234567890\n")
    report = run_security_audit(workspace_root=ws)
    out_json = os.path.join(reports_dir, "security_audit_seed.json")
    out_md = os.path.join(reports_dir, "security_audit_seed.md")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(f"# Seeded Security Audit\n\nGenerated at: {_now_iso()}\n\nSummary: {report.get('summary')}\n")
    print(f"Seeded file: {seed_path}")
    print(f"Gate: {report.get('security_gate')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
