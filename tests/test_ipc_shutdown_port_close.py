from pathlib import Path
import os
import socket
import subprocess
import time

from core.ipc.client import IpcClient
from core.ipc.spawn import ensure_core_running


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False


def _terminate_pid(pid: int) -> None:
    if pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.kill(pid, 9)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass


def _wait_for_port_closed(port: int, timeout_s: float) -> bool:
    deadline = time.time() + max(0.1, float(timeout_s))
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.35)
            if sock.connect_ex(("127.0.0.1", int(port))) != 0:
                return True
        time.sleep(0.2)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex(("127.0.0.1", int(port))) != 0


def test_system_shutdown_closes_ipc_port(tmp_path: Path) -> None:
    prev_test_mode = os.environ.get("NH_TEST_MODE")
    os.environ["NH_TEST_MODE"] = "0"
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    events_port = _free_port()
    token = "ipc-shutdown-port-close"
    spawned_pid = 0
    try:
        spawned = ensure_core_running(
            host="127.0.0.1",
            port=port,
            events_port=events_port,
            token=token,
            project_root=str(project_root),
            workspace_root=str(workspace_root),
            startup_timeout_s=8.0,
            health_timeout_s=0.8,
        )
        spawned_pid = int(spawned.pid)
        client = IpcClient(host="127.0.0.1", port=port, token=token, timeout_s=3.0)
        out = client.call_ok(
            "system.shutdown",
            {
                "scope": "core_and_events",
                "timeout_sec": 10,
                "force": True,
            },
        )
        assert out.get("ok") is True
        assert out.get("phase") == "initiated"
        assert int(out.get("pid") or 0) > 0

        assert _wait_for_port_closed(port, timeout_s=18.0) is True
        assert _wait_for_port_closed(events_port, timeout_s=6.0) is True
    finally:
        if _pid_alive(spawned_pid):
            _terminate_pid(spawned_pid)
        if prev_test_mode is None:
            os.environ.pop("NH_TEST_MODE", None)
        else:
            os.environ["NH_TEST_MODE"] = prev_test_mode
