from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
from typing import List


def pcm16_rms_energy(pcm16: bytes) -> float:
    if not pcm16:
        return 0.0
    data = array("h")
    data.frombytes(pcm16)
    if not data:
        return 0.0
    total = 0.0
    for sample in data:
        val = float(sample)
        total += val * val
    return math.sqrt(total / float(len(data)))


@dataclass
class EnergyVAD:
    threshold: float = 650.0

    def energy(self, pcm16: bytes) -> float:
        return pcm16_rms_energy(pcm16)

    def is_speech(self, pcm16: bytes) -> bool:
        return self.energy(pcm16) >= self.threshold


class EnergyTurnDetector:
    def __init__(self, *, vad: EnergyVAD, min_speech_ms: int = 260, silence_ms: int = 520) -> None:
        self._vad = vad
        self._min_speech_ms = max(40, int(min_speech_ms))
        self._silence_ms = max(80, int(silence_ms))
        self._speech_frames: List[bytes] = []
        self._speech_ms = 0.0
        self._silence_after_speech_ms = 0.0
        self._in_speech = False

    def reset(self) -> None:
        self._speech_frames = []
        self._speech_ms = 0.0
        self._silence_after_speech_ms = 0.0
        self._in_speech = False

    def consume(self, pcm16: bytes, sample_rate: int) -> List[bytes]:
        if not pcm16:
            return []
        frame_ms = self._frame_ms(pcm16, sample_rate)
        is_speech = self._vad.is_speech(pcm16)
        emitted: List[bytes] = []

        if is_speech:
            self._in_speech = True
            self._silence_after_speech_ms = 0.0
            self._speech_ms += frame_ms
            self._speech_frames.append(pcm16)
            return emitted

        if not self._in_speech:
            return emitted

        self._speech_frames.append(pcm16)
        self._silence_after_speech_ms += frame_ms
        self._speech_ms += frame_ms

        if self._silence_after_speech_ms < self._silence_ms:
            return emitted
        if self._speech_ms >= self._min_speech_ms:
            emitted.append(b"".join(self._speech_frames))
        self.reset()
        return emitted

    @staticmethod
    def _frame_ms(pcm16: bytes, sample_rate: int) -> float:
        sr = max(1, int(sample_rate))
        samples = len(pcm16) / 2.0
        return (samples / float(sr)) * 1000.0
