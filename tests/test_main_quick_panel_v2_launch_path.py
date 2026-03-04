from __future__ import annotations

from pathlib import Path


def test_main_includes_quick_panel_v2_subcommand_and_launcher() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "main.py").read_text(encoding="utf-8")

    assert "def _launch_quick_panel_v2() -> int:" in text
    assert "subparsers.add_parser(\"quick_panel_v2\"" in text
    assert "if args.command == \"quick_panel_v2\":" in text
    assert "from ui.quick_panel_v2.app import main as quick_panel_v2_main" in text
