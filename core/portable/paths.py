from __future__ import annotations
import os
from typing import List


def detect_base_dir() -> str:
    env = os.environ.get("NH_BASE_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)

    candidates = [os.getcwd(), os.path.abspath(os.path.dirname(__file__))]
    seen = set()
    for start in candidates:
        cur = os.path.abspath(start)
        while cur and cur not in seen:
            seen.add(cur)
            if _has_portable_marker(cur):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    return os.path.abspath(os.getcwd())


def _has_portable_marker(path: str) -> bool:
    for name in ("run_chat.py", "run_whatsapp.py", "run_ui.py", "main.py"):
        if os.path.exists(os.path.join(path, name)):
            return True
    return False


def default_workspace_dir(base_dir: str) -> str:
    return os.path.join(base_dir, "workspace")


def ensure_workspace_dirs(base_dir: str) -> List[str]:
    workspace = default_workspace_dir(base_dir)
    subfolders = [
        "projects",
        "imports",
        "snapshots",
        "reports",
        "logs",
        "releases",
        "patches",
        "outputs",
    ]
    created = []
    os.makedirs(workspace, exist_ok=True)
    for s in subfolders:
        p = os.path.join(workspace, s)
        os.makedirs(p, exist_ok=True)
        created.append(p)
    return created
