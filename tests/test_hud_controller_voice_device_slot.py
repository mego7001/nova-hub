from __future__ import annotations

from pathlib import Path
import tempfile

from ui.hud_qml.controller import HUDController
import ui.hud_qml.controller as controller_mod


def test_set_voice_device_slot_no_frozen_instance_error() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )

        controller.set_voice_device("default")

        assert controller.voiceCurrentDevice == "default"


def test_voice_input_devices_fallbacks_to_default_on_import_error(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        monkeypatch.setattr(controller_mod, "list_input_devices", lambda: (_ for _ in ()).throw(ImportError("missing")))

        assert controller.voice_input_devices() == ["default"]


class _FakeVoiceConfig:
    def __init__(self) -> None:
        self.stt_model = "small"
        self.device = "default"
        self.tts_voice = ""
        self.sample_rate = 16000
        self.vad_mode = "energy"
        self.push_to_talk = True


class _FailingVoiceManager:
    def __init__(self) -> None:
        self.enabled = False
        self.muted = False
        self.state = "idle"
        self.last_error = ""
        self.last_transcript = ""
        self.last_spoken_text = ""
        self.last_voice_error_kind = "missing_dependency"
        self.config = _FakeVoiceConfig()
        self.push_to_talk_active = False

    def set_config(self, **kwargs) -> None:
        self.config.device = str(kwargs.get("device") or "default")

    def start_loop(self) -> bool:
        raise ModuleNotFoundError("No module named 'ctranslate2'")

    def stop_loop(self) -> None:
        self.enabled = False

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)

    def stop_speaking(self) -> None:
        return

    def replay_last(self) -> None:
        return

    def set_push_to_talk_active(self, active: bool) -> None:
        self.push_to_talk_active = bool(active)


def test_toggle_voice_enabled_gracefully_handles_missing_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller._voice_manager = _FailingVoiceManager()  # type: ignore[assignment]

        controller.toggle_voice_enabled()

        assert "Voice unavailable: missing dependency" in controller.statusText


def test_set_voice_device_gracefully_handles_restart_failure() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        failing_manager = _FailingVoiceManager()
        failing_manager.enabled = True
        controller._voice_manager = failing_manager  # type: ignore[assignment]

        controller.set_voice_device("default")

        assert "Voice unavailable: missing dependency" in controller.statusText


class _SuccessfulVoiceManager(_FailingVoiceManager):
    def __init__(self) -> None:
        super().__init__()
        self.enabled = True

    def start_loop(self) -> bool:
        self.config.device = "Mic-USB"
        self.enabled = True
        return True


def test_set_voice_device_persists_after_successful_restart() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        manager = _SuccessfulVoiceManager()
        controller._voice_manager = manager  # type: ignore[assignment]
        persisted: list[bool] = []
        controller._persist_voice_preferences = lambda: persisted.append(True)  # type: ignore[method-assign]

        controller.set_voice_device("invalid-mic")

        assert controller.voiceCurrentDevice == "Mic-USB"
        assert persisted


def test_voice_push_slots_update_push_state_without_crash() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        manager = _SuccessfulVoiceManager()
        manager.config.push_to_talk = True
        controller._voice_manager = manager  # type: ignore[assignment]

        controller.voicePushStart()
        assert bool(getattr(manager, "push_to_talk_active", False)) is True

        controller.voicePushStop()
        assert bool(getattr(manager, "push_to_talk_active", False)) is False
