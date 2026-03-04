from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import json, os

@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    kind: str
    entrypoint: str
    tool_groups: List[str]
    config_schema: Dict[str, Any]

    @staticmethod
    def load(path: str) -> "PluginManifest":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Plugin manifest not found: {path}")
        raw = json.loads(open(path, "r", encoding="utf-8-sig").read())
        for k in ["id","name","version","kind","entrypoint"]:
            if k not in raw:
                raise ValueError(f"Manifest missing key: {k}")
        return PluginManifest(
            id=str(raw["id"]),
            name=str(raw["name"]),
            version=str(raw["version"]),
            kind=str(raw["kind"]),
            entrypoint=str(raw["entrypoint"]),
            tool_groups=[str(x) for x in (raw.get("tool_groups") or [])],
            config_schema=(raw.get("config_schema") or {"type":"object","properties":{},"required":[]}),
        )
