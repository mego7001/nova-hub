from __future__ import annotations

import threading
import time
from typing import List, Optional

from core.voice.schemas import SttResult, TtsResult


class MockSttProvider:
    def __init__(self, transcripts: Optional[List[str]] = None, latency_ms: float = 8.0) -> None:
        self._transcripts = list(transcripts or [])
        self._latency_ms = float(latency_ms)
        self.calls: List[int] = []

    @property
    def name(self) -> str:
        return "mock-stt"

    def transcribe_stream(self, audio_pcm16: bytes, sample_rate: int) -> SttResult:
        self.calls.append(len(audio_pcm16 or b""))
        time.sleep(max(0.0, self._latency_ms / 1000.0))
        if self._transcripts:
            text = self._transcripts.pop(0)
        else:
            text = "mock transcript"
        return SttResult(text=text, latency_ms=self._latency_ms, provider=self.name)

    def transcribe_file(self, path: str) -> SttResult:
        _ = path
        return SttResult(text="mock transcript", latency_ms=self._latency_ms, provider=self.name)


class MockTtsProvider:
    def __init__(self, step_delay_s: float = 0.01, total_steps: int = 6) -> None:
        self._step_delay_s = max(0.0, float(step_delay_s))
        self._total_steps = max(1, int(total_steps))
        self.speak_calls: List[str] = []
        self.stop_calls = 0

    @property
    def name(self) -> str:
        return "mock-tts"

    def speak(
        self,
        text: str,
        *,
        cancel_event: Optional[threading.Event] = None,
        voice_id: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> TtsResult:
        _ = (voice_id, sample_rate)
        self.speak_calls.append(text)
        started = time.perf_counter()
        for _ in range(self._total_steps):
            if cancel_event is not None and cancel_event.is_set():
                break
            time.sleep(self._step_delay_s)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return TtsResult(ok=True, latency_ms=latency_ms, provider=self.name)

    def stop(self) -> None:
        self.stop_calls += 1
