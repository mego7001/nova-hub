from pathlib import Path
import json

from core.plugin_engine.registry import PluginRegistration, PluginRegistry, ToolRegistration
from core.ux.tools_index import build_tools_index_payload, write_tools_index_report


def _registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register_plugin(
        PluginRegistration(
            plugin_id="test.plugin",
            kind="python",
            name="Test Plugin",
            version="1.0.0",
            entrypoint="tests.stub",
            tool_groups=["fs_read"],
            config={},
        )
    )
    reg.register_tool(
        ToolRegistration(
            tool_id="conversation.chat",
            plugin_id="test.plugin",
            tool_group="fs_read",
            op="conversation_chat",
            handler=lambda **_: {"ok": True},
            description="Chat boundary",
        )
    )
    return reg


def test_tools_index_payload_contains_mode_tags():
    payload = build_tools_index_payload(_registry())
    assert int(payload.get("tools_total") or 0) == 1
    rows = payload.get("tools") or []
    assert isinstance(rows, list)
    assert rows
    row = rows[0]
    assert row.get("tool_id") == "conversation.chat"
    assert "mode_tags" in row
    assert "curated_modes" in row


def test_tools_index_writer_creates_json(tmp_path: Path):
    out = tmp_path / "tools_index.json"
    written = write_tools_index_report(_registry(), str(out))
    assert Path(written).exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload.get("tools_total") == 1
