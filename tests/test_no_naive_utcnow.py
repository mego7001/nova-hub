from __future__ import annotations

from pathlib import Path


def test_no_datetime_utcnow_in_release_code() -> None:
    root = Path(__file__).resolve().parents[1]
    scan_paths = [
        root / "main.py",
        root / "core",
        root / "integrations",
    ]
    allowlist = {
        "scripts/audit/run_full_audit.py",  # mention appears in recommendation text only
    }

    hits: list[str] = []
    for base in scan_paths:
        if base.is_file():
            candidates = [base]
        else:
            candidates = [p for p in base.rglob("*.py") if p.is_file()]
        for path in candidates:
            rel = path.relative_to(root).as_posix()
            if rel in allowlist:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "datetime.utcnow(" in text:
                hits.append(rel)

    assert not hits, f"Found forbidden datetime.utcnow usage in: {hits}"

