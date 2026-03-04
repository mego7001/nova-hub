from __future__ import annotations

import os
import wave
from typing import Any, Dict, Tuple


def detect_tts() -> bool:
    try:
        import pyttsx3  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError, OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False


def detect_stt() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError, OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False


def record_audio(path: str, seconds: int = 4, sample_rate: int = 16000) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # try real recording
    try:
        import numpy as np
        import sounddevice as sd

        duration = max(1, int(seconds))
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())
        return {"status": "ok", "audio_path": path, "seconds": duration, "engine": "sounddevice"}
    except (ImportError, ModuleNotFoundError, OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        # fallback: write silence
        duration = max(1, int(seconds))
        frames = b"\x00\x00" * sample_rate * duration
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(frames)
        return {"status": "unavailable", "audio_path": path, "seconds": duration, "engine": "silent"}


def transcribe_audio(path: str) -> Tuple[str, Dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _info = model.transcribe(path)
        parts = [s.text.strip() for s in segments if s.text]
        text = " ".join(parts).strip()
        return text, {"status": "ok", "engine": "faster_whisper"}
    except (ImportError, ModuleNotFoundError, OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return "", {"status": "unavailable", "engine": "none"}


def speak_text(text: str) -> Dict[str, Any]:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return {"status": "ok", "engine": "pyttsx3"}
    except (ImportError, ModuleNotFoundError, OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {"status": "unavailable", "engine": "none"}
