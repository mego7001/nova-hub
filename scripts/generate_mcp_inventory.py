from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


@dataclass(frozen=True)
class ToolInventoryRow:
    tool_id: str
    tool_group: str
    plugin_id: str
    op: str
    handler: str
    description: str
    default_target: str
    plugin_file: str
    line: int


def _repo_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _text_or_none(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value.strip()
        return text if text else None
    return None


def _name_or_attr(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        try:
            return ast.unparse(node)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return None
    return None


def _is_register_tool_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return str(func.attr or "") == "register_tool"
    if isinstance(func, ast.Name):
        return str(func.id or "") == "register_tool"
    return False


def _dict_lookup(dict_node: ast.Dict, key: str) -> Optional[ast.AST]:
    for k, v in zip(dict_node.keys, dict_node.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


def _safe_text(value: Optional[str], *, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _build_row(
    *,
    tool_id: Optional[str],
    tool_group: Optional[str],
    plugin_id: Optional[str],
    op: Optional[str],
    handler: Optional[str],
    description: Optional[str],
    default_target: Optional[str],
    plugin_file: str,
    line: int,
) -> ToolInventoryRow:
    return ToolInventoryRow(
        tool_id=_safe_text(tool_id, default="unresolved"),
        tool_group=_safe_text(tool_group, default="unresolved"),
        plugin_id=_safe_text(plugin_id, default="unresolved"),
        op=_safe_text(op, default="unresolved"),
        handler=_safe_text(handler, default="unresolved"),
        description=_safe_text(description, default=""),
        default_target=_safe_text(default_target, default=""),
        plugin_file=_safe_text(plugin_file, default=""),
        line=max(0, int(line or 0)),
    )


def _parse_toolregistration_call(node: ast.Call, *, plugin_file: str, line: int) -> ToolInventoryRow:
    positional = list(node.args)
    by_key: Dict[str, ast.AST] = {str(k.arg): k.value for k in node.keywords if k.arg}

    tool_id = _text_or_none(positional[0]) if len(positional) > 0 else _text_or_none(by_key.get("tool_id"))
    plugin_id = _text_or_none(positional[1]) if len(positional) > 1 else _text_or_none(by_key.get("plugin_id"))
    tool_group = _text_or_none(positional[2]) if len(positional) > 2 else _text_or_none(by_key.get("tool_group"))
    op = _text_or_none(positional[3]) if len(positional) > 3 else _text_or_none(by_key.get("op"))
    handler = _name_or_attr(positional[4]) if len(positional) > 4 else _name_or_attr(by_key.get("handler"))
    description = _text_or_none(positional[5]) if len(positional) > 5 else _text_or_none(by_key.get("description"))
    default_target = _text_or_none(positional[6]) if len(positional) > 6 else _text_or_none(by_key.get("default_target"))

    return _build_row(
        tool_id=tool_id,
        tool_group=tool_group,
        plugin_id=plugin_id,
        op=op,
        handler=handler,
        description=description,
        default_target=default_target,
        plugin_file=plugin_file,
        line=line,
    )


def _parse_register_tool_kwargs_call(node: ast.Call, *, plugin_file: str, line: int) -> ToolInventoryRow:
    by_key: Dict[str, ast.AST] = {str(k.arg): k.value for k in node.keywords if k.arg}
    return _build_row(
        tool_id=_text_or_none(by_key.get("tool_id")),
        tool_group=_text_or_none(by_key.get("tool_group")),
        plugin_id=_text_or_none(by_key.get("plugin_id")),
        op=_text_or_none(by_key.get("op")),
        handler=_name_or_attr(by_key.get("handler")),
        description=_text_or_none(by_key.get("description")),
        default_target=_text_or_none(by_key.get("default_target")),
        plugin_file=plugin_file,
        line=line,
    )


def _parse_register_tool_dict_call(dict_node: ast.Dict, *, plugin_file: str, line: int) -> ToolInventoryRow:
    return _build_row(
        tool_id=_text_or_none(_dict_lookup(dict_node, "tool_id")),
        tool_group=_text_or_none(_dict_lookup(dict_node, "tool_group")),
        plugin_id=_text_or_none(_dict_lookup(dict_node, "plugin_id")),
        op=_text_or_none(_dict_lookup(dict_node, "op")),
        handler=_name_or_attr(_dict_lookup(dict_node, "handler")),
        description=_text_or_none(_dict_lookup(dict_node, "description")),
        default_target=_text_or_none(_dict_lookup(dict_node, "default_target")),
        plugin_file=plugin_file,
        line=line,
    )


def _parse_register_tool_call(node: ast.Call, *, plugin_file: str, fallback_plugin_id: str) -> ToolInventoryRow:
    line = int(getattr(node, "lineno", 0) or 0)

    if node.args:
        first = node.args[0]
        if isinstance(first, ast.Call):
            is_tool_reg_ctor = isinstance(first.func, ast.Name) and str(first.func.id or "") == "ToolRegistration"
            if is_tool_reg_ctor:
                row = _parse_toolregistration_call(first, plugin_file=plugin_file, line=line)
            else:
                row = _build_row(
                    tool_id=None,
                    tool_group=None,
                    plugin_id=None,
                    op=None,
                    handler=None,
                    description=None,
                    default_target=None,
                    plugin_file=plugin_file,
                    line=line,
                )
        elif isinstance(first, ast.Dict):
            row = _parse_register_tool_dict_call(first, plugin_file=plugin_file, line=line)
        else:
            row = _build_row(
                tool_id=None,
                tool_group=None,
                plugin_id=None,
                op=None,
                handler=None,
                description=None,
                default_target=None,
                plugin_file=plugin_file,
                line=line,
            )
    elif node.keywords:
        row = _parse_register_tool_kwargs_call(node, plugin_file=plugin_file, line=line)
    else:
        row = _build_row(
            tool_id=None,
            tool_group=None,
            plugin_id=None,
            op=None,
            handler=None,
            description=None,
            default_target=None,
            plugin_file=plugin_file,
            line=line,
        )

    if row.plugin_id == "unresolved":
        row = ToolInventoryRow(
            tool_id=row.tool_id,
            tool_group=row.tool_group,
            plugin_id=fallback_plugin_id,
            op=row.op,
            handler=row.handler,
            description=row.description,
            default_target=row.default_target,
            plugin_file=row.plugin_file,
            line=row.line,
        )
    return row


def _load_enabled_plugins(config_path: Path) -> List[str]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    enabled = raw.get("enabled")
    if not isinstance(enabled, list):
        return []
    out: List[str] = []
    for item in enabled:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def parse_plugin_file(plugin_path: Path, *, project_root: Path) -> List[ToolInventoryRow]:
    plugin_id = plugin_path.parent.name
    plugin_file = _repo_rel(plugin_path, project_root)
    try:
        tree = ast.parse(plugin_path.read_text(encoding="utf-8"), filename=str(plugin_path))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, SyntaxError):
        return []

    rows: List[ToolInventoryRow] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_register_tool_call(node):
            continue
        rows.append(_parse_register_tool_call(node, plugin_file=plugin_file, fallback_plugin_id=plugin_id))
    return rows


def collect_inventory(project_root: Path) -> List[ToolInventoryRow]:
    root = project_root.resolve()
    config_path = root / "configs" / "plugins_enabled.yaml"
    enabled = _load_enabled_plugins(config_path) if config_path.exists() else []
    enabled_set = set(enabled)

    rows: List[ToolInventoryRow] = []
    integrations_root = root / "integrations"
    for plugin_path in sorted(integrations_root.glob("*/plugin.py"), key=lambda p: _repo_rel(p, root)):
        plugin_id = plugin_path.parent.name
        if enabled_set and plugin_id not in enabled_set:
            continue
        rows.extend(parse_plugin_file(plugin_path, project_root=root))

    rows.sort(
        key=lambda row: (
            str(row.tool_id),
            str(row.plugin_id),
            str(row.op),
            str(row.plugin_file),
            int(row.line),
        )
    )
    return rows


def _bucket_lines(rows: Iterable[ToolInventoryRow], prefix: str) -> List[str]:
    out: List[str] = []
    for row in rows:
        if str(row.tool_id).startswith(prefix):
            out.append(f"- `{row.tool_id}` ({row.plugin_id})")
    return out


def render_inventory_markdown(rows: List[ToolInventoryRow], *, project_root: Path) -> str:
    root = project_root.resolve()
    lines: List[str] = []
    lines.append("# MCP Migration Inventory")
    lines.append("")
    lines.append("Static inventory generated from `configs/plugins_enabled.yaml` and AST parsing of `integrations/*/plugin.py`.")
    lines.append("No runtime plugin loading, no core/HUD startup, deterministic ordering.")
    lines.append("")
    lines.append("## Tool Registry (Static)")
    lines.append("")
    lines.append("| tool_id | tool_group | plugin_id | op | handler | plugin_file | default_target |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.tool_id,
                    row.tool_group,
                    row.plugin_id,
                    row.op,
                    row.handler,
                    row.plugin_file,
                    row.default_target or "",
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## MCP Candidate Buckets")
    lines.append("")
    bucket_map = {
        "patch.*": ["patch."],
        "fs.* + repo/project scan": ["fs.", "repo.search", "project.scan_repo"],
        "sketch.* / cad.*": ["sketch.", "cad."],
        "stable_diffusion.*": ["stable_diffusion."],
        "voice.*": ["voice."],
    }
    tool_ids = [str(r.tool_id) for r in rows]
    for title, patterns in bucket_map.items():
        lines.append(f"### {title}")
        matched: List[str] = []
        for tid in tool_ids:
            for p in patterns:
                if tid.startswith(p):
                    matched.append(tid)
                    break
        if not matched:
            lines.append("- none")
        else:
            for tid in sorted(set(matched)):
                lines.append(f"- `{tid}`")
        lines.append("")

    has_engineering = any(str(r.tool_id).startswith("engineering.") for r in rows)
    lines.append("## Notes")
    lines.append("")
    if has_engineering:
        lines.append("- `engineering.*` group detected in current static registry.")
    else:
        lines.append("- `engineering.*` group is not present in current static registry.")
    lines.append(f"- Total tools parsed: {len(rows)}")
    lines.append(f"- Project root: `{_repo_rel(root, root) or '.'}`")
    lines.append("")
    return "\n".join(lines)


def write_inventory(project_root: Path, output_path: Path) -> Path:
    rows = collect_inventory(project_root)
    markdown = render_inventory_markdown(rows, project_root=project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate static MCP migration inventory.")
    parser.add_argument("--project-root", default=".", help="Nova project root")
    parser.add_argument("--output", default="docs/mcp_migration_inventory.md", help="Output markdown path")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    out = (root / str(args.output)).resolve() if not Path(args.output).is_absolute() else Path(args.output).resolve()
    written = write_inventory(root, out)
    print(f"inventory_written={written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
