from pathlib import Path


def test_hud_v2_composer_exposes_voice_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    composer = (root / "ui" / "hud_qml_v2" / "components" / "Composer.qml").read_text(encoding="utf-8")

    assert "signal voiceToggleRequested()" in composer
    assert "signal voicePushStartRequested()" in composer
    assert "signal voicePushStopRequested()" in composer
    assert "signal voiceMuteToggleRequested()" in composer
    assert "signal voiceStopRequested()" in composer
    assert "signal voiceReplayRequested()" in composer
    assert "signal voicePanelRequested()" in composer

    assert "Mic On" in composer
    assert "Mic Off" in composer
    assert "Mute" in composer
    assert "Stop Voice" in composer
    assert "Replay" in composer
    assert "Voice" in composer
    assert 'objectName: "hudV2ComposerMicButton"' in composer
    assert 'objectName: "hudV2ComposerMuteButton"' in composer
    assert 'objectName: "hudV2ComposerStopVoiceButton"' in composer
    assert 'objectName: "hudV2ComposerReplayButton"' in composer
    assert 'objectName: "hudV2ComposerVoicePanelButton"' in composer
    assert 'objectName: "hudV2ComposerSendButton"' in composer


def test_hud_v2_voice_signals_are_wired_to_controller() -> None:
    root = Path(__file__).resolve().parents[1]
    chat_pane = (root / "ui" / "hud_qml_v2" / "components" / "ChatPane.qml").read_text(encoding="utf-8")
    main_v2 = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellFull.qml").read_text(encoding="utf-8")
    voice_panel = (root / "ui" / "hud_qml_v2" / "panels" / "PanelVoice.qml").read_text(encoding="utf-8")

    assert "onVoiceToggleRequested: root.voiceToggleRequested()" in chat_pane
    assert "onVoicePushStartRequested: root.voicePushStartRequested()" in chat_pane
    assert "onVoicePushStopRequested: root.voicePushStopRequested()" in chat_pane
    assert "onVoiceMuteToggleRequested: root.voiceMuteToggleRequested()" in chat_pane
    assert "onVoiceStopRequested: root.voiceStopRequested()" in chat_pane
    assert "onVoiceReplayRequested: root.voiceReplayRequested()" in chat_pane
    assert "onVoicePanelRequested: root.voicePanelRequested()" in chat_pane

    assert "onVoiceToggleRequested" in main_v2
    assert "hudController.toggle_voice_enabled()" in main_v2
    assert "onVoicePushStartRequested" in main_v2
    assert "hudController.voicePushStart()" in main_v2
    assert "onVoicePushStopRequested" in main_v2
    assert "hudController.voicePushStop()" in main_v2
    assert "hudController.voice_unmute()" in main_v2
    assert "hudController.voice_mute()" in main_v2
    assert "onVoiceStopRequested" in main_v2
    assert "hudController.voice_stop_speaking()" in main_v2
    assert "onVoiceReplayRequested" in main_v2
    assert "hudController.voice_replay_last()" in main_v2
    assert "win._openDrawer(\"voice\")" in main_v2
    assert "id: voiceDrawer" in main_v2
    assert "hudController.voice_input_devices()" in main_v2
    assert "hudController.set_voice_device(selected)" in main_v2
    assert "VoiceDrawerMicButton" in voice_panel
    assert "VoiceDrawerMuteButton" in voice_panel
    assert "VoiceDrawerStopButton" in voice_panel
    assert "VoiceDrawerReplayButton" in voice_panel
    assert "VoiceDeviceCombo" in voice_panel
    assert "VoiceRefreshDevicesButton" in voice_panel
