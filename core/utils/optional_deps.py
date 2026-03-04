from __future__ import annotations

import importlib
from typing import Tuple


class FeatureUnavailable(RuntimeError):
    """Raised when an optional dependency-backed feature is unavailable."""


def _build_message(dep_name: str, pip_hint: str, feature_name: str) -> str:
    dep = str(dep_name or "").strip() or "unknown"
    feature = str(feature_name or "").strip() or "feature"
    hint = str(pip_hint or "").strip()
    if hint:
        return (
            f"Feature disabled: missing dependency '{dep}' for {feature}. "
            f"Install with: {hint}"
        )
    return f"Feature disabled: missing dependency '{dep}' for {feature}."


def require(
    dep_name: str,
    pip_hint: str,
    feature_name: str,
    raise_on_missing: bool = False,
) -> Tuple[bool, str]:
    dep = str(dep_name or "").strip()
    if not dep:
        msg = _build_message(dep_name, pip_hint, feature_name)
        if raise_on_missing:
            raise FeatureUnavailable(msg)
        return False, msg
    try:
        importlib.import_module(dep)
    except (ImportError, ModuleNotFoundError, OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        msg = _build_message(dep, pip_hint, feature_name)
        if raise_on_missing:
            raise FeatureUnavailable(msg)
        return False, msg
    return True, ""

