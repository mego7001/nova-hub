from __future__ import annotations

import os
import tempfile
import time
import wave
from typing import Any, Dict, List, Optional, Tuple

from core.voice.schemas import SttResult, SttSegment
from core.utils.optional_deps import require


class FasterWhisperSttProvider:
    def __init__(
        self,
        *,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ) -> None:
        self._model_name = str(model_name or os.environ.get("VOICE_STT_MODEL") or "small").strip()
        self._device = self._resolve_device(device)
        self._compute_type = str(compute_type or self._default_compute_type(self._device)).strip()
        self._model = None

    @property
    def name(self) -> str:
        return f"faster-whisper:{self._model_name}"

    def transcribe_stream(self, audio_pcm16: bytes, sample_rate: int) -> SttResult:
        data = bytes(audio_pcm16 or b"")
        if not data:
            return SttResult(text="", provider=self.name)
        sr = max(8000, int(sample_rate or 16000))
        with tempfile.NamedTemporaryFile(prefix="nova_voice_", suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(data)
            return self.transcribe_file(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                RuntimeError,
                ImportError,
            ):
                pass

    def transcribe_file(self, path: str) -> SttResult:
        started = time.perf_counter()
        model = self._ensure_model()
        segments: List[SttSegment] = []
        meta: Dict[str, Any] = {
            "model": self._model_name,
            "device": self._device,
            "compute_type": self._compute_type,
        }
        try:
            seg_iter, info = model.transcribe(
                path,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
                vad_filter=False,
            )
            text_parts: List[str] = []
            for seg in seg_iter:
                seg_text = str(getattr(seg, "text", "") or "").strip()
                if not seg_text:
                    continue
                start = float(getattr(seg, "start", 0.0) or 0.0)
                end = float(getattr(seg, "end", 0.0) or 0.0)
                segments.append(SttSegment(start=start, end=end, text=seg_text))
                text_parts.append(seg_text)
            if info is not None:
                lang = str(getattr(info, "language", "") or "").strip()
                if lang:
                    meta["language"] = lang
                try:
                    meta["language_probability"] = float(getattr(info, "language_probability", 0.0) or 0.0)
                except (
                    OSError,
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    RuntimeError,
                    ImportError,
                ):
                    pass
            latency_ms = (time.perf_counter() - started) * 1000.0
            return SttResult(
                text=" ".join(text_parts).strip(),
                segments=segments,
                latency_ms=latency_ms,
                provider=self.name,
                metadata=meta,
            )
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            ImportError,
        ) as exc:
            raise RuntimeError(f"faster-whisper transcription failed: {exc}") from exc

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        ok, msg = require(
            "faster_whisper",
            "pip install -r requirements-voice.txt",
            "voice STT",
        )
        if not ok:
            raise RuntimeError(
                "Missing dependency 'faster-whisper' (or backend runtime). "
                "Install with: pip install -r requirements-voice.txt"
            )
        try:
            from faster_whisper import WhisperModel
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            ImportError,
        ) as exc:
            raise RuntimeError(
                "Missing dependency 'faster-whisper' (or backend runtime). "
                "Install with: pip install -r requirements-voice.txt"
            ) from exc
        try:
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            ImportError,
        ) as exc:
            raise RuntimeError(
                f"Failed to load faster-whisper model '{self._model_name}' on device '{self._device}'."
            ) from exc
        return self._model

    @staticmethod
    def _resolve_device(device: Optional[str]) -> str:
        raw = str(device or os.environ.get("VOICE_STT_DEVICE") or "").strip().lower()
        if raw in ("cpu", "cuda", "auto"):
            if raw == "auto":
                return FasterWhisperSttProvider._cuda_or_cpu()
            return raw
        return FasterWhisperSttProvider._cuda_or_cpu()

    @staticmethod
    def _cuda_or_cpu() -> str:
        ok, _msg = require(
            "ctranslate2",
            "pip install -r requirements-voice.txt",
            "voice STT CUDA auto-detection",
        )
        if not ok:
            return "cpu"
        try:
            import ctranslate2  # type: ignore

            if int(ctranslate2.get_cuda_device_count()) > 0:
                return "cuda"
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            ImportError,
        ):
            pass
        return "cpu"

    @staticmethod
    def _default_compute_type(device: str) -> str:
        return "float16" if str(device).lower() == "cuda" else "int8"
