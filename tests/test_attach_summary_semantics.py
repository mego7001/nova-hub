from __future__ import annotations

from core.ingest.summary_contract import build_attach_summary_text, normalize_ingest_result


def test_attach_summary_contract_normalizes_counts_and_reason_codes():
    raw = {
        "status": "ok",
        "accepted": [{"path": "a.txt", "stored_path": "docs/a.txt", "type": "text", "size": 12}],
        "rejected": [{"path": "bad.exe", "reason": "Unsupported format. Allowed: zip/pdf/docx/xlsx/images/txt/code/config files."}],
        "counts": {"files_extracted": 1, "keys_imported": 0},
    }

    normalized = normalize_ingest_result(raw)

    assert normalized["status"] == "partial"
    assert normalized["counts"]["accepted"] == 1
    assert normalized["counts"]["rejected"] == 1
    rejected = normalized["rejected"][0]
    assert rejected["reason_code"] == "unsupported_format"
    assert build_attach_summary_text(normalized) == "Accepted 1, rejected 1, extracted 1."
