from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_fingerprint(record: Dict[str, Any]) -> str:
    payload = {
        "stored_path": os.path.basename(str(record.get("stored_path") or "")),
        "extracted_text_path": os.path.basename(str(record.get("extracted_text_path") or "")),
        "type": str(record.get("type") or ""),
        "size": int(record.get("size") or 0),
        "source_zip": os.path.basename(str(record.get("source_zip") or "")),
        "zip_member": str(record.get("zip_member") or ""),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def load_manifest(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_manifest(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def merge_records_lossless(
    dst_records: Iterable[Dict[str, Any]],
    src_records: Iterable[Dict[str, Any]],
    *,
    chat_id: str,
    path_map: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], int]:
    merged: List[Dict[str, Any]] = [dict(item) for item in dst_records if isinstance(item, dict)]
    existing_ids = {str(item.get("doc_id") or "") for item in merged if str(item.get("doc_id") or "").strip()}
    seen = {str(item.get("_migration_fingerprint") or "").strip() for item in merged if str(item.get("_migration_fingerprint") or "").strip()}
    if not seen:
        for item in merged:
            seen.add(record_fingerprint(item))

    added = 0
    for rec in src_records:
        if not isinstance(rec, dict):
            continue
        clone = dict(rec)
        old_stored = str(clone.get("stored_path") or "")
        if old_stored:
            clone["stored_path"] = path_map.get(old_stored, old_stored)
        old_extracted = str(clone.get("extracted_text_path") or "")
        if old_extracted:
            clone["extracted_text_path"] = path_map.get(old_extracted, old_extracted)
        clone["migrated_from_chat_id"] = str(chat_id or "")
        clone["migrated_at"] = _now_iso()
        fp = record_fingerprint(clone)
        if fp in seen:
            continue
        doc_id = str(clone.get("doc_id") or "").strip() or uuid.uuid4().hex[:12]
        while doc_id in existing_ids:
            doc_id = uuid.uuid4().hex[:12]
        clone["doc_id"] = doc_id
        clone["_migration_fingerprint"] = fp
        merged.append(clone)
        existing_ids.add(doc_id)
        seen.add(fp)
        added += 1
    return merged, added
