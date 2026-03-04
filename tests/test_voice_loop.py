from __future__ import annotations

import time

from core.voice.providers.mock import MockSttProvider, MockTtsProvider
from core.voice.schemas import VoiceConfig, VoiceState
from core.voice.voice_loop import VoiceLoop


def _wait_until(predicate, timeout_s: float = 2.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_voice_loop_state_transitions_single_turn():
    stt = MockSttProvider(transcripts=["hello from mic"])
    tts = MockTtsProvider(step_delay_s=0.01, total_steps=4)
    states = []
    transcripts = []

    loop = VoiceLoop(
        stt_provider=stt,
        tts_provider=tts,
        config=VoiceConfig(sample_rate=16000),
        on_transcript=lambda text: transcripts.append(text),
        on_state_changed=lambda state: states.append(state.value),
    )
    assert loop.start() is True
    assert loop.state == VoiceState.LISTENING

    assert loop.submit_audio_utterance(b"\x10\x00" * 3200) is True
    assert _wait_until(lambda: transcripts == ["hello from mic"])
    assert "TRANSCRIBING" in states
    assert "THINKING" in states

    assert loop.enqueue_tts("assistant response") is True
    assert _wait_until(lambda: "SPEAKING" in states)
    assert _wait_until(lambda: loop.state == VoiceState.LISTENING)
    assert loop.last_spoken_text == "assistant response"
    loop.stop()
    assert loop.state == VoiceState.IDLE


def test_voice_loop_replay_uses_last_spoken_text():
    stt = MockSttProvider(transcripts=[])
    tts = MockTtsProvider(step_delay_s=0.005, total_steps=2)
    loop = VoiceLoop(stt_provider=stt, tts_provider=tts, config=VoiceConfig())
    assert loop.start() is True

    assert loop.enqueue_tts("first answer") is True
    assert _wait_until(lambda: loop.last_spoken_text == "first answer")
    assert loop.replay_last() is True
    assert _wait_until(lambda: len(tts.speak_calls) >= 2)
    loop.stop()


def test_voice_loop_barge_in_stops_tts():
    stt = MockSttProvider(transcripts=["interrupt"])
    tts = MockTtsProvider(step_delay_s=0.03, total_steps=30)
    states = []
    loop = VoiceLoop(
        stt_provider=stt,
        tts_provider=tts,
        config=VoiceConfig(vad_energy_threshold=200.0, push_to_talk=False),
        on_state_changed=lambda state: states.append(state.value),
    )
    assert loop.start() is True
    assert loop.enqueue_tts("long reply for interruption test") is True
    assert _wait_until(lambda: loop.state == VoiceState.SPEAKING)

    # Loud frame should trigger barge-in and call provider.stop().
    assert loop.submit_audio_frame(b"\xff\x7f" * 1200) is True
    assert _wait_until(lambda: tts.stop_calls > 0)
    assert _wait_until(lambda: loop.state in (VoiceState.LISTENING, VoiceState.TRANSCRIBING, VoiceState.THINKING))
    loop.stop()
    assert "SPEAKING" in states


class _BoomAudioInput:
    @property
    def device_name(self) -> str:
        return "broken"

    def start(self) -> None:
        raise Exception("PortAudioError: Invalid device")

    def stop(self) -> None:
        return

    def read(self, timeout: float = 0.1):
        _ = timeout
        return None


def test_voice_loop_start_handles_unexpected_audio_input_exception():
    stt = MockSttProvider(transcripts=[])
    tts = MockTtsProvider(step_delay_s=0.005, total_steps=1)
    loop = VoiceLoop(
        stt_provider=stt,
        tts_provider=tts,
        config=VoiceConfig(),
        audio_input=_BoomAudioInput(),
    )

    assert loop.start() is False
    assert loop.state == VoiceState.ERROR
    assert "Invalid device" in loop.last_error


def test_voice_loop_push_to_talk_gates_capture_frames():
    stt = MockSttProvider(transcripts=["ptt"])
    tts = MockTtsProvider(step_delay_s=0.005, total_steps=1)
    loop = VoiceLoop(
        stt_provider=stt,
        tts_provider=tts,
        config=VoiceConfig(push_to_talk=True),
    )
    assert loop.start() is True

    # Push-to-talk blocks passive frames until explicitly activated.
    assert loop.submit_audio_frame(b"\x10\x00" * 1200) is False
    loop.set_push_to_talk_active(True)
    assert loop.submit_audio_frame(b"\x10\x00" * 1200) is True

    loop.stop()
