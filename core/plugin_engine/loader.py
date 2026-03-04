from __future__ import annotations
import importlib, os
from dataclasses import dataclass
from typing import Any, Dict, List
import yaml

from .manifest import PluginManifest
from .schema import validate_json_schema
from .registry import PluginRegistry, PluginRegistration

@dataclass(frozen=True)
class LoadedPlugin:
    manifest: PluginManifest
    config: Dict[str, Any]

class PluginLoader:
    def __init__(self, project_root: str):
        self.project_root = project_root

    def load_enabled(self, enabled_yaml_path: str, registry: PluginRegistry) -> List[LoadedPlugin]:
        raw = yaml.safe_load(open(enabled_yaml_path, "r", encoding="utf-8").read()) or {}
        enabled = raw.get("enabled") or []
        configs = raw.get("configs") or {}
        loaded: List[LoadedPlugin] = []

        for pid in enabled:
            pid = str(pid)
            mp = os.path.join(self.project_root, "integrations", pid, "novahub.plugin.json")
            manifest = PluginManifest.load(mp)

            cfg = configs.get(pid) or {}
            errs = validate_json_schema(cfg, manifest.config_schema, path=f"$({pid})")
            if errs:
                msg = "\n".join([f"{e.path}: {e.message}" for e in errs])
                raise ValueError(f"Config schema errors for '{pid}':\n{msg}")

            mod = importlib.import_module(manifest.entrypoint)
            init_fn = getattr(mod, "init_plugin", None)

            registry.register_plugin(PluginRegistration(
                plugin_id=manifest.id,
                kind=manifest.kind,
                name=manifest.name,
                version=manifest.version,
                entrypoint=manifest.entrypoint,
                tool_groups=manifest.tool_groups,
                config=cfg,
            ))

            if callable(init_fn):
                init_fn(cfg, registry, manifest)

            loaded.append(LoadedPlugin(manifest, cfg))
        return loaded
