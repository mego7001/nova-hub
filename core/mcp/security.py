from __future__ import annotations

import os
from typing import Any, Dict, Optional

from core.portable.paths import default_workspace_dir, detect_base_dir


def resolve_workspace_root(explicit: Optional[str] = None) -> str:
    base_dir = detect_base_dir()
    workspace = os.path.abspath(explicit or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base_dir))
    return workspace


def _canonical(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def ensure_within_workspace(
    path_value: str,
    *,
    workspace_root: str,
    label: str,
    base_path: Optional[str] = None,
    require_exists: bool = False,
) -> str:
    text = str(path_value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    candidate = text
    if base_path and not os.path.isabs(candidate):
        candidate = os.path.join(base_path, candidate)

    candidate_abs = os.path.abspath(candidate)
    if require_exists and not os.path.exists(candidate_abs):
        raise FileNotFoundError(f"{label} not found: {text}")

    workspace_real = _canonical(workspace_root)
    candidate_real = _canonical(candidate_abs)
    try:
        common = os.path.commonpath([workspace_real, candidate_real])
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
        raise PermissionError(f"{label} escapes workspace: {text}") from exc
    if common != workspace_real:
        raise PermissionError(f"{label} escapes workspace: {text}")
    return candidate_real


def validate_patch_workspace_constraints(tool_id: str, payload: Dict[str, Any], *, workspace_root: str) -> None:
    tid = str(tool_id or "").strip()
    if tid not in {"patch.plan", "patch.apply"}:
        return

    data = payload if isinstance(payload, dict) else {}
    target_root_value = data.get("target_root")
    if target_root_value is None:
        target_root_value = data.get("target")
    if target_root_value is None:
        target_root_value = "."

    target_root_resolved = ensure_within_workspace(
        str(target_root_value),
        workspace_root=workspace_root,
        label="target_root",
        base_path=workspace_root,
        require_exists=False,
    )

    if tid == "patch.apply":
        diff_path = str(data.get("diff_path") or "").strip()
        if not diff_path:
            raise ValueError("diff_path is required")
        ensure_within_workspace(
            diff_path,
            workspace_root=workspace_root,
            label="diff_path",
            base_path=target_root_resolved,
            require_exists=False,
        )
