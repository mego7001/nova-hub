from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Dict, Optional

from .audio_io import IAudioInput
from .schemas import ISttProvider, ITtsProvider, VoiceConfig, VoiceState
from .vad import EnergyTurnDetector, EnergyVAD


class VoiceLoop:
    def __init__(
        self,
        *,
        stt_provider: ISttProvider,
        tts_provider: ITtsProvider,
        config: Optional[VoiceConfig] = None,
        audio_input: Optional[IAudioInput] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_state_changed: Optional[Callable[[VoiceState], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._stt_provider = stt_provider
        self._tts_provider = tts_provider
        self._config = config or VoiceConfig()
        self._audio_input = audio_input
        self._on_transcript = on_transcript
        self._on_state_changed = on_state_changed
        self._on_error = on_error

        self.audio_in: "queue.Queue[bytes]" = queue.Queue(maxsize=512)
        self.transcripts_out: "queue.Queue[str]" = queue.Queue(maxsize=128)
        self.tts_out: "queue.Queue[str]" = queue.Queue(maxsize=128)
        self._stt_in: "queue.Queue[bytes]" = queue.Queue(maxsize=128)

        self._state = VoiceState.IDLE
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._tts_cancel = threading.Event()
        self._stt_cancel = threading.Event()
        self._running = False
        self._muted = False
        self._last_error = ""
        self._last_transcript = ""
        self._last_spoken_text = ""
        self._last_assistant_text = ""
        self._last_stt_latency_ms = 0.0
        self._last_tts_latency_ms = 0.0
        self._last_capture_latency_ms = 0.0
        self._last_llm_latency_ms = 0.0
        self._last_playback_latency_ms = 0.0
        self._barge_in_count = 0
        self._push_to_talk_active = not bool(self._config.push_to_talk)

        self._vad = EnergyVAD(threshold=self._config.vad_energy_threshold)
        self._turn_detector = EnergyTurnDetector(
            vad=self._vad,
            min_speech_ms=self._config.vad_min_speech_ms,
            silence_ms=self._config.vad_silence_ms,
        )
        self._threads: list[threading.Thread] = []

    @property
    def state(self) -> VoiceState:
        with self._state_lock:
            return self._state

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def last_transcript(self) -> str:
        return self._last_transcript

    @property
    def last_spoken_text(self) -> str:
        return self._last_spoken_text

    @property
    def provider_summary(self) -> str:
        return f"STT={self._stt_provider.name}, TTS={self._tts_provider.name}"

    @property
    def device_name(self) -> str:
        if self._audio_input is None:
            return "none"
        try:
            return str(self._audio_input.device_name or "default")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return "default"

    def status_snapshot(self) -> Dict[str, str]:
        return {
            "state": self.state.value,
            "providers": self.provider_summary,
            "device": self.device_name,
            "last_error": self._last_error,
            "last_transcript": self._last_transcript,
            "last_spoken_text": self._last_spoken_text,
            "stt_latency_ms": f"{self._last_stt_latency_ms:.1f}",
            "tts_latency_ms": f"{self._last_tts_latency_ms:.1f}",
            "capture_latency_ms": f"{self._last_capture_latency_ms:.1f}",
            "llm_latency_ms": f"{self._last_llm_latency_ms:.1f}",
            "playback_latency_ms": f"{self._last_playback_latency_ms:.1f}",
            "barge_in_count": str(self._barge_in_count),
            "push_to_talk": str(bool(self._config.push_to_talk)).lower(),
            "push_to_talk_active": str(bool(self._push_to_talk_active)).lower(),
        }

    def note_llm_latency(self, latency_ms: float) -> None:
        try:
            self._last_llm_latency_ms = max(0.0, float(latency_ms))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            self._last_llm_latency_ms = 0.0

    def start(self) -> bool:
        if self._running:
            return True
        self._stop_event.clear()
        self._stt_cancel.clear()
        self._tts_cancel.clear()
        self._last_error = ""
        self._push_to_talk_active = not bool(self._config.push_to_talk)
        self._turn_detector.reset()
        try:
            if self._audio_input is not None:
                self._audio_input.start()
        except Exception as exc:
            self._set_state(VoiceState.ERROR)
            self._report_error(str(exc))
            self._running = False
            return False

        self._running = True
        self._threads = []
        if self._audio_input is not None:
            self._spawn(self._audio_reader_loop, "voice-audio-reader")
        self._spawn(self._audio_ingest_loop, "voice-audio-ingest")
        self._spawn(self._stt_loop, "voice-stt")
        self._spawn(self._transcript_loop, "voice-transcript")
        self._spawn(self._tts_loop, "voice-tts")
        self._set_state(VoiceState.LISTENING)
        return True

    def stop(self) -> None:
        if not self._running:
            self._set_state(VoiceState.IDLE)
            return
        self._stop_event.set()
        self.stop_speaking()
        if self._audio_input is not None:
            try:
                self._audio_input.stop()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        for th in list(self._threads):
            th.join(timeout=1.2)
        self._threads = []
        self._running = False
        self._set_state(VoiceState.IDLE)

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        if self._muted:
            self.stop_speaking()

    def set_push_to_talk_active(self, active: bool) -> None:
        self._push_to_talk_active = bool(active)

    def stop_speaking(self) -> None:
        self._tts_cancel.set()
        try:
            self._tts_provider.stop()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        if self.state == VoiceState.SPEAKING and not self._stop_event.is_set():
            self._set_state(VoiceState.LISTENING)

    def replay_last(self) -> bool:
        if not self._last_spoken_text:
            return False
        return self.enqueue_tts(self._last_spoken_text)

    def enqueue_tts(self, text: str) -> bool:
        payload = str(text or "").strip()
        if not payload or self._muted:
            return False
        return self._offer(self.tts_out, payload)

    def notify_assistant_text(self, text: str) -> bool:
        self._last_assistant_text = str(text or "").strip()
        if not self._last_assistant_text:
            return False
        return self.enqueue_tts(self._last_assistant_text)

    def submit_audio_frame(self, pcm16: bytes) -> bool:
        chunk = bytes(pcm16 or b"")
        if not chunk:
            return False
        if bool(self._config.push_to_talk) and not bool(self._push_to_talk_active):
            return False
        if self.state == VoiceState.SPEAKING and self._vad.is_speech(chunk):
            self._barge_in_count += 1
            self.stop_speaking()
        return self._offer(self.audio_in, chunk)

    def submit_audio_utterance(self, pcm16: bytes) -> bool:
        utterance = bytes(pcm16 or b"")
        if not utterance:
            return False
        return self._offer(self._stt_in, utterance)

    def _spawn(self, target: Callable[[], None], name: str) -> None:
        th = threading.Thread(target=target, name=name, daemon=True)
        self._threads.append(th)
        th.start()

    def _set_state(self, state: VoiceState) -> None:
        with self._state_lock:
            if self._state == state:
                return
            self._state = state
        if self._on_state_changed is not None:
            try:
                self._on_state_changed(state)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return

    def _report_error(self, text: str) -> None:
        msg = str(text or "").strip()
        if not msg:
            return
        self._last_error = msg
        if self._on_error is not None:
            try:
                self._on_error(msg)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return

    @staticmethod
    def _offer(q: "queue.Queue[str] | queue.Queue[bytes]", item) -> bool:
        try:
            q.put_nowait(item)
            return True
        except queue.Full:
            try:
                _ = q.get_nowait()
            except queue.Empty:
                return False
            try:
                q.put_nowait(item)
                return True
            except queue.Full:
                return False

    def _audio_reader_loop(self) -> None:
        assert self._audio_input is not None
        while not self._stop_event.is_set():
            try:
                chunk = self._audio_input.read(timeout=0.08)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                self._set_state(VoiceState.ERROR)
                self._report_error(f"Microphone read failed: {exc}")
                time.sleep(0.1)
                continue
            if not chunk:
                continue
            self.submit_audio_frame(chunk)

    def _audio_ingest_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                chunk = self.audio_in.get(timeout=0.08)
            except queue.Empty:
                continue
            if not chunk:
                continue
            started = time.perf_counter()
            utterances = self._turn_detector.consume(chunk, self._config.sample_rate)
            for utterance in utterances:
                self._offer(self._stt_in, utterance)
            if utterances:
                self._last_capture_latency_ms = (time.perf_counter() - started) * 1000.0

    def _stt_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                utterance = self._stt_in.get(timeout=0.08)
            except queue.Empty:
                continue
            if not utterance:
                continue
            self._stt_cancel.clear()
            self._set_state(VoiceState.TRANSCRIBING)
            try:
                result = self._stt_provider.transcribe_stream(utterance, self._config.sample_rate)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                self._set_state(VoiceState.ERROR)
                self._report_error(f"STT failed: {exc}")
                continue

            self._last_stt_latency_ms = float(result.latency_ms or 0.0)
            text = str(result.text or "").strip()
            if not text:
                self._set_state(VoiceState.LISTENING)
                continue
            self._last_transcript = text
            self._set_state(VoiceState.THINKING)
            self._offer(self.transcripts_out, text)

    def _transcript_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self.transcripts_out.get(timeout=0.08)
            except queue.Empty:
                continue
            if self._on_transcript is None:
                continue
            try:
                self._on_transcript(str(text))
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                self._report_error(f"Transcript callback failed: {exc}")

    def _tts_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self.tts_out.get(timeout=0.08)
            except queue.Empty:
                continue
            payload = str(text or "").strip()
            if not payload or self._muted:
                continue

            self._tts_cancel.clear()
            self._set_state(VoiceState.SPEAKING)
            started = time.perf_counter()
            try:
                result = self._tts_provider.speak(
                    payload,
                    cancel_event=self._tts_cancel,
                    voice_id=self._config.tts_voice,
                    sample_rate=self._config.sample_rate,
                )
                self._last_tts_latency_ms = float(result.latency_ms or 0.0)
                self._last_playback_latency_ms = self._last_tts_latency_ms
                self._last_spoken_text = payload
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                self._set_state(VoiceState.ERROR)
                self._report_error(f"TTS failed: {exc}")
                continue
            finally:
                if self._last_tts_latency_ms <= 0.0:
                    self._last_tts_latency_ms = (time.perf_counter() - started) * 1000.0
            if not self._stop_event.is_set():
                self._set_state(VoiceState.LISTENING)
