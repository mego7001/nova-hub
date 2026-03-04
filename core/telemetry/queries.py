from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple

from .db import TelemetryDB


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        return datetime.fromisoformat(text)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return None


def _window_cutoff_iso(window_days: int) -> str:
    cutoff = _utc_now() - timedelta(days=max(1, int(window_days)))
    return cutoff.isoformat().replace("+00:00", "Z")


def _filter_recent(rows: Iterable[Dict[str, Any]], *, window_days: int) -> List[Dict[str, Any]]:
    cutoff = _utc_now() - timedelta(days=max(1, int(window_days)))
    out: List[Dict[str, Any]] = []
    for row in rows:
        ts = _parse_ts(row.get("ts"))
        if ts is None:
            continue
        if ts >= cutoff:
            out.append(dict(row))
    return out


def _take_recent_per_group(
    rows: Iterable[Dict[str, Any]],
    *,
    group_keys: Tuple[str, ...],
    max_calls: int,
) -> List[Dict[str, Any]]:
    counts: Dict[Tuple[str, ...], int] = {}
    out: List[Dict[str, Any]] = []
    for row in rows:
        key = tuple(str(row.get(k) or "") for k in group_keys)
        current = counts.get(key, 0)
        if current >= max_calls:
            continue
        counts[key] = current + 1
        out.append(dict(row))
    return out


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return 0


def _safe_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return 0.0


def provider_stats(
    db: TelemetryDB,
    *,
    mode: str = "",
    provider: str = "",
    request_kind: str = "",
    window_days: int = 7,
    max_calls_per_group: int = 200,
) -> List[Dict[str, Any]]:
    params: List[Any] = [_window_cutoff_iso(window_days)]
    clauses = ["ts >= ?"]
    if mode:
        clauses.append("mode = ?")
        params.append(str(mode))
    if provider:
        clauses.append("provider = ?")
        params.append(str(provider))
    if request_kind:
        clauses.append("request_kind = ?")
        params.append(str(request_kind))
    where_sql = " AND ".join(clauses)
    rows = db.fetch_all(
        f"""
        SELECT ts, mode, provider, request_kind, status, error_kind, error_msg,
               latency_ms, cost_usd, input_tokens, output_tokens
          FROM llm_calls
         WHERE {where_sql}
         ORDER BY ts DESC
        """,
        params,
    )
    rows = _filter_recent(rows, window_days=window_days)
    rows = _take_recent_per_group(
        rows,
        group_keys=("provider", "mode", "request_kind"),
        max_calls=max_calls_per_group,
    )

    grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("provider") or ""),
            str(row.get("mode") or ""),
            str(row.get("request_kind") or ""),
        )
        bucket = grouped.setdefault(
            key,
            {
                "provider": key[0],
                "mode": key[1],
                "request_kind": key[2],
                "calls": 0,
                "ok_calls": 0,
                "error_calls": 0,
                "latency_total": 0.0,
                "latency_count": 0,
                "cost_total": 0.0,
                "cost_count": 0,
                "tokens_total": 0,
                "last_used": "",
                "last_error": "",
                "last_error_kind": "",
            },
        )
        bucket["calls"] += 1
        if str(row.get("status") or "").lower() == "ok":
            bucket["ok_calls"] += 1
        else:
            bucket["error_calls"] += 1
            if not bucket["last_error"]:
                bucket["last_error"] = str(row.get("error_msg") or "")
                bucket["last_error_kind"] = str(row.get("error_kind") or "")
        latency = _safe_int(row.get("latency_ms"))
        if latency > 0:
            bucket["latency_total"] += float(latency)
            bucket["latency_count"] += 1
        cost = row.get("cost_usd")
        if cost is not None:
            bucket["cost_total"] += _safe_float(cost)
            bucket["cost_count"] += 1
        bucket["tokens_total"] += _safe_int(row.get("input_tokens")) + _safe_int(row.get("output_tokens"))
        if not bucket["last_used"]:
            bucket["last_used"] = str(row.get("ts") or "")

    out: List[Dict[str, Any]] = []
    for key in sorted(grouped.keys()):
        item = grouped[key]
        calls = max(1, int(item["calls"]))
        ok_calls = int(item["ok_calls"])
        error_calls = int(item["error_calls"])
        success_rate = ok_calls / calls
        error_rate = error_calls / calls
        avg_latency = (item["latency_total"] / item["latency_count"]) if item["latency_count"] else 0.0
        avg_cost = (item["cost_total"] / item["cost_count"]) if item["cost_count"] else None
        out.append(
            {
                "provider": item["provider"],
                "mode": item["mode"],
                "request_kind": item["request_kind"],
                "calls": calls,
                "ok_calls": ok_calls,
                "error_calls": error_calls,
                "success_rate": round(success_rate, 4),
                "error_rate": round(error_rate, 4),
                "avg_latency_ms": int(round(avg_latency)),
                "avg_cost_usd": None if avg_cost is None else round(avg_cost, 6),
                "avg_tokens": int(round(item["tokens_total"] / calls)),
                "last_used": item["last_used"],
                "last_error": item["last_error"],
                "last_error_kind": item["last_error_kind"],
            }
        )
    return out


