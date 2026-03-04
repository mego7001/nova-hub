from __future__ import annotations

from pathlib import Path

from core.ipc import spawn


class _DummyProc:
    def __init__(self, pid: int = 43210) -> None:
        self.pid = pid

    def poll(self):
        return None

    def terminate(self) -> None:
        return None


def test_spawn_command_uses_main_py_core(tmp_path: Path, monkeypatch) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {"cmd": None}
    probe_count = {"value": 0}

    def _fake_health_ping(**_kwargs):
        probe_count["value"] += 1
        if probe_count["value"] == 1:
            raise RuntimeError("not running yet")
        return {"ok": True}

    def _fake_popen(cmd, **_kwargs):
        captured["cmd"] = list(cmd)
        return _DummyProc()

    monkeypatch.setattr(spawn, "health_ping", _fake_health_ping)
    monkeypatch.setattr(spawn.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(spawn.time, "sleep", lambda _seconds: None)
    monkeypatch.setenv("NH_TEST_MODE", "0")

    out = spawn.ensure_core_running(
        host="127.0.0.1",
        port=17999,
        token="spawn-command-test",
        project_root=str(project_root),
        workspace_root=str(workspace_root),
        startup_timeout_s=3.0,
        health_timeout_s=0.2,
    )

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert any(str(part).endswith("main.py") for part in cmd)
    assert "core" in cmd
    assert "run_core_service.py" not in " ".join(str(part) for part in cmd)
    assert out.port == 17999
