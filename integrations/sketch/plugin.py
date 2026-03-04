from __future__ import annotations

import os
from typing import Any, Dict, List

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.portable.paths import detect_base_dir, default_workspace_dir
from core.security.secrets import SecretsManager
from core.sketch import parser as sketch_parser
from core.sketch import store as sketch_store
from core.sketch.dxf import export_dxf


def _workspace_root() -> str:
    base = detect_base_dir()
    return os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def sketch_parse(text: str) -> Dict[str, Any]:
        ops = sketch_parser.parse_ops(text or "")
        summary = sketch_parser.summarize_ops(ops)
        return {
            "ops": ops,
            "summary": summary,
        }

    def sketch_apply(project_id: str, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not project_id:
            raise ValueError("project_id is required")
        res = sketch_store.apply_ops(project_id, ops, workspace_root=_workspace_root())
        return {
            "status": "ok",
            "count": res.get("count", 0),
            "sketch_path": res.get("path"),
        }

    def sketch_export_dxf(project_id: str, output_path: str = "") -> Dict[str, Any]:
        if not project_id:
            raise ValueError("project_id is required")
        ws = _workspace_root()
        state = sketch_store.load_sketch(project_id, workspace_root=ws)
        entities = state.get("entities") or []
        dxf_text = export_dxf(entities)
        if not output_path:
            out_dir = os.path.join(ws, "projects", project_id, "outputs")
            os.makedirs(out_dir, exist_ok=True)
            output_path = os.path.join(out_dir, f"{project_id}_sketch.dxf")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(SecretsManager.redact_text(dxf_text))
        return {
            "status": "ok",
            "output_path": output_path,
            "entity_count": len(entities),
        }

    registry.register_tool(
        ToolRegistration(
            tool_id="sketch.parse",
            plugin_id=manifest.id,
            tool_group="fs_read",
            op="sketch_parse",
            handler=sketch_parse,
            description="Parse sketch description into operations",
            default_target=None,
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="sketch.apply",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="sketch_apply",
            handler=sketch_apply,
            description="Apply sketch ops to sketch.json",
            default_target=None,
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="sketch.export_dxf",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="sketch_export_dxf",
            handler=sketch_export_dxf,
            description="Export sketch to DXF",
            default_target=None,
        )
    )
