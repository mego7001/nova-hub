from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

from core.ingest.index_store import IndexStore


def search_index(index_path: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    if not query.strip():
        return []
    store = IndexStore(index_path)
    data = store.load_full()
    chunks = data.get("chunks") or []
    q_terms = _tokenize(query)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for ch in chunks:
        text = str(ch.get("text") or "").lower()
        if not text:
            continue
        score = _score_terms(text, q_terms)
        if score <= 0:
            continue
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for score, ch in scored[:top_k]:
        out.append(
            {
                "file_path": ch.get("file_path"),
                "section": ch.get("section"),
                "offset_start": ch.get("offset_start"),
                "offset_end": ch.get("offset_end"),
                "score": score,
            }
        )
    return out


def search_entities(index_path: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    if not query.strip():
        return []
    store = IndexStore(index_path)
    data = store.load_full()
    entities = data.get("entities") or []
    q = query.lower()
    out: List[Dict[str, Any]] = []
    for e in entities:
        funcs = e.get("functions") or []
        imports = e.get("imports") or []
        if any(q in f.lower() for f in funcs) or any(q in i.lower() for i in imports):
            out.append({"file": e.get("file"), "functions": funcs, "imports": imports})
        if len(out) >= top_k:
            break
    return out


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if t]


def _score_terms(text: str, terms: List[str]) -> float:
    score = 0.0
    for t in terms:
        if t and t in text:
            score += 1.0
    return score
