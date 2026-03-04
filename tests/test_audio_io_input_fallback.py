from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from core.voice.audio_io import AudioInputError, SoundDeviceAudioInput


class _FakePortAudioError(RuntimeError):
    pass


class _FakeRawInputStream:
    def __init__(self, *, should_fail: bool) -> None:
        self._should_fail = should_fail
        self._started = False

    def start(self) -> None:
        if self._should_fail:
            raise _FakePortAudioError("Error opening RawInputStream: Invalid device [PaErrorCode -9996]")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def close(self) -> None:
        self._started = False


def _build_sounddevice_module(*, fail_default: bool, fail_idx0: bool, fail_idx1: bool):
    devices = [
        {"name": "Mic-0", "max_input_channels": 1},
        {"name": "Mic-1", "max_input_channels": 1},
    ]

    def query_devices(device=None, kind=None):
        if device is None and kind is None:
            return devices
        if kind == "input":
            if device is None:
                return {"name": "Default Mic", "max_input_channels": 1}
            if device == 0:
                return devices[0]
            if device == 1:
                return devices[1]
            if str(device).strip() == "invalid-mic":
                raise _FakePortAudioError("Invalid device")
        return {"name": str(device or "default"), "max_input_channels": 1}

    def raw_input_stream(**kwargs):
        device = kwargs.get("device")
        if device is None:
            return _FakeRawInputStream(should_fail=fail_default)
        if device == 0:
            return _FakeRawInputStream(should_fail=fail_idx0)
        if device == 1:
            return _FakeRawInputStream(should_fail=fail_idx1)
        if str(device).strip() == "invalid-mic":
            return _FakeRawInputStream(should_fail=True)
        return _FakeRawInputStream(should_fail=False)

    return SimpleNamespace(query_devices=query_devices, RawInputStream=raw_input_stream)


def test_sounddevice_audio_input_auto_fallback_uses_first_valid_device(monkeypatch) -> None:
    fake_sd = _build_sounddevice_module(fail_default=True, fail_idx0=True, fail_idx1=False)
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    audio = SoundDeviceAudioInput(sample_rate=16000, device="invalid-mic")
    audio.start()
    try:
        assert audio.device_name == "Mic-1"
    finally:
        audio.stop()


def test_sounddevice_audio_input_raises_when_all_candidates_fail(monkeypatch) -> None:
    fake_sd = _build_sounddevice_module(fail_default=True, fail_idx0=True, fail_idx1=True)
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    audio = SoundDeviceAudioInput(sample_rate=16000, device="invalid-mic")
    with pytest.raises(AudioInputError, match="Unable to start microphone capture"):
        audio.start()
