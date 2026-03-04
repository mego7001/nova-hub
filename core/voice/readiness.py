from __future__ import annotations

import importlib.util
import os
import shutil
from typing import Any, Dict, List

from core.voice.audio_io import list_input_devices


def probe_voice_readiness(sample_rate: int = 16000) -> Dict[str, Any]:
    deps = {
        "faster_whisper": bool(importlib.util.find_spec("faster_whisper")),
        "sounddevice": bool(importlib.util.find_spec("sounddevice")),
        "pyttsx3": bool(importlib.util.find_spec("pyttsx3")),
    }
    piper_binary = bool(shutil.which("piper"))
    configured_voice = str(os.environ.get("VOICE_TTS_VOICE") or "").strip()
    configured_voice_exists = bool(configured_voice and os.path.exists(configured_voice))

    try:
        devices = list_input_devices()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, ImportError, ModuleNotFoundError):
        devices = ["default"]

    issues: List[str] = []
    if not deps["faster_whisper"]:
        issues.append("missing dependency: faster_whisper")
    if not deps["sounddevice"]:
        issues.append("missing dependency: sounddevice")
    if not piper_binary and not deps["pyttsx3"]:
        issues.append("no TTS backend: install Piper binary or pyttsx3")
    if configured_voice and not configured_voice_exists:
        issues.append("configured VOICE_TTS_VOICE path does not exist")
    if not devices:
        issues.append("no input devices detected")

    status = "ready" if not issues else "degraded"
    return {
        "status": status,
        "sample_rate": int(sample_rate or 16000),
        "dependencies": deps,
        "tts": {
            "piper_binary_found": piper_binary,
            "voice_path": configured_voice,
            "voice_path_exists": configured_voice_exists,
        },
        "devices": list(devices or ["default"]),
        "issues": issues,
    }
