
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional

from core.plugin_engine.registry import PluginRegistry


class TaskMode(str, Enum):
    GENERAL = "general"
    BUILD_SOFTWARE = "build_software"
    GEN_3D_STEP = "gen_3d_step"
    GEN_2D_DXF = "gen_2d_dxf"


AUTO_MODE_ID = "auto"


@dataclass(frozen=True)
class TaskModeSpec:
    mode: TaskMode
    title: str
    description: str
    aliases: tuple[str, ...] = ()
    required_tools_any: tuple[str, ...] = ()
    required_tools_all: tuple[str, ...] = ()


TASK_MODE_SPECS: tuple[TaskModeSpec, ...] = (
    TaskModeSpec(
        mode=TaskMode.GENERAL,
        title="General",
        description="General assistant mode for exploration, Q&A, and lightweight workflows.",
    ),
    TaskModeSpec(
        mode=TaskMode.BUILD_SOFTWARE,
        title="Build Software",
        description="Research -> plan -> patch -> verify flow through approved software tools.",
        required_tools_any=("conversation.chat", "patch.plan", "pipeline.run"),
    ),
    TaskModeSpec(
        mode=TaskMode.GEN_3D_STEP,
        title="3D -> STEP",
        description="Route prompt context for 3D generation and STEP-oriented CAD workflows.",
        required_tools_any=("cad.step.generate",),
    ),
    TaskModeSpec(
        mode=TaskMode.GEN_2D_DXF,
        title="2D -> DXF",
        description="Route prompt context for 2D geometry and DXF generation workflows.",
        required_tools_any=("sketch.parse", "sketch.apply", "sketch.export_dxf"),
    ),
)


LEGACY_ALIAS_MAP: Dict[str, str] = {
    "chat": TaskMode.GENERAL.value,
    "deep_research": TaskMode.BUILD_SOFTWARE.value,
    "engineering": TaskMode.BUILD_SOFTWARE.value,
    "verify": TaskMode.BUILD_SOFTWARE.value,
    "sketch": TaskMode.GEN_2D_DXF.value,
}


INTERNAL_ALIAS_MAP: Dict[str, str] = {
    "build": TaskMode.BUILD_SOFTWARE.value,
    "3d": TaskMode.GEN_3D_STEP.value,
    "gen_3d": TaskMode.GEN_3D_STEP.value,
    "geometry3d": TaskMode.GEN_3D_STEP.value,
    "step": TaskMode.GEN_3D_STEP.value,
    "2d": TaskMode.GEN_2D_DXF.value,
    "gen_2d": TaskMode.GEN_2D_DXF.value,
    "dxf": TaskMode.GEN_2D_DXF.value,
}


def _alias_map() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for spec in TASK_MODE_SPECS:
        out[spec.mode.value] = spec.mode.value
        for alias in spec.aliases:
            key = str(alias or "").strip().lower()
            if key:
                out[key] = spec.mode.value
    out.update(INTERNAL_ALIAS_MAP)
    out.update(LEGACY_ALIAS_MAP)
    return out


def normalize_task_mode(raw_mode: str, fallback: TaskMode | str = TaskMode.GENERAL) -> str:
    aliases = _alias_map()
    raw = str(raw_mode or "").strip().lower()
    if raw in aliases:
        return aliases[raw]
    if isinstance(fallback, TaskMode):
        fallback_text = fallback.value
    else:
        fallback_text = str(fallback or "").strip().lower()
    if fallback_text in aliases:
        return aliases[fallback_text]
    return TaskMode.GENERAL.value


def is_auto_mode(raw_mode: str) -> bool:
    return str(raw_mode or "").strip().lower() == AUTO_MODE_ID


