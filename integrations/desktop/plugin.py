from __future__ import annotations
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import yaml

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.portable.paths import detect_base_dir, default_workspace_dir
from core.security.process_allowlist import validate_command, CommandNotAllowed

_ALLOWED_DOMAINS = {
    "chat.openai.com",
    "chatgpt.com",
    "gemini.google.com",
    "github.com",
    "perplexity.ai",
    "deepseek.com",
}

_ALLOWED_EXEC = {"python", "chrome", "code", "explorer"}
_DENY_EXEC = {"cmd", "powershell", "pwsh"}


def _load_config(base_dir: str) -> Dict[str, Any]:
    path = os.path.join(base_dir, "configs", "desktop.yaml")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}


def _write_report(base_dir: str, text: str) -> str:
    reports_dir = os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, "desktop_actions.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    return path


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https URLs are allowed")
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in _ALLOWED_DOMAINS:
        raise ValueError(f"Domain not allowed: {host}")


def _ensure_within_workspace(path: str, workspace: str) -> str:
    ap = os.path.abspath(path)
    ws = os.path.abspath(workspace)
    if not ap.startswith(ws + os.sep) and ap != ws:
        raise ValueError("Path must be within workspace")
    return ap


def _ensure_dir_exists(path: str) -> str:
    ap = os.path.abspath(path)
    if not os.path.isdir(ap):
        raise ValueError("Folder not found")
    return ap


def _resolve_executable(name: str, configured: str) -> str:
    if configured:
        ap = os.path.abspath(configured)
        base = os.path.basename(ap).lower()
        if base.endswith(".exe"):
            base = base[:-4]
        if base in _DENY_EXEC:
            raise ValueError("Executable is explicitly denied")
        if base not in _ALLOWED_EXEC:
            raise ValueError("Configured executable not allowlisted")
        if os.path.exists(ap):
            return ap
        raise ValueError("Configured executable not found")
    return name


def _run_exec(cmd: list[str]) -> None:
    try:
        validate_command(cmd, allowed_entries=["run_chat.py", "run_ui.py", "main.py", "app.py", "__main__.py"])
    except CommandNotAllowed as e:
        raise ValueError(str(e)) from e
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    base_dir = detect_base_dir()
    cfg = _load_config(base_dir)

    def open_vscode(path: str) -> Dict[str, Any]:
        target = _ensure_dir_exists(path)
        exe = _resolve_executable("code", str(cfg.get("vscode_path") or ""))
        _run_exec([exe, target])
        report = _write_report(base_dir, f"{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} open_vscode {target}")
        return {"status": "ok", "path": target, "report_path": report}

    def open_chrome(url: str) -> Dict[str, Any]:
        _validate_url(url)
        exe = _resolve_executable("chrome", str(cfg.get("chrome_path") or ""))
        _run_exec([exe, url])
        report = _write_report(base_dir, f"{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} open_chrome {url}")
        return {"status": "ok", "url": url, "report_path": report}

    def open_folder(path: str) -> Dict[str, Any]:
        workspace = default_workspace_dir(base_dir)
        target = _ensure_within_workspace(path, workspace)
        _run_exec(["explorer", target])
        report = _write_report(base_dir, f"{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} open_folder {target}")
        return {"status": "ok", "path": target, "report_path": report}

    registry.register_tool(ToolRegistration(
        tool_id="desktop.open_vscode",
        plugin_id=manifest.id,
        tool_group="process_exec",
        op="desktop_open_vscode",
        handler=open_vscode,
        description="Open VS Code in a folder (allowlisted)",
        default_target=None,
    ))

    registry.register_tool(ToolRegistration(
        tool_id="desktop.open_chrome",
        plugin_id=manifest.id,
        tool_group="process_exec",
        op="desktop_open_chrome",
        handler=open_chrome,
        description="Open Chrome to an allowlisted URL (https only)",
        default_target=None,
    ))

    registry.register_tool(ToolRegistration(
        tool_id="desktop.open_folder",
        plugin_id=manifest.id,
        tool_group="process_exec",
        op="desktop_open_folder",
        handler=open_folder,
        description="Open Explorer for a workspace folder (allowlisted)",
        default_target=None,
    ))

