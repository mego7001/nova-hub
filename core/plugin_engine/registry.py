from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

@dataclass
class PluginRegistration:
    plugin_id: str
    kind: str
    name: str
    version: str
    entrypoint: str
    tool_groups: List[str]
    config: Dict[str, Any]

@dataclass
class ToolRegistration:
    tool_id: str
    plugin_id: str
    tool_group: str
    op: str
    handler: Callable[..., Any]
    description: str = ""
    default_target: Optional[str] = None

@dataclass
class PluginRegistry:
    plugins: Dict[str, PluginRegistration] = field(default_factory=dict)
    tools: Dict[str, ToolRegistration] = field(default_factory=dict)

    def register_plugin(self, reg: PluginRegistration) -> None:
        if reg.plugin_id in self.plugins:
            raise ValueError(f"Plugin already registered: {reg.plugin_id}")
        self.plugins[reg.plugin_id] = reg

    def register_tool(self, tool: ToolRegistration) -> None:
        if tool.tool_id in self.tools:
            raise ValueError(f"Tool already registered: {tool.tool_id}")
        if tool.plugin_id not in self.plugins:
            raise ValueError(f"Unknown plugin: {tool.plugin_id}")
        self.tools[tool.tool_id] = tool

    def list_plugins(self) -> List[PluginRegistration]:
        return list(self.plugins.values())

    def list_tools(self) -> List[ToolRegistration]:
        return list(self.tools.values())
