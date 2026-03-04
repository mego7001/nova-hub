from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

from core.telemetry.db import TelemetryDB
from core.telemetry.queries import provider_stats

from .selection_policy import (
    fallback_order,
    mode_weights,
    normalize_mode,
    selector_build_min_success_rate,
    selector_cooldown_minutes,
    selector_max_calls_per_group,
    selector_min_calls_for_dynamic,
    selector_window_days,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _metric_range(rows: Iterable[Dict[str, Any]], key: str) -> tuple[float, float]:
    vals: List[float] = []
    for row in rows:
        try:
            vals.append(float(row.get(key) or 0.0))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            vals.append(0.0)
    if not vals:
        return 0.0, 1.0
    lo = min(vals)
    hi = max(vals)
    if hi <= lo:
        return lo, lo + 1.0
    return lo, hi


def _normalize_metric(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    n = (value - lo) / (hi - lo)
    if n < 0.0:
        return 0.0
    if n > 1.0:
        return 1.0
    return float(n)


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


class WeightedProviderSelector:
    def __init__(self, db: TelemetryDB) -> None:
        self.db = db

    def pick_provider(
        self,
        *,
        mode: str,
        request_kind: str,
        candidates: List[str],
        profile: str = "",
    ) -> Dict[str, Any]:
        canonical_mode = normalize_mode(mode)
        window_days = selector_window_days()
        max_calls_per_group = selector_max_calls_per_group()
        min_calls_for_dynamic = selector_min_calls_for_dynamic()
        cooldown_minutes = selector_cooldown_minutes()
        build_min_success_rate = selector_build_min_success_rate()
        ordered_candidates = [str(c or "").strip().lower() for c in candidates if str(c or "").strip()]
        if not ordered_candidates:
            ordered_candidates = fallback_order(canonical_mode)

        fallback = [p for p in fallback_order(canonical_mode) if p in ordered_candidates]
        for candidate in ordered_candidates:
            if candidate not in fallback:
                fallback.append(candidate)

        stats_rows = provider_stats(
            self.db,
            mode=canonical_mode,
            request_kind=str(request_kind or "").strip().lower() or "conversation",
            window_days=window_days,
            max_calls_per_group=max_calls_per_group,
        )
        stats_by_provider: Dict[str, Dict[str, Any]] = {str(r.get("provider") or ""): dict(r) for r in stats_rows}
        scored: List[Dict[str, Any]] = []
        for provider in fallback:
            stats = stats_by_provider.get(provider, {})
            calls = int(stats.get("calls") or 0)
            success_rate = float(stats.get("success_rate") or 0.0)
            error_rate = float(stats.get("error_rate") or (1.0 if calls else 0.0))
            avg_latency_ms = float(stats.get("avg_latency_ms") or 0.0)
            avg_cost_usd = stats.get("avg_cost_usd")
            if avg_cost_usd is None:
                avg_cost_metric = float(stats.get("avg_tokens") or 0.0) / 1000.0
            else:
                avg_cost_metric = float(avg_cost_usd or 0.0)

            scored.append(
                {
                    "provider": provider,
                    "profile": str(profile or ""),
                    "calls": calls,
                    "success_rate": success_rate,
                    "error_rate": error_rate,
                    "avg_latency_ms": avg_latency_ms,
                    "avg_cost_metric": avg_cost_metric,
                    "last_error_kind": str(stats.get("last_error_kind") or ""),
                    "last_used": str(stats.get("last_used") or ""),
                    "insufficient_data": calls < min_calls_for_dynamic,
                    "fallback_rank": fallback.index(provider),
                }
            )

        latency_lo, latency_hi = _metric_range(scored, "avg_latency_ms")
        cost_lo, cost_hi = _metric_range(scored, "avg_cost_metric")
        weights = mode_weights(canonical_mode)

        now = _utc_now()
        best_success = max(float(row.get("success_rate") or 0.0) for row in scored) if scored else 0.0
        for row in scored:
            quality = float(row.get("success_rate") or 0.0)
            error_rate = float(row.get("error_rate") or 0.0)
            latency_norm = _normalize_metric(float(row.get("avg_latency_ms") or 0.0), latency_lo, latency_hi)
            cost_norm = _normalize_metric(float(row.get("avg_cost_metric") or 0.0), cost_lo, cost_hi)
            score = (
                weights.quality * quality
                - weights.cost * cost_norm
                - weights.latency * latency_norm
                - weights.error_rate * error_rate
            )

            # Deterministic fallback boost for sparse telemetry.
            if bool(row.get("insufficient_data")):
                rank = int(row.get("fallback_rank") or 0)
                score += max(0.0, 0.05 - (0.01 * rank))

            # Cooldown penalty when latest failure is auth/rate-limit.
            last_error_kind = str(row.get("last_error_kind") or "").strip().lower()
            last_used = _parse_ts(row.get("last_used"))
            if last_error_kind in ("rate_limit", "auth") and last_used is not None:
                if now - last_used <= timedelta(minutes=cooldown_minutes):
                    score -= 10.0
                    row["cooldown_active"] = True
                else:
                    row["cooldown_active"] = False
            else:
                row["cooldown_active"] = False

            if canonical_mode == "build_software":
                if quality < build_min_success_rate and best_success >= build_min_success_rate:
                    score -= 5.0
                    row["guardrail_penalty"] = True
                else:
                    row["guardrail_penalty"] = False

            row["score"] = round(score, 6)

        scored.sort(
            key=lambda x: (
                -float(x.get("score") or 0.0),
                int(x.get("fallback_rank") or 0),
                str(x.get("provider") or ""),
            )
        )
        chosen = str(scored[0].get("provider") or fallback[0]) if scored else (fallback[0] if fallback else "deepseek")
        return {
            "provider": chosen,
            "mode": canonical_mode,
            "request_kind": str(request_kind or "conversation"),
            "scored": scored,
            "window_days": window_days,
            "max_calls_per_group": max_calls_per_group,
        }
