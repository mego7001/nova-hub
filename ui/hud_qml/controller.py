from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QCoreApplication, QObject, Property, QUrl, Signal, Slot

from core.audit_spine import ProjectAuditSpine
from core.ingest.ingest_manager import IngestManager
from core.ingest.summary_contract import build_attach_summary_text, normalize_ingest_result
from core.jobs.controller import JobController
from core.permission_guard.approval_flow import ApprovalFlow
from core.permission_guard.tool_policy import ToolPolicy
from core.plugin_engine.loader import PluginLoader
from core.plugin_engine.registry import PluginRegistry
from core.projects.manager import ProjectManager
from core.task_engine.runner import Runner
from core.conversation.brain import ConversationalBrain
from core.conversation.intent_parser import parse_intent_soft
from core.voice.audio_io import SoundDeviceAudioInput, list_input_devices
from core.voice.providers import FasterWhisperSttProvider, PiperTtsProvider
from core.voice.readiness import probe_voice_readiness
from core.voice.schemas import VoiceConfig, VoiceState
from core.voice.voice_loop import VoiceLoop
from core.ux.mode_routing import parse_mode_wrapped_message, route_message_for_mode
from core.ux.task_modes import allowed_user_task_modes, auto_fallback_mode, is_auto_mode, normalize_task_mode
from core.ux.tools_catalog import (
    build_tools_catalog,
    filter_codex_tool_rows,
    flatten_catalog_rows,
)
from core.ux.ui_contracts import load_panel_contract
from core.ipc.client import EventsClient, IpcClient
from core.ipc.protocol import DEFAULT_HOST as IPC_DEFAULT_HOST, ipc_enabled, resolve_ipc_events_port, resolve_ipc_port
from core.ipc.spawn import ensure_core_running_with_events
from ui.hud_qml.geometry_adapter import GeometryAdapter
from ui.hud_qml.controller_core import now_utc, read_jsonl, read_text, safe_read_json, write_jsonl
from ui.hud_qml.controller_ingest import build_attach_rows, has_image_attachments
from ui.hud_qml.controller_tools import preferred_user_mode
from ui.hud_qml.controller_voice import headset_warning, latency_summary
from ui.hud_qml.models import DictListModel
from ui.hud_qml.managers.network_manager import NetworkManager
from ui.hud_qml.managers.chat_manager import ChatManager
from ui.hud_qml.managers.voice_manager import VoiceManager
from ui.hud_qml.managers.candidate_manager import CandidateManager


def _now() -> str:
    return now_utc()


def _read_text(path: str) -> str:
    return read_text(path)


def _write_jsonl(path: str, payload: Dict[str, Any]) -> None:
    write_jsonl(path, payload)


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    return read_jsonl(path)


def _safe_read_json(path: str) -> Dict[str, Any]:
    return safe_read_json(path)


def _resolve_inside_root(root: str, candidate_path: str) -> str:
    root_resolved = Path(root).resolve(strict=False)
    cand_resolved = Path(candidate_path).resolve(strict=False)
    if cand_resolved != root_resolved and root_resolved not in cand_resolved.parents:
        raise RuntimeError(f"Diff path escapes target_root: {cand_resolved}")
    return str(cand_resolved)


def _normalize_diff_path(path: str) -> str:
    p = str(path or "").replace("\\", "/").strip()
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


def _parse_unified_diff(diff_text: str) -> Tuple[List[Dict[str, Any]], int, int]:
    files: List[Dict[str, Any]] = []
    plus = 0
    minus = 0
    current: Optional[Dict[str, Any]] = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = _normalize_diff_path(line[4:].strip())
            if path == "/dev/null":
                path = "(deleted)"
            current = {"path": path, "added": 0, "removed": 0}
            files.append(current)
            continue
        if line.startswith("@@ "):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            plus += 1
            if current is not None:
                current["added"] = int(current.get("added") or 0) + 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            minus += 1
            if current is not None:
                current["removed"] = int(current.get("removed") or 0) + 1
    return files, plus, minus


def _sha256(path: str) -> str:
    if not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


GENERAL_CHAT_ID = "__general__"
CHAT_SESSION_PREFIX = "chat_"
DEFAULT_UI_ACTION_KINDS = {
    "switch_mode",
    "open_drawer",
    "run_doctor",
    "apply_queue",
    "apply_confirm",
    "apply_reject",
    "security_audit",
    "refresh_timeline",
    "voice_toggle",
    "voice_mute_toggle",
    "voice_stop",
    "voice_replay",
    "app_minimize",
    "app_close",
    "toggle_ipc_hint",
}


