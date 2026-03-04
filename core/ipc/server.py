from __future__ import annotations

from collections import defaultdict
import socketserver
import threading
from typing import Any, Callable, Dict, Optional, Set, Tuple

from .protocol import MAX_MESSAGE_BYTES, make_event, make_response, parse_message_line, serialize_message


DispatchFn = Callable[[str, Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class _LocalRequestMixin:
    def _send(self, payload: Dict[str, Any]) -> None:
        self.wfile.write(serialize_message(payload, max_bytes=self.server.max_message_bytes))
        self.wfile.flush()

    def _readline(self) -> Optional[bytes]:
        raw = self.rfile.readline(self.server.max_message_bytes + 1)
        if not raw:
            return None
        if len(raw) > self.server.max_message_bytes and not raw.endswith(b"\n"):
            raise ValueError("message too large")
        return raw

    def _peer_allowed(self) -> bool:
        peer_ip = str(self.client_address[0] if self.client_address else "")
        return peer_ip in ("127.0.0.1", "::1")

    def _read_hello(self) -> bool:
        raw = self._readline()
        if raw is None:
            return False
        msg = parse_message_line(raw, max_bytes=self.server.max_message_bytes)
        if str(msg.get("type") or "") != "hello":
            self._send(
                {
                    "type": "hello",
                    "ok": False,
                    "error": {"message": "expected hello handshake"},
                }
            )
            return False
        expected_token = str(self.server.token or "")
        got_token = str(msg.get("token") or "")
        if expected_token and got_token != expected_token:
            self._send(
                {
                    "type": "hello",
                    "ok": False,
                    "error": {"message": "token mismatch"},
                }
            )
            return False
        self._send({"type": "hello", "ok": True})
        return True


class _ThreadingLocalServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        dispatcher: DispatchFn,
        *,
        token: str = "",
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        self.dispatcher = dispatcher
        self.token = str(token or "")
        self.max_message_bytes = int(max_message_bytes)
        super().__init__(server_address, _IpcRequestHandler)


class _IpcRequestHandler(_LocalRequestMixin, socketserver.StreamRequestHandler):
    def handle(self) -> None:
        if not self._peer_allowed():
            return
        try:
            if not self._read_hello():
                return
            while True:
                raw = self._readline()
                if raw is None:
                    return
                try:
                    msg = parse_message_line(raw, max_bytes=self.server.max_message_bytes)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                    self._send(
                        make_response(
                            "",
                            ok=False,
                            error={"message": f"invalid message: {exc}"},
                        )
                    )
                    continue
                if str(msg.get("type") or "") != "request":
                    self._send(
                        make_response(
                            str(msg.get("id") or ""),
                            ok=False,
                            error={"message": "expected request message"},
                        )
                    )
                    continue
                req_id = str(msg.get("id") or "")
                op = str(msg.get("op") or "")
                payload = msg.get("payload")
                if not isinstance(payload, dict):
                    payload = {}
                ctx = {
                    "peer": str(self.client_address[0] if self.client_address else ""),
                    "port": int(self.server.server_address[1]),
                }
                try:
                    result = self.server.dispatcher(op, payload, ctx)
                    if not isinstance(result, dict):
                        result = {"value": result}
                    self._send(make_response(req_id, ok=True, result=result))
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                    self._send(make_response(req_id, ok=False, error={"message": str(exc)}))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return


class _ThreadingEventsServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        token: str = "",
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        self.token = str(token or "")
        self.max_message_bytes = int(max_message_bytes)
        self._subscribers: Dict[Tuple[str, str], Set[_EventsRequestHandler]] = defaultdict(set)
        self._sub_lock = threading.Lock()
        super().__init__(server_address, _EventsRequestHandler)

    def add_subscriber(self, session_id: str, project_id: str, handler: "_EventsRequestHandler") -> None:
        key = (str(session_id or ""), str(project_id or ""))
        with self._sub_lock:
            self._subscribers[key].add(handler)

    def remove_subscriber(self, handler: "_EventsRequestHandler") -> None:
        with self._sub_lock:
            to_drop: list[Tuple[str, str]] = []
            for key, handlers in self._subscribers.items():
                handlers.discard(handler)
                if not handlers:
                    to_drop.append(key)
            for key in to_drop:
                self._subscribers.pop(key, None)

    def publish_event(self, *, session_id: str, project_id: str, topic: str, data: Dict[str, Any] | None = None) -> int:
        event = make_event(topic, data, session_id=session_id, project_id=project_id)
        keys = {
            (str(session_id or ""), str(project_id or "")),
            (str(session_id or ""), ""),
            ("", str(project_id or "")),
            ("", ""),
        }
        targets: Set[_EventsRequestHandler] = set()
        with self._sub_lock:
            for key in keys:
                targets.update(self._subscribers.get(key, set()))
        if not targets:
            return 0
        sent = 0
        dead: list[_EventsRequestHandler] = []
        for handler in targets:
            try:
                handler.send_event(event)
                sent += 1
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                dead.append(handler)
        if dead:
            with self._sub_lock:
                for handler in dead:
                    for handlers in self._subscribers.values():
                        handlers.discard(handler)
        return sent


class _EventsRequestHandler(_LocalRequestMixin, socketserver.StreamRequestHandler):
    def setup(self) -> None:
        super().setup()
        self._write_lock = threading.Lock()
        self._subscribed = False

    def send_event(self, payload: Dict[str, Any]) -> None:
        with self._write_lock:
            self._send(payload)

    def _send_subscribe_ack(self, *, ok: bool, session_id: str = "", project_id: str = "", message: str = "") -> None:
        out: Dict[str, Any] = {"type": "subscribe", "ok": bool(ok), "session_id": str(session_id or ""), "project_id": str(project_id or "")}
        if not ok:
            out["error"] = {"message": message or "subscribe failed"}
        self.send_event(out)

    def handle(self) -> None:
        if not self._peer_allowed():
            return
        try:
            if not self._read_hello():
                return
            while True:
                raw = self._readline()
                if raw is None:
                    return
                try:
                    msg = parse_message_line(raw, max_bytes=self.server.max_message_bytes)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                    self._send_subscribe_ack(ok=False, message=f"invalid message: {exc}")
                    continue
                if str(msg.get("type") or "") != "subscribe":
                    self._send_subscribe_ack(ok=False, message="expected subscribe message")
                    continue
                session_id = str(msg.get("session_id") or "")
                project_id = str(msg.get("project_id") or "")
                self.server.remove_subscriber(self)
                self.server.add_subscriber(session_id, project_id, self)
                self._subscribed = True
                self._send_subscribe_ack(ok=True, session_id=session_id, project_id=project_id)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return
        finally:
            if self._subscribed:
                self.server.remove_subscriber(self)


class LocalIpcServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        dispatcher: DispatchFn,
        token: str = "",
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        self._server = _ThreadingLocalServer(
            (host, int(port)),
            dispatcher,
            token=token,
            max_message_bytes=max_message_bytes,
        )
        self._thread: Optional[threading.Thread] = None

    @property
    def host(self) -> str:
        return str(self._server.server_address[0])

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def serve_forever(self, poll_interval: float = 0.2) -> None:
        self._server.serve_forever(poll_interval=poll_interval)

    def start_in_thread(self, poll_interval: float = 0.2) -> threading.Thread:
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(
            target=self.serve_forever,
            kwargs={"poll_interval": poll_interval},
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def shutdown(self) -> None:
        try:
            self._server.shutdown()
        finally:
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


class LocalEventsServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        token: str = "",
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        self._server = _ThreadingEventsServer(
            (host, int(port)),
            token=token,
            max_message_bytes=max_message_bytes,
        )
        self._thread: Optional[threading.Thread] = None

    @property
    def host(self) -> str:
        return str(self._server.server_address[0])

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def serve_forever(self, poll_interval: float = 0.2) -> None:
        self._server.serve_forever(poll_interval=poll_interval)

    def start_in_thread(self, poll_interval: float = 0.2) -> threading.Thread:
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(
            target=self.serve_forever,
            kwargs={"poll_interval": poll_interval},
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def publish_event(self, *, session_id: str, project_id: str, topic: str, data: Dict[str, Any] | None = None) -> int:
        return self._server.publish_event(session_id=session_id, project_id=project_id, topic=topic, data=data)

    def shutdown(self) -> None:
        try:
            self._server.shutdown()
        finally:
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
