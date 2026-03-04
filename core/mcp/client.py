from __future__ import annotations

from collections import deque
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .protocol import JsonRpcProtocolError, build_request, dump_message, parse_line, validate_response


class McpClientError(RuntimeError):
    def __init__(self, message: str, *, error_kind: str = "other", code: Optional[int] = None) -> None:
        super().__init__(message)
        self.error_kind = str(error_kind or "other")
        self.code = code


class StdioJsonRpcClient:
    def __init__(
        self,
        *,
        cmd: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> None:
        self._cmd = list(cmd or [])
        self._env = dict(env or {})
        self._cwd = str(cwd or "")
        self._proc: Optional[subprocess.Popen[str]] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._pending: Dict[str, queue.Queue[Tuple[str, Any]]] = {}
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._fatal_error: Optional[McpClientError] = None
        self._stderr_tail: deque[str] = deque(maxlen=120)
        self._closing = False
        self._initialized = False

    def __enter__(self) -> "StdioJsonRpcClient":
        self.start_server()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.shutdown()

    def start_server(
        self,
        cmd: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> None:
        if cmd is not None:
            self._cmd = list(cmd)
        if env is not None:
            self._env = dict(env)
        if cwd is not None:
            self._cwd = str(cwd or "")

        if self._proc is not None and self._proc.poll() is None:
            return

        normalized_cmd = self._normalize_cmd(self._cmd)
        spawn_env = os.environ.copy()
        for key, value in dict(self._env or {}).items():
            k = str(key or "").strip()
            if k:
                spawn_env[k] = str(value or "")
        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))

        try:
            self._proc = subprocess.Popen(
                normalized_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=(self._cwd or None),
                env=spawn_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            raise McpClientError(f"Failed to spawn MCP server: {exc}", error_kind="spawn_failed") from exc

        if self._proc.stdin is None or self._proc.stdout is None or self._proc.stderr is None:
            raise McpClientError("Failed to open MCP stdio pipes", error_kind="spawn_failed")

        self._closing = False
        self._fatal_error = None
        self._initialized = False
        self._stdout_thread = threading.Thread(target=self._stdout_reader_loop, name="mcp-stdout", daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_reader_loop, name="mcp-stderr", daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def initialize(self, timeout_sec: float = 10.0) -> Dict[str, Any]:
        if self._initialized:
            return {"ok": True}
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "nova-hub-core", "version": "1"},
                "capabilities": {"tools": {}},
            },
            timeout_sec=timeout_sec,
        )
        if not isinstance(result, dict):
            raise McpClientError("Invalid initialize response shape", error_kind="protocol_error")
        self._initialized = True
        return result

    def list_tools(self, timeout_sec: float = 10.0) -> Any:
        return self._request("tools/list", {}, timeout_sec=timeout_sec)

    def call_tool(self, tool_id: str, payload: Dict[str, Any], timeout_sec: float = 30.0) -> Any:
        return self._request(
            "tools/call",
            {"name": str(tool_id or ""), "arguments": dict(payload or {})},
            timeout_sec=timeout_sec,
        )

    def shutdown(self, grace_sec: float = 1.5) -> None:
        proc = self._proc
        if proc is None:
            return

        self._closing = True
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

        if proc.poll() is None:
            try:
                proc.terminate()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
            deadline = time.monotonic() + max(0.05, float(grace_sec))
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                time.sleep(0.02)
            if proc.poll() is None:
                try:
                    proc.kill()
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
                try:
                    proc.wait(timeout=1.0)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass

        self._notify_all_pending(
            McpClientError("MCP server closed", error_kind="server_closed"),
        )

        if self._stdout_thread is not None:
            self._stdout_thread.join(timeout=0.5)
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=0.5)

        self._proc = None
        self._stdout_thread = None
        self._stderr_thread = None
        self._initialized = False

    def _normalize_cmd(self, raw_cmd: List[str]) -> List[str]:
        cmd = [str(part or "").strip() for part in list(raw_cmd or []) if str(part or "").strip()]
        if not cmd:
            raise McpClientError("MCP server command is missing", error_kind="spawn_failed")
        head = os.path.basename(cmd[0]).lower()
        if head in {"python", "python3", "python.exe"}:
            cmd[0] = sys.executable
        return cmd

    def _request(self, method: str, params: Dict[str, Any], *, timeout_sec: float) -> Any:
        self.start_server()
        req = build_request(method, params=params)
        req_id = str(req["id"])
        q: queue.Queue[Tuple[str, Any]] = queue.Queue(maxsize=1)

        with self._lock:
            if self._fatal_error is not None:
                raise self._fatal_error
            self._pending[req_id] = q

        try:
            with self._write_lock:
                if self._proc is None or self._proc.stdin is None or self._proc.poll() is not None:
                    raise McpClientError("MCP server is not running", error_kind="server_closed")
                self._proc.stdin.write(dump_message(req))
                self._proc.stdin.flush()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._pending.pop(req_id, None)
            if isinstance(exc, McpClientError):
                raise
            raise McpClientError(f"Failed to send JSON-RPC request: {exc}", error_kind="server_closed") from exc

        deadline = time.monotonic() + max(0.01, float(timeout_sec))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with self._lock:
                    self._pending.pop(req_id, None)
                raise TimeoutError(f"MCP call timed out: method={method}")

            try:
                kind, payload = q.get(timeout=min(0.10, remaining))
            except queue.Empty:
                with self._lock:
                    fatal = self._fatal_error
                if fatal is not None:
                    with self._lock:
                        self._pending.pop(req_id, None)
                    raise fatal
                if self._proc is not None and self._proc.poll() is not None:
                    with self._lock:
                        self._pending.pop(req_id, None)
                    raise McpClientError(
                        f"MCP server exited during call: method={method}; stderr={self._stderr_tail_text()}",
                        error_kind="server_closed",
                    )
                continue

            with self._lock:
                self._pending.pop(req_id, None)

            if kind == "error":
                raise payload
            try:
                result, error = validate_response(payload, expected_id=req_id)
            except JsonRpcProtocolError as exc:
                raise McpClientError(f"Invalid JSON-RPC response: {exc}", error_kind="protocol_error") from exc

            if error is not None:
                code = error.get("code")
                message = str(error.get("message") or "Remote MCP error")
                data = error.get("data")
                suffix = ""
                if data is not None:
                    suffix = f"; data={data}"
                raise McpClientError(
                    f"Remote MCP error ({code}): {message}{suffix}",
                    error_kind="remote_error",
                    code=code if isinstance(code, int) else None,
                )
            return result

    def _stdout_reader_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for raw_line in proc.stdout:
                if raw_line is None:
                    break
                line = str(raw_line or "")
                if not line.strip():
                    continue
                try:
                    payload = parse_line(line)
                except JsonRpcProtocolError as exc:
                    self._set_fatal(McpClientError(f"Protocol parse failure: {exc}", error_kind="protocol_error"))
                    return
                req_id = payload.get("id")
                if req_id is None:
                    continue
                with self._lock:
                    waiter = self._pending.get(str(req_id))
                if waiter is not None:
                    waiter.put(("message", payload))
        except Exception as exc:  # noqa: BLE001
            self._set_fatal(McpClientError(f"MCP stdout reader failed: {exc}", error_kind="server_closed"))
            return

        if not self._closing:
            self._set_fatal(
                McpClientError(
                    f"MCP server stdout closed unexpectedly; stderr={self._stderr_tail_text()}",
                    error_kind="server_closed",
                )
            )

    def _stderr_reader_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        try:
            for raw_line in proc.stderr:
                if raw_line is None:
                    break
                line = str(raw_line or "").rstrip()
                if line:
                    self._stderr_tail.append(line)
        except Exception:
            return

    def _notify_all_pending(self, exc: McpClientError) -> None:
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for waiter in pending:
            waiter.put(("error", exc))

    def _set_fatal(self, exc: McpClientError) -> None:
        with self._lock:
            if self._fatal_error is None:
                self._fatal_error = exc
        self._notify_all_pending(exc)

    def _stderr_tail_text(self) -> str:
        if not self._stderr_tail:
            return ""
        return " | ".join(list(self._stderr_tail)[-20:])