def canonical_mode_aliases(mode: TaskMode | str) -> List[str]:
    normalized = normalize_task_mode(str(mode))
    aliases = [normalized]
    for alias, canonical in _alias_map().items():
        if canonical == normalized and alias != normalized:
            aliases.append(alias)
    dedup: List[str] = []
    seen = set()
    for item in aliases:
        key = str(item or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        dedup.append(key)
    return dedup or [TaskMode.GENERAL.value]


def _tool_ids(registry: Optional[PluginRegistry]) -> set[str]:
    if registry is None:
        return set()
    return {str(tool_id) for tool_id in registry.tools.keys()}


def _mode_available(spec: TaskModeSpec, tool_ids: set[str]) -> tuple[bool, str]:
    if not spec.required_tools_any and not spec.required_tools_all:
        return True, ""

    if spec.required_tools_all:
        missing = [tool_id for tool_id in spec.required_tools_all if tool_id not in tool_ids]
        if missing:
            return False, f"Missing tools: {', '.join(sorted(missing))}"

    if spec.required_tools_any:
        if not any(tool_id in tool_ids for tool_id in spec.required_tools_any):
            return False, f"Missing one of: {', '.join(sorted(spec.required_tools_any))}"

    return True, ""


def available_task_modes(
    registry: Optional[PluginRegistry],
    *,
    include_unavailable: bool = False,
) -> List[Dict[str, object]]:
    tool_ids = _tool_ids(registry)
    rows: List[Dict[str, object]] = []
    for spec in TASK_MODE_SPECS:
        available, reason = _mode_available(spec, tool_ids)
        if not available and not include_unavailable:
            continue
        rows.append(
            {
                "id": spec.mode.value,
                "title": spec.title,
                "description": spec.description,
                "available": available,
                "reason": reason,
            }
        )
    return rows


def mode_ids(registry: Optional[PluginRegistry], *, include_unavailable: bool = False) -> List[str]:
    return [str(row.get("id") or "") for row in available_task_modes(registry, include_unavailable=include_unavailable)]


def is_mode_supported(mode: str, registry: Optional[PluginRegistry]) -> bool:
    selected = normalize_task_mode(mode)
    for row in available_task_modes(registry, include_unavailable=False):
        if str(row.get("id") or "") == selected:
            return bool(row.get("available"))
    return False


def iter_specs() -> Iterable[TaskModeSpec]:
    return TASK_MODE_SPECS


def is_codex_ui_enabled() -> bool:
    return str(os.environ.get("NH_CODEX_UI_ENABLED") or "").strip() == "1"


def _is_user_visible_mode(mode_id: str) -> bool:
    key = str(mode_id or "").strip().lower()
    if key == TaskMode.BUILD_SOFTWARE.value and not is_codex_ui_enabled():
        return False
    return bool(key)


def allowed_user_task_modes(
    registry: Optional[PluginRegistry],
    *,
    include_unavailable: bool = False,
) -> List[Dict[str, object]]:
    rows = available_task_modes(registry, include_unavailable=include_unavailable)
    visible = [row for row in rows if _is_user_visible_mode(str(row.get("id") or ""))]
    auto_row = {
        "id": AUTO_MODE_ID,
        "title": "Auto",
        "description": "Automatically picks the best executable mode.",
        "available": True,
        "reason": "",
    }
    return [auto_row, *visible]


def allowed_user_mode_ids(registry: Optional[PluginRegistry], *, include_unavailable: bool = False) -> List[str]:
    return [str(row.get("id") or "") for row in allowed_user_task_modes(registry, include_unavailable=include_unavailable)]


def auto_fallback_mode(registry: Optional[PluginRegistry], *, project_context: bool = False) -> str:
    preferred: List[str]
    if project_context:
        preferred = [
            TaskMode.BUILD_SOFTWARE.value,
            TaskMode.GEN_3D_STEP.value,
            TaskMode.GEN_2D_DXF.value,
            TaskMode.GENERAL.value,
        ]
    else:
        preferred = [
            TaskMode.GENERAL.value,
            TaskMode.BUILD_SOFTWARE.value,
            TaskMode.GEN_3D_STEP.value,
            TaskMode.GEN_2D_DXF.value,
        ]
    for mode in preferred:
        if is_mode_supported(mode, registry):
            return mode
    rows = available_task_modes(registry, include_unavailable=False)
    if rows:
        return str(rows[0].get("id") or TaskMode.GENERAL.value)
    return TaskMode.GENERAL.value
