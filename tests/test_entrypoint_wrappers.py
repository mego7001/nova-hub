from __future__ import annotations

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    ("module_name", "expected_command"),
    [
        ("run_hud_qml", "hud"),
        ("run_quick_panel", "quick_panel_v2"),
        ("run_quick_panel_v2", "quick_panel_v2"),
        ("run_whatsapp", "whatsapp"),
        ("run_chat", "chat"),
        ("run_ui", "dashboard"),
        ("run_core_service", "core"),
        ("run_ipc_cli", "call"),
    ],
)
def test_wrapper_routes_to_canonical_main(module_name: str, expected_command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module(module_name)
    captured: dict[str, list[str]] = {}

    def _fake_main() -> int:
        captured["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr(module, "nova_main", _fake_main)
    monkeypatch.setattr(sys, "argv", [f"{module_name}.py", "--help"])
    result = module.main()

    assert result == 0
    assert captured["argv"][1] == expected_command
    assert "--help" in captured["argv"]
