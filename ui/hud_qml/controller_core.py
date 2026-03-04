from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_jsonl(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    item = json.loads(s)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    continue
                if isinstance(item, dict):
                    out.append(item)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return []
    return out


def safe_read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}
    return data if isinstance(data, dict) else {}
