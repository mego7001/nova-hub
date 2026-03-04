from __future__ import annotations

from pathlib import Path
import tempfile

from ui.hud_qml.controller import HUDController


class _FakeVoiceConfig:
    def __init__(self) -> None:
        self.stt_model = "fake-stt"
        self.device = "fake-mic"
        self.push_to_talk = True


class _FakeVoiceManager:
    def __init__(self) -> None:
        self.notified = []
        self.enabled = True
        self.muted = False
        self.state = "listening"
        self.last_transcript = ""
        self.last_spoken_text = ""
        self.push_to_talk_active = False
        self.config = _FakeVoiceConfig()

    def notify_assistant_text(self, text: str) -> None:
        self.notified.append(text)
        self.last_spoken_text = text

    def set_push_to_talk_active(self, active: bool) -> None:
        self.push_to_talk_active = bool(active)


def test_voice_error_message_is_user_friendly_for_missing_dependency():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        fake = _FakeVoiceManager()
        fake.last_error = "No module named 'ctranslate2'"
        fake.last_voice_error_kind = "missing_dependency"
        controller._voice_manager = fake  # type: ignore[assignment]

        controller._on_voice_error_event("No module named 'ctranslate2'")

        assert "Voice unavailable: missing dependency" in controller.statusText


def test_voice_error_message_prefers_device_error_when_message_indicates_invalid_device():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        fake = _FakeVoiceManager()
        fake.last_error = "No module named 'ctranslate2'"
        fake.last_voice_error_kind = "missing_dependency"
        controller._voice_manager = fake  # type: ignore[assignment]

        controller._on_voice_error_event("Error opening RawInputStream: Invalid device [PaErrorCode -9996]")

        assert "Voice unavailable: microphone/device error" in controller.statusText


def test_voice_transcript_routes_through_send_message_boundary():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        seen = []
        controller.send_message = lambda msg: seen.append(msg)  # type: ignore[method-assign]

        controller.send_message("typed message")
        controller._on_voice_transcript_ready("spoken transcript")
        assert seen == ["typed message", "spoken transcript"]


def test_assistant_append_routes_to_voice_tts_when_enabled():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        fake = _FakeVoiceManager()
        controller._voice_manager = fake  # type: ignore[assignment]

        controller._append_assistant_message("voice this response")
        assert fake.notified == ["voice this response"]
        assert "fake-stt" in controller.voiceProviderNames
        assert controller.voiceCurrentDevice == "fake-mic"
        assert controller.voiceLastSpokenText == "voice this response"


def test_voice_properties_and_slots_exist():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        assert hasattr(controller, "voiceEnabled")
        assert hasattr(controller, "voiceMuted")
        assert hasattr(controller, "voiceState")
        assert hasattr(controller, "voiceStatusLine")
        assert hasattr(controller, "voicePushToTalk")
        assert hasattr(controller, "voicePushActive")
        assert hasattr(controller, "toggle_voice_enabled")
        assert hasattr(controller, "voicePushStart")
        assert hasattr(controller, "voicePushStop")
        assert hasattr(controller, "voice_mute")
        assert hasattr(controller, "voice_unmute")
        assert hasattr(controller, "voice_stop_speaking")
        assert hasattr(controller, "voice_replay_last")
