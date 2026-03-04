from pathlib import Path
import os
import socket
import subprocess

from core.ipc.health import health_ping
from core.ipc.spawn import ensure_core_running


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _terminate_pid(pid: int) -> None:
    if pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.kill(pid, 15)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass


def test_ensure_core_running_autospawns_service(tmp_path: Path) -> None:
    prev_test_mode = os.environ.get("NH_TEST_MODE")
    os.environ["NH_TEST_MODE"] = "0"
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    token = "ipc-autospawn-test-token"
    spawned_pid = 0

    try:
        spawned = ensure_core_running(
            host="127.0.0.1",
            port=port,
            token=token,
            project_root=str(project_root),
            workspace_root=str(workspace_root),
            startup_timeout_s=6.0,
            health_timeout_s=0.8,
        )
        spawned_pid = int(spawned.pid)
        assert spawned.pid > 0
        assert spawned.port == port
        assert Path(spawned.pidfile).exists()

        health = health_ping(host="127.0.0.1", port=port, token=token, timeout_s=1.0)
        assert health.get("ok") is True
        assert int(health.get("tools_loaded") or 0) >= 0

        reused = ensure_core_running(
            host="127.0.0.1",
            port=port,
            token=token,
            project_root=str(project_root),
            workspace_root=str(workspace_root),
            startup_timeout_s=3.0,
            health_timeout_s=0.8,
        )
        assert reused.started is False
    finally:
        _terminate_pid(spawned_pid)
        if prev_test_mode is None:
            os.environ.pop("NH_TEST_MODE", None)
        else:
            os.environ["NH_TEST_MODE"] = prev_test_mode