class HUDController(QObject):
    jarvisModeChanged = Signal()
    busyChanged = Signal()
    statusTextChanged = Signal()
    wiringStatusChanged = Signal()
    currentProjectChanged = Signal()
    selectedProjectChanged = Signal()
    projectBadgeChanged = Signal()
    projectStatusChanged = Signal()
    toolsBadgeChanged = Signal()
    applyEnabledChanged = Signal()
    confirmationChanged = Signal()
    diffPreviewChanged = Signal()
    chipsChanged = Signal()
    summariesChanged = Signal()
    geometryChanged = Signal()
    capsChanged = Signal()
    qaChanged = Signal()
    latestReplyChanged = Signal()
    voiceChanged = Signal()
    uxChanged = Signal()
    attachChanged = Signal()
    candidateChanged = Signal()
    _asyncResult = Signal(str, object, str)
    _voiceTranscript = Signal(str)
    _voiceState = Signal(str)
    _voiceError = Signal(str)
    _ipcEvent = Signal(object)
    _ipcConnection = Signal(bool, str)

    def __init__(
        self,
        project_root: str,
        workspace_root: str,
        backend_enabled: bool = True,
        background_tasks: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._project_root = os.path.abspath(project_root)
        self._workspace_root = os.path.abspath(workspace_root)
        self._project_manager = ProjectManager(workspace_root=self._workspace_root)
        self._geometry_adapter = GeometryAdapter()

        self._registry: Optional[PluginRegistry] = None
        self._runner: Optional[Runner] = None
        self._approval_flow: Optional[ApprovalFlow] = None
        self._jobs_controller: Optional[JobController] = None
        self._approval_gate_open = False
        self._approval_lock = threading.Lock()
        self._layout_lock = threading.Lock()
        self._layout_save_timer: Optional[threading.Timer] = None

        self._background_enabled = bool(background_tasks and QCoreApplication.instance() is not None)
        self._async_callbacks: Dict[str, Tuple[Callable[[Any], None], Optional[Callable[[Exception], None]]]] = {}
        self._asyncResult.connect(self._on_async_result)
        self._voiceTranscript.connect(self._on_voice_transcript_ready)
        self._voiceState.connect(self._on_voice_state_event)
        self._voiceError.connect(self._on_voice_error_event)
        
        # Managers
        self._network = NetworkManager(project_root, workspace_root, parent=self)
        self._network.ipcEvent.connect(self._on_ipc_event)
        self._network.ipcConnection.connect(self._on_ipc_connection_change)
        self._network.statusChanged.connect(self._set_status)

        self._jarvis_mode = True
        self._busy_count = 0
        self._status_text = "Ready"
        self._wiring_status = "placeholder"
        self._render_backend = self._detect_render_backend()
        self._layout_state = self._load_layout_state()

        self._selected_project_id = ""
        self._selected_project: Dict[str, Any] = {}
        self._chat_sessions_rows: List[Dict[str, Any]] = []
        self._project_status = "risks"
        self._project_runtime_status: Dict[str, str] = {}

        self._tools_missing: List[str] = []
        self._verify_tool_id = ""
        self._tools_badge = "Tools: MISSING(patch.plan, patch.apply, verify.*)"

        self._confirmation_mode = "none"
        self._confirmation_summary = ""



        self._diff_preview_visible = False
        self._diff_unified_text = ""
        self._diff_stats_text = ""
        self._last_diff_files: List[Dict[str, Any]] = []

        self._evidence_chip = "Evidence: n/a"
        self._actions_chip = "Actions: n/a"
        self._risks_chip = "Risks: n/a"

        self._engineering_summary = "No jobs loaded."
        self._three_d_summary = "No geometry loaded."
        self._sketch_summary = "Sketch adapter ready."
        self._security_summary = "Security Doctor idle."
        self._timeline_summary = "No timeline events."
        self._geometry_empty = True
        self._qa_latest_path = os.path.join(self._workspace_root, "reports", "qa", "latest.json")
        self._qa_legacy_path = os.path.join(self._workspace_root, "reports", "dxf_clip_qa", "latest.json")
        self._qa_status_chip = "QA: n/a"
        self._qa_report_text = "No QA report loaded."
        self._latest_reply_preview = "No replies yet."
        self._conversation_brain = ConversationalBrain()
        self._provider_backoff_until: Dict[str, float] = {}
        self._provider_last_error: Dict[str, str] = {}
        self._voice_enabled_default = str(os.environ.get("VOICE_ENABLED_DEFAULT") or "false").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self._voice_manager: Optional[VoiceManager] = None
        self._ingest = IngestManager(workspace_root=self._workspace_root, runner=None, registry=None)
        self._task_modes_rows: List[Dict[str, Any]] = []
        self._current_task_mode = normalize_task_mode(str(self._layout_state.get("ux", {}).get("task_mode", "general")))
        
        # IPC attributes (legacy)
        self._ipc_thinking = False
        self._ipc_progress_pct = 0
        self._ipc_progress_label = ""
        self._ipc_tool_feed: List[str] = []
        self._tools_menu_open = False
        self._health_stats_summary = "Health stats unavailable (IPC disabled)."
        self._ollama_health_status = "unavailable"
        self._ollama_health_details = ""
        self._ollama_base_url = str(os.environ.get("NH_OLLAMA_BASE_URL") or os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434")
        self._ollama_default_general_model = str(
            os.environ.get("NH_OLLAMA_DEFAULT_MODEL_GENERAL")
            or os.environ.get("OLLAMA_MODEL_GENERAL")
            or os.environ.get("OLLAMA_MODEL")
            or "gemma3:4b"
        )
        self._ollama_default_code_model = str(
            os.environ.get("NH_OLLAMA_DEFAULT_MODEL_CODE")
            or os.environ.get("OLLAMA_MODEL_CODER")
            or "qwen2.5-coder:7b-instruct"
        )
        self._ollama_session_model_override = ""
        self._ollama_available_models: List[str] = []
        self._has_image_attachments = False
        self._updating_chats = False
        self._ipc_enabled = ipc_enabled()
        self._attach_last_summary = ""
        self._voice_status_line = "Voice: disabled"
        self._voice_latency_summary = "capture=0ms stt=0ms llm=0ms tts=0ms playback=0ms"
        self._voice_readiness_summary = "Voice readiness not checked."
        self._ui_profile = str(os.environ.get("NH_UI_PROFILE") or "full").strip().lower() or "full"
        self._ui_events_log_path = os.path.join(self._workspace_root, "runtime", "logs", "ui_events.jsonl")
        self._allowed_ui_action_kinds = self._load_allowed_ui_action_kinds()
        self._voice_enabled = False
        self._voice_muted = False
        self._voice_last_spoken_text = ""
        self._pending_candidates: List[Dict[str, Any]] = []

        self._projects_model = DictListModel(
            ["project_id", "name", "status", "last_opened", "working_path"],
            parent=self,
        )
        self._chat_manager = ChatManager(self._workspace_root, parent=self)
        self._chat_manager.chatsChanged.connect(self.refresh_chats_proxy)

        self._voice_manager = VoiceManager(self._workspace_root, parent=self)
        voice_cfg = self._voice_config_from_layout()
        self._voice_manager.set_config(
            stt_model=voice_cfg.stt_model,
            device=voice_cfg.device,
            tts_voice=voice_cfg.tts_voice,
            sample_rate=voice_cfg.sample_rate,
            vad_mode=voice_cfg.vad_mode,
            push_to_talk=voice_cfg.push_to_talk,
        )
        self._voice_manager.transcriptReady.connect(self._on_voice_transcript_ready)
        self._voice_manager.stateChanged.connect(self._on_voice_state_event)
        self._voice_manager.errorOccurred.connect(self._on_voice_error_event)
        self._voice_manager.configChanged.connect(self._refresh_voice_status_line)

        self._candidate_manager = CandidateManager(self._workspace_root, parent=self)
        self._candidate_manager.candidateChanged.connect(self.candidateChanged)

        self._jobs_model = DictListModel(
            ["job_id", "title", "status", "steps", "waiting_reason", "current_step_label"],
            parent=self,
        )
        self._timeline_model = DictListModel(["event_type", "recorded_at", "detail"], parent=self)
        self._entities_model = DictListModel(
            ["entity_id", "name", "visible", "x", "y", "z", "size", "size_x", "size_y", "size_z", "color", "category"],
            parent=self,
        )
        # self._diff_files_model is now self._candidate_manager.diff_files_model
        # self._qa_findings_model is now self._candidate_manager.qa_findings_model
        # self._qa_metrics_model is now self._candidate_manager.qa_metrics_model
        self._tools_catalog_model = DictListModel(
            ["section", "group", "id", "badge", "description", "enabled", "approval_required", "reason"],
            parent=self,
        )
        self._attach_summary_model = DictListModel(["path", "status", "reason", "reason_code", "type", "size"], parent=self)
        self._health_stats_model = DictListModel(
            ["provider", "calls", "success_rate", "avg_latency_ms", "last_error", "last_used"],
            parent=self,
        )

        self._load_workspace_secrets_env()
        self._init_backend(backend_enabled)
        self.refresh_chats()
        self.refresh_projects()
        if not self._selected_project_id:
            self.select_project(GENERAL_CHAT_ID)
        self._probe_tools()
        self.refreshQaReport()
        self._refresh_task_modes()
        self._refresh_tools_catalog()
        self._refresh_voice_status_line()
        if self._ipc_enabled:
            self._init_ipc_if_enabled()
        else:
            self._refresh_health_stats()

    def _load_allowed_ui_action_kinds(self) -> set[str]:
        allowed = set(DEFAULT_UI_ACTION_KINDS)
        contract_path = os.path.join(self._project_root, "configs", "panel_contract_v3.json")
        try:
            payload = load_panel_contract(contract_path)
            items = payload.get("interaction_contract")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    action_id = str(item.get("action_id") or "").strip()
                    if action_id:
                        allowed.add(action_id)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        return allowed

    def __del__(self) -> None:
        try:
            if hasattr(self, "_network") and self._network:
                self._network.shutdown()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _load_workspace_secrets_env(self) -> None:
        path = os.path.join(self._workspace_root, "secrets", ".env")
        if not os.path.exists(path):
            return
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return
        for line in lines:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

    def _init_backend(self, backend_enabled: bool) -> None:
        if not backend_enabled:
            self._registry = PluginRegistry()
            self._ingest.runner = None
            self._ingest.registry = self._registry
            self._wiring_status = "placeholder (backend disabled)"
            self._jobs_controller = JobController(
                runner=None,
                registry=self._registry,
                approval_flow=None,
                workspace_root=self._workspace_root,
            )
            self.wiringStatusChanged.emit()
            return

        try:
            profile = os.environ.get("NH_PROFILE", "engineering")
            policy = ToolPolicy(
                os.path.join(self._project_root, "configs", "tool_policy.yaml"),
                active_profile=profile,
            )
            approvals = ApprovalFlow(
                policy,
                os.path.join(self._project_root, "configs", "approvals.yaml"),
            )
            runner = Runner(approval_flow=approvals, approval_callback=self._approval_callback)
            registry = PluginRegistry()
            PluginLoader(self._project_root).load_enabled(
                os.path.join(self._project_root, "configs", "plugins_enabled.yaml"),
                registry,
            )
            try:
                from integrations.security_doctor.plugin import set_ui_context

                set_ui_context(runner, registry, self._project_root, self._workspace_root)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

            self._approval_flow = approvals
            self._runner = runner
            self._registry = registry
            self._ingest.runner = self._runner
            self._ingest.registry = self._registry
            self._jobs_controller = JobController(
                runner=self._runner,
                registry=self._registry,
                approval_flow=self._approval_flow,
                workspace_root=self._workspace_root,
            )
            self._wiring_status = "real"
            self._status_text = "Backend tools wired."
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            self._registry = PluginRegistry()
            self._ingest.runner = None
            self._ingest.registry = self._registry
            self._jobs_controller = JobController(
                runner=None,
                registry=self._registry,
                approval_flow=None,
                workspace_root=self._workspace_root,
            )
            self._wiring_status = f"placeholder ({e})"
            self._status_text = "Backend failed to initialize."
        self.wiringStatusChanged.emit()
        self.statusTextChanged.emit()
        self.capsChanged.emit()

    def _init_ipc_if_enabled(self) -> None:
        if self._network:
             self._network.init_ipc()

    def _ipc_subscription_scope(self) -> tuple[str, str]:
        session_id = str(self._selected_project_id or GENERAL_CHAT_ID)
        if self._has_project_context():
            project_id = str(self._selected_project_id or "")
        else:
            project_id = ""
        return session_id, project_id

    def _restore_ipc_history(self) -> None:
        if not self._network:
            return
        session_id, project_id = self._ipc_subscription_scope()
        try:
            history = self._network.call_core(
                "conversation.history.get",
                {"session_id": session_id, "project_id": project_id, "limit": 50},
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return
        rows = history.get("messages")
        if not isinstance(rows, list):
            return
        if self._chat_manager.messages_model.count() > 0:
            return
        normalized: List[Dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "role": str(item.get("role") or ""),
                    "text": str(item.get("text") or ""),
                    "timestamp": str(item.get("ts") or item.get("timestamp") or ""),
                }
            )
        if normalized:
            self._chat_manager.messages_model.set_items(normalized)

    def _on_ipc_connection_change(self, connected: bool, reason: str) -> None:
        if connected:
            self._set_status("Core reconnected")
            self._restore_ipc_history()
            return
        msg = "Core disconnected; reconnecting..."
        if reason:
            msg = f"{msg} {reason}"
        self._set_status(msg)

    def _on_ipc_event(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        topic = str(payload.get("topic") or "").strip().lower()
        data = payload.get("data")
        data_map = data if isinstance(data, dict) else {}
        if topic == "thinking":
            state = str(data_map.get("state") or "").strip().lower()
            self._ipc_thinking = state == "start"
            self._set_status("Core is thinking..." if self._ipc_thinking else "Core response ready")
            return
        if topic == "progress":
            pct = int(data_map.get("pct") or 0)
            label = str(data_map.get("label") or "").strip()
            self._ipc_progress_pct = max(0, min(100, pct))
            self._ipc_progress_label = label
            if label:
                self._set_status(f"{label} ({self._ipc_progress_pct}%)")
            return
        if topic == "tool_start":
            tool_name = str(data_map.get("tool") or "")
            if tool_name:
                self._ipc_tool_feed.append(f"start:{tool_name}")
                self._ipc_tool_feed = self._ipc_tool_feed[-20:]
                self._timeline_model.append_item({"event_type": "ipc.tool_start", "recorded_at": _now(), "detail": tool_name})
                self._set_status(f"Tool started: {tool_name}")
            return
        if topic == "tool_end":
            tool_name = str(data_map.get("tool") or "")
            tool_status = str(data_map.get("status") or "ok")
            if tool_name:
                self._ipc_tool_feed.append(f"end:{tool_name}:{tool_status}")
                self._ipc_tool_feed = self._ipc_tool_feed[-20:]
                self._timeline_model.append_item(
                    {"event_type": "ipc.tool_end", "recorded_at": _now(), "detail": f"{tool_name}:{tool_status}"}
                )
                self._set_status(f"Tool {tool_name}: {tool_status}")
            return
        if topic == "error":
            msg = str(data_map.get("error_msg") or "").strip()
            if msg:
                self._set_status(f"Core error: {msg}")

    def _approval_callback(self, _req, _res) -> bool:
        with self._approval_lock:
            allowed = self._approval_gate_open
            self._approval_gate_open = False
        return bool(allowed)

    def _grant_single_approval(self) -> None:
        with self._approval_lock:
            self._approval_gate_open = True

    def _push_busy(self) -> None:
        was_busy = self._busy_count > 0
        self._busy_count += 1
        if not was_busy:
            self.busyChanged.emit()
            self.applyEnabledChanged.emit()

    def _pop_busy(self) -> None:
        self._busy_count = max(0, self._busy_count - 1)
        if self._busy_count == 0:
            self.busyChanged.emit()
            self.applyEnabledChanged.emit()

    def _run_background(
        self,
        title: str,
        fn: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self._set_status(title)
        if not self._background_enabled:
            self._push_busy()
            try:
                on_done(fn())
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                if on_error:
                    on_error(e)
                else:
                    self._append_assistant_message(f"{title} failed: {e}")
                    self._set_status(f"{title} failed")
            finally:
                self._pop_busy()
            return

        task_id = uuid.uuid4().hex
        self._async_callbacks[task_id] = (on_done, on_error)
        self._push_busy()

        def worker() -> None:
            try:
                payload = fn()
                self._asyncResult.emit(task_id, payload, "")
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                self._asyncResult.emit(task_id, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    @Slot(str, object, str)
    def _on_async_result(self, task_id: str, payload: object, error: str) -> None:
        callback = self._async_callbacks.pop(task_id, None)
        self._pop_busy()
        if callback is None:
            return
        on_done, on_error = callback
        if error:
            if on_error is not None:
                on_error(RuntimeError(error))
            else:
                self._append_assistant_message(f"Background task failed: {error}")
                self._set_status("Task failed")
            return
        on_done(payload)

    def _set_status(self, text: str) -> None:
        if text == self._status_text:
            return
        self._status_text = text
        self.statusTextChanged.emit()

    def _detect_render_backend(self) -> str:
        raw = str(os.environ.get("QSG_RHI_BACKEND") or "").strip().lower()
        if raw in ("software", "sw", "opengl", "d3d11sw"):
            return "SW"
        return "GPU"

    def _layout_path(self) -> str:
        return os.path.join(self._workspace_root, "ui_state", "hud_layout.json")

    def _default_layout_state(self) -> Dict[str, Any]:
        cfg = VoiceConfig.from_env()
        return {
            "popouts": {
                "diff.preview": False,
                "timeline": False,
                "threed": False,
            },
            "geometries": {},
            "voice": {
                "muted": False,
                "device": cfg.device,
                "stt_model": cfg.stt_model,
                "tts_voice": cfg.tts_voice,
                "sample_rate": int(cfg.sample_rate),
                "vad_mode": cfg.vad_mode,
                "push_to_talk": bool(cfg.push_to_talk),
            },
            "ux": {
                "task_mode": "general",
            },
        }

    def _load_layout_state(self) -> Dict[str, Any]:
        raw = _safe_read_json(self._layout_path())
        state = self._default_layout_state()
        if not raw:
            return state
        popouts = raw.get("popouts")
        if isinstance(popouts, dict):
            for key in state["popouts"].keys():
                state["popouts"][key] = bool(popouts.get(key, state["popouts"][key]))
        geometries = raw.get("geometries")
        if isinstance(geometries, dict):
            clean: Dict[str, Dict[str, int]] = {}
            for key, val in geometries.items():
                if not isinstance(val, dict):
                    continue
                try:
                    clean[str(key)] = {
                        "x": int(val.get("x", 0)),
                        "y": int(val.get("y", 0)),
                        "width": int(val.get("width", 0)),
                        "height": int(val.get("height", 0)),
                    }
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    continue
            state["geometries"] = clean
        voice = raw.get("voice")
        if isinstance(voice, dict):
            clean_voice = state.get("voice", {})
            if isinstance(clean_voice, dict):
                clean_voice["muted"] = bool(voice.get("muted", clean_voice.get("muted", False)))
                clean_voice["device"] = str(voice.get("device", clean_voice.get("device", "default")) or "default")
                clean_voice["stt_model"] = str(voice.get("stt_model", clean_voice.get("stt_model", "small")) or "small")
                clean_voice["tts_voice"] = str(voice.get("tts_voice", clean_voice.get("tts_voice", "")) or "")
                try:
                    clean_voice["sample_rate"] = max(8000, int(voice.get("sample_rate", clean_voice.get("sample_rate", 16000))))
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    clean_voice["sample_rate"] = int(clean_voice.get("sample_rate", 16000))
                clean_voice["vad_mode"] = str(voice.get("vad_mode", clean_voice.get("vad_mode", "energy")) or "energy")
                clean_voice["push_to_talk"] = bool(voice.get("push_to_talk", clean_voice.get("push_to_talk", True)))
                state["voice"] = clean_voice
        ux = raw.get("ux")
        if isinstance(ux, dict):
            clean_ux = state.get("ux", {})
            if isinstance(clean_ux, dict):
                clean_ux["task_mode"] = normalize_task_mode(str(ux.get("task_mode", clean_ux.get("task_mode", "general"))))
                state["ux"] = clean_ux
        return state

    def _schedule_layout_save(self) -> None:
        with self._layout_lock:
            if self._layout_save_timer is not None:
                try:
                    self._layout_save_timer.cancel()
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
            timer = threading.Timer(0.25, self._save_layout_state_now)
            timer.daemon = True
            self._layout_save_timer = timer
            timer.start()

    def _save_layout_state_now(self) -> None:
        with self._layout_lock:
            self._layout_save_timer = None
            snapshot = json.loads(json.dumps(self._layout_state))
        try:
            path = self._layout_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return

    def _voice_state_store(self) -> Dict[str, Any]:
        voice = self._layout_state.setdefault("voice", {})
        if not isinstance(voice, dict):
            voice = {}
            self._layout_state["voice"] = voice
        return voice

    def _voice_config_from_layout(self) -> VoiceConfig:
        cfg = VoiceConfig.from_env()
        voice = self._layout_state.get("voice")
        if not isinstance(voice, dict):
            return cfg
        stt_model = str(voice.get("stt_model", cfg.stt_model) or cfg.stt_model)
        device = str(voice.get("device", cfg.device) or cfg.device)
        tts_voice = str(voice.get("tts_voice", cfg.tts_voice) or cfg.tts_voice)
        vad_mode = str(voice.get("vad_mode", cfg.vad_mode) or cfg.vad_mode)
        try:
            sample_rate = max(8000, int(voice.get("sample_rate", cfg.sample_rate)))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            sample_rate = cfg.sample_rate
        return VoiceConfig(
            stt_model=stt_model,
            device=device,
            tts_voice=tts_voice,
            sample_rate=sample_rate,
            vad_mode=vad_mode,
            vad_energy_threshold=cfg.vad_energy_threshold,
            vad_min_speech_ms=cfg.vad_min_speech_ms,
            vad_silence_ms=cfg.vad_silence_ms,
            tts_sentence_pause_ms=cfg.tts_sentence_pause_ms,
            push_to_talk=bool(voice.get("push_to_talk", cfg.push_to_talk)),
        )

    def _persist_voice_preferences(self) -> None:
        store = self._voice_state_store()
        store["muted"] = bool(self._voice_manager.muted)
        store["enabled"] = bool(self._voice_manager.enabled)
        store["device"] = str(self._voice_manager.config.device)
        store["stt_model"] = str(self._voice_manager.config.stt_model)
        store["tts_voice"] = str(self._voice_manager.config.tts_voice)
        store["sample_rate"] = int(self._voice_manager.config.sample_rate)
        store["vad_mode"] = str(self._voice_manager.config.vad_mode)
        store["push_to_talk"] = bool(self._voice_manager.config.push_to_talk)
        self._schedule_layout_save()

    def _ux_state_store(self) -> Dict[str, Any]:
        ux = self._layout_state.setdefault("ux", {})
        if not isinstance(ux, dict):
            ux = {}
            self._layout_state["ux"] = ux
        return ux

    def _persist_ux_preferences(self) -> None:
        store = self._ux_state_store()
        store["task_mode"] = str(self._current_task_mode or "general")
        self._schedule_layout_save()

    def _refresh_task_modes(self) -> None:
        if self._registry is not None:
            rows = allowed_user_task_modes(self._registry, include_unavailable=False)
        else:
            rows = [{"id": "general", "title": "General", "description": "Default routing", "available": True, "reason": ""}]
        if not rows:
            rows = [{"id": "general", "title": "General", "description": "Default routing", "available": True, "reason": ""}]
        self._task_modes_rows = [dict(row) for row in rows if isinstance(row, dict)]
        self._current_task_mode = preferred_user_mode(self._task_modes_rows, self._current_task_mode)
        self._persist_ux_preferences()
        self.uxChanged.emit()

    def _refresh_tools_catalog(self) -> None:
        if self._registry is None:
            self._tools_catalog_model.clear()
            self.uxChanged.emit()
            return
        policy = self._approval_flow.tool_policy if self._approval_flow else None
        catalog = build_tools_catalog(
            self._registry,
            policy=policy,
            project_context=self._has_project_context(),
            task_mode=self._current_task_mode,
        )
        rows = filter_codex_tool_rows(flatten_catalog_rows(catalog))
        self._tools_catalog_model.set_items(rows)
        self.uxChanged.emit()

    def _refresh_health_stats(self) -> None:
        if not self._ipc_enabled:
            self._health_stats_model.set_items([])
            self._health_stats_summary = "Health stats unavailable (IPC disabled)."
            self._ollama_health_status = "unavailable"
            self._ollama_health_details = "IPC disabled"
            self._ollama_available_models = []
            self.uxChanged.emit()
            return
        try:
            payload = self._network.call_core(
                "telemetry.scoreboard.get",
                {"mode": str(self._current_task_mode or "general")},
            )
            provider_rows = payload.get("providers")
            if not isinstance(provider_rows, list):
                provider_rows = []
            rows: List[Dict[str, Any]] = []
            for item in provider_rows:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "provider": str(item.get("provider") or ""),
                        "calls": int(item.get("calls") or 0),
                        "success_rate": float(item.get("success_rate") or 0.0),
                        "avg_latency_ms": int(item.get("avg_latency_ms") or 0),
                        "last_error": str(item.get("last_error") or ""),
                        "last_used": str(item.get("last_used") or ""),
                    }
                )
            self._health_stats_model.set_items(rows)
            self._health_stats_summary = f"Providers tracked: {len(rows)}"
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._health_stats_model.set_items([])
            self._health_stats_summary = f"Health stats unavailable: {exc}"
        self._refresh_ollama_health()
        self.uxChanged.emit()

    def _refresh_ollama_health(self) -> None:
        if not self._ipc_enabled:
            self._ollama_health_status = "unavailable"
            self._ollama_health_details = "IPC disabled"
            self._ollama_available_models = []
            return
        try:
            payload = self._network.call_core("ollama.health.ping", {})
            if isinstance(payload, dict):
                self._ollama_health_status = str(payload.get("status") or "unavailable")
                self._ollama_base_url = str(payload.get("base_url") or self._ollama_base_url)
                details = payload.get("details")
                if isinstance(details, dict):
                    model_count = int(details.get("model_count") or 0)
                    self._ollama_health_details = f"models={model_count}"
                else:
                    self._ollama_health_details = str(details or "")
            else:
                self._ollama_health_status = "unavailable"
                self._ollama_health_details = "Invalid health response"
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._ollama_health_status = "unavailable"
            self._ollama_health_details = str(exc)
            self._ollama_available_models = []
            return
        self._refresh_ollama_models()

    def _refresh_ollama_models(self) -> None:
        if not self._ipc_enabled:
            self._ollama_available_models = []
            return
        try:
            payload = self._network.call_core("ollama.models.list", {})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            self._ollama_available_models = []
            return
        models_raw = payload.get("models") if isinstance(payload, dict) else []
        names: List[str] = []
        if isinstance(models_raw, list):
            for item in models_raw:
                if isinstance(item, dict):
                    name = str(item.get("name") or "").strip()
                else:
                    name = str(item or "").strip()
                if name and name not in names:
                    names.append(name)
        self._ollama_available_models = names

    def _set_attach_summary(self, result: Dict[str, Any]) -> None:
        normalized = normalize_ingest_result(result if isinstance(result, dict) else {})
        rows = build_attach_rows(normalized)
        self._attach_summary_model.set_items(rows[-200:])
        self._attach_last_summary = build_attach_summary_text(normalized)
        self._has_image_attachments = has_image_attachments(rows)
        self.attachChanged.emit()

    def _coerce_local_paths(self, values: Any) -> List[str]:
        out: List[str] = []
        if values is None:
            return out
        if isinstance(values, (str, bytes)):
            values = [values]
        if not isinstance(values, list):
            try:
                values = list(values)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                values = []
        for item in values:
            if isinstance(item, QUrl):
                raw = str(item.toLocalFile() or "").strip()
            else:
                raw = str(item or "").strip()
            if not raw:
                continue
            if raw.startswith("file:/"):
                try:
                    parsed = QUrl(raw).toLocalFile()
                    if parsed:
                        raw = parsed
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
            out.append(raw)
        dedup: List[str] = []
        seen = set()
        for path in out:
            norm = os.path.abspath(path)
            key = norm.lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(norm)
        return dedup

    def _replace_voice_config(
        self,
        *,
        stt_model: Optional[str] = None,
        device: Optional[str] = None,
        tts_voice: Optional[str] = None,
        sample_rate: Optional[int] = None,
        vad_mode: Optional[str] = None,
    ) -> None:
        cfg = self._voice_manager.config
        self._voice_manager.set_config(
            stt_model=stt_model,
            device=device,
            tts_voice=tts_voice,
            sample_rate=sample_rate,
            vad_mode=vad_mode,
        )
        self._persist_voice_preferences()


    def _refresh_voice_status_line(self) -> None:
        self._voice_enabled = bool(self._voice_manager.enabled)
        self._voice_muted = bool(self._voice_manager.muted)
        self._voice_last_spoken_text = str(self._voice_manager.last_spoken_text or "")
        if not self._voice_manager.enabled:
            if self._voice_manager.state == VoiceState.ERROR.value and self._voice_manager.last_error:
                self._voice_status_line = "Voice: error"
            else:
                self._voice_status_line = "Voice: disabled"
        else:
            state = self._voice_manager.state.lower()
            muted = " [MUTED]" if self._voice_manager.muted else ""
            ptt = " [PTT]" if bool(self._voice_manager.config.push_to_talk) else " [ALWAYS-LISTEN]"
            warning = headset_warning(str(self._voice_manager.config.device or ""), enabled=bool(self._voice_manager.enabled))
            self._voice_status_line = f"Voice: {state}{muted}{ptt}{warning}"
        metrics_fn = getattr(self._voice_manager, "latency_metrics", None)
        metrics: Dict[str, str] = {}
        if callable(metrics_fn):
            try:
                raw_metrics = metrics_fn()
                if isinstance(raw_metrics, dict):
                    metrics = {str(k): str(v) for k, v in raw_metrics.items()}
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                metrics = {}
        self._voice_latency_summary = latency_summary(metrics)
        self.voiceChanged.emit()

    def _voice_error_status_text(self, message: str = "") -> str:
        err = str(message or self._voice_manager.last_error or "").strip()
        err_lower = err.lower()
        error_kind = str(getattr(self._voice_manager, "last_voice_error_kind", "") or "").strip().lower()
        if (
            "invalid device" in err_lower
            or "paerrorcode" in err_lower
            or "error opening rawinputstream" in err_lower
            or "input device" in err_lower
            or error_kind == "device_error"
        ):
            return "Voice unavailable: microphone/device error. Check audio input settings."
        if (
            error_kind == "missing_dependency"
            or "no module named" in err_lower
            or "missing dependency" in err_lower
            or "ctranslate2" in err_lower
            or "faster-whisper" in err_lower
        ):
            return "Voice unavailable: missing dependency. Install requirements-voice.txt"
        if err:
            return f"Voice unavailable: {err}"
        return "Voice unavailable right now."

    def _start_voice_or_status(self) -> bool:
        try:
            ok = self._voice_manager.start_loop()
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            ImportError,
            ModuleNotFoundError,
        ) as exc:
            self._set_status(self._voice_error_status_text(str(exc)))
            return False
        if not ok:
            self._set_status(self._voice_error_status_text())
            return False
        self._persist_voice_preferences()
        return ok

    def _normalize_panel_id(self, panel_id: str) -> str:
        pid = str(panel_id or "").strip().lower()
        if pid in ("diff", "diff.preview", "diff_preview"):
            return "diff.preview"
        if pid in ("timeline",):
            return "timeline"
        if pid in ("threed", "3d", "three_d", "three-d"):
            return "threed"
        return pid


    @Slot(str)
    def _on_voice_transcript_ready(self, text: str) -> None:
        payload = str(text or "").strip()
        if payload:
            self.send_message(payload)

    @Slot(str)
    def _on_voice_state_event(self, state_value: str) -> None:
        self._refresh_voice_status_line()

    @Slot(str)
    def _on_voice_error_event(self, message: str) -> None:
        self._refresh_voice_status_line()
        err = str(message or "").strip()
        if err:
            self._set_status(self._voice_error_status_text(err))

    def _enqueue_voice_tts(self, text: str) -> None:
        self._voice_manager.notify_assistant_text(text)
        self._refresh_voice_status_line()

    @Slot()
    def refresh_chats_proxy(self) -> None:
        self.refresh_chats()

    def _is_general_chat(self, project_id: Optional[str] = None) -> bool:
        pid = project_id or self._selected_project_id
        return pid == GENERAL_CHAT_ID

    def _is_chat_session(self, project_id: Optional[str] = None) -> bool:
        pid = project_id or self._selected_project_id
        if self._chat_manager:
            return self._chat_manager.is_chat_session(pid)
        return str(pid or "").startswith(CHAT_SESSION_PREFIX) or pid == GENERAL_CHAT_ID

    def _touch_chat(self, chat_id: str) -> None:
        if self._chat_manager:
            self._chat_manager.touch_chat(chat_id)

    def _touch_project(self, project_id: str) -> None:
        if self._project_manager:
            self._project_manager.update_last_opened(project_id)

    def _has_project_context(self) -> bool:
        return bool(self._selected_project_id) and not self._is_chat_session()

    def _mark_chat_converted(self, chat_id: str, project_id: str) -> None:
        self._chat_manager.mark_chat_converted(chat_id, project_id)

    def _migrate_chat_messages_to_project(self, chat_id: str, project_id: str) -> int:
        if not self._is_chat_session(chat_id):
            return 0
        source = self._chat_manager.chat_message_log(chat_id)
        items = self._chat_manager._read_jsonl(source)
        if not items:
            return 0
        target = os.path.join(self._project_paths(project_id).project_root, "hud_messages.jsonl")
        moved = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            text = str(item.get("text") or "")
            if role not in ("user", "assistant") or not text:
                continue
            payload = {
                "role": role,
                "text": text,
                "timestamp": str(item.get("timestamp") or _now()),
            }
            _write_jsonl(target, payload)
            moved += 1
        return moved

    def _sanitize_project_name(self, raw_name: str) -> str:
        name = str(raw_name or "").strip()
        if not name:
            raise ValueError("Project name is required.")
        name = re.sub(r"\s+", " ", name)
        if len(name) > 64:
            name = name[:64].rstrip()
        if not re.search(r"[A-Za-z0-9\u0600-\u06FF]", name):
            raise ValueError("Project name must contain letters or numbers.")
        return name

    def _create_project_from_name(self, raw_name: str) -> str:
        name = self._sanitize_project_name(raw_name)
        imports_root = Path(self._workspace_root) / "imports"
        imports_root.mkdir(parents=True, exist_ok=True)
        seed_dir = imports_root / f"_hud_seed_{uuid.uuid4().hex[:8]}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        (seed_dir / "README.md").write_text(
            f"# {name}\n\nCreated from chat session.\n",
            encoding="utf-8",
        )
        try:
            project_id = self._project_manager.add_project_from_folder(str(seed_dir))
            try:
                self._project_manager.rename_project(project_id, name)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
            return project_id
        finally:
            shutil.rmtree(seed_dir, ignore_errors=True)

    def _convert_chat_to_project(self, source_chat_id: str, project_name: str) -> Tuple[str, int, Dict[str, Any]]:
        new_project_id = self._create_project_from_name(project_name)
        migrated_messages = 0
        ingest_migration: Dict[str, Any] = {}
        if self._is_chat_session(source_chat_id):
            try:
                migrated_messages = self._migrate_chat_messages_to_project(source_chat_id, new_project_id)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                migrated_messages = 0
            try:
                ingest_migration = self._ingest.migrate_general_to_project(
                    source_chat_id,
                    new_project_id,
                    remove_source=True,
                )
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                ingest_migration = {"status": "error", "error": str(exc)}
            self._mark_chat_converted(source_chat_id, new_project_id)
        return new_project_id, migrated_messages, ingest_migration

    def _project_paths(self, project_id: str):
        return self._project_manager.get_project_paths(project_id)



    def _project_message_log(self, project_id: str) -> str:
        if self._is_chat_session(project_id):
            return self._chat_manager.chat_message_log(project_id)
        return os.path.join(self._project_paths(project_id).project_root, "hud_messages.jsonl")

    def _update_latest_reply_preview(self, text: str) -> None:
        val = str(text or "").strip()
        if not val:
            val = "No replies yet."
        if val == self._latest_reply_preview:
            return
        self._latest_reply_preview = val
        self.latestReplyChanged.emit()

    def _provider_choice_order(self) -> List[str]:
        raw = str(os.environ.get("NH_CHAT_PROVIDER") or "auto").strip().lower()
        if raw in ("deepseek", "gemini", "openai"):
            others = [p for p in ("deepseek", "gemini", "openai") if p != raw]
            return [raw, *others]
        return ["deepseek", "gemini", "openai"]

    def _provider_tool_id(self, provider: str) -> str:
        p = str(provider or "").strip().lower()
        if p == "deepseek":
            return "deepseek.chat"
        if p == "gemini":
            return "gemini.prompt"
        if p == "openai":
            return "openai.chat"
        return ""

    def _provider_key_present(self, provider: str) -> bool:
        p = str(provider or "").strip().lower()
        if p == "deepseek":
            env_key = str(os.environ.get("DEEPSEEK_API_KEY") or "").strip()
            cfg_key = ""
            plugin = self._registry.plugins.get("deepseek") if self._registry else None
            if plugin and isinstance(plugin.config, dict):
                cfg_key = str(plugin.config.get("api_key") or "").strip()
            return bool(env_key or cfg_key)
        if p == "gemini":
            env_key = str(os.environ.get("GEMINI_API_KEY") or "").strip()
            cfg_key = ""
            plugin = self._registry.plugins.get("gemini") if self._registry else None
            if plugin and isinstance(plugin.config, dict):
                cfg_key = str(plugin.config.get("api_key") or "").strip()
            return bool(env_key or cfg_key)
        if p == "openai":
            env_key = str(os.environ.get("OPENAI_API_KEY") or "").strip()
            cfg_key = ""
            plugin = self._registry.plugins.get("openai") if self._registry else None
            if plugin and isinstance(plugin.config, dict):
                cfg_key = str(plugin.config.get("api_key") or "").strip()
            return bool(env_key or cfg_key)
        return False

    def _provider_ready(self, provider: str) -> bool:
        tool_id = self._provider_tool_id(provider)
        has_tool = bool(tool_id and self._registry and tool_id in self._registry.tools)
        return bool(has_tool and self._provider_key_present(provider))

    def _sanitize_provider_error(self, error_text: str) -> str:
        s = str(error_text or "").strip()
        if "\n" in s:
            s = s.split("\n", 1)[0]
        s = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-***", s)
        return s[:220] if len(s) > 220 else s

    def _provider_backoff_seconds(self, error_text: str) -> int:
        low = str(error_text or "").lower()
        if "insufficient balance" in low or "quota" in low or "exceeded your current quota" in low:
            return 600
        if "model" in low and "not found" in low:
            return 900
        if "429" in low:
            return 300
        return 120

    def _provider_in_backoff(self, provider: str) -> bool:
        return float(self._provider_backoff_until.get(provider, 0.0) or 0.0) > time.monotonic()

    def _provider_backoff_remaining(self, provider: str) -> int:
        remaining = float(self._provider_backoff_until.get(provider, 0.0) or 0.0) - time.monotonic()
        return max(0, int(remaining))

    def _record_provider_failure(self, provider: str, error_text: str) -> None:
        msg = self._sanitize_provider_error(error_text)
        self._provider_last_error[provider] = msg
        self._provider_backoff_until[provider] = time.monotonic() + self._provider_backoff_seconds(msg)

    def _clear_provider_failure(self, provider: str) -> None:
        self._provider_last_error.pop(provider, None)
        self._provider_backoff_until.pop(provider, None)

    def _chat_api_report_text(self) -> str:
        self._load_workspace_secrets_env()
        lines = ["API probe (chat providers):"]
        if self._ipc_enabled:
            try:
                ollama = self._network.call_core("ollama.health.ping", {})
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                ollama = {"status": "unavailable", "details": str(exc)}
            ollama_status = str(ollama.get("status") or "unavailable").upper() if isinstance(ollama, dict) else "UNAVAILABLE"
            ollama_base = str(ollama.get("base_url") or self._ollama_base_url) if isinstance(ollama, dict) else self._ollama_base_url
            lines.append(f"- ollama: {ollama_status} ({ollama_base})")
        for provider in ("deepseek", "gemini", "openai"):
            if provider in ("deepseek", "gemini", "openai"):
                tool_id = self._provider_tool_id(provider)
                has_tool = bool(self._registry and tool_id in self._registry.tools)
                key_ok = self._provider_key_present(provider)
                if has_tool and key_ok:
                    status = "OK"
                elif has_tool and not key_ok:
                    status = "MISSING_KEY"
                else:
                    status = "TOOL_MISSING"
                if self._provider_in_backoff(provider):
                    status += f" (cooldown {self._provider_backoff_remaining(provider)}s)"
                lines.append(f"- {provider}: {status}")
                last_error = self._provider_last_error.get(provider)
                if last_error:
                    lines.append(f"  last_error: {last_error}")
        chosen = next((p for p in self._provider_choice_order() if self._provider_ready(p)), "fallback")
        lines.append(f"- selected_for_chat: {chosen}")
        lines.append("Tip: write /api to re-check providers at any time.")
        return "\n".join(lines)

    def _build_chat_prompt(self, user_text: str, limit: int = 12) -> str:
        history: List[Dict[str, Any]] = []
        total = self._chat_manager.messages_model.count()
        start = max(0, total - max(2, int(limit)))
        for idx in range(start, total):
            item = self._chat_manager.messages_model.get(idx)
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "")
            text = str(item.get("text") or "").strip()
            if role not in ("user", "assistant") or not text:
                continue
            history.append({"role": role, "text": text})

        lines = ["Conversation context:"]
        for item in history:
            who = "User" if item["role"] == "user" else "Nova"
            lines.append(f"{who}: {item['text']}")
        lines.append("Respond naturally and briefly, matching user language.")
        lines.append("If user asks for file/code work, remind: /project <name>.")
        lines.append(f"User now: {user_text}")
        return "\n".join(lines)

    def _extract_provider_text(self, provider: str, payload: Dict[str, Any]) -> str:
        p = str(provider or "").strip().lower()
        if p in ("deepseek", "openai"):
            try:
                choices = payload.get("choices") or []
                if choices:
                    msg = choices[0].get("message") or {}
                    return str(msg.get("content") or "").strip()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return ""
        if p == "gemini":
            try:
                cands = payload.get("candidates") or []
                if cands:
                    content = cands[0].get("content") or {}
                    parts = content.get("parts") or []
                    if parts:
                        return str(parts[0].get("text") or "").strip()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return ""
        return ""

    def _call_chat_provider(self, provider: str, user_text: str) -> str:
        if not self._registry:
            return ""
        tool_id = self._provider_tool_id(provider)
        tool = self._registry.tools.get(tool_id)
        if tool is None:
            return ""

        system_prompt = (
            "You are Nova HUD assistant. Keep replies concise, practical, and clear. "
            "Respect safety: never execute apply directly; only suggest /project for workspace tasks."
        )
        prompt = self._build_chat_prompt(user_text)
        if provider in ("deepseek", "openai"):
            kwargs: Dict[str, Any] = {"prompt": prompt, "system": system_prompt, "temperature": 0.35}
        else:
            kwargs = {"text": prompt, "system": system_prompt, "temperature": 0.35}

        if self._runner:
            # External LLM tools are guarded by approval flow; grant only this one call.
            self._grant_single_approval()
            payload = self._runner.execute_registered_tool(tool, **kwargs)
        else:
            payload = tool.handler(**kwargs)
        if not isinstance(payload, dict):
            return ""
        return self._extract_provider_text(provider, payload)

    def _recent_user_messages(self, limit: int = 4) -> List[str]:
        out: List[str] = []
        for idx in range(self._chat_manager.messages_model.count() - 1, -1, -1):
            item = self._chat_manager.messages_model.get(idx)
            if not isinstance(item, dict):
                continue
            if str(item.get("role") or "") != "user":
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            out.append(text)
            if len(out) >= max(1, int(limit)):
                break
        out.reverse()
        return out

    def _recent_assistant_message(self) -> str:
        for idx in range(self._chat_manager.messages_model.count() - 1, -1, -1):
            item = self._chat_manager.messages_model.get(idx)
            if not isinstance(item, dict):
                continue
            if str(item.get("role") or "") != "assistant":
                continue
            text = str(item.get("text") or "").strip()
            if text:
                return text
        return ""

    def _pick_variant(self, seed: str, variants: List[str]) -> str:
        clean = [str(v) for v in variants if str(v).strip()]
        if not clean:
            return ""
        digest = hashlib.sha256(str(seed or "").encode("utf-8", "ignore")).hexdigest()
        index = int(digest[:8], 16) % len(clean)
        return clean[index]

    def _normalize_reply_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _looks_canned_reply(self, text: str) -> bool:
        normalized = self._normalize_reply_text(text)
        if not normalized:
            return True
        canned_tokens = [
            "ØªÙ… Ø§\u0633ØªÙ„Ø§Ù… Ø±Ø³Ø§Ù„ØªÙƒ",
            "general chat message saved",
            "online ai is required",
            "enable online ai to proceed",
            "use /project <name>",
        ]
        return any(token in normalized for token in canned_tokens)

    def _offline_contextual_reply(self, text: str) -> str:
        original = str(text or "").strip()
        low = original.lower()
        if low in ("/api", "api", "api status", "status api", "check api", "\u0641\u062d\u0635 api", "\u062d\u0627\u0644\u0629 api"):
            return self._chat_api_report_text()
        if low in ("/api reset", "api reset", "/api retry", "api retry"):
            self._provider_backoff_until.clear()
            self._provider_last_error.clear()
            return "API provider cooldowns were cleared. Type /api to inspect status again."

        if any(
            k in low
            for k in (
                "\u0635\u0628\u0627\u062d",
                "morning",
                "hello",
                "hi",
                "hey",
                "\u0627\u0647\u0644\u0627",
                "\u0623\u0647\u0644\u0627",
                "\u0645\u0631\u062d\u0628\u0627",
            )
        ):
            return "\u0635\u0628\u0627\u062d \u0627\u0644\u0646\u0648\u0631. \u0645\u0639\u0627\u0643 \u062e\u0637\u0648\u0629 \u0628\u062e\u0637\u0648\u0629. \u0642\u0644\u0651\u064a \u0639\u0627\u064a\u0632 \u0646\u0628\u062f\u0623 \u0645\u0646\u064a\u0646\u061f"
        if any(k in low for k in ("\u0643\u064a\u0641 \u062d\u0627\u0644\u0643", "\u0639\u0627\u0645\u0644 \u0627\u064a\u0647", "\u0639\u0627\u0645\u0644 \u0625\u064a\u0647", "how are you")):
            return self._pick_variant(
                original,
                [
                    "\u0623\u0646\u0627 \u0628\u062e\u064a\u0631. \u062c\u0627\u0647\u0632 \u0623\u0643\u0645\u0644 \u0645\u0639\u0643 \u0645\u0628\u0627\u0634\u0631\u0629 \u0639\u0644\u0649 \u0623\u064a \u0646\u0642\u0637\u0629.",
                    "\u062a\u0645\u0627\u0645. \u062a\u062d\u062a \u0623\u0645\u0631\u0643\u060c \u0642\u0648\u0644\u0651\u064a \u0627\u0644\u0633\u0624\u0627\u0644 \u0627\u0644\u0644\u064a \u0628\u0639\u062f\u0647 \u0648\u0646\u0628\u0646\u064a \u0639\u0644\u064a\u0647.",
                ],
            )
        if any(k in low for k in ("\u0645\u0627 \u0647\u0648 \u0627\u0644\u064a\u0648\u0645", "\u0627\u0644\u0646\u0647\u0627\u0631\u062f\u0629", "today", "date")):
            return f"\u0627\u0644\u064a\u0648\u0645 {datetime.now().strftime('%Y-%m-%d')}."
        if any(k in low for k in ("\u0645\u0646 \u0627\u0646\u062a", "\u0645\u0646 \u0623\u0646\u062a", "\u0627\u0633\u0645\u0643", "who are you", "your name")):
            return "\u0623\u0646\u0627 Nova \u062f\u0627\u062e\u0644 HUD. \u0623\u0642\u062f\u0631 \u0623\u062f\u064a\u0631 \u0627\u0644\u062d\u0648\u0627\u0631 \u0627\u0644\u0639\u0627\u0645 \u0623\u0648 \u0646\u062d\u0648\u0644 \u0627\u0644\u0634\u0627\u062a \u0644\u0645\u0634\u0631\u0648\u0639 \u0628\u0640 /project <name> \u0639\u0646\u062f \u0627\u0644\u062d\u0627\u062c\u0629."

        intent = parse_intent_soft(original)
        intent_name = str(intent.get("intent") or "unknown")
        if intent_name in ("plan", "analyze", "search", "verify", "pipeline", "apply", "execute"):
            return self._pick_variant(
                original,
                [
                    "\u0641\u0627\u0647\u0645 \u0625\u0646\u0643 \u062f\u0627\u062e\u0644 \u0639\u0644\u0649 \u0634\u063a\u0644 \u062a\u0642\u0646\u064a. \u0644\u0648 \u0639\u0627\u064a\u0632 \u0627\u0644\u062a\u0646\u0641\u064a\u0630 \u0639\u0644\u0649 \u0645\u0644\u0641\u0627\u062a \u0641\u0639\u0644\u064a\u0629\u060c \u0623\u0646\u0634\u0626 \u0645\u0634\u0631\u0648\u0639 \u0623\u0648\u0644\u064b\u0627 \u0628\u0640 /project <name>\u060c \u062b\u0645 \u0646\u0643\u0645\u0644.",
                    "\u0637\u0644\u0628\u0643 \u062a\u0642\u0646\u064a \u0648\u0645\u062d\u062a\u0627\u062c \u0633\u064a\u0627\u0642 \u0645\u0634\u0631\u0648\u0639. \u0627\u0643\u062a\u0628 /project <name> \u0639\u0634\u0627\u0646 \u0623\u0642\u062f\u0631 \u0623\u0634\u062a\u063a\u0644 \u0639\u0644\u0649 \u0627\u0644\u0645\u0644\u0641\u0627\u062a \u0645\u0639\u0627\u0643 \u0628\u0634\u0643\u0644 \u0622\u0645\u0646.",
                ],
            )

        recent_users = self._recent_user_messages(limit=3)
        prev_user = recent_users[-2] if len(recent_users) >= 2 else ""
        topic = original if len(original) <= 140 else original[:137] + "..."

        if prev_user and any(k in low for k in ("\u062f\u0647", "\u062f\u0627", "this", "that", "it", "\u062f\u064a")):
            prev_topic = prev_user if len(prev_user) <= 90 else prev_user[:87] + "..."
            return (
                f"\u0648\u0627\u0636\u062d \u0625\u0646\u0643 \u062a\u0642\u0635\u062f \u0627\u0644\u0646\u0642\u0637\u0629 \u0627\u0644\u0633\u0627\u0628\u0642\u0629: \"{prev_topic}\". "
                f"\u0648\u0628\u0627\u0644\u0646\u0633\u0628\u0629 \u0644\u0631\u0633\u0627\u0644\u062a\u0643 \u0627\u0644\u062d\u0627\u0644\u064a\u0629 \"{topic}\" \u0646\u0642\u062f\u0631 \u0646\u062d\u0648\u0644\u0647\u0627 \u0644\u062e\u0637\u0629 \u0628\u0633\u064a\u0637\u0629 \u0645\u0646 \u062e\u0637\u0648\u062a\u064a\u0646 \u0644\u0648 \u062a\u062d\u0628."
            )

        if "?" in original or "\u061f" in original:
            return self._pick_variant(
                original,
                [
                    f"\u0633\u0624\u0627\u0644 \u0645\u0645\u062a\u0627\u0632 \u0628\u062e\u0635\u0648\u0635 \"{topic}\". \u0623\u0639\u0637\u0646\u064a \u0633\u0637\u0631 \u0632\u064a\u0627\u062f\u0629 \u0639\u0646 \u0627\u0644\u0647\u062f\u0641 \u0627\u0644\u0646\u0647\u0627\u0626\u064a \u0648\u0623\u0646\u0627 \u0623\u062c\u0627\u0648\u0628\u0643 \u0628\u0634\u0643\u0644 \u0623\u062f\u0642.",
                    f"\u0641\u0647\u0645\u062a \u0633\u0624\u0627\u0644\u0643 \u0639\u0646 \"{topic}\". \u062a\u0641\u0636\u0651\u0644 \u0646\u062c\u0627\u0648\u0628 \u0628\u0634\u0643\u0644 \u0633\u0631\u064a\u0639 \u0648\u0644\u0627 \u062a\u0641\u0635\u064a\u0644\u064a\u061f",
                ],
            )

        return self._pick_variant(
            original,
            [
                f"\u0648\u0635\u0644\u062a\u0646\u064a \u0641\u0643\u0631\u062a\u0643: \"{topic}\". \u0623\u0643\u0645\u0644 \u0648\u0623\u0646\u0627 \u0647\u0631\u062a\u0651\u0628\u0647\u0627 \u0645\u0639\u0643 \u062e\u0637\u0648\u0629 \u0628\u062e\u0637\u0648\u0629.",
                f"\u0641\u0627\u0647\u0645 \u0642\u0635\u062f\u0643 \u0641\u064a \"{topic}\". \u0644\u0648 \u062a\u062d\u0628\u060c \u0623\u062d\u0648\u0651\u0644\u0647\u0627 \u0627\u0644\u0622\u0646 \u0644\u062e\u0637\u0629 \u062a\u0646\u0641\u064a\u0630 \u0642\u0635\u064a\u0631\u0629.",
                f"\u062a\u0645\u0627\u0645\u060c \u0627\u0644\u0631\u0633\u0627\u0644\u0629 \u0648\u0627\u0636\u062d\u0629: \"{topic}\". \u062d\u062f\u0651\u062f \u0623\u0648\u0644 \u0623\u0648\u0644\u0648\u064a\u0629 \u0646\u0628\u062f\u0623 \u0628\u0647\u0627.",
            ],
        )

    def _local_chat_brain_reply(self, text: str) -> str:
        ctx: Dict[str, Any] = {
            "online_enabled": False,
            "project_id": "",
            "prefs": {"explanation_level": "normal", "risk_posture": "balanced"},
            "state": None,
        }
        try:
            result = self._conversation_brain.respond(text, ctx)
            reply = str(getattr(result, "reply_text", "") or "").strip()
            if reply and not self._looks_canned_reply(reply):
                previous_assistant = self._recent_assistant_message()
                if self._normalize_reply_text(reply) != self._normalize_reply_text(previous_assistant):
                    return reply
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        return self._offline_contextual_reply(text)

    def _interactive_chat_reply(self, text: str) -> Dict[str, Any]:
        envelope = parse_mode_wrapped_message(text)
        provider_input = text if envelope.wrapped else str(text or "")
        local_input = envelope.text if envelope.wrapped else str(text or "")
        self._load_workspace_secrets_env()
        errors: Dict[str, str] = {}
        for provider in self._provider_choice_order():
            if not self._provider_ready(provider):
                continue
            if self._provider_in_backoff(provider):
                errors[provider] = f"cooldown {self._provider_backoff_remaining(provider)}s"
                continue
            try:
                out = self._call_chat_provider(provider, provider_input).strip()
                if out:
                    self._clear_provider_failure(provider)
                    return {"text": out, "source": provider, "errors": errors}
                self._record_provider_failure(provider, "empty response")
                errors[provider] = "empty response"
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                msg = self._sanitize_provider_error(str(e))
                self._record_provider_failure(provider, msg)
                errors[provider] = msg
                continue

        local_reply = self._local_chat_brain_reply(local_input)
        return {"text": local_reply, "source": "local", "errors": errors}

    def _reply_in_chat_mode(self, text: str) -> None:
        parsed = parse_mode_wrapped_message(text)
        local_text = parsed.text if parsed.wrapped else str(text or "")

        def work() -> Dict[str, Any]:
            return self._interactive_chat_reply(text)

        def done(payload: Dict[str, Any]) -> None:
            reply = str(payload.get("text") or "").strip()
            source = str(payload.get("source") or "local")
            errors = payload.get("errors") if isinstance(payload.get("errors"), dict) else {}
            self._append_assistant_message(reply or self._general_chat_reply(local_text))
            if source == "local":
                if errors:
                    self._set_status("Chat local fallback active. Type /api for provider status.")
                else:
                    self._set_status("Chat reply ready (local).")
            else:
                self._set_status(f"Chat reply ready ({source}).")

        def on_error(e: Exception) -> None:
            self._append_assistant_message(self._general_chat_reply(local_text))
            self._set_status(f"Chat fallback used: {e}")

        self._run_background("Generating chat reply", work, done, on_error)

    def _reply_in_chat_mode_ipc(self, text: str) -> None:
        parsed = parse_mode_wrapped_message(text)
        local_text = parsed.text if parsed.wrapped else str(text or "")

        def work() -> Dict[str, Any]:
            if not self._network:
                raise RuntimeError("Core service unavailable")
            result = self._network.call_core(
                "chat.send",
                {
                    "text": text,
                    "mode": self._current_task_mode,
                    "session_id": self._selected_project_id or GENERAL_CHAT_ID,
                    "project_path": "",
                    "write_reports": True,
                    "ui": "hud",
                    "ollama_model_override": self._ollama_session_model_override,
                },
            )
            return result

        def done(payload: Dict[str, Any]) -> None:
            assistant = payload.get("assistant") if isinstance(payload.get("assistant"), dict) else {}
            reply = str(assistant.get("text") or payload.get("response") or "").strip()
            try:
                llm_latency = float(payload.get("latency_ms") or 0.0)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                llm_latency = 0.0
            if llm_latency > 0:
                self._voice_manager.note_llm_latency(llm_latency)
                self._refresh_voice_status_line()
            self._append_assistant_message(reply or self._general_chat_reply(local_text))
            self._set_status("Chat reply ready (ipc).")

        def on_error(e: Exception) -> None:
            self._append_assistant_message(self._general_chat_reply(local_text))
            self._set_status("Core service failed to start")
            self._append_assistant_message(f"Core service failed to start: {e}")

        self._run_background("Generating chat reply", work, done, on_error)

    def _general_chat_reply(self, text: str) -> str:
        return self._offline_contextual_reply(text)

    def _append_assistant_message(self, text: str) -> None:
        payload = str(text or "").strip()
        if not payload:
            return
        self._append_message("assistant", payload)
        self._enqueue_voice_tts(payload)

    def _append_message(self, role: str, text: str) -> None:
        text_str = str(text or "")
        item = {"role": role, "text": text_str, "timestamp": _now()}
        self._chat_manager.messages_model.append_item(item)
        self._update_latest_reply_preview(text_str)

        pid = self._selected_project_id
        if self._is_chat_session(pid):
            self._chat_manager.append_message(pid, role, text_str)
        else:
            _write_jsonl(self._project_message_log(pid), item)

    def _load_messages(self, project_id: str) -> None:
        if self._is_chat_session(project_id):
            primary = self._chat_manager.chat_message_log(project_id)
            fallback = ""
        else:
            primary = self._project_message_log(project_id)
            fallback = os.path.join(self._project_paths(project_id).working, "chat.md")

        normalized = self._chat_manager.load_messages(primary, fallback)
        self._chat_manager.messages_model.set_items(normalized)
        latest = ""
        for item in reversed(normalized):
            if str(item.get("role") or "") == "assistant":
                latest = str(item.get("text") or "")
                break
        self._update_latest_reply_preview(latest)

    def _active_candidate(self) -> Optional[Dict[str, Any]]:
        pid = self._selected_project_id
        if not pid:
            return None
        return self._candidate_manager.get_active_candidate()

    def _remove_candidate(self, candidate_id: str) -> None:
        self._candidate_manager.remove_candidate(candidate_id)

    def _set_confirmation(self, mode: str, summary: str) -> None:
        changed = mode != self._confirmation_mode or summary != self._confirmation_summary
        self._confirmation_mode = mode
        self._confirmation_summary = summary
        if changed:
            self.confirmationChanged.emit()
            self.applyEnabledChanged.emit()

    def _refresh_confirmation(self) -> None:
        if self._confirmation_mode == "readonly":
            if self._tools_missing:
                return
            self._set_confirmation("none", "")
            return
        active = self._active_candidate()
        if active is None:
            self._set_confirmation("none", "")
            return
        rel = str(active.get("diff_rel") or active.get("diff_path") or "")
        plus = int(active.get("plus") or 0)
        minus = int(active.get("minus") or 0)
        status = str(active.get("status") or "")
        if status == "RUNNING":
            self._set_confirmation("running", f"I will execute: patch.apply {rel} (RUNNING)")
            return
        self._set_confirmation("pending", f"I will execute: patch.apply {rel} (+{plus}/-{minus})")

    def _show_tools_missing_notice(self) -> None:
        if not self._has_project_context():
            return
        if not self._tools_missing:
            return
        if self._active_candidate() is not None:
            return
        msg = "Apply disabled: missing tools " + ", ".join(self._tools_missing)
        self._set_confirmation("readonly", msg)

    def _emit_project_event(self, project_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        try:
            spine = ProjectAuditSpine(project_id, workspace_root=self._workspace_root)
            spine.emit(event_type, payload)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return

    def _derive_project_status(self, project_id: str, default_status: str = "risks") -> str:
        if any(
            c.get("project_id") == project_id and c.get("status") in ("PENDING", "RUNNING")
            for c in self._candidate_manager._pending_candidates
        ):
            return "awaiting confirm"
        if project_id in self._project_runtime_status:
            return self._project_runtime_status[project_id]
        try:
            state = self._project_manager.load_state(project_id)
            if str(state.last_diff_path or "").strip():
                return "awaiting confirm"
            if any("verify_smoke" in str(p) for p in (state.last_reports or [])):
                return "verified"
            return default_status
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return default_status

    def _set_project_runtime_status(self, project_id: str, status: str) -> None:
        self._project_runtime_status[project_id] = status
        if project_id == self._selected_project_id and status != self._project_status:
            self._project_status = status
            self.projectStatusChanged.emit()
            self.selectedProjectChanged.emit()

    def _probe_tools(self) -> None:
        missing: List[str] = []
        verify_candidates: List[str] = []
        tools = self._registry.tools if self._registry else {}

        if "patch.plan" not in tools:
            missing.append("patch.plan")
        if "patch.apply" not in tools:
            missing.append("patch.apply")
        verify_candidates = sorted([tid for tid in tools.keys() if tid.startswith("verify.")])
        if not verify_candidates:
            missing.append("verify.*")
        self._verify_tool_id = verify_candidates[0] if verify_candidates else ""
        self._tools_missing = missing

        badge = "Tools: OK" if not missing else f"Tools: MISSING({', '.join(missing)})"
        if badge != self._tools_badge:
            self._tools_badge = badge
            self.toolsBadgeChanged.emit()
            self.applyEnabledChanged.emit()
            self.capsChanged.emit()
        if missing:
            self._show_tools_missing_notice()
        else:
            self._refresh_confirmation()

    def _refresh_selected_project_snapshot(self) -> None:
        pid = self._selected_project_id
        if not pid:
            self._selected_project = {}
            self._project_status = "risks"
            self.selectedProjectChanged.emit()
            self.projectBadgeChanged.emit()
            self.projectStatusChanged.emit()
            return
        if self._is_chat_session(pid):
            chat_row = self._chat_manager.get_chat_row(pid)
            chat_name = str(chat_row.get("title") or ("General Chat" if self._is_general_chat(pid) else pid))
            chat_status = str(chat_row.get("status") or "chat")
            linked_project = str(chat_row.get("linked_project_id") or "")
            path_hint = "(chat session; not attached to project)"
            if linked_project:
                path_hint = f"converted to project: {linked_project}"
            self._project_status = "chat"
            self._selected_project = {
                "project_id": pid,
                "name": chat_name,
                "working_path": path_hint,
                "status": chat_status,
            }
            self.selectedProjectChanged.emit()
            self.projectBadgeChanged.emit()
            self.projectStatusChanged.emit()
            return
        try:
            info = self._project_manager.open_project(pid)
            status = self._derive_project_status(pid)
            self._project_status = status
            self._selected_project = {
                "project_id": pid,
                "name": str(info.get("name") or pid),
                "working_path": str(info.get("working") or ""),
                "status": status,
            }
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            self._selected_project = {
                "project_id": pid,
                "name": pid,
                "working_path": "",
                "status": self._derive_project_status(pid),
            }
            self._project_status = str(self._selected_project.get("status") or "risks")
        self.selectedProjectChanged.emit()
        self.projectBadgeChanged.emit()
        self.projectStatusChanged.emit()

    def _set_diff_preview(self, files: List[Dict[str, Any]], plus: int, minus: int, diff_text: str) -> None:
        self._last_diff_files = [dict(x or {}) for x in files]
        self._candidate_manager.diff_files_model.set_items(files)
        self._diff_stats_text = f"{len(files)} file(s) | +{plus} / -{minus}"
        self._diff_unified_text = diff_text
        self._diff_preview_visible = bool(diff_text or files)
        self.diffPreviewChanged.emit()

    def _load_geometry(self, project_id: str) -> None:
        if self._is_chat_session(project_id):
            self._entities_model.set_items([])
            self._geometry_empty = True
            self._three_d_summary = "Chat mode: no project geometry."
            self.geometryChanged.emit()
            self.summariesChanged.emit()
            return
        entities = self._geometry_adapter.load_entities(project_id, workspace_root=self._workspace_root)
        if entities:
            self._entities_model.set_items(entities)
            self._geometry_empty = False
            self._three_d_summary = f"{len(entities)} geometry entities loaded."
        else:
            self._entities_model.set_items([])
            self._geometry_empty = True
            self._three_d_summary = "No geometry loaded."
        self.geometryChanged.emit()
        self.summariesChanged.emit()

    def _hash_verify(self, target_root: str, changed_files: List[str]) -> Dict[str, Any]:
        hashes = []
        for rel in changed_files:
            norm = _normalize_diff_path(rel)
            if not norm:
                continue
            abs_path = os.path.abspath(os.path.join(target_root, norm))
            hashes.append(
                {
                    "path": norm,
                    "before": _sha256(abs_path + ".bak"),
                    "after": _sha256(abs_path),
                }
            )
        changed = [h for h in hashes if h.get("before") != h.get("after")]
        return {
            "mode": "hash",
            "hashes": hashes,
            "evidence": [f"hash differences: {len(changed)} file(s)"],
            "actions": ["verify fallback: file hash comparison"],
            "risks": [],
        }

    def _run_verify(self, target_root: str, changed_files: List[str]) -> Dict[str, Any]:
        if not self._verify_tool_id or not self._registry or not self._runner:
            return self._hash_verify(target_root, changed_files)
        tool = self._registry.tools.get(self._verify_tool_id)
        if tool is None:
            return self._hash_verify(target_root, changed_files)
        try:
            self._grant_single_approval()
            result = self._runner.execute_registered_tool(
                tool,
                target_root=target_root,
                write_reports=True,
            )
            failed = int(((result or {}).get("totals") or {}).get("failed_count") or 0)
            return {
                "mode": "tool",
                "tool_id": self._verify_tool_id,
                "result": result,
                "evidence": [f"{self._verify_tool_id} failed checks: {failed}"],
                "actions": [f"{self._verify_tool_id}: {'pass' if failed == 0 else 'fail'}"],
                "risks": [] if failed == 0 else [f"{failed} verification checks failed"],
            }
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            fallback = self._hash_verify(target_root, changed_files)
            fallback["risks"] = [f"verify tool failed: {e}"]
            return fallback

    def _set_verify_chips(self, payload: Dict[str, Any]) -> None:
        apply_res = payload.get("apply") or {}
        verify_res = payload.get("verify") or {}
        changed = payload.get("changed_files") or []
        totals = apply_res.get("totals") or {}
        success_count = int(totals.get("success_count") or 0)
        failed_count = int(totals.get("failed_count") or 0)

        evidence = [f"changed files: {len(changed)}"]
        evidence.extend([str(x) for x in (verify_res.get("evidence") or [])])

        actions = [f"patch.apply success={success_count} failed={failed_count}"]
        actions.extend([str(x) for x in (verify_res.get("actions") or [])])

        risks = [str(x) for x in (verify_res.get("risks") or [])]
        if str(payload.get("outcome") or "") != "success":
            risks.append("patch.apply reported failures")

        self._evidence_chip = "Evidence: " + ("; ".join(evidence) if evidence else "n/a")
        self._actions_chip = "Actions: " + ("; ".join(actions) if actions else "n/a")
        self._risks_chip = "Risks: " + ("; ".join(risks) if risks else "none")
        self.chipsChanged.emit()

    def _execute_apply_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        if not self._runner or not self._registry:
            raise RuntimeError("Runner not initialized.")
        tool = self._registry.tools.get("patch.apply")
        if tool is None:
            raise RuntimeError("patch.apply tool missing.")

        self._grant_single_approval()
        apply_res = self._runner.execute_registered_tool(
            tool,
            diff_path=str(candidate.get("diff_path") or ""),
            target_root=str(candidate.get("target_root") or ""),
            write_reports=True,
        )
        files = apply_res.get("files") or []
        changed_files = [str(x.get("path") or "") for x in files if str(x.get("status") or "") == "success"]
        if not changed_files:
            changed_files = [str(x.get("path") or "") for x in (candidate.get("files") or []) if x.get("path")]
        totals = apply_res.get("totals") or {}
        failed = int(totals.get("failed_count") or 0)
        success = int(totals.get("success_count") or 0)
        outcome = "success" if failed == 0 and success > 0 else "fail"
        verify = self._run_verify(str(candidate.get("target_root") or ""), changed_files)
        return {
            "apply": apply_res,
            "verify": verify,
            "changed_files": changed_files,
            "outcome": outcome,
        }

    def _known_diff_files(self) -> List[str]:
        out: List[str] = []
        for item in self._last_diff_files:
            path = str(item.get("path") or "").strip()
            if not path or path == "(deleted)" or path in out:
                continue
            out.append(path)
        return out

    def _run_verify_selected(self) -> None:
        pid = self._selected_project_id
        if not self._has_project_context():
            self._set_confirmation("readonly", "Select a project before verification.")
            return
        target_root = self._project_paths(pid).working
        changed_files = self._known_diff_files()

        def work() -> Dict[str, Any]:
            return self._run_verify(target_root, changed_files)

        def done(payload: Dict[str, Any]) -> None:
            evidence = [str(x) for x in (payload.get("evidence") or [])]
            actions = [str(x) for x in (payload.get("actions") or [])]
            risks = [str(x) for x in (payload.get("risks") or [])]
            self._evidence_chip = "Evidence: " + ("; ".join(evidence) if evidence else "n/a")
            self._actions_chip = "Actions: " + ("; ".join(actions) if actions else "n/a")
            self._risks_chip = "Risks: " + ("; ".join(risks) if risks else "none")
            self.chipsChanged.emit()

            outcome = "verified" if not risks else "risks"
            self._set_project_runtime_status(pid, outcome)
            self._emit_project_event(
                pid,
                "hud.verify.completed",
                {
                    "tool": str(payload.get("tool_id") or "hash.verify"),
                    "mode": str(payload.get("mode") or ""),
                    "changed_files": changed_files,
                    "outcome": "success" if not risks else "fail",
                    "risks": risks,
                },
            )
            self.refresh_timeline()
            self.refresh_projects()
            self._append_assistant_message("Verification finished for selected project.")
            self._set_status("Verification completed.")

        def on_error(e: Exception) -> None:
            self._set_project_runtime_status(pid, "risks")
            self._emit_project_event(
                pid,
                "hud.verify.completed",
                {
                    "tool": str(self._verify_tool_id or "hash.verify"),
                    "mode": "error",
                    "changed_files": changed_files,
                    "outcome": "fail",
                    "error": str(e),
                },
            )
            self.refresh_timeline()
            self.refresh_projects()
            self._append_assistant_message(f"Verification failed: {e}")
            self._set_status("Verification failed.")

        self._run_background("Running verification", work, done, on_error)

    def _open_reports_folder(self) -> None:
        reports_dir = _resolve_inside_root(self._workspace_root, os.path.join(self._workspace_root, "reports"))
        os.makedirs(reports_dir, exist_ok=True)

        if self._registry and self._runner and "desktop.open_folder" in self._registry.tools:
            tool = self._registry.tools["desktop.open_folder"]

            def work() -> Dict[str, Any]:
                self._grant_single_approval()
                return self._runner.execute_registered_tool(tool, path=reports_dir)

            def done(payload: Dict[str, Any]) -> None:
                self._append_assistant_message(f"Opened reports folder: {payload.get('path') or reports_dir}")
                self._set_status("Reports folder opened.")

            def on_error(e: Exception) -> None:
                self._append_assistant_message(f"Open reports folder failed: {e}")
                self._append_assistant_message(f"Reports path: {reports_dir}")
                self._set_status("Open reports folder failed.")

            self._run_background("Opening reports folder", work, done, on_error)
            return

        if self._registry and "fs.list_dir" in self._registry.tools:
            tool = self._registry.tools["fs.list_dir"]
            try:
                result = tool.handler(path=reports_dir)
                entries = result.get("entries") or result.get("items") or []
                self._append_assistant_message(f"Reports folder: {reports_dir} ({len(entries)} entries)")
                self._set_status("Reports folder inspected.")
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                self._append_assistant_message(f"Reports path: {reports_dir} ({e})")
                self._set_status("Reports path shown.")
            return

        self._append_assistant_message(f"Reports path: {reports_dir}")
        self._set_status("Reports path shown.")

    @Slot(result="QVariantList")
    def getPaletteActions(self):  # type: ignore[override]
        self._probe_tools()
        actions: List[Dict[str, Any]] = []
        selected = self._has_project_context()
        has_patch_plan = bool(self._registry and "patch.plan" in self._registry.tools)
        has_patch_apply = bool(self._registry and "patch.apply" in self._registry.tools)
        has_security = bool(self._registry and "security.audit" in self._registry.tools)
        has_desktop_open_folder = bool(self._registry and "desktop.open_folder" in self._registry.tools)
        has_fs_list = bool(self._registry and "fs.list_dir" in self._registry.tools)

        def badge(enabled: bool, missing: str = "", reason: str = "") -> str:
            if missing:
                return f"MISSING({missing})"
            if not enabled:
                return f"DISABLED({reason or 'not available'})"
            return "OK"

        actions.append(
            {
                "id": "chat.new",
                "title": "Chat: new session",
                "category": "Chat",
                "hotkey": "",
                "enabled": True,
                "description": "Start a normal chat session; convert later using /project <name>.",
                "badge": "OK",
            }
        )
        actions.append(
            {
                "id": "chat.api_probe",
                "title": "Chat: API probe",
                "category": "Chat",
                "hotkey": "",
                "enabled": True,
                "description": "Check DeepSeek/Gemini/OpenAI key and tool readiness.",
                "badge": "OK",
            }
        )
        actions.append(
            {
                "id": f"project.switch:{GENERAL_CHAT_ID}",
                "title": "Chat: switch to General",
                "category": "Chat",
                "hotkey": "",
                "enabled": not self._is_general_chat(),
                "description": "Use chat without binding to a project workspace.",
                "badge": badge(not self._is_general_chat(), reason="already selected"),
            }
        )
        for chat_row in self._chat_sessions_rows:
            cid = str(chat_row.get("chat_id") or "")
            if not cid or cid == GENERAL_CHAT_ID:
                continue
            title = str(chat_row.get("title") or cid)
            enabled = cid != self._selected_project_id
            actions.append(
                {
                    "id": f"chat.switch:{cid}",
                    "title": f"Chat: switch to {title}",
                    "category": "Chat",
                    "hotkey": "",
                    "enabled": enabled,
                    "description": "Switch active HUD context to a chat session.",
                    "badge": badge(enabled, reason="already selected"),
                }
            )
        actions.append(
            {
                "id": "project.create",
                "title": "Project: create from query",
                "category": "Project",
                "hotkey": "",
                "enabled": not self._has_project_context(),
                "description": "From chat mode, type project name in palette query to convert current chat into a project.",
                "badge": badge(not self._has_project_context(), reason="switch to chat mode first"),
            }
        )

        for item in self._project_manager.list_projects(include_archived=False):
            pid = str(item.get("id") or "")
            if not pid:
                continue
            enabled = pid != self._selected_project_id
            actions.append(
                {
                    "id": f"project.switch:{pid}",
                    "title": f"Project: switch to {pid}",
                    "category": "Project",
                    "hotkey": "",
                    "enabled": enabled,
                    "description": f"Switch active HUD context to project {pid}.",
                    "badge": badge(enabled, reason="already selected"),
                }
            )

        apply_enabled = self.applyEnabled
        apply_missing = ""
        if not has_patch_plan:
            apply_missing = "patch.plan"
        elif not has_patch_apply:
            apply_missing = "patch.apply"
        elif self._tools_missing:
            apply_missing = ", ".join(self._tools_missing)
        apply_reason = "select project" if not selected else ("busy/locked" if not apply_enabled else "")
        actions.append(
            {
                "id": "apply.queue",
                "title": "Apply: queue candidate",
                "category": "Apply",
                "hotkey": "Ctrl+Shift+A",
                "enabled": apply_enabled,
                "description": "Run patch.plan and create PendingApproval; never executes patch.apply directly.",
                "badge": badge(apply_enabled, missing=apply_missing, reason=apply_reason),
            }
        )

        verify_enabled = selected
        verify_missing = "" if self._verify_tool_id else "verify.*"
        actions.append(
            {
                "id": "verify.run",
                "title": "Verify: selected project",
                "category": "Verify",
                "hotkey": "",
                "enabled": verify_enabled,
                "description": "Run verify.* if available; otherwise hash-verify known changed files.",
                "badge": badge(verify_enabled, missing=verify_missing, reason="select project"),
            }
        )

        sec_enabled = selected and has_security
        actions.append(
            {
                "id": "security.audit",
                "title": "Security: run audit",
                "category": "Security",
                "hotkey": "",
                "enabled": sec_enabled,
                "description": "Run security doctor audit for selected project.",
                "badge": badge(sec_enabled, missing="" if has_security else "security.audit", reason="select project"),
            }
        )

        actions.append(
            {
                "id": "hud.refresh",
                "title": "Refresh: chats/projects/jobs/timeline",
                "category": "HUD",
                "hotkey": "",
                "enabled": True,
                "description": "Refresh chat sessions, project list, job list, and timeline models.",
                "badge": "OK",
            }
        )
        qa_exists = os.path.exists(self._qa_latest_path) or os.path.exists(self._qa_legacy_path)
        actions.append(
            {
                "id": "qa.refresh",
                "title": "QA: refresh latest report",
                "category": "QA",
                "hotkey": "",
                "enabled": True,
                "description": "Load workspace QA latest.json into read-only HUD models.",
                "badge": "OK" if qa_exists else "OK (path)",
            }
        )
        actions.append(
            {
                "id": "threed.activate",
                "title": "3D: activate viewport",
                "category": "3D",
                "hotkey": "",
                "enabled": selected,
                "description": "Load project geometry into the 3D viewport.",
                "badge": badge(selected, reason="select project"),
            }
        )
        actions.append(
            {
                "id": "threed.sample",
                "title": "3D: load sample geometry",
                "category": "3D",
                "hotkey": "",
                "enabled": True,
                "description": "Load local sample entities into the viewport.",
                "badge": "OK",
            }
        )

        reports_enabled = True
        reports_badge = "OK"
        reports_description = "Open workspace reports folder (workspace-only path)."
        if has_desktop_open_folder:
            reports_badge = "OK"
        elif has_fs_list:
            reports_badge = "OK (fs)"
            reports_description = "Inspect workspace reports folder via fs.list_dir (workspace-only path)."
        else:
            reports_badge = "OK (path)"
            reports_description = "Prints workspace reports path only (no folder-open tool available)."
        actions.append(
            {
                "id": "reports.open",
                "title": "Open reports folder",
                "category": "Workspace",
                "hotkey": "",
                "enabled": reports_enabled,
                "description": reports_description,
                "badge": reports_badge,
            }
        )

        voice_enabled = self._voice_enabled
        actions.append(
            {
                "id": "voice.toggle",
                "title": "Voice: toggle loop",
                "category": "Voice",
                "hotkey": "",
                "enabled": True,
                "description": "Enable or disable local voice loop (faster-whisper + Piper).",
                "badge": "ON" if voice_enabled else "OFF",
            }
        )
        actions.append(
            {
                "id": "voice.mute",
                "title": "Voice: mute",
                "category": "Voice",
                "hotkey": "",
                "enabled": voice_enabled and not self._voice_muted,
                "description": "Mute speech playback while keeping STT listening active.",
                "badge": badge(voice_enabled and not self._voice_muted, reason="already muted or disabled"),
            }
        )
        actions.append(
            {
                "id": "voice.unmute",
                "title": "Voice: unmute",
                "category": "Voice",
                "hotkey": "",
                "enabled": voice_enabled and self._voice_muted,
                "description": "Unmute speech playback.",
                "badge": badge(voice_enabled and self._voice_muted, reason="already unmuted or disabled"),
            }
        )
        actions.append(
            {
                "id": "voice.stop_speaking",
                "title": "Voice: stop speaking",
                "category": "Voice",
                "hotkey": "",
                "enabled": voice_enabled,
                "description": "Stop current TTS playback immediately.",
                "badge": badge(voice_enabled, reason="voice disabled"),
            }
        )
        actions.append(
            {
                "id": "voice.replay_last",
                "title": "Voice: replay last response",
                "category": "Voice",
                "hotkey": "",
                "enabled": voice_enabled and bool(self._voice_last_spoken_text),
                "description": "Replay the last assistant response via TTS.",
                "badge": badge(voice_enabled and bool(self._voice_last_spoken_text), reason="no spoken message"),
            }
        )

        return actions

    @Slot(str, str, result=bool)
    def runPaletteAction(self, action_id: str, queryText: str) -> bool:
        aid = str(action_id or "").strip()
        query = str(queryText or "").strip()
        if not aid:
            return False
        if aid == "chat.new":
            self.create_chat()
            return True
        if aid == "chat.api_probe":
            self._append_assistant_message(self._chat_api_report_text())
            self._set_status("API probe completed.")
            return True
        if aid.startswith("chat.switch:"):
            cid = aid.split(":", 1)[1].strip()
            if not cid:
                return False
            self.select_chat(cid)
            return True
        if aid == "project.create":
            if self._has_project_context():
                self._set_confirmation("readonly", "Switch to chat mode first.")
                return False
            if not query:
                self._set_confirmation("readonly", "Enter project name in palette query, then run Project: create.")
                return False
            source_chat_id = self._selected_project_id or GENERAL_CHAT_ID
            try:
                new_project_id, migrated, ingest_migration = self._convert_chat_to_project(source_chat_id, query)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                self._set_confirmation("readonly", f"Project create failed: {e}")
                return False
            self.refresh_projects()
            self.select_project(new_project_id)
            docs_migrated = int((ingest_migration.get("migrated_docs") or 0) if isinstance(ingest_migration, dict) else 0)
            self._append_assistant_message(
                (
                    f"Converted chat to project '{query}' and switched context. "
                    f"Migrated {migrated} message(s), {docs_migrated} attachment file(s)."
                )
            )
            return True
        if aid.startswith("project.switch:"):
            pid = aid.split(":", 1)[1].strip()
            if not pid:
                return False
            self.select_project(pid)
            return True
        if aid == "apply.queue":
            if not self.applyEnabled:
                self._show_tools_missing_notice()
                return False
            self.queue_apply()
            return True
        if aid == "verify.run":
            if not self._selected_project_id:
                return False
            self._run_verify_selected()
            return True
        if aid == "security.audit":
            if not self._selected_project_id:
                return False
            self.run_security_audit()
            return True
        if aid == "hud.refresh":
            self.refresh_chats()
            self.refresh_projects()
            self.refresh_jobs()
            self.refresh_timeline()
            self._set_status("HUD refreshed.")
            return True
        if aid == "qa.refresh":
            self.refreshQaReport()
            self._set_status("QA report refreshed.")
            return True
        if aid == "threed.activate":
            if not self._selected_project_id:
                return False
            self.activateThreeD()
            return True
        if aid == "threed.sample":
            self.loadSampleGeometry()
            return True
        if aid == "reports.open":
            self._open_reports_folder()
            return True
        if aid == "voice.toggle":
            self.toggle_voice_enabled()
            return True
        if aid == "voice.mute":
            self.voice_mute()
            return True
        if aid == "voice.unmute":
            self.voice_unmute()
            return True
        if aid == "voice.stop_speaking":
            self.voice_stop_speaking()
            return True
        if aid == "voice.replay_last":
            self.voice_replay_last()
            return True
        return False

    @Slot(bool, int, bool, result="QVariantMap")
    def shutdownNova(self, keep_ollama_running: bool = True, timeout_sec: int = 15, force: bool = True):  # type: ignore[override]
        if not self._ipc_enabled:
            return {
                "ok": False,
                "error": "IPC disabled",
                "watchdog": {},
            }
        timeout_s = max(1, int(timeout_sec))
        self._set_status("Shutting down Nova core...")
        if self._voice_manager.enabled:
            self._voice_manager.stop_loop()
            self._refresh_voice_status_line()
            self.voiceChanged.emit()
        try:
            result = self._network.request_system_shutdown(
                scope="core_and_events",
                timeout_sec=timeout_s,
                force=bool(force),
                keep_ollama_running=bool(keep_ollama_running),
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._set_status(f"Shutdown failed: {exc}")
            return {
                "ok": False,
                "error": str(exc),
                "watchdog": {},
            }
        watchdog = result.get("watchdog") if isinstance(result.get("watchdog"), dict) else {}
        ports_closed = watchdog.get("verified_ports_closed") if isinstance(watchdog.get("verified_ports_closed"), dict) else {}
        if bool(ports_closed.get("ipc")) and bool(ports_closed.get("events")):
            self._set_status("Nova core stopped.")
        else:
            self._set_status("Shutdown requested; waiting for core termination.")
        return result if isinstance(result, dict) else {"ok": False, "error": "invalid shutdown response"}

    @Slot(str, result=bool)
    def isUiActionAllowed(self, action_id: str) -> bool:
        aid = str(action_id or "").strip()
        if not aid:
            return False
        return aid in self._allowed_ui_action_kinds

    @Slot(str, str, str)
    def recordUiEvent(self, event_key: str, source: str = "", value: str = "") -> None:
        key = str(event_key or "").strip()
        if not key:
            return
        payload = {
            "ts": _now(),
            "event_key": key,
            "source": str(source or "").strip(),
            "value": str(value or "").strip(),
            "profile": self._ui_profile,
            "session_id": str(self._selected_project_id or GENERAL_CHAT_ID),
            "project_id": str(self._selected_project_id if self._has_project_context() else ""),
        }
        try:
            _write_jsonl(self._ui_events_log_path, payload)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return

    @Property(str, notify=uxChanged)
    def uiProfile(self) -> str:
        return self._ui_profile

    @Slot(str, result=bool)
    def isPanelPoppedOut(self, panel_id: str) -> bool:
        pid = self._normalize_panel_id(panel_id)
        popouts = self._layout_state.get("popouts") if isinstance(self._layout_state, dict) else {}
        if not isinstance(popouts, dict):
            return False
        return bool(popouts.get(pid, False))

    @Slot(str, bool)
    def setPanelPoppedOut(self, panel_id: str, popped: bool) -> None:
        pid = self._normalize_panel_id(panel_id)
        if not pid:
            return
        popouts = self._layout_state.setdefault("popouts", {})
        if not isinstance(popouts, dict):
            popouts = {}
            self._layout_state["popouts"] = popouts
        if bool(popouts.get(pid, False)) == bool(popped):
            return
        popouts[pid] = bool(popped)
        self._schedule_layout_save()

    @Slot(str, int, int, int, int)
    def updatePopoutGeometry(self, panel_id: str, x: int, y: int, width: int, height: int) -> None:
        pid = self._normalize_panel_id(panel_id)
        if not pid:
            return
        geos = self._layout_state.setdefault("geometries", {})
        if not isinstance(geos, dict):
            geos = {}
            self._layout_state["geometries"] = geos
        geo = {
            "x": int(x),
            "y": int(y),
            "width": max(0, int(width)),
            "height": max(0, int(height)),
        }
        prev = geos.get(pid)
        if isinstance(prev, dict) and prev == geo:
            return
        geos[pid] = geo
        self._schedule_layout_save()

    @Slot(str, result="QVariantMap")
    def getPopoutGeometry(self, panel_id: str):  # type: ignore[override]
        pid = self._normalize_panel_id(panel_id)
        geos = self._layout_state.get("geometries") if isinstance(self._layout_state, dict) else {}
        if not isinstance(geos, dict):
            return {}
        geo = geos.get(pid)
        if not isinstance(geo, dict):
            return {}
        return {
            "x": int(geo.get("x", 0)),
            "y": int(geo.get("y", 0)),
            "width": int(geo.get("width", 0)),
            "height": int(geo.get("height", 0)),
        }

    @Property(QObject, constant=True)
    def projectsModel(self) -> QObject:
        return self._projects_model

    @Property(QObject, constant=True)
    def chatsModel(self) -> QObject:
        return self._chat_manager.chats_model

    @Property(QObject, constant=True)
    def jobsModel(self) -> QObject:
        return self._jobs_model

    @Property(QObject, constant=True)
    def messagesModel(self) -> QObject:
        return self._chat_manager.messages_model

    @Property(QObject, constant=True)
    def timelineModel(self) -> QObject:
        return self._timeline_model

    @Property(QObject, constant=True)
    def entitiesModel(self) -> QObject:
        return self._entities_model

    @Property(QObject, notify=candidateChanged)
    def diffFilesModel(self) -> QObject:
        return self._candidate_manager.diff_files_model

    @Property(QObject, notify=candidateChanged)
    def qaFindingsModel(self) -> QObject:
        return self._candidate_manager.qa_findings_model

    @Property(QObject, notify=candidateChanged)
    def qaMetricsModel(self) -> QObject:
        return self._candidate_manager.qa_metrics_model

    @Property(bool, notify=jarvisModeChanged)
    def jarvisMode(self) -> bool:
        return self._jarvis_mode

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy_count > 0

    @Property(str, notify=statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=wiringStatusChanged)
    def wiringStatus(self) -> str:
        return self._wiring_status

    @Property(str, notify=capsChanged)
    def renderBackend(self) -> str:
        return self._render_backend

    @Property(str, notify=capsChanged)
    def capsSummary(self) -> str:
        backend = "real" if self._wiring_status.startswith("real") else "placeholder"
        return f"Backend={backend} | {self._tools_badge} | 3D={self._render_backend}"

    @Property(str, notify=currentProjectChanged)
    def currentProjectId(self) -> str:
        return self._selected_project_id

    @Property(str, notify=currentProjectChanged)
    def currentChatId(self) -> str:
        if self._is_chat_session(self._selected_project_id):
            return self._selected_project_id
        return ""

    @Property(str, notify=currentProjectChanged)
    def selectedProjectId(self) -> str:
        return self._selected_project_id

    @Property("QVariantMap", notify=selectedProjectChanged)
    def selectedProject(self):  # type: ignore[override]
        return dict(self._selected_project)

    @Property(str, notify=projectBadgeChanged)
    def projectBadge(self) -> str:
        if not self._selected_project_id:
            return "Project: (none)"
        if self._is_chat_session():
            name = str(self._selected_project.get("name") or "Chat")
            return f"Chat: {name}"
        return f"Project: {self._selected_project_id}"

    @Property(str, notify=projectStatusChanged)
    def projectStatus(self) -> str:
        return self._project_status

    @Property(str, notify=toolsBadgeChanged)
    def toolsBadge(self) -> str:
        return self._tools_badge

    @Property(bool, notify=applyEnabledChanged)
    def applyEnabled(self) -> bool:
        return self._has_project_context() and not self._tools_missing and self._confirmation_mode != "running" and not self.busy

    @Property(bool, notify=confirmationChanged)
    def hasPendingApproval(self) -> bool:
        return self._confirmation_mode != "none"

    @Property(str, notify=confirmationChanged)
    def confirmationSummary(self) -> str:
        return self._confirmation_summary

    @Property(bool, notify=confirmationChanged)
    def confirmationReadOnly(self) -> bool:
        return self._confirmation_mode == "readonly"

    @Property(bool, notify=confirmationChanged)
    def confirmationLocked(self) -> bool:
        return self._confirmation_mode == "running"

    @Property(bool, notify=diffPreviewChanged)
    def diffPreviewVisible(self) -> bool:
        return self._diff_preview_visible

    @Property(str, notify=diffPreviewChanged)
    def diffUnifiedText(self) -> str:
        return self._diff_unified_text

    @Property(str, notify=diffPreviewChanged)
    def diffStatsText(self) -> str:
        return self._diff_stats_text

    @Property(str, notify=chipsChanged)
    def evidenceChip(self) -> str:
        return self._evidence_chip

    @Property(str, notify=chipsChanged)
    def actionsChip(self) -> str:
        return self._actions_chip

    @Property(str, notify=chipsChanged)
    def risksChip(self) -> str:
        return self._risks_chip

    @Property(str, notify=summariesChanged)
    def engineeringSummary(self) -> str:
        return self._engineering_summary

    @Property(bool, notify=attachChanged)
    def hasImageAttachments(self) -> bool:
        return self._has_image_attachments

    @Property(str, notify=summariesChanged)
    def threeDSummary(self) -> str:
        return self._three_d_summary

    @Property(str, notify=summariesChanged)
    def sketchSummary(self) -> str:
        return self._sketch_summary

    @Property(str, notify=summariesChanged)
    def securitySummary(self) -> str:
        return self._security_summary

    @Property(str, notify=summariesChanged)
    def timelineSummary(self) -> str:
        return self._timeline_summary

    @Property(str, notify=qaChanged)
    def qaLatestPath(self) -> str:
        return self._qa_latest_path

    @Property(str, notify=qaChanged)
    def qaStatusChip(self) -> str:
        return self._qa_status_chip

    @Property(str, notify=qaChanged)
    def qaReportText(self) -> str:
        return self._qa_report_text

    @Property(str, notify=latestReplyChanged)
    def latestReplyPreview(self) -> str:
        return self._latest_reply_preview

    @Property(bool, notify=voiceChanged)
    def voiceEnabled(self) -> bool:
        return self._voice_manager.enabled

    @Property(bool, notify=voiceChanged)
    def voiceMuted(self) -> bool:
        return self._voice_manager.muted

    @Property(str, notify=voiceChanged)
    def voiceState(self) -> str:
        return self._voice_manager.state

    @Property(str, notify=voiceChanged)
    def voiceStatusLine(self) -> str:
        return self._voice_status_line

    @Property(str, notify=voiceChanged)
    def voiceProviderNames(self) -> str:
        return f"STT=faster-whisper:{self._voice_manager.config.stt_model}, TTS=piper"

    @Property(str, notify=voiceChanged)
    def voiceLastTranscript(self) -> str:
        return self._voice_manager.last_transcript

    @Property(str, notify=voiceChanged)
    def voiceLastSpokenText(self) -> str:
        return self._voice_manager.last_spoken_text

    @Property(str, notify=voiceChanged)
    def voiceLatencySummary(self) -> str:
        return self._voice_latency_summary

    @Property(str, notify=voiceChanged)
    def voiceReadinessSummary(self) -> str:
        return self._voice_readiness_summary

    @Property(bool, notify=voiceChanged)
    def voicePushToTalk(self) -> bool:
        return bool(self._voice_manager.config.push_to_talk)

    @Property(bool, notify=voiceChanged)
    def voicePushActive(self) -> bool:
        return bool(getattr(self._voice_manager, "push_to_talk_active", False))

    @Property(str, notify=voiceChanged)
    def voiceCurrentDevice(self) -> str:
        return self._voice_manager.config.device

    @Property("QVariantList", notify=uxChanged)
    def taskModesModel(self):  # type: ignore[override]
        return list(self._task_modes_rows)

    @Property(str, notify=uxChanged)
    def currentTaskMode(self) -> str:
        return self._current_task_mode

    @Property(bool, notify=uxChanged)
    def toolsMenuVisible(self) -> bool:
        return self._tools_menu_open

    @Property(QObject, constant=True)
    def toolsCatalogModel(self) -> QObject:
        return self._tools_catalog_model

    @Property(QObject, constant=True)
    def attachSummaryModel(self) -> QObject:
        return self._attach_summary_model

    @Property(QObject, constant=True)
    def healthStatsModel(self) -> QObject:
        return self._health_stats_model

    @Property(str, notify=uxChanged)
    def healthStatsSummary(self) -> str:
        return self._health_stats_summary

    @Property(str, notify=uxChanged)
    def ollamaHealthSummary(self) -> str:
        status = str(self._ollama_health_status or "unavailable").strip().upper()
        details = str(self._ollama_health_details or "").strip()
        detail_part = f" | {details}" if details else ""
        return (
            f"Local LLM: Ollama | Status={status} | Base={self._ollama_base_url} | "
            f"general={self._ollama_default_general_model} | code={self._ollama_default_code_model}"
            f"{detail_part}"
        )

    @Property("QVariantList", notify=uxChanged)
    def ollamaAvailableModels(self):  # type: ignore[override]
        return list(self._ollama_available_models)

    @Property(str, notify=uxChanged)
    def ollamaSessionModelOverride(self) -> str:
        return self._ollama_session_model_override

    @Property(str, notify=attachChanged)
    def attachLastSummary(self) -> str:
        return self._attach_last_summary

    @Property(bool, notify=geometryChanged)
    def geometryEmpty(self) -> bool:
        return self._geometry_empty

    @Slot()
    def toggleMode(self) -> None:
        self._jarvis_mode = not self._jarvis_mode
        self.jarvisModeChanged.emit()

    @Slot()
    def toggle_voice_enabled(self) -> None:
        if self._voice_manager.enabled:
            self._voice_manager.stop_loop()
        else:
            self._start_voice_or_status()
        self._refresh_voice_status_line()
        self.voiceChanged.emit()

    @Slot(bool)
    def set_voice_enabled(self, enabled: bool) -> None:
        if bool(enabled):
            self._start_voice_or_status()
        else:
            self._voice_manager.stop_loop()
        self._refresh_voice_status_line()
        self.voiceChanged.emit()

    @Slot()
    def voice_mute(self) -> None:
        self._voice_manager.set_muted(True)
        self._refresh_voice_status_line()
        self.voiceChanged.emit()

    @Slot()
    def voice_unmute(self) -> None:
        self._voice_manager.set_muted(False)
        self._refresh_voice_status_line()
        self.voiceChanged.emit()

    @Slot()
    def voice_stop_speaking(self) -> None:
        self._voice_manager.stop_speaking()
        self._refresh_voice_status_line()

    @Slot()
    def voice_replay_last(self) -> None:
        self._voice_manager.replay_last()
        self._refresh_voice_status_line()

    @Slot()
    def voicePushStart(self) -> None:
        if not bool(self._voice_manager.config.push_to_talk):
            return
        if not self._voice_manager.enabled:
            self._start_voice_or_status()
        self._voice_manager.set_push_to_talk_active(True)
        self._refresh_voice_status_line()
        self.voiceChanged.emit()

    @Slot()
    def voicePushStop(self) -> None:
        if not bool(self._voice_manager.config.push_to_talk):
            return
        self._voice_manager.set_push_to_talk_active(False)
        self._refresh_voice_status_line()
        self.voiceChanged.emit()

    @Slot()
    def refreshVoiceReadiness(self) -> None:
        report: Dict[str, Any]
        if self._ipc_enabled:
            try:
                payload = self._network.call_core("voice.readiness", {"sample_rate": int(self._voice_manager.config.sample_rate)})
                report = payload if isinstance(payload, dict) else {}
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                report = probe_voice_readiness(sample_rate=int(self._voice_manager.config.sample_rate))
        else:
            report = probe_voice_readiness(sample_rate=int(self._voice_manager.config.sample_rate))
        status = str(report.get("status") or "unknown").strip().lower()
        issues = report.get("issues") if isinstance(report.get("issues"), list) else []
        if status == "ready":
            self._voice_readiness_summary = "Voice readiness: ready"
        else:
            issue_text = "; ".join(str(x) for x in issues[:2]) if issues else "degraded"
            self._voice_readiness_summary = f"Voice readiness: degraded ({issue_text})"
        self.voiceChanged.emit()

    @Slot(str)
    def set_voice_device(self, device_name: str) -> None:
        self._voice_manager.set_config(device=str(device_name or "default"))
        if self._voice_manager.enabled:
            self._start_voice_or_status()  # Restart with new device
        else:
            self._persist_voice_preferences()
        self._refresh_voice_status_line()
        self.voiceChanged.emit()

    @Slot(str)
    def setTaskMode(self, mode_id: str) -> None:
        if is_auto_mode(mode_id):
            mode = auto_fallback_mode(self._registry, project_context=self._has_project_context())
        else:
            mode = normalize_task_mode(mode_id)
        if mode == self._current_task_mode:
            return
        allowed_ids = {str(row.get("id") or "") for row in self._task_modes_rows}
        if allowed_ids and mode not in allowed_ids:
            mode = "general"
        self._current_task_mode = mode
        self._persist_ux_preferences()
        self._refresh_tools_catalog()
        self.uxChanged.emit()

    @Slot()
    def openToolsMenu(self) -> None:
        if self._tools_menu_open:
            return
        self._tools_menu_open = True
        self.uxChanged.emit()

    @Slot()
    def closeToolsMenu(self) -> None:
        if not self._tools_menu_open:
            return
        self._tools_menu_open = False
        self.uxChanged.emit()

    @Slot()
    def toggleToolsMenu(self) -> None:
        self._tools_menu_open = not self._tools_menu_open
        self.uxChanged.emit()

    @Slot()
    def refreshHealthStats(self) -> None:
        self._refresh_health_stats()

    @Slot()
    def refreshOllamaModels(self) -> None:
        self._refresh_ollama_health()
        self.uxChanged.emit()

    @Slot(str)
    def setOllamaSessionModel(self, model_name: str) -> None:
        value = str(model_name or "").strip()
        if value.lower() == "default":
            value = ""
        if value == self._ollama_session_model_override:
            return
        self._ollama_session_model_override = value
        if value:
            self._set_status(f"Ollama session model override: {value}")
        else:
            self._set_status("Ollama session model override cleared")
        self.uxChanged.emit()

    @Slot(str, str, int, int, result="QVariantMap")
    def memorySearchPage(self, query: str, scope: str = "general", limit: int = 20, offset: int = 0):  # type: ignore[override]
        text = str(query or "").strip()
        if not text:
            self._set_status("Memory search returned no results.")
            return {"status": "ok", "hits": [], "total": 0, "offset": int(offset or 0), "limit": int(limit or 20)}
        scope_name = str(scope or "general").strip().lower() or "general"
        scope_id = self._selected_project_id if scope_name == "project" else (self._selected_project_id or GENERAL_CHAT_ID)
        if not self._ipc_enabled:
            self._set_status("Memory search unavailable (IPC disabled).")
            return {"status": "error", "hits": [], "total": 0, "offset": int(offset or 0), "limit": int(limit or 20)}
        try:
            payload = self._network.call_core(
                "memory.search",
                {
                    "query": text,
                    "scope": scope_name,
                    "scope_id": scope_id,
                    "limit": int(limit or 20),
                    "offset": int(offset or 0),
                },
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._set_status(f"Memory search failed: {exc}")
            return {
                "status": "error",
                "hits": [],
                "total": 0,
                "offset": int(offset or 0),
                "limit": int(limit or 20),
                "message": str(exc),
            }
        hits = payload.get("hits") if isinstance(payload, dict) else []
        if not isinstance(hits, list):
            self._set_status("Memory search returned no results.")
            return {"status": "ok", "hits": [], "total": 0, "offset": int(offset or 0), "limit": int(limit or 20)}
        filtered = [item for item in hits if isinstance(item, dict)]
        total = int(payload.get("total") or len(filtered)) if isinstance(payload, dict) else len(filtered)
        if filtered:
            self._set_status(f"Memory search returned {len(filtered)} results.")
        else:
            self._set_status("Memory search returned no results.")
        return {
            "status": "ok",
            "hits": filtered,
            "total": max(total, len(filtered)),
            "offset": int(offset or 0),
            "limit": int(limit or 20),
        }

    @Slot(str, str, int, int, result="QVariantList")
    def memorySearch(self, query: str, scope: str = "general", limit: int = 20, offset: int = 0):  # type: ignore[override]
        page = self.memorySearchPage(query, scope, limit, offset)
        hits = page.get("hits") if isinstance(page, dict) else []
        if not isinstance(hits, list):
            return []
        return [item for item in hits if isinstance(item, dict)]

    @Slot("QVariantList")
    def attachFiles(self, paths):  # type: ignore[override]
        normalized_paths = self._coerce_local_paths(paths)
        if not normalized_paths:
            self._set_status("No files selected for attachment.")
            return
        target_id = self._selected_project_id or GENERAL_CHAT_ID
        try:
            if self._has_project_context():
                result = self._ingest.ingest_project(target_id, normalized_paths)
            else:
                result = self._ingest.ingest_general(target_id, normalized_paths)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._set_status(f"Attach failed: {exc}")
            self._set_attach_summary(
                {
                    "accepted": [],
                    "rejected": [{"path": p, "reason": str(exc)} for p in normalized_paths],
                    "counts": {"files_extracted": 0},
                }
            )
            return
        self._set_attach_summary(result if isinstance(result, dict) else {})
        self._set_status(self._attach_last_summary)

    @Slot(str, result=bool)
    def migrateGeneralToProject(self, project_name: str) -> bool:
        if self._has_project_context():
            self._set_status("Already in project context.")
            return False
        source_chat_id = self._selected_project_id or GENERAL_CHAT_ID
        name = str(project_name or "").strip()
        if not name:
            self._set_status("Project name is required for migration.")
            return False
        try:
            new_project_id, migrated_messages, ingest_migration = self._convert_chat_to_project(source_chat_id, name)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._set_status(f"Migration failed: {exc}")
            return False

        self.refresh_projects()
        self.select_project(new_project_id)
        docs_migrated = int((ingest_migration.get("migrated_docs") or 0) if isinstance(ingest_migration, dict) else 0)
        self._append_assistant_message(
            f"Converted chat to project '{name}'. Migrated {migrated_messages} message(s), {docs_migrated} attachment file(s)."
        )
        self._set_status(f"Chat migrated to project: {name}")
        return True

    @Slot(result="QVariantList")
    def voice_input_devices(self):  # type: ignore[override]
        try:
            devices = list_input_devices()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, ImportError):
            return ["default"]
        if not devices:
            return ["default"]
        return devices

    @Slot()
    def refresh_chats(self) -> None:
        if self._updating_chats:
            return
        self._updating_chats = True
        try:
            selected_before = self._selected_project_id
            rows = self._chat_manager.refresh_chats()
            self._chat_sessions_rows = rows
            chat_ids = {str(r.get("chat_id") or "") for r in rows}
            if selected_before and selected_before in chat_ids:
                self._refresh_selected_project_snapshot()
                return
            if not self._selected_project_id:
                self._selected_project_id = GENERAL_CHAT_ID
                self.currentProjectChanged.emit()
        finally:
            self._updating_chats = False

    def _normalize_chat_id(self, chat_id: str) -> str:
        return self._chat_manager._normalize_chat_id(chat_id)

    @Slot(str)
    def select_chat(self, chat_id: str) -> None:
        cid = self._normalize_chat_id(chat_id)
        if not cid:
            return
        if not any(str(r.get("chat_id") or "") == cid for r in self._chat_manager._chat_sessions_rows):
            return
        self.select_project(cid)

    @Slot(result=str)
    def create_chat(self) -> str:
        cid = self._chat_manager.create_chat_session("")
        self.select_project(cid)
        self._append_assistant_message("New chat created. Use /project <name> any time to convert it to a project.")
        return cid

    @Slot()
    def refresh_projects(self) -> None:
        selected_before = self._selected_project_id
        rows: List[Dict[str, Any]] = []
        for item in self._project_manager.list_projects(include_archived=False):
            pid = str(item.get("id") or "")
            if not pid:
                continue
            status = self._derive_project_status(pid, "risks")
            try:
                paths = self._project_paths(pid)
                working = paths.working
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                working = ""
            rows.append(
                {
                    "project_id": pid,
                    "name": str(item.get("name") or pid),
                    "status": status,
                    "last_opened": str(item.get("last_opened") or ""),
                    "working_path": working,
                }
            )
        rows.sort(key=lambda x: x.get("last_opened") or "", reverse=True)
        self._projects_model.set_items(rows)
        ids = {r["project_id"] for r in rows}
        if selected_before and (selected_before in ids or self._is_chat_session(selected_before)):
            self._refresh_selected_project_snapshot()
            return
        self.select_project(GENERAL_CHAT_ID)

    @Slot(str)
    def select_project(self, project_id: str) -> None:
        pid = str(project_id or "").strip()
        if not pid:
            return
        if self._is_chat_session(pid):
            pid = self._normalize_chat_id(pid)
            if not pid:
                return
        changed = pid != self._selected_project_id
        self._selected_project_id = pid
        if changed:
            self.currentProjectChanged.emit()
            self.applyEnabledChanged.emit()
        self._refresh_selected_project_snapshot()
        self._load_messages(pid)
        self.refresh_jobs()
        self.refresh_timeline()
        self.refreshQaReport()
        self._load_geometry(pid)
        self._probe_tools()
        self._refresh_tools_catalog()
        self._refresh_confirmation()
        self._refresh_confirmation()
        if self._network:
            session_id, project_id = self._ipc_subscription_scope()
            self._network.update_subscription(session_id, project_id)
            self._restore_ipc_history()
        if self._is_chat_session(pid):
            self._touch_chat(pid)
            chat_name = str(self._selected_project.get("name") or "Chat")
            self._set_status(f"Chat selected: {chat_name}")
        else:
            self._touch_project(pid)
            self._set_status(f"Project selected: {pid}")

    @Slot()
    def refresh_jobs(self) -> None:
        pid = self._selected_project_id
        if not self._has_project_context():
            self._jobs_model.clear()
            self._engineering_summary = "Chat mode: jobs are project-only."
            self.summariesChanged.emit()
            return
        if not pid or not self._jobs_controller:
            self._jobs_model.clear()
            self._engineering_summary = "No jobs loaded."
            self.summariesChanged.emit()
            return
        rows = []
        jobs = self._jobs_controller.list_jobs(pid)
        for job in jobs:
            rows.append(
                {
                    "job_id": str(job.get("job_id") or ""),
                    "title": str(job.get("title") or "Job"),
                    "status": str(job.get("status") or "unknown"),
                    "steps": f"{int(job.get('steps_done') or 0)}/{int(job.get('steps_total') or 0)}",
                    "waiting_reason": str(job.get("waiting_reason") or ""),
                    "current_step_label": str(job.get("current_step_label") or ""),
                }
            )
        self._jobs_model.set_items(rows)
        pending = sum(1 for j in rows if j.get("status") == "waiting_for_user")
        self._engineering_summary = f"Jobs: {len(rows)} total; waiting confirm: {pending}"
        self.summariesChanged.emit()

    @Slot()
    def refresh_timeline(self) -> None:
        pid = self._selected_project_id
        if not self._has_project_context():
            self._timeline_model.clear()
            self._timeline_summary = "Chat mode: no project timeline."
            self.summariesChanged.emit()
            return
        if not pid:
            self._timeline_model.clear()
            self._timeline_summary = "No timeline events."
            self.summariesChanged.emit()
            return
        spine = ProjectAuditSpine(pid, workspace_root=self._workspace_root)
        events = spine.read_events(limit=300)
        rows = []
        for evt in reversed(events):
            payload = evt.get("payload") or {}
            detail = json.dumps(payload, ensure_ascii=False)
            rows.append(
                {
                    "event_type": str(evt.get("event_type") or ""),
                    "recorded_at": str(evt.get("recorded_at") or ""),
                    "detail": detail[:600],
                }
            )
        self._timeline_model.set_items(rows)
        self._timeline_summary = f"Timeline events: {len(events)}"
        self.summariesChanged.emit()

    @Slot()
    def refreshQaReport(self) -> None:
        candidates = [self._qa_latest_path, self._qa_legacy_path]
        chosen = self._qa_latest_path
        for candidate in candidates:
            try:
                safe = _resolve_inside_root(self._workspace_root, candidate)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                continue
            if os.path.exists(safe):
                chosen = safe
                break
            if candidate == self._qa_latest_path:
                chosen = safe

        self._qa_latest_path = chosen
        payload = _safe_read_json(chosen)
        if not payload:
            self._qa_status_chip = "QA: n/a"
            self._qa_report_text = "No QA report found."
            self._candidate_manager.qa_findings_model.set_items([])
            self._candidate_manager.qa_metrics_model.set_items([])
            self.qaChanged.emit()
            return

        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = str(summary.get("status") or "ok").lower()
        total = int(summary.get("findings_total") or 0)
        warn = int(summary.get("warn") or 0)
        fail = int(summary.get("fail") or 0)
        self._qa_status_chip = f"QA={status.upper()} | total={total} warn={warn} fail={fail}"

        run_id = str(payload.get("run_id") or "")
        project_id = str(payload.get("project_id") or "")
        self._qa_report_text = f"Run={run_id[:10] if run_id else 'n/a'} | project={project_id or 'n/a'}"

        findings_rows: List[Dict[str, Any]] = []
        findings = payload.get("findings")
        if isinstance(findings, list):
            for item in findings:
                if not isinstance(item, dict):
                    continue
                findings_rows.append(
                    {
                        "severity": str(item.get("severity") or ""),
                        "code": str(item.get("code") or ""),
                        "message": str(item.get("message") or ""),
                        "context": json.dumps(item.get("context") or {}, ensure_ascii=False),
                    }
                )
        self._candidate_manager.qa_findings_model.set_items(findings_rows)

        metric_rows: List[Dict[str, Any]] = []
        for section_name in ("dxf_metrics", "clip_metrics"):
            section = payload.get(section_name)
            if not isinstance(section, dict):
                legacy_name = "dxf" if section_name == "dxf_metrics" else "clip"
                section = payload.get(legacy_name)
            if not isinstance(section, dict):
                continue
            for key in sorted(section.keys()):
                value = section.get(key)
                if isinstance(value, (dict, list)):
                    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
                else:
                    rendered = str(value)
                metric_rows.append({"section": section_name, "key": str(key), "value": rendered})
        self._candidate_manager.qa_metrics_model.set_items(metric_rows)
        self.qaChanged.emit()

        if self._has_project_context():
            self._emit_project_event(
                self._selected_project_id,
                "hud.qa.refreshed",
                {
                    "path": self._qa_latest_path,
                    "status": status,
                    "findings_total": total,
                },
            )
            self.refresh_timeline()

    @Slot(str)
    def send_message(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        low = text.lower()
        if low.startswith("/project "):
            if self._has_project_context():
                self._set_confirmation("readonly", "Project already selected. Switch to chat mode to create another.")
                return
            source_chat_id = self._selected_project_id or GENERAL_CHAT_ID
            project_name = text.split(" ", 1)[1].strip()
            try:
                new_project_id, migrated, ingest_migration = self._convert_chat_to_project(source_chat_id, project_name)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                self._set_confirmation("readonly", f"Project create failed: {e}")
                self._append_assistant_message(f"Project create failed: {e}")
                return
            self.refresh_projects()
            self.select_project(new_project_id)
            docs_migrated = int((ingest_migration.get("migrated_docs") or 0) if isinstance(ingest_migration, dict) else 0)
            self._append_assistant_message(
                (
                    f"Converted chat to project '{project_name}' and switched context. "
                    f"Migrated {migrated} message(s), {docs_migrated} attachment file(s)."
                )
            )
            self._set_status(f"Project created: {project_name}")
            return
        if not self._selected_project_id:
            self.select_project(GENERAL_CHAT_ID)
        self._append_message("user", text)
        if self._is_chat_session():
            if "apply" in low or "patch" in low or low.startswith("edit"):
                self._set_confirmation("readonly", "Chat mode: create project with /project <name> first.")
                self._append_assistant_message(
                    "You're in chat mode. When you start files/data work, type /project <name>."
                )
                return
            routed = route_message_for_mode(
                self._current_task_mode,
                text,
                {
                    "ui": "hud",
                    "scope": self._selected_project_id or GENERAL_CHAT_ID,
                },
            )
            if self._ipc_enabled:
                self._reply_in_chat_mode_ipc(routed)
            else:
                self._reply_in_chat_mode(routed)
            return
        if "apply" in low or "patch" in low or low.startswith("edit"):
            self._queue_apply_internal(text)
            return
        if low in ("refresh", "reload"):
            self.refresh_projects()
            self.refresh_jobs()
            self.refresh_timeline()
            self._append_assistant_message("Project, jobs, and timeline refreshed.")
            return
        self._append_assistant_message("Message recorded in project log.")

    @Slot()
    def queue_apply(self) -> None:
        self._queue_apply_internal("")

    def _queue_apply_internal(self, goal_text: str) -> None:
        pid = self._selected_project_id
        if not self._has_project_context():
            self._set_confirmation("readonly", "General chat mode: create/select project first. Use /project <name>.")
            return
        self._probe_tools()
        if self._tools_missing:
            self._show_tools_missing_notice()
            return
        if not self._registry:
            self._set_confirmation("readonly", "Tool registry unavailable.")
            return
        tool = self._registry.tools.get("patch.plan")
        if tool is None:
            self._set_confirmation("readonly", "patch.plan not available.")
            return

        target_root = self._project_paths(pid).working
        goal = goal_text.strip() or "Generate safe patch candidate for selected project."

        def work() -> Dict[str, Any]:
            res = tool.handler(
                target_root=target_root,
                goal=goal,
                max_files=10,
                write_reports=True,
            )
            diff_ref = str(res.get("diff_path") or "").strip()
            if not diff_ref:
                raise RuntimeError("patch.plan returned no diff_path.")
            joined = diff_ref if os.path.isabs(diff_ref) else os.path.join(target_root, diff_ref)
            diff_abs = _resolve_inside_root(target_root, joined)
            if not os.path.exists(diff_abs):
                raise FileNotFoundError(f"diff not found: {diff_abs}")
            diff_text = _read_text(diff_abs)
            files, plus, minus = _parse_unified_diff(diff_text)
            return {
                "project_id": pid,
                "target_root": target_root,
                "diff_path": diff_abs,
                "diff_rel": os.path.relpath(diff_abs, target_root).replace("\\", "/"),
                "diff_text": diff_text,
                "files": files,
                "plus": plus,
                "minus": minus,
            }

        def done(payload: Dict[str, Any]) -> None:
            files = payload.get("files") or []
            plus = int(payload.get("plus") or 0)
            minus = int(payload.get("minus") or 0)
            diff_text = str(payload.get("diff_text") or "")
            self._set_diff_preview(files, plus, minus, diff_text)
            if not files:
                self._set_confirmation("readonly", "No diff hunks generated. Nothing to apply.")
                self._append_assistant_message("Patch plan generated no hunks.")
                self._set_project_runtime_status(pid, "risks")
                self.refresh_projects()
                return

            candidate = {
                "id": uuid.uuid4().hex,
                "project_id": pid,
                "target_root": str(payload.get("target_root") or ""),
                "diff_path": str(payload.get("diff_path") or ""),
                "diff_rel": str(payload.get("diff_rel") or ""),
                "files": files,
                "plus": plus,
                "minus": minus,
                "status": "PENDING",
                "created_at": _now(),
            }
            self._candidate_manager.add_candidate(candidate)
            self._refresh_confirmation()
            self._set_project_runtime_status(pid, "awaiting confirm")
            self._emit_project_event(
                pid,
                "hud.apply.candidate_created",
                {
                    "tool": "patch.plan",
                    "diff_path": candidate["diff_path"],
                    "target_root": candidate["target_root"],
                    "file_count": len(files),
                    "plus": plus,
                    "minus": minus,
                },
            )
            self.refresh_timeline()
            self.refresh_projects()
            self._append_assistant_message("Pending approval created for planned diff.")
            self._set_status("Apply candidate queued.")

        def on_error(e: Exception) -> None:
            msg = str(e)
            if "escapes target_root" in msg:
                self._emit_project_event(
                    pid,
                    "hud.apply.plan_rejected",
                    {
                        "tool": "patch.plan",
                        "target_root": target_root,
                        "outcome": "rejected",
                        "error": msg,
                    },
                )
                self.refresh_timeline()
            self._set_confirmation("readonly", f"Plan failed: {e}")
            self._append_assistant_message(f"patch.plan failed: {e}")
            self._set_status("Apply plan failed.")

        self._run_background("Planning apply candidate", work, done, on_error)

    @Slot()
    def confirm_pending(self) -> None:
        candidate = self._active_candidate()
        if candidate is None:
            if self._confirmation_mode == "readonly":
                self._set_confirmation("none", "")
            return
        if str(candidate.get("status") or "") != "PENDING":
            return

        pid = str(candidate.get("project_id") or "")
        candidate["status"] = "RUNNING"
        self._refresh_confirmation()
        self._candidate_manager.candidateChanged.emit()

        def work() -> Dict[str, Any]:
            return self._execute_apply_candidate(candidate)

        def done(payload: Dict[str, Any]) -> None:
            candidate["status"] = "DONE"
            changed_files = [str(p) for p in (payload.get("changed_files") or []) if p]
            outcome = str(payload.get("outcome") or "fail")
            self._set_verify_chips(payload)
            self._emit_project_event(
                pid,
                "hud.apply.completed",
                {
                    "tool": "patch.apply",
                    "diff_path": candidate.get("diff_path"),
                    "target_root": candidate.get("target_root"),
                    "changed_files": changed_files,
                    "outcome": outcome,
                },
            )
            self._remove_candidate(str(candidate.get("id") or ""))
            self._refresh_confirmation()
            if outcome == "success" and "verification checks failed" not in self._risks_chip:
                self._set_project_runtime_status(pid, "verified")
            else:
                self._set_project_runtime_status(pid, "risks")
            self.refresh_timeline()
            self.refresh_projects()
            self._append_assistant_message(f"Apply {outcome.upper()}: {len(changed_files)} file(s) changed.")
            self._set_status(f"Apply {outcome}.")

        def on_error(e: Exception) -> None:
            candidate["status"] = "FAILED"
            self._remove_candidate(str(candidate.get("id") or ""))
            self._refresh_confirmation()
            self._set_project_runtime_status(pid, "risks")
            self._evidence_chip = "Evidence: n/a"
            self._actions_chip = "Actions: patch.apply failed"
            self._risks_chip = f"Risks: {e}"
            self.chipsChanged.emit()
            self._emit_project_event(
                pid,
                "hud.apply.completed",
                {
                    "tool": "patch.apply",
                    "diff_path": candidate.get("diff_path"),
                    "target_root": candidate.get("target_root"),
                    "changed_files": [],
                    "outcome": "fail",
                    "error": str(e),
                },
            )
            self.refresh_timeline()
            self.refresh_projects()
            self._append_assistant_message(f"Apply failed: {e}")
            self._set_status("Apply failed.")

        self._run_background("Applying pending candidate", work, done, on_error)

    @Slot()
    def reject_pending(self) -> None:
        if self._confirmation_mode == "readonly":
            self._set_confirmation("none", "")
            return
        candidate = self._active_candidate()
        if candidate is None:
            return
        if str(candidate.get("status") or "") != "PENDING":
            return
        pid = str(candidate.get("project_id") or "")
        self._emit_project_event(
            pid,
            "hud.apply.rejected",
            {
                "tool": "patch.apply",
                "diff_path": candidate.get("diff_path"),
                "target_root": candidate.get("target_root"),
                "outcome": "rejected",
            },
        )
        self._remove_candidate(str(candidate.get("id") or ""))
        self._refresh_confirmation()
        self._set_project_runtime_status(pid, "risks")
        self.refresh_timeline()
        self.refresh_projects()
        self._append_assistant_message("Pending apply candidate rejected.")
        self._set_status("Pending apply rejected.")

    @Slot()
    def run_security_audit(self) -> None:
        pid = self._selected_project_id
        if not self._has_project_context():
            self._security_summary = "Select a project first."
            self.summariesChanged.emit()
            return
        if not self._registry:
            self._security_summary = "security.audit unavailable."
            self.summariesChanged.emit()
            return
        tool = self._registry.tools.get("security.audit")
        if tool is None:
            self._security_summary = "security.audit tool missing."
            self.summariesChanged.emit()
            return
        self._security_summary = "Security audit running..."
        self.summariesChanged.emit()

        def work() -> Dict[str, Any]:
            if self._runner is not None:
                self._grant_single_approval()
                return self._runner.execute_registered_tool(tool, project_id=pid, write_reports=True)
            return tool.handler(project_id=pid, write_reports=True)

        def done(payload: Dict[str, Any]) -> None:
            summary = payload.get("summary") or {}
            crit = int(summary.get("CRITICAL") or 0)
            warn = int(summary.get("WARNING") or 0)
            self._security_summary = f"Security Doctor: CRITICAL={crit}, WARNING={warn}"
            self.summariesChanged.emit()
            self._emit_project_event(pid, "hud.security.audit", {"critical": crit, "warning": warn})
            self.refresh_timeline()
            self._set_status("Security audit finished.")

        def on_error(e: Exception) -> None:
            self._security_summary = f"Security Doctor failed: {e}"
            self.summariesChanged.emit()
            self._set_status("Security audit failed.")

        self._run_background("Running security audit", work, done, on_error)

    @Slot()
    def activateThreeD(self) -> None:
        pid = self._selected_project_id
        if not self._has_project_context():
            return
        self._load_geometry(pid)

    @Slot()
    def loadSampleGeometry(self) -> None:
        entities = self._geometry_adapter.sample_entities()
        self._entities_model.set_items(entities)
        self._geometry_empty = False
        self._three_d_summary = f"Sample geometry loaded ({len(entities)} entities)."
        self.geometryChanged.emit()
        self.summariesChanged.emit()

    @Slot(int, bool)
    def setEntityVisible(self, row: int, visible: bool) -> None:
        self._entities_model.update_row(int(row), {"visible": bool(visible)})
