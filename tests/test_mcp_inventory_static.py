from __future__ import annotations

from pathlib import Path

from scripts.generate_mcp_inventory import (
    collect_inventory,
    parse_plugin_file,
    render_inventory_markdown,
)


def test_collect_inventory_static_is_deterministic() -> None:
    root = Path(__file__).resolve().parents[1]
    rows_a = collect_inventory(root)
    rows_b = collect_inventory(root)
    assert rows_a == rows_b
    assert rows_a
    assert all(not str(row.plugin_file).startswith(str(root)) for row in rows_a)
    assert all("\\" not in str(row.plugin_file) for row in rows_a)
    assert [row.tool_id for row in rows_a] == sorted(row.tool_id for row in rows_a)


def test_collect_inventory_contains_patch_tools() -> None:
    root = Path(__file__).resolve().parents[1]
    rows = collect_inventory(root)
    tool_ids = {row.tool_id for row in rows}
    assert "patch.plan" in tool_ids
    assert "patch.apply" in tool_ids


def test_render_inventory_markdown_has_no_timestamps() -> None:
    root = Path(__file__).resolve().parents[1]
    rows = collect_inventory(root)
    text = render_inventory_markdown(rows, project_root=root)
    assert "generated_at" not in text
    assert "Static inventory generated" in text
    assert "## Tool Registry (Static)" in text


def test_parser_supports_multiple_register_patterns_and_unresolved_handler(tmp_path: Path) -> None:
    root = tmp_path
    plugin_dir = root / "integrations" / "sample_plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin_path = plugin_dir / "plugin.py"
    plugin_path.write_text(
        "\n".join(
            [
                "from core.plugin_engine.registry import ToolRegistration",
                "def init_plugin(config, registry, manifest):",
                "    def handler_one(**kwargs):",
                "        return {'ok': True}",
                "    registry.register_tool(ToolRegistration('tool.one', manifest.id, 'fs_read', 'op_one', handler_one, 'desc', None))",
                "    registry.register_tool(tool_id='tool.two', plugin_id='sample_plugin', tool_group='fs_write', op='op_two', handler=handler_one)",
                "    registry.register_tool({'tool_id': 'tool.three', 'plugin_id': 'sample_plugin', 'tool_group': 'fs_write', 'op': 'op_three', 'handler': some_factory()})",
            ]
        ),
        encoding="utf-8",
    )

    rows = parse_plugin_file(plugin_path, project_root=root)
    by_id = {row.tool_id: row for row in rows}
    assert "tool.one" in by_id
    assert "tool.two" in by_id
    assert "tool.three" in by_id
    assert by_id["tool.one"].handler == "handler_one"
    assert by_id["tool.two"].handler == "handler_one"
    assert by_id["tool.three"].handler == "unresolved"

