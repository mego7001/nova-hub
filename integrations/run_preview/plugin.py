from __future__ import annotations
import os
import subprocess
import uuid
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.projects.manager import ProjectManager
from core.run.smart_runner import detect_run_profiles
from core.security.process_allowlist import validate_command, CommandNotAllowed
from core.portable.paths import detect_base_dir, default_workspace_dir


_PROCESSES: Dict[str, Dict[str, Any]] = {}


def _workspace_root() -> str:
    base = detect_base_dir()
    return os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)


def _make_log_path(project_id: str) -> str:
    ws = _workspace_root()
    run_logs = os.path.join(ws, "projects", project_id, "run_logs")
    os.makedirs(run_logs, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(run_logs, f"preview_run_{project_id}_{stamp}.log")


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    manager = ProjectManager()

    def run_preview(project_id: str, profile_id: str) -> Dict[str, Any]:
        if not project_id:
            raise ValueError("project_id is required")
        if not profile_id:
            raise ValueError("profile_id is required")

        paths = manager.get_project_paths(project_id)
        profiles = detect_run_profiles(paths.working)
        selected = None
        for p in profiles:
            if p.get("id") == profile_id:
                selected = p
                break
        if not selected:
            raise ValueError("Profile not found")

        preview_root = manager.build_preview(project_id)
        entry = os.path.join(preview_root, selected["entry"])
        if not os.path.abspath(entry).startswith(os.path.abspath(preview_root) + os.sep):
            raise ValueError("Entrypoint outside preview root")
        if not os.path.isfile(entry):
            raise FileNotFoundError("Preview entry not found")

        cmd = [sys.executable, entry]
        try:
            validate_command(cmd, allowed_entries=[os.path.basename(entry)])
        except CommandNotAllowed as e:
            raise ValueError(str(e)) from e

        log_path = _make_log_path(project_id)
        log_handle = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=preview_root, stdout=log_handle, stderr=subprocess.STDOUT)

        run_id = uuid.uuid4().hex[:10]
        _PROCESSES[run_id] = {
            "process": proc,
            "log_path": log_path,
            "log_handle": log_handle,
            "preview_root": preview_root,
            "entry": entry,
        }

        return {
            "status": "started",
            "run_id": run_id,
            "pid": proc.pid,
            "log_path": log_path,
            "preview_root": preview_root,
            "entry": entry,
        }

    def stop_preview(run_id: str) -> Dict[str, Any]:
        if not run_id:
            raise ValueError("run_id is required")
        info = _PROCESSES.get(run_id)
        if not info:
            return {"status": "not_found", "run_id": run_id}
        proc = info.get("process")
        log_handle = info.get("log_handle")
        status = "stopped"
        exit_code = None
        if proc:
            exit_code = proc.poll()
            if exit_code is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    proc.kill()
                exit_code = proc.poll()
            elif exit_code != 0:
                status = "crashed"
        if log_handle:
            try:
                log_handle.close()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        _PROCESSES.pop(run_id, None)
        summary = ""
        if status == "crashed" and info.get("log_path"):
            tail = _read_log_tail(info.get("log_path"))
            summary = "Preview crashed. Check log tail:\n" + tail + "\nNext steps: review entrypoint, missing deps, or config."
        _PROCESSES.pop(run_id, None)
        return {"status": status, "run_id": run_id, "exit_code": exit_code, "summary": summary}

    registry.register_tool(
        ToolRegistration(
            tool_id="run.preview",
            plugin_id=manifest.id,
            tool_group="process_exec",
            op="run_preview",
            handler=run_preview,
            description="Run a preview copy of the project (approval required)",
            default_target=None,
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="run.stop",
            plugin_id=manifest.id,
            tool_group="process_exec",
            op="run_stop",
            handler=stop_preview,
            description="Stop a running preview process",
            default_target=None,
        )
    )


def _read_log_tail(path: str, max_lines: int = 20) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:]).strip()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return ""

