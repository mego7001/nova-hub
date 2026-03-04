from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
import threading
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class VoiceConfig:
    stt_model: str = "small"
    device: str = "default"
    tts_voice: str = ""
    sample_rate: int = 16000
    vad_mode: str = "energy"
    vad_energy_threshold: float = 650.0
    vad_min_speech_ms: int = 260
    vad_silence_ms: int = 520
    tts_sentence_pause_ms: int = 35
    push_to_talk: bool = True

    @classmethod
    def from_env(cls) -> "VoiceConfig":
        def _int(name: str, default: int) -> int:
            raw = str(os.environ.get(name) or "").strip()
            if not raw:
                return default
            try:
                return int(raw)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return default

        def _float(name: str, default: float) -> float:
            raw = str(os.environ.get(name) or "").strip()
            if not raw:
                return default

        def _bool(name: str, default: bool) -> bool:
            raw = str(os.environ.get(name) or "").strip().lower()
            if not raw:
                return bool(default)
            return raw not in ("0", "false", "off", "no")
            try:
                return float(raw)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return default

        return cls(
            stt_model=str(os.environ.get("VOICE_STT_MODEL") or cls.stt_model).strip() or cls.stt_model,
            device=str(os.environ.get("VOICE_DEVICE") or cls.device).strip() or cls.device,
            tts_voice=str(os.environ.get("VOICE_TTS_VOICE") or cls.tts_voice).strip(),
            sample_rate=max(8000, _int("VOICE_SAMPLE_RATE", cls.sample_rate)),
            vad_mode=str(os.environ.get("VOICE_VAD_MODE") or cls.vad_mode).strip() or cls.vad_mode,
            vad_energy_threshold=max(1.0, _float("VOICE_VAD_THRESHOLD", cls.vad_energy_threshold)),
            vad_min_speech_ms=max(40, _int("VOICE_VAD_MIN_SPEECH_MS", cls.vad_min_speech_ms)),
            vad_silence_ms=max(80, _int("VOICE_VAD_SILENCE_MS", cls.vad_silence_ms)),
            tts_sentence_pause_ms=max(0, _int("VOICE_TTS_PAUSE_MS", cls.tts_sentence_pause_ms)),
            push_to_talk=_bool("VOICE_PUSH_TO_TALK", cls.push_to_talk),
        )


@dataclass(frozen=True)
class SttSegment:
    start: float
    end: float
    text: str


@dataclass
class SttResult:
    text: str = ""
    segments: List[SttSegment] = field(default_factory=list)
    latency_ms: float = 0.0
    provider: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TtsResult:
    ok: bool = True
    latency_ms: float = 0.0
    provider: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ISttProvider(Protocol):
    @property
    def name(self) -> str:
        ...

    def transcribe_stream(self, audio_pcm16: bytes, sample_rate: int) -> SttResult:
        ...

    def transcribe_file(self, path: str) -> SttResult:
        ...


@runtime_checkable
class ITtsProvider(Protocol):
    @property
    def name(self) -> str:
        ...

    def speak(
        self,
        text: str,
        *,
        cancel_event: Optional[threading.Event] = None,
        voice_id: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> TtsResult:
        ...

    def stop(self) -> None:
        ...
