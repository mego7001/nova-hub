from __future__ import annotations

from pathlib import Path
import sys

from core.mcp.client import StdioJsonRpcClient


def test_mcp_patch_server_subprocess_plan_roundtrip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project_dir = workspace / "projects" / "demo" / "working"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")

    client = StdioJsonRpcClient(
        cmd=[sys.executable, "-m", "mcp_servers.patch_server"],
        env={"NH_WORKSPACE": str(workspace)},
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    try:
        client.start_server()
        client.initialize(timeout_sec=5.0)
        tools = client.list_tools(timeout_sec=5.0)
        assert tools == ["patch.apply", "patch.plan"]

        out = client.call_tool(
            "patch.plan",
            {"target_root": str(project_dir), "goal": "Harden gitignore", "write_reports": False},
            timeout_sec=10.0,
        )
        assert isinstance(out, dict)
        assert str(out.get("diff_path") or "").strip()
        diff_rel = str(out.get("diff_path"))
        assert (project_dir / diff_rel).exists()
    finally:
        client.shutdown()
