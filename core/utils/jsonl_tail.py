from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Tuple


def _safe_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return int(default)


def _tail_lines(path: str, limit: int, chunk_size: int = 65536) -> List[str]:
    take = max(0, _safe_int(limit, 0))
    if take <= 0 or not os.path.exists(path):
        return []

    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            if end <= 0:
                return []

            data = b""
            pos = end
            while pos > 0:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                if not chunk:
                    break
                data = chunk + data
                if data.count(b"\n") >= take + 1:
                    break
    except OSError:
        return []

    lines = data.splitlines()
    if len(lines) > take:
        lines = lines[-take:]
    out: List[str] = []
    for line in lines:
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            out.append(text)
    return out


def tail_jsonl_dicts(path: str, limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in _tail_lines(path, limit):
        try:
            item = json.loads(line)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def read_jsonl_page(path: str, cursor: int, limit: int) -> Tuple[List[Dict[str, Any]], int, bool]:
    if not os.path.exists(path):
        return [], max(0, _safe_int(cursor, 0)), False

    start = max(0, _safe_int(cursor, 0))
    take = max(1, _safe_int(limit, 200))

    idx = 0
    items: List[Dict[str, Any]] = []
    has_more = False

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    parsed = json.loads(s)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    continue
                if not isinstance(parsed, dict):
                    continue
                if idx < start:
                    idx += 1
                    continue
                if len(items) < take:
                    items.append(parsed)
                    idx += 1
                    continue
                has_more = True
                break
    except OSError:
        return [], start, False

    next_cursor = start + len(items)
    return items, next_cursor, has_more

