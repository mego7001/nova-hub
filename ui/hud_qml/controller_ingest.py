from __future__ import annotations

from typing import Any, Dict, List


def build_attach_rows(normalized: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in normalized.get("accepted") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "path": str(item.get("path") or item.get("stored_path") or ""),
                "status": "accepted",
                "reason": "",
                "reason_code": "",
                "type": str(item.get("type") or ""),
                "size": str(item.get("size") or ""),
            }
        )
    for item in normalized.get("rejected") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "path": str(item.get("path") or ""),
                "status": "rejected",
                "reason": str(item.get("reason") or ""),
                "reason_code": str(item.get("reason_code") or ""),
                "type": "",
                "size": "",
            }
        )
    return rows


def has_image_attachments(rows: List[Dict[str, Any]]) -> bool:
    for row in rows:
        if str(row.get("status") or "") != "accepted":
            continue
        kind = str(row.get("type") or "").lower()
        if kind == "image" or kind.startswith("image/"):
            return True
    return False
