from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.conversation.brain import ConversationalBrain
from core.ipc.protocol import resolve_ipc_events_port, resolve_ipc_port
from core.llm.ollama_config import load_ollama_settings
from core.llm.router import LLMRouter
from core.memory.search_service import MemorySearchService
from core.llm.selector import WeightedProviderSelector
from core.llm.selection_policy import fallback_order
from core.plugin_engine.loader import PluginLoader
from core.plugin_engine.registry import PluginRegistry
from core.portable.paths import default_workspace_dir, detect_base_dir, ensure_workspace_dirs
from core.projects.manager import ProjectManager
from core.task_engine.runner import Runner
from core.tooling.invoker import InvokeContext, invoke_tool
from core.tooling.trace import ToolTraceRecorder
from core.permission_guard.approval_flow import ApprovalFlow
from core.permission_guard.tool_policy import ToolPolicy
from core.telemetry.db import TelemetryDB
from core.telemetry.queries import provider_scoreboard, provider_stats, recent_provider_errors, tool_scoreboard
from core.telemetry.recorders import TelemetryRecorder, classify_error_kind
from core.telemetry.sanitize import truncate_text
from core.ux.mode_routing import parse_mode_wrapped_message, route_message_for_mode
from core.voice.readiness import probe_voice_readiness


@dataclass
class ApprovalState:
    approve_session: bool = False
    approve_once: bool = False


_SHUTDOWN_SCOPE_CORE_ONLY = "core_only"
_SHUTDOWN_SCOPE_CORE_AND_EVENTS = "core_and_events"
_SHUTDOWN_SCOPES = {_SHUTDOWN_SCOPE_CORE_ONLY, _SHUTDOWN_SCOPE_CORE_AND_EVENTS}


