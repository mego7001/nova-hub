import os
from pathlib import Path

import pytest

from core.ipc.service import NovaCoreService


def test_system_shutdown_dispatch_initiates_once(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")

    service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
    service.set_runtime_ports(ipc_port=17840, events_port=17841)
    captured: list[dict] = []
    service.set_shutdown_handler(lambda payload: captured.append(dict(payload)))
    try:
        out = service.dispatch(
            "system.shutdown",
            {
                "scope": "core_and_events",
                "timeout_sec": 12,
                "force": True,
            },
            {},
        )
        assert out.get("ok") is True
        assert out.get("phase") == "initiated"
        assert int(out.get("pid") or 0) > 0
        ports = out.get("ports")
        assert isinstance(ports, dict)
        assert int(ports.get("ipc") or 0) == 17840
        assert int(ports.get("events") or 0) == 17841

        assert len(captured) == 1
        assert captured[0]["scope"] == "core_and_events"
        assert int(captured[0]["timeout_sec"]) == 12
        assert captured[0]["force"] is True

        out_second = service.dispatch("system.shutdown", {"scope": "core_only", "timeout_sec": 5, "force": False}, {})
        assert out_second.get("ok") is True
        assert len(captured) == 1
    finally:
        os.chdir(prev_cwd)
        if prev_base is None:
            os.environ.pop("NH_BASE_DIR", None)
        else:
            os.environ["NH_BASE_DIR"] = prev_base
        if prev_workspace is None:
            os.environ.pop("NH_WORKSPACE", None)
        else:
            os.environ["NH_WORKSPACE"] = prev_workspace


def test_system_shutdown_rejects_invalid_scope(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")

    service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
    service.set_shutdown_handler(lambda _payload: None)
    try:
        with pytest.raises(ValueError):
            service.dispatch("system.shutdown", {"scope": "invalid"}, {})
    finally:
        os.chdir(prev_cwd)
        if prev_base is None:
            os.environ.pop("NH_BASE_DIR", None)
        else:
            os.environ["NH_BASE_DIR"] = prev_base
        if prev_workspace is None:
            os.environ.pop("NH_WORKSPACE", None)
        else:
            os.environ["NH_WORKSPACE"] = prev_workspace
