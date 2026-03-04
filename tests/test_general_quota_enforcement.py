from __future__ import annotations

from pathlib import Path

from core.ingest.ingest_manager import IngestManager


def test_general_quota_enforcement_rejects_after_max_files(tmp_path: Path):
    mgr = IngestManager(workspace_root=str(tmp_path))
    inputs = tmp_path / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    paths = []
    for idx in range(26):
        p = inputs / f"f{idx}.txt"
        p.write_text(f"file {idx}", encoding="utf-8")
        paths.append(str(p))

    result = mgr.ingest_general("quota_case", paths)
    accepted = result.get("accepted") or []
    rejected = result.get("rejected") or []

    assert len(accepted) == 25
    assert len(rejected) == 1
    assert "Quota exceeded" in str(rejected[0].get("reason") or "")
