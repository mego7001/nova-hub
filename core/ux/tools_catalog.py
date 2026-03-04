from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from core.permission_guard.tool_policy import ToolPolicy
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.ux.task_modes import normalize_task_mode
from core.ux.tools_registry import curated_tool_ids_for_mode, metadata_for_tool


@dataclass(frozen=True)
class ToolCatalogEntry:
    id: str
    group: str
    badge: str
    description: str
    mode_tags: tuple[str, ...]
    enabled: bool
    approval_required: bool
    reason: str


_GROUP_TITLES: Dict[str, str] = {
    "fs_read": "Read",
    "fs_write": "Write",
    "process_exec": "Execution",
    "git": "Git",
    "network": "Network",
    "security": "Security",
    "telegram": "Messaging",
    "voice": "Voice",
    "gemini": "Cloud AI",
    "deepseek": "Cloud AI",
    "openai": "Cloud AI",
}


def _group_title(tool_group: str) -> str:
    tg = str(tool_group or "").strip().lower()
    if tg in _GROUP_TITLES:
        return _GROUP_TITLES[tg]
    if not tg:
        return "Other"
    return tg.replace("_", " ").title()


def _badge_for_tool(tool: ToolRegistration, policy: Optional[ToolPolicy]) -> tuple[str, bool, bool, str]:
    if policy is None:
        return "available", True, False, ""
    decision = policy.evaluate_group(str(tool.tool_group or ""))
    if not decision.allowed:
        return "unavailable", False, False, decision.reason
    if decision.requires_approval:
        return "approval", True, True, decision.reason
    return "available", True, False, decision.reason


def _entry(tool: ToolRegistration, policy: Optional[ToolPolicy], *, project_context: bool) -> ToolCatalogEntry:
    badge, enabled, requires_approval, reason = _badge_for_tool(tool, policy)
    meta = metadata_for_tool(str(tool.tool_id))
    if enabled and meta.required_modules:
        missing = [name for name in meta.required_modules if not importlib.util.find_spec(str(name))]
        if missing:
            enabled = False
            requires_approval = False
            badge = "unavailable"
            reason = f"missing dependency: {', '.join(missing)}"
    if enabled and meta.required_env_vars:
        missing_env = [name for name in meta.required_env_vars if not str(os.environ.get(str(name)) or "").strip()]
        if missing_env:
            enabled = False
            requires_approval = False
            badge = "unavailable"
            reason = f"missing secret/env: {', '.join(missing_env)}"
    if enabled and meta.requires_project_context and not project_context:
        enabled = False
        requires_approval = False
        badge = "unavailable"
        reason = "context mismatch: requires project context"
    return ToolCatalogEntry(
        id=str(tool.tool_id),
        group=_group_title(str(tool.tool_group)),
        badge=badge,
        description=str(tool.description or "").strip() or str(tool.op or ""),
        mode_tags=tuple(meta.mode_tags),
        enabled=enabled,
        approval_required=requires_approval,
        reason=reason,
    )


def _to_row(item: ToolCatalogEntry) -> Dict[str, object]:
    return {
        "id": item.id,
        "group": item.group,
        "badge": item.badge,
        "description": item.description,
        "mode_tags": list(item.mode_tags),
        "enabled": item.enabled,
        "approval_required": item.approval_required,
        "reason": item.reason,
    }


def _sorted_tools(registry: PluginRegistry) -> List[ToolRegistration]:
    tools = list(registry.list_tools())
    tools.sort(key=lambda t: (str(t.tool_group or ""), str(t.tool_id or "")))
    return tools


def build_tools_catalog(
    registry: PluginRegistry,
    *,
    policy: Optional[ToolPolicy] = None,
    project_context: bool = False,
    task_mode: str | None = None,
) -> Dict[str, object]:
    if task_mode is None:
        selected_mode = "build_software" if project_context else "general"
    else:
        selected_mode = normalize_task_mode(task_mode)
    curated_ids = curated_tool_ids_for_mode(selected_mode, project_context=project_context)
    advanced_entries: List[Dict[str, object]] = []
    grouped: Dict[str, List[Dict[str, object]]] = {}
    curated_entries: List[Dict[str, object]] = []

    by_id: Dict[str, ToolRegistration] = {}
    for tool in _sorted_tools(registry):
        by_id[str(tool.tool_id)] = tool
        entry = _entry(tool, policy, project_context=project_context)
        row = _to_row(entry)
        advanced_entries.append(row)
        grouped.setdefault(entry.group, []).append(row)

    for tool_id in curated_ids:
        tool = by_id.get(tool_id)
        if tool is None:
            continue
        curated_entries.append(_to_row(_entry(tool, policy, project_context=project_context)))

    ordered_groups: List[Dict[str, object]] = []
    for group_name in sorted(grouped.keys()):
        rows = grouped[group_name]
        rows.sort(key=lambda item: str(item.get("id") or ""))
        ordered_groups.append({"group": group_name, "items": rows})

    return {
        "task_mode": selected_mode,
        "curated": curated_entries,
        "advanced": advanced_entries,
        "groups": ordered_groups,
    }


def flatten_catalog_rows(catalog: Dict[str, object]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    curated = catalog.get("curated") if isinstance(catalog, dict) else []
    if isinstance(curated, list):
        for row in curated:
            if isinstance(row, dict):
                tagged = dict(row)
                tagged["section"] = "Curated"
                rows.append(tagged)
    groups = catalog.get("groups") if isinstance(catalog, dict) else []
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, dict):
                continue
            gname = str(group.get("group") or "Other")
            items = group.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                tagged = dict(item)
                tagged["section"] = f"Advanced / {gname}"
                rows.append(tagged)
    return rows


def _should_show_tool_row(row: Dict[str, object]) -> bool:
    if not isinstance(row, dict):
        return False
    tool_id = str(row.get("id") or "").strip().lower()
    if not tool_id:
        return False
    group = str(row.get("group") or "").strip().lower()
    patterns = [
        "patch.plan",
        "patch.apply",
        "patch_planner",
        "patch_apply",
        "ide.",
        "codex.",
        "codex",
    ]
    for pattern in patterns:
        if pattern and pattern in tool_id:
            return False
        if pattern and pattern in group:
            return False
    return True


def filter_codex_tool_rows(rows: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    visible: List[Dict[str, object]] = []
    for row in rows:
        if _should_show_tool_row(row):
            visible.append(row)
    return visible


def iter_catalog_entries(catalog: Dict[str, object]) -> Iterable[Dict[str, object]]:
    for row in flatten_catalog_rows(catalog):
        yield row
