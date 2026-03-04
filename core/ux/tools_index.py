from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import json
import inspect

from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.ux.tools_registry import metadata_for_tool


def _signature_text(tool: ToolRegistration) -> str:
    try:
        return f"{tool.op}{inspect.signature(tool.handler)}"
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return str(tool.op or "")


def _tool_row(tool: ToolRegistration) -> Dict[str, object]:
    meta = metadata_for_tool(str(tool.tool_id))
    return {
        "tool_id": str(tool.tool_id),
        "plugin_id": str(tool.plugin_id),
        "tool_group": str(tool.tool_group),
        "op": str(tool.op),
        "description": str(tool.description or ""),
        "default_target": tool.default_target,
        "handler_signature": _signature_text(tool),
        "mode_tags": list(meta.mode_tags),
        "curated_modes": list(meta.curated_modes),
    }


def build_tools_index_payload(registry: PluginRegistry) -> Dict[str, object]:
    tools = sorted(registry.list_tools(), key=lambda t: str(t.tool_id or ""))
    rows: List[Dict[str, object]] = [_tool_row(tool) for tool in tools]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tools_total": len(rows),
        "tools": rows,
    }


def write_tools_index_report(registry: PluginRegistry, output_path: str) -> str:
    payload = build_tools_index_payload(registry)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return str(path.resolve())
