from __future__ import annotations

import os
import threading
import time
from typing import Optional

from core.voice.schemas import TtsResult


class Pyttsx3TtsProvider:
    def __init__(
        self,
        *,
        voice_id: Optional[str] = None,
        rate: Optional[int] = None,
        volume: Optional[float] = None,
    ) -> None:
        self._voice_id = voice_id or os.environ.get("VOICE_TTS_VOICE_PYTTSX3")
        self._rate = int(rate or os.environ.get("VOICE_TTS_RATE_PYTTSX3") or 180)
        self._volume = float(volume or os.environ.get("VOICE_TTS_VOLUME_PYTTSX3") or 1.0)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._engine = None

    @property
    def name(self) -> str:
        return "pyttsx3"

    def speak(
        self,
        text: str,
        *,
        cancel_event: Optional[threading.Event] = None,
        voice_id: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> TtsResult:
        _ = sample_rate
        payload = str(text or "").strip()
        if not payload:
            return TtsResult(ok=True, provider=self.name, metadata={"reason": "empty"})

        started = time.perf_counter()
        self._stop_event.clear()

        try:
            import pyttsx3
        except ImportError:
            raise RuntimeError("pyttsx3 is not installed. Install with: pip install pyttsx3")

        with self._lock:
            if self._engine is None:
                self._engine = pyttsx3.init()
            
            engine = self._engine
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            
            actual_voice = voice_id or self._voice_id
            if actual_voice:
                engine.setProperty("voice", actual_voice)
            else:
                # Try to find an Arabic voice if not specified
                voices = engine.getProperty("voices")
                for v in voices:
                    if "arabic" in str(v.name).lower() or "ar-sa" in str(v.id).lower() or "ar-eg" in str(v.id).lower():
                        engine.setProperty("voice", v.id)
                        break

            # Use a thread-safe way to run and wait, but pyttsx3 is not very thread-friendly
            # for interruption. We'll use the basic say/runAndWait logic for now.
            try:
                engine.say(payload)
                engine.runAndWait()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                raise RuntimeError(f"pyttsx3 synthesis failed: {exc}")

        latency_ms = (time.perf_counter() - started) * 1000.0
        return TtsResult(ok=True, latency_ms=latency_ms, provider=self.name)

    def stop(self) -> None:
        self._stop_event.set()
        if self._engine:
            try:
                self._engine.stop()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
