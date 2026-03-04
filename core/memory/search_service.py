from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from core.ingest.index_store import IndexStore
from core.projects.manager import ProjectManager


class MemorySearchService:
    def __init__(self, workspace_root: str, project_manager: Optional[ProjectManager] = None) -> None:
        self.workspace_root = os.path.abspath(workspace_root)
        self.project_manager = project_manager or ProjectManager(self.workspace_root)

    @staticmethod
    def _normalize_chat_id(chat_id: str) -> str:
        raw = str(chat_id or "").strip().lower()
        if not raw:
            return "general"
        safe = re.sub(r"[^a-z0-9_.-]+", "_", raw).strip("._-")
        return safe[:96] if safe else "general"

    def _index_path_for_scope(self, scope: str, scope_id: str) -> str:
        normalized_scope = str(scope or "general").strip().lower()
        if normalized_scope == "project":
            if not scope_id:
                raise ValueError("scope_id is required for project search")
            return self.project_manager.get_project_paths(scope_id).index_path
        cid = self._normalize_chat_id(scope_id or "general")
        return os.path.join(self.workspace_root, "chat", "sessions", cid, "index.json")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [tok for tok in re.split(r"\W+", str(text or "").lower()) if tok]

    @staticmethod
    def _snippet(text: str, query: str, width: int = 180) -> str:
        if not text:
            return ""
        q = str(query or "").strip().lower()
        low = text.lower()
        pos = low.find(q) if q else -1
        if pos < 0:
            return text[:width].strip()
        start = max(0, pos - width // 3)
        end = min(len(text), start + width)
        return text[start:end].strip()

    def search(
        self,
        query: str,
        *,
        scope: str = "general",
        scope_id: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        q = str(query or "").strip()
        if not q:
            return {"status": "ok", "scope": str(scope or "general"), "scope_id": str(scope_id or ""), "total": 0, "hits": []}

        idx = self._index_path_for_scope(scope, scope_id)
        docs = IndexStore(idx).load()
        terms = self._tokenize(q)
        scored: List[Dict[str, Any]] = []

        for rec in docs:
            if not isinstance(rec, dict):
                continue
            extracted_path = str(rec.get("extracted_text_path") or "")
            if not extracted_path or not os.path.exists(extracted_path):
                continue
            try:
                with open(extracted_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                continue
            body = text.lower()
            score = 0
            for term in terms:
                if term and term in body:
                    score += body.count(term)
            if score <= 0:
                continue
            scored.append(
                {
                    "doc_id": str(rec.get("doc_id") or ""),
                    "path": str(rec.get("stored_path") or ""),
                    "type": str(rec.get("type") or ""),
                    "score": int(score),
                    "snippet": self._snippet(text, q),
                }
            )

        scored.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("path") or "")))
        start = max(0, int(offset or 0))
        stop = start + max(1, min(int(limit or 20), 200))
        return {
            "status": "ok",
            "scope": str(scope or "general"),
            "scope_id": str(scope_id or ""),
            "total": len(scored),
            "hits": scored[start:stop],
            "limit": max(1, min(int(limit or 20), 200)),
            "offset": start,
            "index_path": idx,
        }
