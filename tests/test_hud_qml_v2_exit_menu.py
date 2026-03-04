from pathlib import Path


def test_hud_v2_top_header_exposes_exit_button() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "ui" / "hud_qml_v2" / "components" / "TopHeader.qml").read_text(encoding="utf-8")
    assert "TopExitButton" in text
    assert "⏻ Exit" in text
    assert "signal exitRequested()" in text


def test_hud_v2_shell_wires_shutdown_menu_and_controller_call() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellFull.qml").read_text(encoding="utf-8")
    assert "Shutdown Nova" in text
    assert "Exit HUD only" in text
    assert "Keep Ollama running" in text
    assert "hudController.shutdownNova(" in text