def provider_scoreboard(
    db: TelemetryDB,
    *,
    mode: str = "",
    window_days: int = 7,
    max_calls_per_group: int = 200,
) -> List[Dict[str, Any]]:
    rows = provider_stats(
        db,
        mode=mode,
        provider="",
        request_kind="",
        window_days=window_days,
        max_calls_per_group=max_calls_per_group,
    )
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        provider = str(row.get("provider") or "")
        if not provider:
            continue
        bucket = grouped.setdefault(
            provider,
            {
                "provider": provider,
                "calls": 0,
                "ok_calls": 0,
                "error_calls": 0,
                "latency_total": 0,
                "latency_count": 0,
                "cost_total": 0.0,
                "cost_count": 0,
                "tokens_total": 0,
                "last_used": "",
                "last_error": "",
                "last_error_kind": "",
            },
        )
        calls = _safe_int(row.get("calls"))
        bucket["calls"] += calls
        bucket["ok_calls"] += _safe_int(row.get("ok_calls"))
        bucket["error_calls"] += _safe_int(row.get("error_calls"))
        latency = _safe_int(row.get("avg_latency_ms"))
        if latency > 0 and calls > 0:
            bucket["latency_total"] += latency * calls
            bucket["latency_count"] += calls
        cost = row.get("avg_cost_usd")
        if cost is not None and calls > 0:
            bucket["cost_total"] += _safe_float(cost) * calls
            bucket["cost_count"] += calls
        bucket["tokens_total"] += _safe_int(row.get("avg_tokens")) * calls
        if not bucket["last_used"]:
            bucket["last_used"] = str(row.get("last_used") or "")
        if not bucket["last_error"] and str(row.get("last_error") or "").strip():
            bucket["last_error"] = str(row.get("last_error") or "")
            bucket["last_error_kind"] = str(row.get("last_error_kind") or "")

    out: List[Dict[str, Any]] = []
    for provider in sorted(grouped.keys()):
        item = grouped[provider]
        calls = max(1, int(item["calls"]))
        success_rate = item["ok_calls"] / calls
        error_rate = item["error_calls"] / calls
        avg_latency = (item["latency_total"] / item["latency_count"]) if item["latency_count"] else 0.0
        avg_cost = (item["cost_total"] / item["cost_count"]) if item["cost_count"] else None
        out.append(
            {
                "provider": provider,
                "calls": int(item["calls"]),
                "ok_calls": int(item["ok_calls"]),
                "error_calls": int(item["error_calls"]),
                "success_rate": round(success_rate, 4),
                "error_rate": round(error_rate, 4),
                "avg_latency_ms": int(round(avg_latency)),
                "avg_cost_usd": None if avg_cost is None else round(avg_cost, 6),
                "avg_tokens": int(round(item["tokens_total"] / calls)),
                "last_used": item["last_used"],
                "last_error": item["last_error"],
                "last_error_kind": item["last_error_kind"],
            }
        )
    out.sort(key=lambda x: (-float(x.get("success_rate") or 0.0), float(x.get("avg_latency_ms") or 0), str(x.get("provider") or "")))
    return out


