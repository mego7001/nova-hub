from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.portable.paths import default_workspace_dir, detect_base_dir, ensure_workspace_dirs

from .health import health_ping
from .protocol import (
    DEFAULT_HOST,
    parse_message_line,
    resolve_ipc_events_port,
    resolve_ipc_port,
    resolve_ipc_token,
    serialize_message,
)


@dataclass
class SpawnResult:
    started: bool
    pid: int
    host: str
    port: int
    pidfile: str
    logfile: str
    events_port: int = 0


def _is_test_mode() -> bool:
    raw = os.getenv("NH_TEST_MODE")
    if raw is not None:
        norm = str(raw).strip().lower()
        if norm in {"0", "false", "no", "off"}:
            return False
        return bool(norm)
    return "PYTEST_CURRENT_TEST" in os.environ


def _tiny_timeout_s(value: float) -> float:
    try:
        val = float(value)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        val = 0.2
    if val <= 0:
        val = 0.2
    return min(0.2, max(0.05, val))


def _resolve_roots(project_root: str | None = None, workspace_root: str | None = None) -> tuple[str, str]:
    base = os.path.abspath(project_root or detect_base_dir())
    ensure_workspace_dirs(base)
    ws = os.path.abspath(workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base))
    os.environ.setdefault("NH_BASE_DIR", base)
    os.environ.setdefault("NH_WORKSPACE", ws)
    return base, ws


def _runtime_dir(workspace_root: str) -> str:
    path = os.path.join(workspace_root, "runtime")
    os.makedirs(path, exist_ok=True)
    return path


def pidfile_path(*, workspace_root: str, port: int) -> str:
    return os.path.join(_runtime_dir(workspace_root), f"core_service_{int(port)}.pid")


def logfile_path(*, workspace_root: str, port: int) -> str:
    return os.path.join(_runtime_dir(workspace_root), f"core_service_{int(port)}.log")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False


