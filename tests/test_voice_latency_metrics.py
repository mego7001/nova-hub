from __future__ import annotations

import time

from core.voice.providers.mock import MockSttProvider, MockTtsProvider
from core.voice.schemas import VoiceConfig
from core.voice.voice_loop import VoiceLoop


def _wait_until(predicate, timeout_s: float = 1.5) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_voice_latency_metrics_include_stage_values():
    loop = VoiceLoop(
        stt_provider=MockSttProvider(transcripts=["hello"], latency_ms=5.0),
        tts_provider=MockTtsProvider(step_delay_s=0.01, total_steps=2),
        config=VoiceConfig(),
    )
    try:
        assert loop.start() is True
        loop.note_llm_latency(123.0)
        assert loop.enqueue_tts("assistant response") is True
        assert _wait_until(lambda: float(loop.status_snapshot().get("tts_latency_ms") or "0") > 0.0)
        snap = loop.status_snapshot()
        for key in ("capture_latency_ms", "stt_latency_ms", "llm_latency_ms", "tts_latency_ms", "playback_latency_ms"):
            assert key in snap
        assert float(snap["llm_latency_ms"]) == 123.0
        assert float(snap["playback_latency_ms"]) >= 0.0
    finally:
        loop.stop()
