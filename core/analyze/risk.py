from __future__ import annotations
import os
import re
from typing import Any, Dict, List


_RISK_WORDS = ["password", "secret", "token", "apikey", "api_key", "private_key", "subprocess", "eval", "exec"]


def score_risks(root_path: str, search_res: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    file_hits = {}
    if search_res:
        for m in search_res.get("matches") or []:
            p = m.get("path")
            if p:
                file_hits[p] = file_hits.get(p, 0) + 1

    risks: List[Dict[str, Any]] = []
    for base, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", "dist", "build")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root_path)
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                text = ""
            score = 0
            reasons = []
            if size > 200_000:
                score += 3
                reasons.append("large_file")
            if size > 100_000:
                score += 2
                reasons.append("big_file")
            hits = file_hits.get(rel, 0)
            if hits >= 10:
                score += 3
                reasons.append("many_todos_or_hits")
            elif hits >= 5:
                score += 2
                reasons.append("todo_hits")
            for w in _RISK_WORDS:
                if re.search(rf"\\b{re.escape(w)}\\b", text, re.IGNORECASE):
                    score += 1
                    reasons.append(f"risk_word:{w}")
                    break
            if "subprocess" in text or "os.system" in text:
                score += 2
                reasons.append("process_exec_usage")
            if score > 0:
                risks.append({"file": rel, "score": score, "reasons": reasons})

    risks.sort(key=lambda x: x.get("score", 0), reverse=True)
    return risks