def _read_pidfile(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_pidfile(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _probe_only_with_tiny_timeout(
    *,
    host: str,
    port: int,
    token: str,
    health_timeout_s: float,
    events_port: int | None = None,
) -> None:
    tiny = _tiny_timeout_s(health_timeout_s)
    health_ping(host=host, port=port, token=token, timeout_s=tiny)
    if events_port is not None:
        _events_subscribe_ping(
            host=host,
            port=int(events_port),
            token=token,
            timeout_s=tiny,
        )


def ensure_core_running(
    *,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    events_port: int | None = None,
    token: str | None = None,
    project_root: str | None = None,
    workspace_root: str | None = None,
    startup_timeout_s: float = 3.0,
    health_timeout_s: float = 0.8,
) -> SpawnResult:
    resolved_port = int(resolve_ipc_port(port))
    resolved_events_port = int(resolve_ipc_events_port(events_port, rpc_port=resolved_port))
    resolved_token = resolve_ipc_token() if token is None else str(token or "")
    root, ws = _resolve_roots(project_root=project_root, workspace_root=workspace_root)
    ppath = pidfile_path(workspace_root=ws, port=resolved_port)
    lpath = logfile_path(workspace_root=ws, port=resolved_port)

    if _is_test_mode():
        try:
            _probe_only_with_tiny_timeout(
                host=host,
                port=resolved_port,
                token=resolved_token,
                health_timeout_s=health_timeout_s,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            raise RuntimeError(f"IPC probe failed in test mode on {host}:{resolved_port}: {exc}") from exc
        info = _read_pidfile(ppath)
        return SpawnResult(
            started=False,
            pid=int(info.get("pid") or 0),
            host=host,
            port=resolved_port,
            pidfile=ppath,
            logfile=lpath,
            events_port=resolved_events_port,
        )

    try:
        health_ping(host=host, port=resolved_port, token=resolved_token, timeout_s=health_timeout_s)
        info = _read_pidfile(ppath)
        return SpawnResult(
            started=False,
            pid=int(info.get("pid") or 0),
            host=host,
            port=resolved_port,
            pidfile=ppath,
            logfile=lpath,
            events_port=resolved_events_port,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass

    cmd = [
        sys.executable,
        os.path.join(root, "main.py"),
        "core",
        "--host",
        host,
        "--port",
        str(resolved_port),
        "--events-port",
        str(resolved_events_port),
    ]
    env = os.environ.copy()
    env["NH_BASE_DIR"] = root
    env["NH_WORKSPACE"] = ws
    env["NH_IPC_PORT"] = str(resolved_port)
    env["NH_IPC_EVENTS_PORT"] = str(resolved_events_port)
    if resolved_token:
        env["NH_IPC_TOKEN"] = resolved_token
    os.makedirs(os.path.dirname(lpath), exist_ok=True)
    with open(lpath, "ab") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=root,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    _write_pidfile(
        ppath,
        {
            "pid": int(proc.pid),
            "host": host,
            "port": resolved_port,
            "started_at": time.time(),
        },
    )

    deadline = time.time() + max(0.2, float(startup_timeout_s))
    while time.time() < deadline:
        try:
            health_ping(host=host, port=resolved_port, token=resolved_token, timeout_s=health_timeout_s)
            return SpawnResult(
                started=True,
                pid=int(proc.pid),
                host=host,
                port=resolved_port,
                pidfile=ppath,
                logfile=lpath,
                events_port=resolved_events_port,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            if proc.poll() is not None:
                break
            time.sleep(0.15)
    try:
        proc.terminate()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    raise RuntimeError(f"Core service failed to start on {host}:{resolved_port}")


def _events_subscribe_ping(
    *,
    host: str,
    port: int,
    token: str,
    timeout_s: float,
    session_id: str = "",
    project_id: str = "",
) -> None:
    with socket.create_connection((host, int(port)), timeout=timeout_s) as sock:
        sock.settimeout(timeout_s)
        with sock.makefile("rwb", buffering=0) as fp:
            hello: Dict[str, Any] = {"type": "hello"}
            if token:
                hello["token"] = token
            fp.write(serialize_message(hello))
            hello_ack = parse_message_line(fp.readline(2 * 1024 * 1024 + 1))
            if str(hello_ack.get("type") or "") != "hello" or not bool(hello_ack.get("ok")):
                raise RuntimeError("events hello failed")

            subscribe = {
                "type": "subscribe",
                "session_id": str(session_id or ""),
                "project_id": str(project_id or ""),
            }
            fp.write(serialize_message(subscribe))
            ack = parse_message_line(fp.readline(2 * 1024 * 1024 + 1))
            if str(ack.get("type") or "") != "subscribe" or not bool(ack.get("ok")):
                raise RuntimeError("events subscribe failed")


def ensure_core_running_with_events(
    *,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    events_port: int | None = None,
    token: str | None = None,
    project_root: str | None = None,
    workspace_root: str | None = None,
    startup_timeout_s: float = 3.0,
    health_timeout_s: float = 0.8,
) -> SpawnResult:
    resolved_port = int(resolve_ipc_port(port))
    resolved_events_port = int(resolve_ipc_events_port(events_port, rpc_port=resolved_port))
    resolved_token = resolve_ipc_token() if token is None else str(token or "")
    _, ws = _resolve_roots(project_root=project_root, workspace_root=workspace_root)
    ppath = pidfile_path(workspace_root=ws, port=resolved_port)
    lpath = logfile_path(workspace_root=ws, port=resolved_port)

    if _is_test_mode():
        try:
            _probe_only_with_tiny_timeout(
                host=host,
                port=resolved_port,
                token=resolved_token,
                health_timeout_s=health_timeout_s,
                events_port=resolved_events_port,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            raise RuntimeError(
                f"IPC probe failed in test mode on {host}:{resolved_port}/{resolved_events_port}: {exc}"
            ) from exc
        info = _read_pidfile(ppath)
        return SpawnResult(
            started=False,
            pid=int(info.get("pid") or 0),
            host=host,
            port=resolved_port,
            pidfile=ppath,
            logfile=lpath,
            events_port=resolved_events_port,
        )

    try:
        health_ping(host=host, port=resolved_port, token=resolved_token, timeout_s=health_timeout_s)
        _events_subscribe_ping(
            host=host,
            port=resolved_events_port,
            token=resolved_token,
            timeout_s=health_timeout_s,
        )
        return SpawnResult(
            started=False,
            pid=int(_read_pidfile(ppath).get("pid") or 0),
            host=host,
            port=resolved_port,
            pidfile=ppath,
            logfile=lpath,
            events_port=resolved_events_port,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass

    spawned = ensure_core_running(
        host=host,
        port=resolved_port,
        events_port=resolved_events_port,
        token=resolved_token,
        project_root=project_root,
        workspace_root=workspace_root,
        startup_timeout_s=startup_timeout_s,
        health_timeout_s=health_timeout_s,
    )

    deadline = time.time() + max(0.3, float(startup_timeout_s))
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _events_subscribe_ping(
                host=host,
                port=resolved_events_port,
                token=resolved_token,
                timeout_s=health_timeout_s,
            )
            return SpawnResult(
                started=spawned.started,
                pid=spawned.pid,
                host=host,
                port=resolved_port,
                pidfile=spawned.pidfile,
                logfile=spawned.logfile,
                events_port=resolved_events_port,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            last_error = exc
            time.sleep(0.15)
    raise RuntimeError(f"Core service failed to expose events channel on {host}:{resolved_events_port}: {last_error}")


def stop_core_service(
    *,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    token: str | None = None,
    workspace_root: str | None = None,
    wait_timeout_s: float = 2.0,
) -> bool:
    resolved_port = int(resolve_ipc_port(port))
    resolved_token = resolve_ipc_token() if token is None else str(token or "")
    _, ws = _resolve_roots(workspace_root=workspace_root)
    ppath = pidfile_path(workspace_root=ws, port=resolved_port)

    # Soft request first if reachable.
    try:
        from .client import IpcClient

        IpcClient(host=host, port=resolved_port, token=resolved_token, timeout_s=0.5).call("service.stop", {})
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass

    info = _read_pidfile(ppath)
    pid = int(info.get("pid") or 0)
    deadline = time.time() + max(0.2, float(wait_timeout_s))
    while pid > 0 and time.time() < deadline and _pid_alive(pid):
        time.sleep(0.05)

    if pid > 0 and _pid_alive(pid):
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
            deadline = time.time() + max(0.2, float(wait_timeout_s))
            while time.time() < deadline and _pid_alive(pid):
                time.sleep(0.05)
            if _pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass

    try:
        os.remove(ppath)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass

    try:
        health_ping(host=host, port=resolved_port, token=resolved_token, timeout_s=0.3)
        return False
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return True
