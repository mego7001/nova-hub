from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL_GENERAL = "gemma3:4b"
DEFAULT_OLLAMA_MODEL_CODE = "qwen2.5-coder:7b-instruct"
DEFAULT_OLLAMA_MODEL_VISION = "llava"


@dataclass(frozen=True)
class OllamaSettings:
    enabled: bool
    base_url: str
    model_general: str
    model_code: str
    model_vision: str
    model_override: str
    connect_timeout_sec: float
    read_timeout_sec: float


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _coerce_float(value: Any, default: float, minimum: float) -> float:
    try:
        parsed = float(value)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        parsed = default
    if parsed < minimum:
        return minimum
    return parsed


def _pick_env(primary: str, legacy: str) -> str:
    if primary:
        val = str(os.environ.get(primary) or "").strip()
        if val:
            return val
    if legacy:
        return str(os.environ.get(legacy) or "").strip()
    return ""


def _pick_text(primary: str, legacy: str, cfg: Dict[str, Any], cfg_key: str, default: str) -> str:
    env_val = _pick_env(primary, legacy)
    if env_val:
        return env_val
    cfg_val = str(cfg.get(cfg_key) or "").strip()
    if cfg_val:
        return cfg_val
    return str(default)


def load_ollama_settings(config: Optional[Dict[str, Any]] = None) -> OllamaSettings:
    cfg = config if isinstance(config, dict) else {}
    enabled = _coerce_bool(
        os.environ.get("NH_OLLAMA_ENABLED"),
        _coerce_bool(cfg.get("enabled"), True),
    )

    base_url = _pick_text(
        "NH_OLLAMA_BASE_URL",
        "OLLAMA_BASE_URL",
        cfg,
        "base_url",
        DEFAULT_OLLAMA_BASE_URL,
    ).rstrip("/")

    model_general = _pick_text(
        "NH_OLLAMA_DEFAULT_MODEL_GENERAL",
        "OLLAMA_MODEL_GENERAL",
        cfg,
        "model_general",
        "",
    )
    if not model_general:
        model_general = _pick_text("NH_OLLAMA_MODEL", "OLLAMA_MODEL", cfg, "model", DEFAULT_OLLAMA_MODEL_GENERAL)

    model_code = _pick_text(
        "NH_OLLAMA_DEFAULT_MODEL_CODE",
        "OLLAMA_MODEL_CODER",
        cfg,
        "model_code",
        DEFAULT_OLLAMA_MODEL_CODE,
    )
    model_vision = _pick_text(
        "NH_OLLAMA_DEFAULT_MODEL_VISION",
        "OLLAMA_MODEL_VISION",
        cfg,
        "model_vision",
        "",
    )
    if not model_vision:
        model_vision = str(os.environ.get("OLLAMA_VISION_MODEL") or cfg.get("vision_model") or DEFAULT_OLLAMA_MODEL_VISION).strip()

    model_override = _pick_env("NH_OLLAMA_MODEL_OVERRIDE", "")

    connect_timeout_sec = _coerce_float(
        os.environ.get("NH_OLLAMA_CONNECT_TIMEOUT_SEC", cfg.get("connect_timeout_sec", 0.5)),
        0.5,
        0.1,
    )
    read_timeout_sec = _coerce_float(
        os.environ.get("NH_OLLAMA_READ_TIMEOUT_SEC", cfg.get("timeout_sec", 60)),
        60.0,
        1.0,
    )

    return OllamaSettings(
        enabled=enabled,
        base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
        model_general=model_general or DEFAULT_OLLAMA_MODEL_GENERAL,
        model_code=model_code or DEFAULT_OLLAMA_MODEL_CODE,
        model_vision=model_vision or DEFAULT_OLLAMA_MODEL_VISION,
        model_override=model_override,
        connect_timeout_sec=connect_timeout_sec,
        read_timeout_sec=read_timeout_sec,
    )


def pick_ollama_model(
    *,
    mode: str = "",
    request_kind: str = "",
    task_type: str = "",
    task_model_map: Optional[Dict[str, str]] = None,
    settings: Optional[OllamaSettings] = None,
    is_vision: bool = False,
    model_override: str = "",
) -> str:
    cfg = settings or load_ollama_settings()
    task_models = task_model_map if isinstance(task_model_map, dict) else {}
    override = str(model_override or cfg.model_override or "").strip()
    if override:
        return override

    if is_vision:
        return str(task_models.get("vision") or cfg.model_vision).strip()

    task = str(task_type or "").strip().lower()
    mode_name = str(mode or "").strip().lower()
    req_kind = str(request_kind or "").strip().lower()

    code_modes = {"build_software", "gen_2d_dxf", "gen_3d_step"}
    code_tasks = {"build_software", "patch_planning", "plan", "deep_reasoning"}
    if mode_name in code_modes or task in code_tasks:
        return str(task_models.get("build_software") or task_models.get("patch_planning") or cfg.model_code).strip()
    if any(token in req_kind for token in ("patch", "code", "build", "refactor")):
        return str(task_models.get("build_software") or task_models.get("patch_planning") or cfg.model_code).strip()

    direct_task_model = str(task_models.get(task) or "").strip()
    if direct_task_model:
        return direct_task_model

    return str(task_models.get("conversation") or cfg.model_general).strip()
