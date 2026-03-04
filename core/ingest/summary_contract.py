from __future__ import annotations

from typing import Any, Dict, List


def infer_reason_code(reason: str) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return "unknown"
    if "not found" in text:
        return "file_not_found"
    if "directories are not supported" in text:
        return "directory_not_supported"
    if "unsupported format" in text:
        return "unsupported_format"
    if "max " in text and "files" in text:
        return "quota_files_exceeded"
    if "max " in text and "mb" in text:
        return "quota_bytes_exceeded"
    if "zip-slip blocked" in text:
        return "zip_slip_blocked"
    if "too many files" in text:
        return "too_many_files"
    if "total size limit" in text or "max_total_uncompressed_bytes" in text:
        return "max_total_bytes_exceeded"
    if "member exceeds" in text:
        return "member_too_large"
    if "nested zip" in text:
        return "nested_zip_not_allowed"
    if "invalid member path" in text:
        return "invalid_member_path"
    if "copy failed" in text:
        return "copy_failed"
    if "parse error" in text:
        return "parse_error"
    return "policy_rejected"


def _normalize_accepted(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "path": str(item.get("path") or ""),
                "stored_path": str(item.get("stored_path") or ""),
                "type": str(item.get("type") or ""),
                "size": int(item.get("size") or 0),
                "doc_id": str(item.get("doc_id") or ""),
                "extracted_text_path": str(item.get("extracted_text_path") or ""),
                "ocr_status": str(item.get("ocr_status") or "n/a"),
                "index_status": str(item.get("index_status") or ""),
                "source_zip": str(item.get("source_zip") or ""),
                "zip_member": str(item.get("zip_member") or ""),
            }
        )
    return out


def _normalize_rejected(items: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("reason") or "").strip()
        reason_code = str(item.get("reason_code") or "").strip() or infer_reason_code(reason)
        out.append(
            {
                "path": str(item.get("path") or ""),
                "reason": reason,
                "reason_code": reason_code,
            }
        )
    return out


def normalize_ingest_result(result: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(result or {}) if isinstance(result, dict) else {}
    accepted = _normalize_accepted(payload.get("accepted"))
    rejected = _normalize_rejected(payload.get("rejected"))
    errors = [str(x) for x in (payload.get("errors") or []) if str(x or "").strip()]
    counts_raw = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}

    ocr_statuses = [str(item.get("ocr_status") or "n/a").strip().lower() for item in accepted]
    ocr_ok = sum(1 for s in ocr_statuses if s == "ok")
    ocr_empty = sum(1 for s in ocr_statuses if s == "empty")
    ocr_missing_dependency = sum(1 for s in ocr_statuses if s == "missing_dependency")
    ocr_error = sum(1 for s in ocr_statuses if s == "error")
    zip_members = sum(1 for item in accepted if str(item.get("source_zip") or "").strip())

    counts = {
        "files_ingested": int(counts_raw.get("files_ingested") or len(accepted)),
        "files_extracted": int(counts_raw.get("files_extracted") or 0),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "keys_imported": int(counts_raw.get("keys_imported") or 0),
        "zip_members": int(counts_raw.get("zip_members") or zip_members),
        "ocr_ok": int(counts_raw.get("ocr_ok") or ocr_ok),
        "ocr_empty": int(counts_raw.get("ocr_empty") or ocr_empty),
        "ocr_missing_dependency": int(counts_raw.get("ocr_missing_dependency") or ocr_missing_dependency),
        "ocr_error": int(counts_raw.get("ocr_error") or ocr_error),
    }

    status = str(payload.get("status") or "ok")
    if rejected and status == "ok":
        status = "partial"

    return {
        "status": status,
        "target": str(payload.get("target") or ""),
        "scope_id": str(payload.get("scope_id") or ""),
        "batch_id": str(payload.get("batch_id") or ""),
        "accepted": accepted,
        "rejected": rejected,
        "counts": counts,
        "errors": errors,
        "ttl_cleanup": payload.get("ttl_cleanup"),
        "ttl_cleanup_after": payload.get("ttl_cleanup_after"),
    }


def build_attach_summary_text(result: Dict[str, Any]) -> str:
    normalized = normalize_ingest_result(result)
    counts = normalized.get("counts") if isinstance(normalized.get("counts"), dict) else {}
    return (
        f"Accepted {int(counts.get('accepted') or 0)}, "
        f"rejected {int(counts.get('rejected') or 0)}, "
        f"extracted {int(counts.get('files_extracted') or 0)}."
    )


def rejected_preview_lines(result: Dict[str, Any], max_items: int = 3) -> List[str]:
    normalized = normalize_ingest_result(result)
    out: List[str] = []
    rejected = normalized.get("rejected") if isinstance(normalized.get("rejected"), list) else []
    for item in rejected[: max(0, int(max_items or 0))]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "file")
        reason = str(item.get("reason") or "rejected")
        base = path.replace("\\", "/").rsplit("/", 1)[-1]
        out.append(f"{base}: {reason}")
    return out
