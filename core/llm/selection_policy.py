from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class SelectionWeights:
    quality: float
    cost: float
    latency: float
    error_rate: float


WINDOW_DAYS_DEFAULT = 7
MAX_CALLS_PER_GROUP_DEFAULT = 200
MIN_CALLS_FOR_DYNAMIC_DEFAULT = 20
COOLDOWN_MINUTES_DEFAULT = 15
BUILD_MIN_SUCCESS_RATE_DEFAULT = 0.85

DEFAULT_MODE_WEIGHTS: Dict[str, SelectionWeights] = {
    "general": SelectionWeights(quality=0.35, cost=0.30, latency=0.25, error_rate=0.10),
    "build_software": SelectionWeights(quality=0.60, cost=0.10, latency=0.10, error_rate=0.20),
    "gen_3d_step": SelectionWeights(quality=0.55, cost=0.10, latency=0.10, error_rate=0.25),
    "gen_2d_dxf": SelectionWeights(quality=0.55, cost=0.10, latency=0.10, error_rate=0.25),
}

DEFAULT_STATIC_FALLBACK_ORDER: Dict[str, List[str]] = {
    "general": ["ollama", "deepseek", "gemini", "openai"],
    "build_software": ["ollama", "deepseek", "gemini", "openai"],
    "gen_3d_step": ["ollama", "deepseek", "gemini", "openai"],
    "gen_2d_dxf": ["ollama", "deepseek", "gemini", "openai"],
}


def normalize_mode(mode: str) -> str:
    text = str(mode or "").strip().lower()
    if text in DEFAULT_MODE_WEIGHTS:
        return text
    return "general"


def _project_root() -> Path:
    env_root = str(os.environ.get("NH_BASE_DIR") or "").strip()
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def _to_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        parsed = default
    if parsed < minimum:
        return minimum
    return parsed


def _to_float(value: Any, default: float, *, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        parsed = default
    if parsed < minimum:
        return minimum
    return parsed


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_llm_routing_config() -> Dict[str, Any]:
    config_path_raw = str(os.environ.get("NH_LLM_ROUTING_CONFIG") or "").strip()
    if config_path_raw:
        config_path = Path(config_path_raw)
    else:
        config_path = _project_root() / "configs" / "llm_routing.yaml"
    data = _load_yaml(config_path)
    return data if isinstance(data, dict) else {}


_ROUTING_CONFIG = load_llm_routing_config()


def selector_window_days() -> int:
    selector = _ROUTING_CONFIG.get("selector")
    raw = selector.get("window_days") if isinstance(selector, dict) else None
    return _to_int(raw, WINDOW_DAYS_DEFAULT, minimum=1)


def selector_max_calls_per_group() -> int:
    selector = _ROUTING_CONFIG.get("selector")
    raw = selector.get("max_calls_per_group") if isinstance(selector, dict) else None
    return _to_int(raw, MAX_CALLS_PER_GROUP_DEFAULT, minimum=1)


def selector_min_calls_for_dynamic() -> int:
    selector = _ROUTING_CONFIG.get("selector")
    raw = selector.get("min_calls_for_dynamic") if isinstance(selector, dict) else None
    return _to_int(raw, MIN_CALLS_FOR_DYNAMIC_DEFAULT, minimum=1)


def selector_cooldown_minutes() -> int:
    selector = _ROUTING_CONFIG.get("selector")
    raw = selector.get("cooldown_minutes") if isinstance(selector, dict) else None
    return _to_int(raw, COOLDOWN_MINUTES_DEFAULT, minimum=1)


def selector_build_min_success_rate() -> float:
    selector = _ROUTING_CONFIG.get("selector")
    raw = selector.get("build_min_success_rate") if isinstance(selector, dict) else None
    return _to_float(raw, BUILD_MIN_SUCCESS_RATE_DEFAULT, minimum=0.0)


def _configured_mode_weights() -> Dict[str, SelectionWeights]:
    out: Dict[str, SelectionWeights] = dict(DEFAULT_MODE_WEIGHTS)
    raw = _ROUTING_CONFIG.get("mode_weights")
    if not isinstance(raw, dict):
        return out
    for mode_name, mode_cfg in raw.items():
        if not isinstance(mode_cfg, dict):
            continue
        mode_key = normalize_mode(str(mode_name))
        base = out.get(mode_key, DEFAULT_MODE_WEIGHTS["general"])
        out[mode_key] = SelectionWeights(
            quality=_to_float(mode_cfg.get("quality"), base.quality, minimum=0.0),
            cost=_to_float(mode_cfg.get("cost"), base.cost, minimum=0.0),
            latency=_to_float(mode_cfg.get("latency"), base.latency, minimum=0.0),
            error_rate=_to_float(mode_cfg.get("error_rate"), base.error_rate, minimum=0.0),
        )
    return out


def _configured_fallback_order() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {k: list(v) for k, v in DEFAULT_STATIC_FALLBACK_ORDER.items()}
    raw = _ROUTING_CONFIG.get("fallback_order")
    if not isinstance(raw, dict):
        return out
    for mode_name, providers in raw.items():
        if not isinstance(providers, list):
            continue
        mode_key = normalize_mode(str(mode_name))
        cleaned: List[str] = []
        for provider in providers:
            name = str(provider or "").strip().lower()
            if not name or name in cleaned:
                continue
            cleaned.append(name)
        if cleaned:
            out[mode_key] = cleaned
    return out


def mode_weights(mode: str) -> SelectionWeights:
    configured = _configured_mode_weights()
    canonical = normalize_mode(mode)
    return configured.get(canonical, DEFAULT_MODE_WEIGHTS["general"])


def fallback_order(mode: str) -> List[str]:
    configured = _configured_fallback_order()
    canonical = normalize_mode(mode)
    return list(configured.get(canonical, DEFAULT_STATIC_FALLBACK_ORDER["general"]))
