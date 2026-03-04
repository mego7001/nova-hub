from __future__ import annotations

import queue
import threading
from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable

from core.utils.optional_deps import require


class AudioInputError(RuntimeError):
    pass


@runtime_checkable
class IAudioInput(Protocol):
    @property
    def device_name(self) -> str:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def read(self, timeout: float = 0.1) -> Optional[bytes]:
        ...


class QueueAudioInput:
    def __init__(self) -> None:
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=512)
        self._started = False

    @property
    def device_name(self) -> str:
        return "queue://manual"

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def push(self, pcm16: bytes) -> None:
        if not self._started or not pcm16:
            return
        try:
            self._queue.put_nowait(bytes(pcm16))
        except queue.Full:
            try:
                _ = self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(bytes(pcm16))
            except queue.Full:
                return

    def read(self, timeout: float = 0.1) -> Optional[bytes]:
        if not self._started:
            return None
        try:
            return self._queue.get(timeout=max(0.01, float(timeout)))
        except queue.Empty:
            return None


def list_input_devices() -> List[str]:
    ok, _msg = require(
        "sounddevice",
        "pip install -r requirements-voice.txt",
        "voice input",
    )
    if not ok:
        return []
    import sounddevice as sd
    out: List[str] = []
    try:
        devices = sd.query_devices()
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
        ImportError,
    ):
        return []
    for idx, item in enumerate(devices):
        try:
            max_in = int(item.get("max_input_channels") or 0)
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            ImportError,
        ):
            max_in = 0
        if max_in <= 0:
            continue
        name = str(item.get("name") or f"device-{idx}")
        out.append(name)
    return out


def _collect_input_device_entries(sd: Any) -> List[Tuple[int, str]]:
    entries: List[Tuple[int, str]] = []
    try:
        devices = sd.query_devices()
    except Exception:
        return entries
    for idx, item in enumerate(devices):
        try:
            max_in = int(item.get("max_input_channels") or 0)
        except Exception:
            max_in = 0
        if max_in <= 0:
            continue
        name = str(item.get("name") or f"device-{idx}").strip() or f"device-{idx}"
        entries.append((idx, name))
    return entries


class SoundDeviceAudioInput:
    def __init__(self, *, sample_rate: int, device: str = "default", block_size: int = 1600) -> None:
        self._sample_rate = max(8000, int(sample_rate))
        self._device = str(device or "default")
        self._block_size = max(160, int(block_size))
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=512)
        self._stream = None
        self._started = False
        self._lock = threading.Lock()
        self._device_name = self._device

    @property
    def device_name(self) -> str:
        return self._device_name

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            ok, msg = require(
                "sounddevice",
                "pip install -r requirements-voice.txt",
                "voice input",
            )
            if not ok:
                raise AudioInputError(msg)
            import sounddevice as sd

            input_entries = _collect_input_device_entries(sd)
            if not input_entries:
                raise AudioInputError("No input audio devices were detected.")

            requested = str(self._device or "").strip()
            requested_is_default = requested.lower() in ("", "default", "system")
            candidates: List[Tuple[str, Any, str]] = []
            if requested_is_default:
                candidates.append(("default", None, "default"))
            else:
                candidates.append((requested, requested, requested))
                candidates.append(("default", None, "default"))
            for idx, name in input_entries:
                candidates.append((name, idx, name))

            deduped_candidates: List[Tuple[str, Any, str]] = []
            seen = set()
            for label, open_value, persisted_name in candidates:
                key = "<default>" if open_value is None else str(open_value).strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped_candidates.append((label, open_value, persisted_name))

            def _callback(indata, _frames, _time_info, _status) -> None:
                chunk = bytes(indata or b"")
                if not chunk:
                    return
                try:
                    self._queue.put_nowait(chunk)
                except queue.Full:
                    try:
                        _ = self._queue.get_nowait()
                    except queue.Empty:
                        return
                    try:
                        self._queue.put_nowait(chunk)
                    except queue.Full:
                        return

            last_exc: Optional[Exception] = None
            last_label = ""
            for label, open_value, persisted_name in deduped_candidates:
                stream = None
                try:
                    stream = sd.RawInputStream(
                        samplerate=self._sample_rate,
                        channels=1,
                        dtype="int16",
                        blocksize=self._block_size,
                        device=open_value,
                        callback=_callback,
                    )
                    stream.start()
                    self._stream = stream
                    self._device_name = str(persisted_name or "default")
                    self._started = True
                    return
                except Exception as exc:
                    last_exc = exc
                    last_label = label
                    try:
                        if stream is not None:
                            stream.close()
                    except Exception:
                        pass
                    self._stream = None
                    continue

            reason = str(last_exc or "unknown audio backend error").strip()
            msg = (
                "Unable to start microphone capture. "
                f"Requested device='{self._device}'. Last tried='{last_label}'. Last error: {reason}"
            )
            raise AudioInputError(msg) from last_exc

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            stream = self._stream
            self._stream = None
            self._started = False
        if stream is not None:
            try:
                stream.stop()
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
            try:
                stream.close()
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
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def read(self, timeout: float = 0.1) -> Optional[bytes]:
        if not self._started:
            return None
        try:
            return self._queue.get(timeout=max(0.01, float(timeout)))
        except queue.Empty:
            return None
