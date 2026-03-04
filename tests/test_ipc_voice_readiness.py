from __future__ import annotations

import os
from pathlib import Path

from core.ipc.service import NovaCoreService


def test_ipc_voice_readiness_op_returns_shape(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    prev_cwd = os.getcwd()
    prev_base = os.environ.get("NH_BASE_DIR")
    prev_workspace = os.environ.get("NH_WORKSPACE")
    try:
        service = NovaCoreService(project_root=str(project_root), workspace_root=str(workspace_root))
        result = service.dispatch("voice.readiness", {"sample_rate": 16000}, {})
        assert isinstance(result, dict)
        assert "status" in result
        assert "dependencies" in result
        assert "devices" in result
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
