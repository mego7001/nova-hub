from __future__ import annotations

from types import SimpleNamespace

import ui.hud_qml.managers.voice_manager as voice_manager_mod
from ui.hud_qml.managers.voice_manager import VoiceManager


class _FakeLoop:
    def __init__(self) -> None:
        self.notified: list[str] = []

    def notify_assistant_text(self, text: str) -> None:
        self.notified.append(text)


def test_voice_manager_set_config_updates_frozen_config_without_mutation_error(tmp_path) -> None:
    manager = VoiceManager(workspace_root=str(tmp_path))

    manager.set_config(device="default", stt_model="small", sample_rate=22050, vad_mode="energy")

    assert manager.config.device == "default"
    assert manager.config.stt_model == "small"
    assert manager.config.sample_rate == 22050
    assert manager.config.vad_mode == "energy"


def test_voice_manager_set_config_ignores_unknown_keys(tmp_path) -> None:
    manager = VoiceManager(workspace_root=str(tmp_path))
    before = manager.config

    manager.set_config(not_a_field="x")

    assert manager.config == before


def test_voice_manager_notify_assistant_text_honors_enabled_and_muted_flags(tmp_path) -> None:
    manager = VoiceManager(workspace_root=str(tmp_path))
    fake_loop = _FakeLoop()
    manager._loop = fake_loop  # type: ignore[assignment]

    manager._enabled = True
    manager._muted = False
    manager.notify_assistant_text("first reply")
    assert fake_loop.notified == ["first reply"]
    assert manager.last_spoken_text == "first reply"

    manager._muted = True
    manager.notify_assistant_text("second reply")
    assert fake_loop.notified == ["first reply"]
    assert manager.last_spoken_text == "second reply"

    manager._enabled = False
    manager._muted = False
    manager.notify_assistant_text("third reply")
    assert fake_loop.notified == ["first reply"]
    assert manager.last_spoken_text == "third reply"


def test_voice_manager_start_loop_handles_missing_dependency_without_raising(tmp_path, monkeypatch) -> None:
    class _MissingSttProvider:
        def __init__(self, *args, **kwargs) -> None:
            raise ModuleNotFoundError("No module named 'ctranslate2'")

    monkeypatch.setattr(voice_manager_mod, "FasterWhisperSttProvider", _MissingSttProvider)
    manager = VoiceManager(workspace_root=str(tmp_path))

    ok = manager.start_loop()

    assert ok is False
    assert manager.enabled is False
    assert str(manager.state).lower() == "error"
    assert manager.last_voice_error_kind == "missing_dependency"
    assert "ctranslate2" in manager.last_error


def test_voice_manager_start_loop_keeps_specific_error_when_loop_returns_false(tmp_path, monkeypatch) -> None:
    class _FakeLoop:
        def __init__(self, *args, **kwargs) -> None:
            self._on_error = kwargs.get("on_error")

        def start(self) -> bool:
            if callable(self._on_error):
                self._on_error("Missing dependency 'sounddevice'. Install with: pip install -r requirements-voice.txt")
            return False

        def stop(self) -> None:
            return

        def set_muted(self, muted: bool) -> None:
            _ = muted

    monkeypatch.setattr(voice_manager_mod, "VoiceLoop", _FakeLoop)
    manager = VoiceManager(workspace_root=str(tmp_path))

    ok = manager.start_loop()

    assert ok is False
    assert manager.last_voice_error_kind == "missing_dependency"
    assert "sounddevice" in manager.last_error.lower()


def test_voice_manager_start_loop_syncs_config_device_from_runtime_device(tmp_path, monkeypatch) -> None:
    class _DummySttProvider:
        def __init__(self, *args, **kwargs) -> None:
            return

    class _DummyTtsProvider:
        def __init__(self, *args, **kwargs) -> None:
            return

    class _DummyAudioInput:
        def __init__(self, *args, **kwargs) -> None:
            return

    class _FakeLoop:
        def __init__(self, *args, **kwargs) -> None:
            self.state = SimpleNamespace(value="LISTENING")
            self.device_name = "Mic-USB"

        def start(self) -> bool:
            return True

        def set_muted(self, muted: bool) -> None:
            _ = muted

        def stop(self) -> None:
            return

    monkeypatch.setattr(voice_manager_mod, "FasterWhisperSttProvider", _DummySttProvider)
    monkeypatch.setattr(voice_manager_mod, "PiperTtsProvider", _DummyTtsProvider)
    monkeypatch.setattr(voice_manager_mod, "Pyttsx3TtsProvider", _DummyTtsProvider)
    monkeypatch.setattr(voice_manager_mod, "SoundDeviceAudioInput", _DummyAudioInput)
    monkeypatch.setattr(voice_manager_mod, "VoiceLoop", _FakeLoop)
    manager = VoiceManager(workspace_root=str(tmp_path))
    manager.set_config(device="default")

    ok = manager.start_loop()

    assert ok is True
    assert manager.config.device == "Mic-USB"
