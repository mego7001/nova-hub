from pathlib import Path


def test_voice_panel_files_and_main_wiring_exist():
    root = Path(__file__).resolve().parents[1]
    main_qml = root / "ui" / "hud_qml" / "qml" / "Main.qml"
    voice_panel_qml = root / "ui" / "hud_qml" / "qml" / "panels" / "VoiceChatPanel.qml"
    controller_py = root / "ui" / "hud_qml" / "controller.py"

    assert main_qml.exists()
    assert voice_panel_qml.exists()
    assert controller_py.exists()

    main_text = main_qml.read_text(encoding="utf-8")
    voice_text = voice_panel_qml.read_text(encoding="utf-8")
    controller_text = controller_py.read_text(encoding="utf-8")

    assert "Voice Chat" in main_text
    assert "voiceChatPanelComponent" in main_text
    assert "VoiceChatPanel" in main_text
    assert "Ctrl+Shift+V" in main_text

    assert "controller.voiceEnabled" in voice_text
    assert "controller.voiceStatusLine" in voice_text
    assert "controller.voiceLastTranscript" in voice_text
    assert "controller.voiceLastSpokenText" in voice_text
    assert "controller.voice_input_devices()" in voice_text

    assert "def toggle_voice_enabled" in controller_text
    assert "def voice_mute" in controller_text
    assert "def voice_unmute" in controller_text
    assert "def voice_stop_speaking" in controller_text
    assert "def voice_replay_last" in controller_text
