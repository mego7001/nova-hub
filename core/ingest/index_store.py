from __future__ import annotations
import json
import os
import hashlib
import ast
from typing import Any, Dict, List, Optional


class IndexStore:
    def __init__(self, index_path: str):
        self.index_path = index_path

    def load(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.index_path):
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f) or []
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                docs = data.get("docs") or []
                if isinstance(docs, list):
                    return docs
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return []
        return []

    def load_full(self) -> Dict[str, Any]:
        if not os.path.exists(self.index_path):
            return {"docs": [], "chunks": [], "entities": []}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if isinstance(data, list):
                return {"docs": data, "chunks": [], "entities": []}
            if isinstance(data, dict):
                return {
                    "docs": data.get("docs") or [],
                    "chunks": data.get("chunks") or [],
                    "entities": data.get("entities") or [],
                }
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return {"docs": [], "chunks": [], "entities": []}
        return {"docs": [], "chunks": [], "entities": []}

    def save(self, records: List[Dict[str, Any]], writer: Any = None, repo_root: Optional[str] = None) -> None:
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        chunks = _build_chunks(records)
        entities = _build_repo_entities(repo_root) if repo_root else []
        payload = {"docs": records, "chunks": chunks, "entities": entities}
        text = json.dumps(payload, indent=2, ensure_ascii=True)
        if writer:
            writer(self.index_path, text)
            return
        with open(self.index_path, "w", encoding="utf-8") as f:
            f.write(text)


def _build_chunks(records: List[Dict[str, Any]], chunk_size: int = 800, overlap: int = 100) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for rec in records:
        text_path = rec.get("extracted_text_path") or ""
        if not text_path or not os.path.exists(text_path):
            continue
        try:
            with open(text_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            continue
        if not text.strip():
            continue
        start = 0
        idx = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk = text[start:end]
            h = hashlib.sha1(chunk.encode("utf-8", errors="replace")).hexdigest()
            chunks.append(
                {
                    "doc_id": rec.get("doc_id"),
                    "file_path": rec.get("stored_path"),
                    "section": f"chunk_{idx}",
                    "hash": h,
                    "tokens_estimate": max(1, len(chunk) // 4),
                    "offset_start": start,
                    "offset_end": end,
                    "text": chunk,
                }
            )
            idx += 1
            if end >= len(text):
                break
            start = end - overlap
    return chunks


def _build_repo_entities(repo_root: Optional[str]) -> List[Dict[str, Any]]:
    if not repo_root:
        return []
    root = repo_root
    working = os.path.join(repo_root, "working")
    if os.path.isdir(working):
        root = working
    entities: List[Dict[str, Any]] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", "dist", "build")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    src = f.read()
                tree = ast.parse(src)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                continue
            funcs: List[str] = []
            imports: List[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    funcs.append(node.name)
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append(n.name)
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for n in node.names:
                        imports.append(f"{mod}.{n.name}" if mod else n.name)
            entities.append({"file": path, "functions": funcs, "imports": imports})
    return entities