def tool_scoreboard(
    db: TelemetryDB,
    *,
    mode: str = "",
    window_days: int = 7,
) -> List[Dict[str, Any]]:
    params: List[Any] = [_window_cutoff_iso(window_days)]
    clauses = ["ts >= ?"]
    if mode:
        clauses.append("mode = ?")
        params.append(str(mode))
    where_sql = " AND ".join(clauses)
    rows = db.fetch_all(
        f"""
        SELECT tool_name, mode, status, error_kind, error_msg, latency_ms, ts
          FROM tool_calls
         WHERE {where_sql}
         ORDER BY ts DESC
        """,
        params,
    )
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("tool_name") or ""), str(row.get("mode") or ""))
        if not key[0]:
            continue
        bucket = grouped.setdefault(
            key,
            {
                "tool_name": key[0],
                "mode": key[1],
                "calls": 0,
                "ok_calls": 0,
                "error_calls": 0,
                "latency_total": 0.0,
                "latency_count": 0,
                "last_used": "",
                "last_error": "",
            },
        )
        bucket["calls"] += 1
        if str(row.get("status") or "").lower() == "ok":
            bucket["ok_calls"] += 1
        else:
            bucket["error_calls"] += 1
            if not bucket["last_error"]:
                bucket["last_error"] = str(row.get("error_msg") or row.get("error_kind") or "")
        latency = _safe_int(row.get("latency_ms"))
        if latency > 0:
            bucket["latency_total"] += float(latency)
            bucket["latency_count"] += 1
        if not bucket["last_used"]:
            bucket["last_used"] = str(row.get("ts") or "")

    out: List[Dict[str, Any]] = []
    for key in sorted(grouped.keys()):
        item = grouped[key]
        calls = max(1, int(item["calls"]))
        out.append(
            {
                "tool_name": item["tool_name"],
                "mode": item["mode"],
                "calls": int(item["calls"]),
                "ok_calls": int(item["ok_calls"]),
                "error_calls": int(item["error_calls"]),
                "success_rate": round(float(item["ok_calls"]) / calls, 4),
                "avg_latency_ms": int(round(item["latency_total"] / item["latency_count"])) if item["latency_count"] else 0,
                "last_used": item["last_used"],
                "last_error": item["last_error"],
            }
        )
    out.sort(key=lambda x: (-float(x.get("success_rate") or 0.0), str(x.get("tool_name") or "")))
    return out


def recent_provider_errors(db: TelemetryDB, *, limit: int = 5, window_days: int = 7) -> List[Dict[str, Any]]:
    cutoff = _window_cutoff_iso(window_days)
    rows = db.fetch_all(
        """
        SELECT provider, error_kind, error_msg, COUNT(*) AS cnt, MAX(ts) AS last_seen
          FROM llm_calls
         WHERE ts >= ? AND status = 'error'
         GROUP BY provider, error_kind, error_msg
         ORDER BY cnt DESC, last_seen DESC
         LIMIT ?
        """,
        (cutoff, int(max(1, limit))),
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "provider": str(row.get("provider") or ""),
                "error_kind": str(row.get("error_kind") or ""),
                "error_msg": str(row.get("error_msg") or ""),
                "count": int(row.get("cnt") or 0),
                "last_seen": str(row.get("last_seen") or ""),
            }
        )
    return out


def _sum_tokens(
    db: TelemetryDB,
    *,
    since_iso: str | None = None,
    session_id: str = "",
) -> int:
    params: List[Any] = []
    clauses: List[str] = []
    if since_iso:
        clauses.append("ts >= ?")
        params.append(str(since_iso))
    if session_id:
        clauses.append("session_id = ?")
        params.append(str(session_id))
    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)
    row = db.fetch_one(
        f"""
        SELECT COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0) AS tokens_total
          FROM llm_calls
         {where_sql}
        """,
        params,
    )
    return _safe_int((row or {}).get("tokens_total"))


def llm_token_usage(db: TelemetryDB, *, session_id: str = "", daily_window_hours: int = 24) -> Dict[str, int]:
    hours = max(1, int(daily_window_hours))
    since = (_utc_now() - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
    daily_total = _sum_tokens(db, since_iso=since, session_id="")
    session_total = _sum_tokens(db, since_iso=None, session_id=str(session_id or ""))
    return {
        "session_tokens": session_total,
        "daily_tokens": daily_total,
    }
