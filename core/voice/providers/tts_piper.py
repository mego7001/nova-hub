from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from typing import List, Optional

from core.voice.schemas import TtsResult


class PiperTtsProvider:
    def __init__(
        self,
        *,
        voice_id: Optional[str] = None,
        piper_bin: Optional[str] = None,
        sentence_pause_ms: Optional[int] = None,
    ) -> None:
        self._voice_id = str(voice_id or os.environ.get("VOICE_TTS_VOICE") or "").strip()
        self._piper_bin = str(piper_bin or os.environ.get("PIPER_BIN") or "piper").strip()
        self._sentence_pause_ms = max(0, int(sentence_pause_ms or os.environ.get("VOICE_TTS_PAUSE_MS") or 35))
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    @property
    def name(self) -> str:
        return "piper"

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
        model = self._resolve_model_path(voice_id)
        self._assert_piper_ready(model)
        started = time.perf_counter()
        self._stop_event.clear()

        chunks = self._split_sentences(payload)
        if not chunks:
            chunks = [payload]

        for chunk in chunks:
            if self._is_cancelled(cancel_event):
                break
            wav_path = self._synthesize_chunk(chunk, model)
            try:
                self._play_wav(wav_path, cancel_event)
            finally:
                try:
                    os.remove(wav_path)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
            if self._is_cancelled(cancel_event):
                break
            if self._sentence_pause_ms > 0:
                time.sleep(self._sentence_pause_ms / 1000.0)

        latency_ms = (time.perf_counter() - started) * 1000.0
        return TtsResult(ok=True, latency_ms=latency_ms, provider=self.name, metadata={"voice_id": model})

    def stop(self) -> None:
        self._stop_event.set()
        if os.name == "nt":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def _is_cancelled(self, cancel_event: Optional[threading.Event]) -> bool:
        return self._stop_event.is_set() or (cancel_event is not None and cancel_event.is_set())

    def _resolve_model_path(self, override: Optional[str]) -> str:
        model = str(override or self._voice_id or "").strip()
        if not model:
            raise RuntimeError(
                "Piper voice is not configured. Set VOICE_TTS_VOICE to a .onnx voice model path."
            )
        return model

    def _assert_piper_ready(self, model_path: str) -> None:
        piper_cmd = shutil.which(self._piper_bin) or (self._piper_bin if os.path.exists(self._piper_bin) else "")
        if not piper_cmd:
            raise RuntimeError(
                "Piper binary not found. Install Piper and set PIPER_BIN, or add piper to PATH."
            )
        if not os.path.exists(model_path):
            raise RuntimeError(
                f"Piper voice model not found: {model_path}. Download a .onnx voice and set VOICE_TTS_VOICE."
            )

    def _synthesize_chunk(self, text: str, model_path: str) -> str:
        piper_cmd = shutil.which(self._piper_bin) or self._piper_bin
        with tempfile.NamedTemporaryFile(prefix="nova_tts_", suffix=".wav", delete=False) as tmp:
            out_path = tmp.name
        cmd = [piper_cmd, "--model", model_path, "--output_file", out_path]
        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            try:
                os.remove(out_path)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
            raise RuntimeError(f"Failed to launch Piper: {exc}") from exc
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            try:
                os.remove(out_path)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
            raise RuntimeError(f"Piper synthesis failed: {err or 'unknown error'}")
        return out_path

    def _play_wav(self, wav_path: str, cancel_event: Optional[threading.Event]) -> None:
        if os.name == "nt":
            self._play_wav_windows(wav_path, cancel_event)
            return
        # Non-Windows fallback: keep behavior deterministic and dependency-free.
        # Audio output can be added by wiring platform players if needed.
        _ = (wav_path, cancel_event)

    def _play_wav_windows(self, wav_path: str, cancel_event: Optional[threading.Event]) -> None:
        try:
            import winsound
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            raise RuntimeError("winsound module is unavailable on this platform.") from exc

        duration_s = 0.0
        try:
            with wave.open(wav_path, "rb") as wf:
                frames = int(wf.getnframes())
                fr = int(wf.getframerate() or 22050)
                duration_s = max(0.0, frames / float(max(1, fr)))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            duration_s = 0.0

        with self._lock:
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        deadline = time.time() + duration_s + 0.25
        while time.time() < deadline:
            if self._is_cancelled(cancel_event):
                break
            time.sleep(0.02)
        if self._is_cancelled(cancel_event):
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+|\n+", str(text or "").strip())
        out = [p.strip() for p in parts if p and p.strip()]
        return out