class NovaCoreService:
    def __init__(
        self,
        *,
        project_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        profile: Optional[str] = None,
    ) -> None:
        base_dir = os.path.abspath(project_root or detect_base_dir())
        ensure_workspace_dirs(base_dir)
        ws = os.path.abspath(workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base_dir))
        os.environ["NH_BASE_DIR"] = base_dir
        os.environ["NH_WORKSPACE"] = ws
        os.chdir(base_dir)

        self.project_root = base_dir
        self.workspace_root = ws
        self.profile = str(profile or os.environ.get("NH_PROFILE") or "engineering")
        self.approval_state = ApprovalState()
        self._dispatch_ctx = threading.local()
        self.telemetry_db = TelemetryDB(workspace_root=self.workspace_root)
        self.telemetry = TelemetryRecorder(self.telemetry_db)
        self.selector = WeightedProviderSelector(self.telemetry_db)
        self.projects = ProjectManager(self.workspace_root)
        self.memory_search = MemorySearchService(self.workspace_root, self.projects)

        policy = ToolPolicy(
            os.path.join(self.project_root, "configs", "tool_policy.yaml"),
            active_profile=self.profile,
            ui_mode=True,
        )
        approvals = ApprovalFlow(
            policy,
            os.path.join(self.project_root, "configs", "approvals.yaml"),
        )
        self.runner = Runner(approval_flow=approvals, approval_callback=self._approval_callback)
        self.tool_trace_recorder = ToolTraceRecorder(capacity=512)
        self.runner._tool_trace_recorder = self.tool_trace_recorder  # type: ignore[attr-defined]
        self._wrap_runner_with_telemetry()
        self.registry = PluginRegistry()
        PluginLoader(self.project_root).load_enabled(
            os.path.join(self.project_root, "configs", "plugins_enabled.yaml"),
            self.registry,
        )
        self.brain = ConversationalBrain(
            router=LLMRouter(
                runner=self.runner,
                registry=self.registry,
                selector=self.selector,
                telemetry_recorder=self.telemetry,
                profile=self.profile,
            )
        )
        self._event_publisher: Optional[Callable[[str, str, str, Dict[str, Any]], None]] = None
        self._session_history_lock = threading.Lock()
        self._session_history: Dict[tuple[str, str], Dict[str, Any]] = {}
        self._session_history_limit = 50
        resolved_ipc_port = resolve_ipc_port(None)
        self._runtime_ports = {
            "ipc": int(resolved_ipc_port),
            "events": int(resolve_ipc_events_port(None, rpc_port=resolved_ipc_port)),
        }
        self._shutdown_handler: Optional[Callable[[Dict[str, Any]], None]] = None
        self._shutdown_lock = threading.Lock()
        self._shutdown_initiated = False
        self._shutdown_cleanup_done = False
        self._shutdown_cleanup_summary: Dict[str, Any] = {}
        self._wire_contexts()

    def set_event_publisher(self, publisher: Optional[Callable[[str, str, str, Dict[str, Any]], None]]) -> None:
        self._event_publisher = publisher

    def set_runtime_ports(self, *, ipc_port: int, events_port: int) -> None:
        self._runtime_ports = {
            "ipc": int(ipc_port),
            "events": int(events_port),
        }

    def set_shutdown_handler(self, handler: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        self._shutdown_handler = handler

    @staticmethod
    def _coerce_bool(value: Any, *, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            norm = value.strip().lower()
            if norm in {"1", "true", "yes", "on"}:
                return True
            if norm in {"0", "false", "no", "off"}:
                return False
        if value is None:
            return bool(default)
        return bool(value)

    def _chat_send_test_mode(self) -> bool:
        raw = os.getenv("NH_TEST_MODE")
        enabled_env = str(raw or "").strip() == "1"
        return bool(enabled_env or ("PYTEST_CURRENT_TEST" in os.environ))

    def _normalize_shutdown_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        scope = str(payload.get("scope") or _SHUTDOWN_SCOPE_CORE_AND_EVENTS).strip().lower() or _SHUTDOWN_SCOPE_CORE_AND_EVENTS
        if scope not in _SHUTDOWN_SCOPES:
            raise ValueError("scope must be one of: core_only | core_and_events")
        try:
            timeout_sec = int(payload.get("timeout_sec") or 15)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            timeout_sec = 15
        timeout_sec = max(1, min(timeout_sec, 300))
        force = self._coerce_bool(payload.get("force"), default=False)
        keep_ollama_running = self._coerce_bool(payload.get("keep_ollama_running"), default=True)
        return {
            "scope": scope,
            "timeout_sec": timeout_sec,
            "force": force,
            "keep_ollama_running": keep_ollama_running,
        }

    def _system_shutdown(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self._normalize_shutdown_payload(payload)
        handler: Optional[Callable[[Dict[str, Any]], None]] = None
        with self._shutdown_lock:
            if not self._shutdown_initiated:
                if self._shutdown_handler is None:
                    raise RuntimeError("system.shutdown is not configured for this core instance")
                self._shutdown_initiated = True
                handler = self._shutdown_handler
        if handler is not None:
            handler(dict(cfg))
        return {
            "ok": True,
            "phase": "initiated",
            "pid": os.getpid(),
            "ports": {
                "ipc": int(self._runtime_ports.get("ipc") or 0),
                "events": int(self._runtime_ports.get("events") or 0),
            },
        }

    def _stop_voice_pipelines(self) -> Dict[str, Any]:
        attempted: List[str] = []
        stopped: List[str] = []
        errors: List[str] = []
        for tool_id in ("voice.stop", "voice.pipeline.stop", "voice.tts.stop"):
            tool = self.registry.tools.get(tool_id)
            if tool is None:
                continue
            attempted.append(tool_id)
            try:
                self._invoke_tool(tool_id, {})
                stopped.append(tool_id)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                errors.append(f"{tool_id}: {exc}")
        return {
            "attempted": attempted,
            "stopped": stopped,
            "errors": errors,
        }

    def prepare_shutdown(
        self,
        *,
        scope: str = _SHUTDOWN_SCOPE_CORE_AND_EVENTS,
        timeout_sec: int = 15,
        force: bool = False,
        keep_ollama_running: bool = True,
    ) -> Dict[str, Any]:
        normalized = self._normalize_shutdown_payload(
            {
                "scope": scope,
                "timeout_sec": timeout_sec,
                "force": force,
                "keep_ollama_running": keep_ollama_running,
            }
        )
        with self._shutdown_lock:
            if self._shutdown_cleanup_done:
                return dict(self._shutdown_cleanup_summary)

        telemetry_flush: Dict[str, Any]
        try:
            telemetry_flush = self.telemetry_db.checkpoint_wal(truncate=True)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            telemetry_flush = {"ok": False, "error": str(exc)}

        voice = self._stop_voice_pipelines()
        self.set_event_publisher(None)
        with self._session_history_lock:
            self._session_history.clear()

        summary = {
            "ok": True,
            "scope": normalized["scope"],
            "timeout_sec": int(normalized["timeout_sec"]),
            "force": bool(normalized["force"]),
            "keep_ollama_running": bool(normalized["keep_ollama_running"]),
            "telemetry_flush": telemetry_flush,
            "voice": voice,
            "cleanup": [
                "event_publisher_detached",
                "session_history_cleared",
            ],
        }
        with self._shutdown_lock:
            if not self._shutdown_cleanup_done:
                self._shutdown_cleanup_done = True
                self._shutdown_cleanup_summary = dict(summary)
            return dict(self._shutdown_cleanup_summary)

    def _emit_event(self, session_id: str, project_id: str, topic: str, data: Optional[Dict[str, Any]] = None) -> None:
        if self._event_publisher is None:
            return
        try:
            self._event_publisher(str(session_id or ""), str(project_id or ""), str(topic or ""), dict(data or {}))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _session_key(self, session_id: str, project_id: str) -> tuple[str, str]:
        return (str(session_id or "default"), str(project_id or ""))

    def _session_append_message(
        self,
        *,
        session_id: str,
        project_id: str,
        role: str,
        text: str,
        mode: str = "",
        provider: str = "",
    ) -> None:
        msg_text = str(text or "").strip()
        if not msg_text:
            return
        key = self._session_key(session_id, project_id)
        now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._session_history_lock:
            entry = self._session_history.setdefault(
                key,
                {"messages": [], "last_mode": str(mode or ""), "last_provider_used": str(provider or "")},
            )
            messages = entry.setdefault("messages", [])
            if not isinstance(messages, list):
                messages = []
                entry["messages"] = messages
            messages.append({"role": str(role or ""), "text": msg_text, "ts": now_ts})
            if len(messages) > self._session_history_limit:
                entry["messages"] = messages[-self._session_history_limit :]
            if mode:
                entry["last_mode"] = str(mode)
            if provider:
                entry["last_provider_used"] = str(provider)

    def _session_history_get(self, *, session_id: str, project_id: str, limit: int = 50) -> Dict[str, Any]:
        key = self._session_key(session_id, project_id)
        take = max(1, min(int(limit or 50), self._session_history_limit))
        with self._session_history_lock:
            entry = self._session_history.get(key) or {}
            messages = entry.get("messages")
            if not isinstance(messages, list):
                messages = []
            return {
                "session_id": key[0],
                "project_id": key[1],
                "last_mode": str(entry.get("last_mode") or ""),
                "last_provider_used": str(entry.get("last_provider_used") or ""),
                "messages": [dict(item) for item in messages[-take:] if isinstance(item, dict)],
                "count": len(messages[-take:]),
            }

    def _wire_contexts(self) -> None:
        try:
            from integrations.conversation.plugin import set_ui_context as set_chat_context

            set_chat_context(self.runner, self.registry, self.project_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        try:
            from integrations.security_doctor.plugin import set_ui_context as set_security_context

            set_security_context(self.runner, self.registry, self.project_root, self.workspace_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _current_ctx(self) -> Dict[str, str]:
        raw = getattr(self._dispatch_ctx, "value", None)
        if isinstance(raw, dict):
            return {str(k): str(v or "") for k, v in raw.items()}
        return {}

    def _invoke_tool(self, tool_id: str, payload: Dict[str, Any]) -> Any:
        call_payload = dict(payload or {})
        dispatch_ctx = self._current_ctx()
        return invoke_tool(
            str(tool_id or ""),
            call_payload,
            InvokeContext(
                runner=self.runner,
                registry=self.registry,
                trace_recorder=self.tool_trace_recorder,
                request_id=str(dispatch_ctx.get("request_id") or call_payload.get("request_id") or ""),
                session_id=str(call_payload.get("session_id") or dispatch_ctx.get("session_id") or ""),
                project_id=str(call_payload.get("project_id") or dispatch_ctx.get("project_id") or ""),
                mode=str(call_payload.get("mode") or dispatch_ctx.get("mode") or ""),
                provider="local",
                server_name="",
            ),
        )

    def _wrap_runner_with_telemetry(self) -> None:
        if getattr(self.runner, "_telemetry_wrapped", False):
            return
        original_execute = self.runner.execute_registered_tool

        def wrapped_execute(tool, **kwargs):
            started = time.perf_counter()
            status = "ok"
            error_kind = ""
            error_msg = ""
            ctx = self._current_ctx()
            tool_id = str(getattr(tool, "tool_id", "") or "")
            session_id = str(kwargs.get("session_id") or ctx.get("session_id") or "")
            mode = str(kwargs.get("mode") or ctx.get("mode") or "")
            project_id = str(kwargs.get("project_id") or ctx.get("project_id") or "")
            if not project_id:
                project_path = str(kwargs.get("project_path") or ctx.get("project_path") or "")
                if project_path:
                    project_id = os.path.basename(os.path.normpath(project_path))
            hidden_keys = {"prompt", "text", "system", "user_message", "content"}
            shown_args = sorted(str(k) for k in kwargs.keys() if str(k) not in hidden_keys)
            args_summary = ", ".join(shown_args[:6]) if shown_args else ""
            self._emit_event(
                session_id,
                project_id,
                "tool_start",
                {"tool": tool_id or str(kwargs.get("tool_name") or ""), "args_summary": args_summary},
            )
            try:
                return original_execute(tool, **kwargs)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                status = "error"
                error_kind = classify_error_kind(exc)
                error_msg = str(exc)
                raise
            finally:
                latency_ms = int((time.perf_counter() - started) * 1000)
                try:
                    self.telemetry.record_tool_call(
                        session_id=session_id,
                        project_id=project_id,
                        mode=mode,
                        tool_name=tool_id or str(kwargs.get("tool_name") or ""),
                        latency_ms=latency_ms,
                        status=status,
                        error_kind=error_kind if error_kind else None,
                        error_msg=error_msg if error_msg else None,
                    )
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
                self._emit_event(
                    session_id,
                    project_id,
                    "tool_end",
                    {
                        "tool": tool_id or str(kwargs.get("tool_name") or ""),
                        "status": status,
                        "latency_ms": latency_ms,
                        "error_kind": error_kind or "",
                        "error_msg": truncate_text(error_msg, max_len=240) if error_msg else "",
                    },
                )
                if status == "error":
                    self._emit_event(
                        session_id,
                        project_id,
                        "error",
                        {
                            "source": "tool",
                            "tool": tool_id or str(kwargs.get("tool_name") or ""),
                            "error_kind": error_kind or "other",
                            "error_msg": truncate_text(error_msg, max_len=240) if error_msg else "",
                        },
                    )

        self.runner.execute_registered_tool = wrapped_execute  # type: ignore[assignment]
        self.runner._telemetry_wrapped = True  # type: ignore[attr-defined]

    def _approval_callback(self, _req, _res) -> bool:
        if self.approval_state.approve_session:
            return True
        if self.approval_state.approve_once:
            self.approval_state.approve_once = False
            return True
        return False

    def dispatch(self, op: str, payload: Dict[str, Any], _ctx: Dict[str, Any]) -> Dict[str, Any]:
        name = str(op or "").strip()
        safe_payload = payload if isinstance(payload, dict) else {}
        dispatch_context = {
            "session_id": str(safe_payload.get("session_id") or ""),
            "mode": str(safe_payload.get("mode") or "general"),
            "project_id": str(safe_payload.get("project_id") or ""),
            "project_path": str(safe_payload.get("project_path") or ""),
            "request_id": str((_ctx or {}).get("request_id") or safe_payload.get("request_id") or ""),
        }
        self._dispatch_ctx.value = dispatch_context
        try:
            if name == "health.ping":
                return {
                    "ok": True,
                    "service": "nova_core",
                    "workspace_root": self.workspace_root,
                    "profile": self.profile,
                    "tools_loaded": len(self.registry.tools),
                }
            elif name == "ollama.health.ping":
                return self._ollama_health_ping(safe_payload)
            elif name == "ollama.models.list":
                return self._ollama_models_list(safe_payload)
            elif name == "ollama.chat":
                return self._ollama_chat(safe_payload)
            elif name == "tools.list":
                return {
                    "tools": [
                        {
                            "id": t.tool_id,
                            "group": t.tool_group,
                            "description": t.description,
                        }
                        for t in sorted(self.registry.list_tools(), key=lambda x: x.tool_id)
                    ]
                }
            elif name == "projects.list":
                return {"projects": self.projects.list_projects(include_archived=False)}
            elif name == "projects.open":
                project_id = str(safe_payload.get("project_id") or "").strip()
                if not project_id:
                    raise ValueError("project_id is required")
                return {"project": self.projects.open_project(project_id)}
            elif name == "approvals.respond":
                return self._approvals_respond(safe_payload)
            elif name == "chat.send":
                return self._chat_send(safe_payload)
            elif name == "conversation.history.get":
                return self._conversation_history_get(safe_payload)
            elif name == "telemetry.scoreboard.get":
                return self._telemetry_scoreboard_get(safe_payload)
            elif name == "telemetry.provider.stats":
                return self._telemetry_provider_stats(safe_payload)
            elif name == "doctor.report":
                return self._doctor_report(safe_payload)
            elif name == "selector.pick_provider":
                return self._selector_pick_provider(safe_payload)
            elif name == "memory.search":
                return self._memory_search(safe_payload)
            elif name == "voice.readiness":
                return self._voice_readiness(safe_payload)
            elif name == "system.shutdown":
                return self._system_shutdown(safe_payload)
            else:
                raise ValueError(f"Unknown op: {name}")
        finally:
            self._dispatch_ctx.value = {}

    def _approvals_respond(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action") or "").strip().lower()
        if action in ("approve_session", "session"):
            self.approval_state.approve_session = True
            self.approval_state.approve_once = False
            return {"ok": True, "mode": "session"}
        if action in ("approve_once", "once"):
            self.approval_state.approve_once = True
            return {"ok": True, "mode": "once"}
        if action in ("deny", "reset"):
            self.approval_state.approve_session = False
            self.approval_state.approve_once = False
            return {"ok": True, "mode": "deny"}
        raise ValueError("Unsupported approvals action. Use approve_once|approve_session|deny.")

    def _conversation_history_get(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        session_id = str(payload.get("session_id") or "default").strip() or "default"
        project_id = str(payload.get("project_id") or "").strip()
        limit = int(payload.get("limit") or 50)
        return self._session_history_get(session_id=session_id, project_id=project_id, limit=limit)

    def _telemetry_scoreboard_get(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(payload.get("mode") or "").strip().lower()
        provider_rows = provider_scoreboard(self.telemetry_db, mode=mode, window_days=7, max_calls_per_group=200)
        tool_rows = tool_scoreboard(self.telemetry_db, mode=mode, window_days=7)
        return {
            "mode": mode or "all",
            "providers": provider_rows,
            "tools": tool_rows,
            "db_path": self.telemetry_db.path,
            "schema_version": self.telemetry_db.schema_version(),
            "wal_enabled": self.telemetry_db.wal_enabled(),
        }

    def _telemetry_provider_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(payload.get("mode") or "").strip().lower()
        provider = str(payload.get("provider") or "").strip().lower()
        request_kind = str(payload.get("request_kind") or "").strip().lower()
        rows = provider_stats(
            self.telemetry_db,
            mode=mode,
            provider=provider,
            request_kind=request_kind,
            window_days=7,
            max_calls_per_group=200,
        )
        return {
            "rows": rows,
            "filters": {"mode": mode, "provider": provider, "request_kind": request_kind},
        }

    def _selector_pick_provider(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(payload.get("mode") or "general").strip().lower() or "general"
        request_kind = str(payload.get("request_kind") or "chat").strip().lower() or "chat"
        candidates_raw = payload.get("candidates")
        candidates: list[str]
        if isinstance(candidates_raw, list):
            candidates = [str(item or "").strip().lower() for item in candidates_raw if str(item or "").strip()]
        else:
            candidates = fallback_order(mode)
        if not candidates:
            candidates = fallback_order(mode)
        picked = self.selector.pick_provider(
            mode=mode,
            request_kind=request_kind,
            candidates=candidates,
            profile=self.profile,
        )
        return picked

    def _memory_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        query = str(payload.get("query") or "").strip()
        scope = str(payload.get("scope") or "general").strip().lower() or "general"
        scope_id = str(payload.get("scope_id") or "").strip()
        limit = int(payload.get("limit") or 20)
        offset = int(payload.get("offset") or 0)
        return self.memory_search.search(
            query,
            scope=scope,
            scope_id=scope_id,
            limit=limit,
            offset=offset,
        )

    def _voice_readiness(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sample_rate = int(payload.get("sample_rate") or 16000)
        return probe_voice_readiness(sample_rate=sample_rate)

    def _ollama_health_ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        _ = payload
        tool = self.registry.tools.get("ollama.health.ping")
        if tool is None:
            settings = load_ollama_settings()
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": settings.base_url,
                "details": "ollama.health.ping tool not available",
            }
        try:
            res = self._invoke_tool("ollama.health.ping", {})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            settings = load_ollama_settings()
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": settings.base_url,
                "details": str(exc),
            }
        if isinstance(res, dict):
            return res
        settings = load_ollama_settings()
        return {
            "status": "unavailable",
            "provider": "ollama",
            "base_url": settings.base_url,
            "details": "Invalid health response shape",
        }

    def _ollama_models_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        _ = payload
        tool = self.registry.tools.get("ollama.models.list")
        if tool is None:
            settings = load_ollama_settings()
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": settings.base_url,
                "models": [],
                "details": "ollama.models.list tool not available",
            }
        try:
            res = self._invoke_tool("ollama.models.list", {})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            settings = load_ollama_settings()
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": settings.base_url,
                "models": [],
                "details": str(exc),
            }
        if isinstance(res, dict):
            models = res.get("models")
            if isinstance(models, list):
                return res
        settings = load_ollama_settings()
        return {
            "status": "unavailable",
            "provider": "ollama",
            "base_url": settings.base_url,
            "models": [],
            "details": "Invalid models response shape",
        }

    def _ollama_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get("prompt") or payload.get("text") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        tool = self.registry.tools.get("ollama.chat")
        if tool is None:
            settings = load_ollama_settings()
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": settings.base_url,
                "text": "",
                "details": "ollama.chat tool not available",
            }
        kwargs: Dict[str, Any] = {"prompt": prompt}
        system = payload.get("system")
        if system is not None:
            kwargs["system"] = str(system)
        model = payload.get("model")
        if model is not None:
            kwargs["model"] = str(model)
        temperature = payload.get("temperature")
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        timeout_sec = payload.get("timeout_sec")
        if timeout_sec is not None:
            kwargs["timeout_sec"] = int(timeout_sec)
        images = payload.get("images")
        if isinstance(images, list):
            kwargs["images"] = [str(item) for item in images if str(item or "").strip()]

        try:
            res = self._invoke_tool("ollama.chat", kwargs)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            settings = load_ollama_settings()
            return {
                "status": "unavailable",
                "provider": "ollama",
                "base_url": settings.base_url,
                "text": "",
                "details": str(exc),
            }
        return res if isinstance(res, dict) else {"status": "unavailable", "provider": "ollama", "text": "", "details": "Invalid response"}

    def _doctor_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(payload.get("mode") or "").strip().lower()
        provider_errors = recent_provider_errors(self.telemetry_db, limit=5, window_days=7)
        best_by_mode: Dict[str, Dict[str, Any]] = {}
        for mode_id in ("general", "build_software", "gen_3d_step", "gen_2d_dxf"):
            picked = self.selector.pick_provider(
                mode=mode_id,
                request_kind="chat",
                candidates=fallback_order(mode_id),
                profile=self.profile,
            )
            best_by_mode[mode_id] = {
                "provider": str(picked.get("provider") or ""),
                "score": (picked.get("scored") or [{}])[0].get("score") if isinstance(picked.get("scored"), list) else None,
            }

        voice_summary = probe_voice_readiness(sample_rate=16000)
        ipc_port = str(os.environ.get("NH_IPC_PORT") or "17840").strip() or "17840"
        token_enabled = bool(str(os.environ.get("NH_IPC_TOKEN") or "").strip())

        remediation: list[str] = []
        deps = voice_summary.get("dependencies") if isinstance(voice_summary.get("dependencies"), dict) else {}
        if not bool(deps.get("faster_whisper")) or not bool(deps.get("sounddevice")):
            remediation.append("Install voice extras: pip install -r requirements-voice.txt")
        tts = voice_summary.get("tts") if isinstance(voice_summary.get("tts"), dict) else {}
        if not bool(tts.get("piper_binary_found")) and not bool(deps.get("pyttsx3")):
            remediation.append("Install Piper binary and set VOICE_TTS_VOICE to a local .onnx model path")
        ollama_status = self._ollama_health_ping({})
        if str(ollama_status.get("status") or "") != "ok":
            remediation.append("Local Ollama unavailable. Start service: ollama serve")
        if provider_errors:
            remediation.append("Recent provider failures detected; review API keys and rate limits")
        if token_enabled is False:
            remediation.append("Optional hardening: set NH_IPC_TOKEN to require authenticated local clients")

        scoreboard = provider_scoreboard(self.telemetry_db, mode=mode, window_days=7, max_calls_per_group=200)
        return {
            "db": {
                "path": self.telemetry_db.path,
                "schema_version": self.telemetry_db.schema_version(),
                "wal_enabled": self.telemetry_db.wal_enabled(),
            },
            "recent_errors": provider_errors,
            "best_provider_by_mode": best_by_mode,
            "scoreboard": scoreboard,
            "voice": voice_summary,
            "ollama": ollama_status,
            "ipc": {
                "host": "127.0.0.1",
                "port": ipc_port,
                "token_enabled": token_enabled,
            },
            "remediation": remediation,
        }

    def _chat_send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        user_message = str(payload.get("text") or payload.get("user_message") or "").strip()
        if not user_message:
            return {"assistant": {"role": "assistant", "text": ""}, "response": "", "state": {}, "actions": []}

        mode = str(payload.get("mode") or "general").strip().lower() or "general"
        if mode and not user_message.startswith("[[NOVA_MODE "):
            user_message = route_message_for_mode(mode, user_message, payload.get("context") if isinstance(payload.get("context"), dict) else None)

        project_path = str(payload.get("project_path") or "").strip()
        session_id = str(payload.get("session_id") or "default").strip() or "default"
        project_id = str(payload.get("project_id") or "").strip()
        if not project_id and project_path:
            project_id = os.path.basename(os.path.normpath(project_path))
        write_reports = bool(payload.get("write_reports", True))
        online_enabled = bool(payload.get("online_enabled", False))
        debug_routing = bool(payload.get("debug_routing", False))
        ollama_model_override = str(payload.get("ollama_model_override") or "").strip()
        task_run_id = ""
        parsed_user_message = parse_mode_wrapped_message(user_message)
        clean_user_text = parsed_user_message.text if parsed_user_message.wrapped else user_message
        objective = truncate_text(clean_user_text, max_len=280)

        self._session_append_message(
            session_id=session_id,
            project_id=project_id,
            role="user",
            text=clean_user_text,
            mode=mode,
        )
        self._emit_event(session_id, project_id, "thinking", {"state": "start"})
        self._emit_event(session_id, project_id, "progress", {"pct": 0, "label": "Received request"})

        if self._chat_send_test_mode():
            reply = "Nova test mode reply (deterministic offline path)."
            out: Dict[str, Any] = {
                "assistant": {"role": "assistant", "text": reply},
                "response": reply,
                "state": {},
                "actions": [],
                "session_id": session_id,
                "project_path": project_path,
                "source": "core.local",
            }
            if debug_routing:
                out["routing"] = {
                    "decision": {"need_online": False, "reason": "test_mode"},
                    "test_mode": True,
                }
            self._session_append_message(
                session_id=session_id,
                project_id=project_id,
                role="assistant",
                text=reply,
                mode=mode,
                provider="test_mode",
            )
            self._emit_event(session_id, project_id, "progress", {"pct": 70, "label": "Deterministic test reply"})
            self._emit_event(session_id, project_id, "thinking", {"state": "end"})
            self._emit_event(session_id, project_id, "progress", {"pct": 100, "label": "Done"})
            return out

        if mode == "build_software":
            try:
                task_run_id = self.telemetry.start_task_run(
                    session_id=session_id,
                    project_id=project_id,
                    mode=mode,
                    objective=objective,
                )
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                task_run_id = ""

        def _finish_task(status: str, notes: str) -> None:
            if not task_run_id:
                return
            try:
                self.telemetry.finish_task_run(task_run_id, status=status, notes=notes)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

        try:
            if not project_path:
                self._emit_event(session_id, project_id, "progress", {"pct": 30, "label": "Generating response"})
                local = self.brain.respond(
                    clean_user_text,
                    {
                        "online_enabled": online_enabled,
                        "project_id": project_id,
                        "session_id": session_id,
                        "mode": mode,
                        "ollama_model_override": ollama_model_override,
                        "prefs": {"explanation_level": "normal", "risk_posture": "balanced"},
                        "state": None,
                    },
                )
                reply = str(getattr(local, "reply_text", "") or "").strip()
                if not reply:
                    reply = "Nova core is running locally. Select or create a project to execute workspace actions."
                out = {
                    "assistant": {"role": "assistant", "text": reply},
                    "response": reply,
                    "state": {},
                    "actions": [],
                    "session_id": session_id,
                    "project_path": "",
                    "source": "core.local",
                }
                if debug_routing:
                    routing_meta = getattr(local, "routing", None)
                    out["routing"] = routing_meta if isinstance(routing_meta, dict) else {}
                self._session_append_message(
                    session_id=session_id,
                    project_id=project_id,
                    role="assistant",
                    text=reply,
                    mode=mode,
                    provider="local",
                )
                self._emit_event(session_id, project_id, "progress", {"pct": 90, "label": "Response ready"})
                _finish_task("ok", "completed in local chat path")
                self._emit_event(session_id, project_id, "thinking", {"state": "end"})
                self._emit_event(session_id, project_id, "progress", {"pct": 100, "label": "Done"})
                return out

            tool = self.registry.tools.get("conversation.chat")
            if tool is None:
                raise RuntimeError("conversation.chat tool is not available.")

            self._emit_event(session_id, project_id, "progress", {"pct": 30, "label": "Running conversation tool"})
            result = self._invoke_tool(
                "conversation.chat",
                {
                    "user_message": user_message,
                    "project_path": project_path,
                    "session_id": session_id,
                    "write_reports": write_reports,
                    "project_id": project_id,
                    "mode": mode,
                },
            )
            self._emit_event(session_id, project_id, "progress", {"pct": 60, "label": "Processing tool output"})
            if not isinstance(result, dict):
                reply = str(result)
                out = {
                    "assistant": {"role": "assistant", "text": reply},
                    "response": reply,
                    "state": {},
                    "actions": [],
                    "session_id": session_id,
                    "project_path": project_path,
                    "source": "core.conversation",
                }
                if debug_routing:
                    out["routing"] = {"available": False, "note": "routing metadata unavailable for non-dict conversation output"}
                self._session_append_message(
                    session_id=session_id,
                    project_id=project_id,
                    role="assistant",
                    text=reply,
                    mode=mode,
                    provider="conversation.chat",
                )
                self._emit_event(session_id, project_id, "progress", {"pct": 90, "label": "Response ready"})
                _finish_task("ok", "completed via conversation tool")
                self._emit_event(session_id, project_id, "thinking", {"state": "end"})
                self._emit_event(session_id, project_id, "progress", {"pct": 100, "label": "Done"})
                return out
            reply = str(result.get("response") or "")
            out = dict(result)
            out["assistant"] = {"role": "assistant", "text": reply}
            out["source"] = "core.conversation"
            if debug_routing:
                routing_meta = result.get("routing")
                if not isinstance(routing_meta, dict):
                    routing_meta = result.get("_routing")
                if isinstance(routing_meta, dict):
                    out["routing"] = routing_meta
                else:
                    out["routing"] = {
                        "available": False,
                        "note": "routing metadata not emitted by conversation.chat path",
                    }
            self._session_append_message(
                session_id=session_id,
                project_id=project_id,
                role="assistant",
                text=reply,
                mode=mode,
                provider="conversation.chat",
            )
            self._emit_event(session_id, project_id, "progress", {"pct": 90, "label": "Response ready"})
            _finish_task("ok", "completed via conversation tool")
            self._emit_event(session_id, project_id, "thinking", {"state": "end"})
            self._emit_event(session_id, project_id, "progress", {"pct": 100, "label": "Done"})
            return out
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            error_kind = classify_error_kind(exc)
            error_text = truncate_text(str(exc), max_len=240)
            self._emit_event(
                session_id,
                project_id,
                "error",
                {"source": "chat.send", "error_kind": error_kind, "error_msg": error_text},
            )
            self._emit_event(session_id, project_id, "thinking", {"state": "end"})
            self._emit_event(session_id, project_id, "progress", {"pct": 100, "label": "Failed"})
            _finish_task("error", f"{error_kind}: {error_text}")
            raise
        finally:
            self._emit_event(session_id, project_id, "thinking", {"state": "end"})


