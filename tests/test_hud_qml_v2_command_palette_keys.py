from __future__ import annotations

from pathlib import Path


def test_v2_command_palette_root_uses_shortcut_not_keys_on_popup() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "ui" / "hud_qml_v2" / "components" / "CommandPalette.qml").read_text(encoding="utf-8")

    assert 'sequence: "Esc"' in text
    assert "enabled: root.visible" in text
    assert text.count("Keys.onPressed") == 1
    assert "root.closePalette()" in text


def test_v2_main_has_close_shortcuts_and_palette_window_actions() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellFull.qml").read_text(encoding="utf-8")
    quick_text = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellCompact.qml").read_text(encoding="utf-8")
    hud_wrapper = (root / "ui" / "hud_qml_v2" / "MainV2.qml").read_text(encoding="utf-8")
    quick_wrapper = (root / "ui" / "quick_panel_v2" / "MainV2.qml").read_text(encoding="utf-8")

    assert 'sequence: "Ctrl+Q"' in text
    assert 'sequence: "Ctrl+W"' in text
    assert "function _appMinimize()" in text
    assert "function _appClose()" in text
    assert 'if (action === "app_minimize")' in text
    assert 'if (action === "app_close")' in text
    assert "MainShellFull" in hud_wrapper
    assert "MainShellCompact" in quick_wrapper

    for seq in ("Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5"):
        assert f'sequence: "{seq}"' in text
        assert f'sequence: "{seq}"' in quick_text
