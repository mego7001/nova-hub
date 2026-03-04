from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List


try:
    import yaml
except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    cmd: List[str]
    tools: List[str]
    timeout_sec: int
    env: Dict[str, str]


@dataclass(frozen=True)
class McpConfig:
    enabled: bool
    servers: Dict[str, McpServerConfig]
    tool_to_server: Dict[str, str]
    source_path: str


def _project_root() -> Path:
    env_root = str(os.environ.get("NH_BASE_DIR") or "").strip()
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def _default_raw() -> Dict[str, Any]:
    return {
        "enabled": False,
        "servers": {
            "patch": {
                "cmd": ["python", "-m", "mcp_servers.patch_server"],
                "tools": ["patch.plan", "patch.apply"],
                "timeout_sec": 90,
                "env": {},
            }
        },
    }


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in {"1", "true", "yes", "on"}:
            return True
        if norm in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _to_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        parsed = default
    return max(minimum, parsed)


def _clean_cmd(raw_cmd: Any, *, default_cmd: List[str]) -> List[str]:
    out: List[str] = []
    if isinstance(raw_cmd, list):
        for item in raw_cmd:
            text = str(item or "").strip()
            if text:
                out.append(text)
    if out:
        return out
    return list(default_cmd)


def _clean_tools(raw_tools: Any, *, default_tools: List[str]) -> List[str]:
    out: List[str] = []
    if isinstance(raw_tools, list):
        for item in raw_tools:
            tool_id = str(item or "").strip()
            if tool_id and tool_id not in out:
                out.append(tool_id)
    if out:
        return out
    return list(default_tools)


def _clean_env(raw_env: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not isinstance(raw_env, dict):
        return out
    for key in sorted(raw_env.keys()):
        k = str(key or "").strip()
        if not k:
            continue
        out[k] = str(raw_env.get(key) or "")
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_mcp_servers_config() -> McpConfig:
    default_raw = _default_raw()
    cfg_path_raw = str(os.environ.get("NH_MCP_CONFIG") or "").strip()
    if cfg_path_raw:
        cfg_path = Path(cfg_path_raw).resolve()
    else:
        cfg_path = (_project_root() / "configs" / "mcp_servers.yaml").resolve()

    loaded = _load_yaml(cfg_path)
    enabled = _to_bool(loaded.get("enabled"), bool(default_raw.get("enabled", False)))

    default_servers_raw = default_raw.get("servers") or {}
    loaded_servers_raw = loaded.get("servers")
    if not isinstance(loaded_servers_raw, dict):
        loaded_servers_raw = {}

    merged_names = sorted({str(k) for k in default_servers_raw.keys()} | {str(k) for k in loaded_servers_raw.keys()})
    servers: Dict[str, McpServerConfig] = {}

    for name in merged_names:
        base_cfg = default_servers_raw.get(name) if isinstance(default_servers_raw, dict) else None
        user_cfg = loaded_servers_raw.get(name) if isinstance(loaded_servers_raw, dict) else None
        if not isinstance(base_cfg, dict):
            base_cfg = {}
        if not isinstance(user_cfg, dict):
            user_cfg = {}
        merged = dict(base_cfg)
        merged.update(user_cfg)

        default_cmd = [str(x) for x in (base_cfg.get("cmd") or []) if str(x or "").strip()]
        default_tools = [str(x) for x in (base_cfg.get("tools") or []) if str(x or "").strip()]
        timeout_default = _to_int(base_cfg.get("timeout_sec"), 90, minimum=1)

        servers[name] = McpServerConfig(
            name=name,
            cmd=_clean_cmd(merged.get("cmd"), default_cmd=default_cmd or ["python", "-m", f"mcp_servers.{name}_server"]),
            tools=_clean_tools(merged.get("tools"), default_tools=default_tools),
            timeout_sec=_to_int(merged.get("timeout_sec"), timeout_default, minimum=1),
            env=_clean_env(merged.get("env")),
        )

    tool_to_server: Dict[str, str] = {}
    for server_name in sorted(servers.keys()):
        server = servers[server_name]
        for tool_id in sorted(server.tools):
            if tool_id not in tool_to_server:
                tool_to_server[tool_id] = server_name

    return McpConfig(
        enabled=enabled,
        servers=servers,
        tool_to_server=tool_to_server,
        source_path=str(cfg_path),
    )
