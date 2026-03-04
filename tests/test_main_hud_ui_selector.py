from __future__ import annotations

import sys

import main as cli_main
from ui.hud_qml import app_qml


def test_main_hud_cli_passes_ui_selection(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def _fake_launch_hud(args=None) -> int:
        captured["ui"] = getattr(args, "ui", None)
        return 0

    monkeypatch.setattr(cli_main, "_launch_hud", _fake_launch_hud)
    monkeypatch.setattr(sys, "argv", ["main.py", "hud", "--ui", "v2"])

    assert cli_main.main() == 0
    assert captured["ui"] == "v2"


def test_main_default_hud_keeps_ui_unspecified(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def _fake_launch_hud(args=None) -> int:
        captured["ui"] = getattr(args, "ui", None)
        return 0

    monkeypatch.setattr(cli_main, "_launch_hud", _fake_launch_hud)
    monkeypatch.setattr(sys, "argv", ["main.py"])

    assert cli_main.main() == 0
    assert captured["ui"] is None


def test_app_qml_resolve_ui_version_precedence(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_VERSION", raising=False)
    monkeypatch.delenv("NH_UI_V2", raising=False)
    assert app_qml._resolve_ui_version() == "auto"

    monkeypatch.setenv("NH_UI_V2", "1")
    assert app_qml._resolve_ui_version() == "v2"

    monkeypatch.setenv("NH_UI_VERSION", "v1")
    assert app_qml._resolve_ui_version() == "v1"
    assert app_qml._resolve_ui_version("v2") == "v2"


def test_app_qml_auto_candidates_try_v2_then_v1() -> None:
    # Shell V3 is now default for V2 and falls back to MainV2 then Main v1.
    candidates = app_qml._resolve_qml_candidates("auto")
    assert len(candidates) == 3
    assert candidates[0].name == "MainShellFull.qml"
    assert candidates[1].name == "MainV2.qml"
    assert candidates[2].name == "Main.qml"


def test_app_qml_v2_candidates_can_use_shell_v3(monkeypatch) -> None:
    monkeypatch.setenv("NH_UI_SHELL_V3", "1")
    candidates = app_qml._resolve_qml_candidates("v2")
    assert len(candidates) == 2
    assert candidates[0].name == "MainShellFull.qml"
    assert candidates[1].name == "MainV2.qml"


def test_app_qml_v2_candidates_can_rollback_shell_v3(monkeypatch) -> None:
    monkeypatch.setenv("NH_UI_SHELL_V3", "0")
    candidates = app_qml._resolve_qml_candidates("v2")
    assert len(candidates) == 1
    assert candidates[0].name == "MainV2.qml"


def test_app_qml_effects_profile_defaults_and_override(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_EFFECTS_PROFILE", raising=False)
    assert app_qml._resolve_effects_profile() == "high_effects"
    monkeypatch.setenv("NH_UI_EFFECTS_PROFILE", "degraded")
    assert app_qml._resolve_effects_profile() == "degraded"


def test_app_qml_theme_variant_defaults_and_override(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_THEME_VARIANT", raising=False)
    assert app_qml._resolve_theme_variant() == "jarvis_cyan"
    monkeypatch.setenv("NH_UI_THEME_VARIANT", "amber_industrial")
    assert app_qml._resolve_theme_variant() == "amber_industrial"


def test_app_qml_motion_intensity_defaults_and_override(monkeypatch) -> None:
    monkeypatch.delenv("NH_UI_MOTION_INTENSITY", raising=False)
    assert app_qml._resolve_motion_intensity() == "cinematic"
    monkeypatch.setenv("NH_UI_MOTION_INTENSITY", "reduced")
    assert app_qml._resolve_motion_intensity() == "reduced"
