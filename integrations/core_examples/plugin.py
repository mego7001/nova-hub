from __future__ import annotations
import os
from typing import Any, Dict
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration

def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def write_text(path: str, text: str, target: str | None = None) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return {"ok": True, "path": os.path.abspath(path), "bytes": len(text.encode("utf-8"))}

    registry.register_tool(ToolRegistration(
        tool_id="fs.write_text",
        plugin_id=manifest.id,
        tool_group="fs_write",
        op="fs_write",
        handler=write_text,
        description="Write a text file (approval guarded; prefer outputs/)",
        default_target="outputs/hello.txt",
    ))
