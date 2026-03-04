from __future__ import annotations
import os
import socket
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import QObject, Signal

from core.ipc.client import EventsClient, IpcClient
from core.ipc.protocol import DEFAULT_HOST as IPC_DEFAULT_HOST, ipc_enabled, resolve_ipc_events_port, resolve_ipc_port
from core.ipc.spawn import ensure_core_running_with_events

# Helper for current timestamp
from datetime import datetime, timezone
def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NetworkManager(QObject):
    ipcEvent = Signal(object)
    ipcConnection = Signal(bool, str)
    statusChanged = Signal(str)
    
    def __init__(self, project_root: str, workspace_root: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._project_root = project_root
        self._workspace_root = workspace_root
        
        self._ipc_enabled = ipc_enabled()
        self._ipc_host = IPC_DEFAULT_HOST
        self._ipc_port = resolve_ipc_port(None)
        self._ipc_events_port = resolve_ipc_events_port(None, rpc_port=self._ipc_port)
        self._ipc_token = str(os.environ.get("NH_IPC_TOKEN") or "").strip()
        
        self._ipc_client: Optional[IpcClient] = None
        self._ipc_events_client: Optional[EventsClient] = None
        self._shutdown_in_progress = False
        
        self.ipc_thinking = False
        self.ipc_progress_pct = 0
        self.ipc_progress_label = ""
        self.ipc_tool_feed: List[str] = []

    def init_ipc(self) -> None:
        if not self._ipc_enabled:
            return
            
        try:
            ensure_core_running_with_events(
                host=self._ipc_host,
                port=self._ipc_port,
                events_port=self._ipc_events_port,
                token=self._ipc_token,
                project_root=self._project_root,
                workspace_root=self._workspace_root,
            )
            self._ipc_client = IpcClient(
                host=self._ipc_host,
                port=self._ipc_port,
                token=self._ipc_token,
                timeout_s=1.0,
            )
            self._ensure_events_client()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._ipc_client = None
            self.statusChanged.emit(f"Core service failed to start: {exc}")

    def call_core(self, method: str, params: Dict[str, Any]) -> Any:
        if not self._ipc_client:
            self._ensure_ipc_client()
            
        if self._ipc_client:
            return self._ipc_client.call_ok(method, params)
        raise RuntimeError("IPC client not available")

    def _ensure_ipc_client(self) -> None:
        if not self._ipc_enabled or self._shutdown_in_progress:
            return
            
        if self._ipc_client is not None:
            try:
                self._ipc_client.call_ok("health.ping", {})
                return
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                self._ipc_client = None

        ensure_core_running_with_events(
            host=self._ipc_host,
            port=self._ipc_port,
            events_port=self._ipc_events_port,
            token=self._ipc_token,
            project_root=self._project_root,
            workspace_root=self._workspace_root,
        )
        self._ipc_client = IpcClient(
            host=self._ipc_host,
            port=self._ipc_port,
            token=self._ipc_token,
            timeout_s=2.0,
        )

    def _ensure_events_client(self, session_id: str = "", project_id: str = "") -> None:
        if not self._ipc_enabled or self._shutdown_in_progress:
            return

        if self._ipc_events_client is None:
            self._ipc_events_client = EventsClient(
                host=self._ipc_host,
                port=self._ipc_events_port,
                token=self._ipc_token,
                timeout_s=1.5,
                reconnect=True,
                ensure_running=lambda: ensure_core_running_with_events(
                    host=self._ipc_host,
                    port=self._ipc_port,
                    events_port=self._ipc_events_port,
                    token=self._ipc_token,
                    project_root=self._project_root,
                    workspace_root=self._workspace_root,
                    startup_timeout_s=3.0,
                    health_timeout_s=0.8,
                ),
            )
            self._ipc_events_client.start(
                session_id=session_id,
                project_id=project_id,
                on_event=lambda evt: self.ipcEvent.emit(evt),
                on_connected=lambda: self.ipcConnection.emit(True, ""),
                on_disconnected=lambda reason: self.ipcConnection.emit(False, str(reason or "")),
            )
        else:
            self._ipc_events_client.subscribe(session_id, project_id)

    def update_subscription(self, session_id: str, project_id: str) -> None:
        self._ensure_events_client(session_id, project_id)

    def _stop_events_client(self) -> None:
        if self._ipc_events_client is not None:
            self._ipc_events_client.stop()
            self._ipc_events_client = None

    def _is_port_closed(self, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(0.35)
            return sock.connect_ex((self._ipc_host, int(port))) != 0
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return True
        finally:
            try:
                sock.close()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def _wait_for_port_closed(self, port: int, timeout_s: float) -> bool:
        deadline = time.time() + max(0.1, float(timeout_s))
        while time.time() < deadline:
            if self._is_port_closed(int(port)):
                return True
            time.sleep(0.25)
        return self._is_port_closed(int(port))

    def request_system_shutdown(
        self,
        *,
        scope: str = "core_and_events",
        timeout_sec: int = 15,
        force: bool = True,
        keep_ollama_running: bool = True,
    ) -> Dict[str, Any]:
        if not self._ipc_enabled:
            raise RuntimeError("IPC is disabled")
        self._shutdown_in_progress = True
        try:
            self._stop_events_client()
            client = self._ipc_client or IpcClient(
                host=self._ipc_host,
                port=self._ipc_port,
                token=self._ipc_token,
                timeout_s=2.0,
            )
            response = client.call_ok(
                "system.shutdown",
                {
                    "scope": str(scope or "core_and_events"),
                    "timeout_sec": int(max(1, timeout_sec)),
                    "force": bool(force),
                    "keep_ollama_running": bool(keep_ollama_running),
                },
            )
            self._ipc_client = None

            ports = response.get("ports") if isinstance(response.get("ports"), dict) else {}
            ipc_port = int(ports.get("ipc") or self._ipc_port)
            events_port = int(ports.get("events") or self._ipc_events_port)
            try:
                core_pid = int(response.get("pid") or 0)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                core_pid = 0

            ipc_closed_in_time = self._wait_for_port_closed(ipc_port, timeout_s=15.0)
            forced_kill = False
            kill_error = ""
            if not ipc_closed_in_time and core_pid > 0:
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(core_pid), "/F"],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        os.kill(core_pid, 9)
                    forced_kill = True
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                    kill_error = str(exc)

            verified_ports = {
                "ipc": bool(self._wait_for_port_closed(ipc_port, timeout_s=3.0)),
                "events": bool(self._wait_for_port_closed(events_port, timeout_s=3.0)),
            }
            default_ports = {
                "17840": bool(self._wait_for_port_closed(17840, timeout_s=3.0)),
                "17841": bool(self._wait_for_port_closed(17841, timeout_s=3.0)),
            }
            return {
                "ok": bool(response.get("ok", True)),
                "phase": str(response.get("phase") or "initiated"),
                "pid": core_pid,
                "ports": {"ipc": ipc_port, "events": events_port},
                "watchdog": {
                    "ipc_closed_within_15s": ipc_closed_in_time,
                    "forced_kill": forced_kill,
                    "kill_error": kill_error,
                    "verified_ports_closed": verified_ports,
                    "verified_default_ports_closed": default_ports,
                },
            }
        finally:
            self._shutdown_in_progress = False

    def shutdown(self) -> None:
        self._stop_events_client()
        self._ipc_client = None
