from dataclasses import replace
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Signal

from core.voice.voice_loop import VoiceLoop
from core.voice.schemas import VoiceConfig, VoiceState
from core.voice.audio_io import list_input_devices, SoundDeviceAudioInput
from core.voice.providers import FasterWhisperSttProvider, PiperTtsProvider, Pyttsx3TtsProvider

class VoiceManager(QObject):
    transcriptReady = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)
    configChanged = Signal()

    def __init__(self, workspace_root: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._workspace_root = workspace_root
        self._loop: Optional[VoiceLoop] = None
        self._config = VoiceConfig()
        self._enabled = False
        self._muted = False
        self._state = VoiceState.IDLE.value
        self._last_transcript = ""
        self._last_spoken_text = ""
        self._last_error = ""
        self._last_llm_latency_ms = 0.0
        self._voice_dependencies_ready = True
        self._last_voice_error_kind = ""
        self._push_to_talk_active = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def state(self) -> str:
        return self._state

    @property
    def last_transcript(self) -> str:
        return self._last_transcript

    @property
    def last_spoken_text(self) -> str:
        return self._last_spoken_text

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def config(self) -> VoiceConfig:
        return self._config

    @property
    def voice_dependencies_ready(self) -> bool:
        return self._voice_dependencies_ready

    @property
    def last_voice_error_kind(self) -> str:
        return self._last_voice_error_kind

    @property
    def push_to_talk_active(self) -> bool:
        return bool(self._push_to_talk_active)

    def set_muted(self, muted: bool):
        self._muted = muted
        if self._loop:
            self._loop.set_muted(muted)

    def set_push_to_talk_active(self, active: bool) -> None:
        self._push_to_talk_active = bool(active)
        if self._loop is not None:
            try:
                self._loop.set_push_to_talk_active(self._push_to_talk_active)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def set_config(self, **kwargs):
        updates: Dict[str, Any] = {}
        string_fields = {"stt_model", "device", "tts_voice", "vad_mode"}
        int_fields = {"sample_rate", "vad_min_speech_ms", "vad_silence_ms", "tts_sentence_pause_ms"}
        float_fields = {"vad_energy_threshold"}
        bool_fields = {"push_to_talk"}

        for key, value in kwargs.items():
            if not hasattr(self._config, key):
                continue

            if key in string_fields:
                cleaned = str(value or "").strip()
                updates[key] = cleaned if cleaned else getattr(self._config, key)
                continue

            if key in int_fields:
                try:
                    parsed = int(value)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    continue
                if key == "sample_rate":
                    parsed = max(8000, parsed)
                elif key in {"vad_min_speech_ms", "vad_silence_ms"}:
                    parsed = max(0, parsed)
                updates[key] = parsed
                continue

            if key in float_fields:
                try:
                    updates[key] = float(value)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    continue
                continue

            if key in bool_fields:
                if isinstance(value, str):
                    updates[key] = str(value).strip().lower() not in ("0", "false", "off", "no")
                else:
                    updates[key] = bool(value)
                continue

            updates[key] = value

        if not updates:
            return

        new_config = replace(self._config, **updates)
        if new_config == self._config:
            return

        self._config = new_config
        self.configChanged.emit()

    def start_loop(self) -> bool:
        if self._loop:
            self.stop_loop()
        
        try:
            # 1. Build Providers
            stt_provider = FasterWhisperSttProvider(model_name=self._config.stt_model)
            
            # Use Piper if a voice is configured, otherwise fallback to pyttsx3 (SAPI5)
            if self._config.tts_voice:
                tts_provider = PiperTtsProvider(
                    voice_id=self._config.tts_voice,
                    sentence_pause_ms=self._config.tts_sentence_pause_ms,
                )
            else:
                tts_provider = Pyttsx3TtsProvider(
                    rate=185,
                    volume=1.0
                )
            
            audio_input = SoundDeviceAudioInput(
                sample_rate=self._config.sample_rate,
                device=self._config.device,
            )

            # 2. Build Loop
            self._loop = VoiceLoop(
                stt_provider=stt_provider,
                tts_provider=tts_provider,
                config=self._config,
                audio_input=audio_input,
                on_transcript=self._on_transcript,
                on_state_changed=self._on_state,
                on_error=self._on_error,
            )
            
            ok = self._loop.start()
            self._enabled = ok
            if not ok:
                self._state = VoiceState.ERROR.value
                if not self._last_error:
                    self._last_error = "Voice loop failed to start."
                self._last_voice_error_kind = self._classify_error_kind(RuntimeError(self._last_error), self._last_error)
                self._voice_dependencies_ready = self._last_voice_error_kind != "missing_dependency"
                return False
            
            self._state = self._loop.state.value
            self._loop.set_muted(self._muted)
            try:
                self._loop.set_push_to_talk_active((not bool(self._config.push_to_talk)) or bool(self._push_to_talk_active))
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
            actual_device = str(getattr(self._loop, "device_name", "") or "").strip()
            if actual_device and actual_device != str(self._config.device or "").strip():
                self.set_config(device=actual_device)
            self._last_error = ""
            self._last_voice_error_kind = ""
            self._voice_dependencies_ready = True
            return True
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            ImportError,
            ModuleNotFoundError,
        ) as e:
            self._last_error = str(e)
            self._last_voice_error_kind = self._classify_error_kind(e, self._last_error)
            self._voice_dependencies_ready = self._last_voice_error_kind != "missing_dependency"
            self._state = VoiceState.ERROR.value
            self._enabled = False
            self.errorOccurred.emit(self._last_error)
            return False

    def stop_loop(self):
        if self._loop:
            try:
                self._loop.stop()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
            self._loop = None
        self._enabled = False
        self._push_to_talk_active = False
        self._state = VoiceState.IDLE.value

    def stop_speaking(self):
        if self._loop:
            self._loop.stop_speaking()

    def replay_last(self):
        if self._loop:
            self._loop.replay_last()

    def notify_assistant_text(self, text: str):
        self._last_spoken_text = text
        if self._enabled and not self._muted and self._loop:
            self._loop.notify_assistant_text(text)

    def note_llm_latency(self, latency_ms: float) -> None:
        try:
            val = max(0.0, float(latency_ms))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            val = 0.0
        self._last_llm_latency_ms = val
        if self._loop is not None:
            self._loop.note_llm_latency(val)

    def latency_metrics(self) -> Dict[str, str]:
        snap: Dict[str, str] = {}
        if self._loop is not None:
            try:
                snap = dict(self._loop.status_snapshot())
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                snap = {}
        if "llm_latency_ms" not in snap:
            snap["llm_latency_ms"] = f"{self._last_llm_latency_ms:.1f}"
        return snap

    def _on_transcript(self, text: str):
        self._last_transcript = text
        self.transcriptReady.emit(text)

    def _on_state(self, state: VoiceState):
        self._state = state.value
        self.stateChanged.emit(self._state)

    def _on_error(self, error: str):
        self._last_error = error
        self._state = VoiceState.ERROR.value
        self.errorOccurred.emit(error)

    def list_devices(self) -> List[str]:
        return list_input_devices()

    @staticmethod
    def _classify_error_kind(exc: Exception, message: str) -> str:
        if isinstance(exc, (ImportError, ModuleNotFoundError)):
            return "missing_dependency"
        text = str(message or "").strip().lower()
        if "missing dependency" in text or "no module named" in text:
            return "missing_dependency"
        if (
            "invalid device" in text
            or "paerrorcode" in text
            or "rawinputstream" in text
            or "input device" in text
            or "microphone" in text
            or "device" in text
        ):
            return "device_error"
        return "runtime_error"
