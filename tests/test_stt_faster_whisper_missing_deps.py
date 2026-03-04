from __future__ import annotations

import builtins

import pytest

from core.voice.providers.stt_faster_whisper import FasterWhisperSttProvider


def test_cuda_or_cpu_missing_ctranslate2_returns_cpu(monkeypatch) -> None:
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "ctranslate2":
            raise ModuleNotFoundError("No module named 'ctranslate2'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    assert FasterWhisperSttProvider._cuda_or_cpu() == "cpu"


def test_ensure_model_missing_faster_whisper_raises_runtime_error(monkeypatch) -> None:
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("missing faster_whisper")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    provider = FasterWhisperSttProvider(model_name="small", device="cpu")
    with pytest.raises(RuntimeError, match="Missing dependency 'faster-whisper'"):
        provider._ensure_model()
