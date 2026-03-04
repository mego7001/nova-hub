from __future__ import annotations
import os
import re
from typing import List, Dict


_NAME_HINTS = {"main.py", "app.py", "cli.py", "__main__.py"}


def detect_entrypoints(root_path: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for base, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", "dist", "build")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root_path)
            reason = ""
            if name in _NAME_HINTS or name.startswith("run_"):
                reason = "filename"
            if _has_main_guard(path):
                reason = "main_guard" if not reason else f"{reason}+main_guard"
            if reason:
                out.append({"path": rel, "reason": reason})
    return out


def _has_main_guard(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return bool(re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]", text))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False
