from __future__ import annotations

import socket
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

from .protocol import (
    DEFAULT_HOST,
    MAX_MESSAGE_BYTES,
    make_request,
    parse_message_line,
    resolve_ipc_events_port,
    resolve_ipc_port,
    resolve_ipc_token,
    serialize_message,
)


class IpcClient:
    def __init__(
        self,
        *,
        host: str = DEFAULT_HOST,
        port: int | None = None,
        token: str | None = None,
        timeout_s: float = 2.0,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        self.host = str(host or DEFAULT_HOST)
        self.port = int(resolve_ipc_port(port))
        self.token = resolve_ipc_token() if token is None else str(token or "")
        self.timeout_s = float(timeout_s)
        self.max_message_bytes = int(max_message_bytes)

    def _readline(self, fp) -> bytes:
        raw = fp.readline(self.max_message_bytes + 1)
        if not raw:
            raise RuntimeError("connection closed")
        if len(raw) > self.max_message_bytes and not raw.endswith(b"\n"):
            raise RuntimeError("incoming message too large")
        return raw

    def call(self, op: str, payload: Optional[Dict[str, Any]] = None, *, req_id: str | None = None) -> Dict[str, Any]:
        request_id = str(req_id or uuid.uuid4().hex)
        req = make_request(str(op or ""), payload or {}, request_id)

        with socket.create_connection((self.host, self.port), timeout=self.timeout_s) as sock:
            sock.settimeout(self.timeout_s)
            with sock.makefile("rwb", buffering=0) as fp:
                hello: Dict[str, Any] = {"type": "hello"}
                if self.token:
                    hello["token"] = self.token
                fp.write(serialize_message(hello, max_bytes=self.max_message_bytes))
                hello_ack = parse_message_line(self._readline(fp), max_bytes=self.max_message_bytes)
                if str(hello_ack.get("type") or "") != "hello" or not bool(hello_ack.get("ok")):
                    msg = ""
                    err = hello_ack.get("error")
                    if isinstance(err, dict):
                        msg = str(err.get("message") or "")
                    raise RuntimeError(msg or "IPC handshake failed")

                fp.write(serialize_message(req, max_bytes=self.max_message_bytes))
                while True:
                    msg = parse_message_line(self._readline(fp), max_bytes=self.max_message_bytes)
                    typ = str(msg.get("type") or "")
                    if typ == "event":
                        continue
                    if typ != "response":
                        continue
                    if str(msg.get("id") or "") != request_id:
                        continue
                    return msg

    def call_ok(self, op: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self.call(op, payload or {})
        if bool(res.get("ok")):
            out = res.get("result")
            return out if isinstance(out, dict) else {"value": out}
        err = res.get("error")
        if isinstance(err, dict):
            raise RuntimeError(str(err.get("message") or "IPC request failed"))
        raise RuntimeError("IPC request failed")


class EventsClient:
    def __init__(
        self,
        *,
        host: str = DEFAULT_HOST,
        port: int | None = None,
        token: str | None = None,
        timeout_s: float = 2.0,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
        reconnect: bool = True,
        backoff_initial_s: float = 0.2,
        backoff_max_s: float = 2.0,
        ensure_running: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.host = str(host or DEFAULT_HOST)
        self.port = int(resolve_ipc_events_port(port))
        self.token = resolve_ipc_token() if token is None else str(token or "")
        self.timeout_s = float(timeout_s)
        self.max_message_bytes = int(max_message_bytes)
        self.reconnect = bool(reconnect)
        self.backoff_initial_s = max(0.05, float(backoff_initial_s))
        self.backoff_max_s = max(self.backoff_initial_s, float(backoff_max_s))
        self.ensure_running = ensure_running

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sock_lock = threading.Lock()
        self._sock: Optional[socket.socket] = None
        self._fp = None
        self._session_id = ""
        self._project_id = ""
        self._on_event: Optional[Callable[[Dict[str, Any]], None]] = None
        self._on_connected: Optional[Callable[[], None]] = None
        self._on_disconnected: Optional[Callable[[str], None]] = None
        self._connected = False

    def _readline(self, fp) -> bytes:
        raw = fp.readline(self.max_message_bytes + 1)
        if not raw:
            raise RuntimeError("events connection closed")
        if len(raw) > self.max_message_bytes and not raw.endswith(b"\n"):
            raise RuntimeError("incoming events message too large")
        return raw

    def _send_json(self, payload: Dict[str, Any]) -> None:
        blob = serialize_message(payload, max_bytes=self.max_message_bytes)
        with self._sock_lock:
            if self._fp is None:
                raise RuntimeError("events client is not connected")
            self._fp.write(blob)

    def _handshake(self, fp) -> None:
        hello: Dict[str, Any] = {"type": "hello"}
        if self.token:
            hello["token"] = self.token
        fp.write(serialize_message(hello, max_bytes=self.max_message_bytes))
        hello_ack = parse_message_line(self._readline(fp), max_bytes=self.max_message_bytes)
        if str(hello_ack.get("type") or "") != "hello" or not bool(hello_ack.get("ok")):
            msg = ""
            err = hello_ack.get("error")
            if isinstance(err, dict):
                msg = str(err.get("message") or "")
            raise RuntimeError(msg or "events IPC handshake failed")

    def _subscribe_current(self, fp) -> None:
        subscribe_msg = {
            "type": "subscribe",
            "session_id": str(self._session_id or ""),
            "project_id": str(self._project_id or ""),
        }
        fp.write(serialize_message(subscribe_msg, max_bytes=self.max_message_bytes))
        ack = parse_message_line(self._readline(fp), max_bytes=self.max_message_bytes)
        if str(ack.get("type") or "") != "subscribe" or not bool(ack.get("ok")):
            msg = ""
            err = ack.get("error")
            if isinstance(err, dict):
                msg = str(err.get("message") or "")
            raise RuntimeError(msg or "events subscribe failed")

    def start(
        self,
        *,
        session_id: str,
        project_id: str,
        on_event: Callable[[Dict[str, Any]], None],
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._session_id = str(session_id or "")
        self._project_id = str(project_id or "")
        self._on_event = on_event
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        if self._thread is not None and self._thread.is_alive():
            self.subscribe(self._session_id, self._project_id)
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def subscribe(self, session_id: str, project_id: str) -> None:
        self._session_id = str(session_id or "")
        self._project_id = str(project_id or "")
        if not self._connected:
            return
        try:
            self._send_json(
                {
                    "type": "subscribe",
                    "session_id": self._session_id,
                    "project_id": self._project_id,
                }
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _disconnect(self, reason: str = "") -> None:
        with self._sock_lock:
            fp = self._fp
            sock = self._sock
            self._fp = None
            self._sock = None
        self._connected = False
        try:
            if fp is not None:
                fp.close()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        try:
            if sock is not None:
                sock.close()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        if self._on_disconnected:
            try:
                self._on_disconnected(reason)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def stop(self) -> None:
        self._stop_event.set()
        self._disconnect("stopped")
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        backoff = self.backoff_initial_s
        while not self._stop_event.is_set():
            try:
                if self.ensure_running is not None:
                    self.ensure_running()
                sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
                sock.settimeout(self.timeout_s)
                fp = sock.makefile("rwb", buffering=0)
                self._handshake(fp)
                self._subscribe_current(fp)
                with self._sock_lock:
                    self._sock = sock
                    self._fp = fp
                self._connected = True
                if self._on_connected:
                    try:
                        self._on_connected()
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                        pass
                backoff = self.backoff_initial_s
                idle_timeout_streak = 0

                def _reopen_reader(current_fp):
                    try:
                        current_fp.close()
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                        pass
                    reopened = sock.makefile("rwb", buffering=0)
                    with self._sock_lock:
                        self._fp = reopened
                    return reopened

                while not self._stop_event.is_set():
                    try:
                        raw = self._readline(fp)
                    except (socket.timeout, TimeoutError):
                        idle_timeout_streak += 1
                        fp = _reopen_reader(fp)
                        if self.reconnect and self.ensure_running is not None and idle_timeout_streak >= 4:
                            raise RuntimeError("events idle timeout")
                        continue
                    except OSError as exc:
                        # Buffered socket readers can surface timeout as OSError.
                        if "timed out" in str(exc).lower():
                            idle_timeout_streak += 1
                            fp = _reopen_reader(fp)
                            if self.reconnect and self.ensure_running is not None and idle_timeout_streak >= 4:
                                raise RuntimeError("events idle timeout")
                            continue
                        raise
                    idle_timeout_streak = 0
                    msg = parse_message_line(raw, max_bytes=self.max_message_bytes)
                    typ = str(msg.get("type") or "")
                    if typ == "event":
                        if self._on_event:
                            try:
                                self._on_event(msg)
                            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                                pass
                        continue
                    # Subscribe ack/pong/noise are intentionally ignored.
                    continue
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                if self._stop_event.is_set():
                    break
                self._disconnect(str(exc))
                if not self.reconnect:
                    break
                if self.ensure_running is not None:
                    try:
                        self.ensure_running()
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                        pass
                time.sleep(backoff)
                backoff = min(self.backoff_max_s, backoff * 2.0)
            else:
                # Read loop exited cleanly without explicit stop: reconnect.
                if self._stop_event.is_set():
                    break
                self._disconnect("events stream ended")
                if not self.reconnect:
                    break
                time.sleep(backoff)
                backoff = min(self.backoff_max_s, backoff * 2.0)
