from __future__ import annotations

from ui.quick_panel_v2 import app


def test_quick_panel_v2_default_qml_path(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_SHELL_V3", raising=False)
    assert app._resolve_qml_path().name == "MainShellCompact.qml"


def test_quick_panel_v2_shell_v3_qml_path(monkeypatch) -> None:
    monkeypatch.setenv("NH_UI_SHELL_V3", "1")
    path = app._resolve_qml_path()
    assert path.name == "MainShellCompact.qml"
    assert "hud_qml_v2" in path.parts


def test_quick_panel_v2_shell_v3_can_rollback(monkeypatch) -> None:
    monkeypatch.setenv("NH_UI_SHELL_V3", "0")
    assert app._resolve_qml_path().name == "MainV2.qml"


def test_quick_panel_v2_effects_profile_defaults_and_override(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_EFFECTS_PROFILE", raising=False)
    assert app._resolve_effects_profile() == "high_effects"
    monkeypatch.setenv("NH_UI_EFFECTS_PROFILE", "high_effects")
    assert app._resolve_effects_profile() == "high_effects"


def test_quick_panel_v2_theme_variant_defaults_and_override(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_THEME_VARIANT", raising=False)
    assert app._resolve_theme_variant() == "jarvis_cyan"
    monkeypatch.setenv("NH_UI_THEME_VARIANT", "amber_industrial")
    assert app._resolve_theme_variant() == "amber_industrial"


def test_quick_panel_v2_motion_intensity_defaults_and_override(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_MOTION_INTENSITY", raising=False)
    assert app._resolve_motion_intensity() == "cinematic"
    monkeypatch.setenv("NH_UI_MOTION_INTENSITY", "reduced")
    assert app._resolve_motion_intensity() == "reduced"
