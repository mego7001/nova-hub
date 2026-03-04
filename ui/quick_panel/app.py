import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QInputDialog,
    QScrollArea,
)

from core.plugin_engine.registry import PluginRegistry
from core.plugin_engine.loader import PluginLoader
from core.permission_guard.tool_policy import ToolPolicy
from core.permission_guard.approval_flow import ApprovalFlow
from core.task_engine.runner import Runner
from core.projects.manager import ProjectManager
from core.projects.models import ProjectState
from core.security.secrets import SecretsManager
from core.fs.safe_workspace_writer import SafeWorkspaceWriter
from core.ingest.ingest_manager import IngestManager
from core.ingest.summary_contract import normalize_ingest_result, rejected_preview_lines
from core.run.smart_runner import detect_run_profiles
from core.security import required_secrets
from core.security.api_importer import ApiImporter
from core.security.status import get_key_status, provider_ready
from core.jobs.controller import JobController
from core.conversation.brain import ConversationalBrain
from core.llm.router import LLMRouter
from core.conversation.intent_parser import parse_intent_soft
from core.conversation.confirmation import build_prompt, is_confirmation, is_rejection, action_labels
from core.conversation.prefs import ConversationPrefs, load_prefs, save_prefs, update_recapped
from core.conversation import jarvis_core
from core.audit_spine import ProjectAuditSpine
from core.sketch import parser as sketch_parser
from core.sketch import store as sketch_store
from core.sketch.model import entity_summary
from core.sketch.renderer import SketchView
from core.geometry3d import intent as geometry3d_intent
from core.geometry3d import store as geometry3d_store
from core.geometry3d import reasoning as geometry3d_reasoning
from core.geometry3d import export as geometry3d_export
from core.geometry3d.preview import Geometry3DView
from core.engineering import extract as engineering_extract
from core.engineering import store as engineering_store
from core.security.online_mode import OnlineModeState
from core.ux.mode_routing import route_message_for_mode
from core.ux.task_modes import allowed_user_task_modes, auto_fallback_mode, is_auto_mode, normalize_task_mode
from core.ux.tools_catalog import build_tools_catalog, filter_codex_tool_rows
from core.ipc.client import EventsClient, IpcClient
from core.ipc.protocol import DEFAULT_HOST as IPC_DEFAULT_HOST, ipc_enabled, resolve_ipc_events_port, resolve_ipc_port
from core.ipc.spawn import ensure_core_running_with_events
from core.voice.audio_io import SoundDeviceAudioInput
from core.voice.providers import FasterWhisperSttProvider, PiperTtsProvider
from core.voice.schemas import VoiceConfig
from core.voice.voice_loop import VoiceLoop

from ui.chat.widgets import ArtifactList
from ui.quick_panel.widgets import ProjectListItem


class ApiSetupDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        secrets: SecretsManager,
        runner: Runner,
        registry: PluginRegistry,
        project_manager: ProjectManager,
        workspace_root: str,
        project_root: str,
        safe_writer: SafeWorkspaceWriter,
        get_project_id,
        append_message,
        refresh_banner,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("API Setup")
        self.setModal(True)
        self.secrets = secrets
        self.runner = runner
        self.registry = registry
        self.project_manager = project_manager
        self.workspace_root = workspace_root
        self.project_root = project_root
        self.safe_writer = safe_writer
        self.get_project_id = get_project_id
        self.append_message = append_message
        self.refresh_banner = refresh_banner
        self.skip_selected = False

        self.fields: dict[str, QLineEdit] = {}
        self.status_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter API keys (optional). Keys are stored in memory until saved."))

        self._add_field(layout, "DeepSeek API Key", "DEEPSEEK_API_KEY")
        self._add_field(layout, "Gemini API Key", "GEMINI_API_KEY")
        self._add_field(layout, "OpenAI API Key", "OPENAI_API_KEY")
        self._add_field(layout, "Telegram Bot Token", "TELEGRAM_BOT_TOKEN")
        self._add_field(layout, "Telegram Chat ID (optional)", "TELEGRAM_CHAT_ID")

        row = QHBoxLayout()
        self.import_btn = QPushButton("Import api.txt")
        self.skip_btn = QPushButton("Skip for now")
        self.skip_forever_btn = QPushButton("Skip and don't ask again")
        row.addWidget(self.import_btn)
        row.addWidget(self.skip_btn)
        row.addWidget(self.skip_forever_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self.import_msg = QLabel("")
        self.import_msg.setStyleSheet("color:#6b7280;")
        layout.addWidget(self.import_msg)

        self.note_label = QLabel("")
        self.note_label.setStyleSheet("color:#6b7280;")
        layout.addWidget(self.note_label)

        self.run_check_btn = QPushButton("Run Quick Check")
        self.run_check_btn.setStyleSheet("font-weight:bold;padding:6px;")
        self.run_check_btn.setEnabled(False)
        layout.addWidget(self.run_check_btn)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color:#2563eb;")
        layout.addWidget(self.summary_label)

        self.import_btn.clicked.connect(self._import_api_keys)
        self.skip_btn.clicked.connect(self._skip)
        self.skip_forever_btn.clicked.connect(self._skip_forever)
        self.run_check_btn.clicked.connect(self._run_quick_check)

        self._prefill_fields()
        self._refresh_statuses()

    def _add_field(self, layout: QVBoxLayout, label: str, key: str) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        field.setMinimumWidth(320)
        toggle = QPushButton("Show")
        toggle.setCheckable(True)
        status = QLabel("MISSING")
        status.setMinimumWidth(90)
        row.addWidget(field, 1)
        row.addWidget(toggle)
        row.addWidget(status)
        layout.addLayout(row)

        self.fields[key] = field
        self.status_labels[key] = status

        def _toggle(checked: bool) -> None:
            field.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            toggle.setText("Hide" if checked else "Show")

        def _changed(text: str) -> None:
            if text.strip():
                self.secrets.set_temp(key, text.strip())
            else:
                self.secrets.clear_temp(key)
            if key == "TELEGRAM_CHAT_ID" and text.strip():
                self.secrets.set_temp("TELEGRAM_DEFAULT_CHAT_ID", text.strip())
            self._refresh_statuses()
            self.refresh_banner()

        toggle.toggled.connect(_toggle)
        field.textChanged.connect(_changed)

    def _prefill_fields(self) -> None:
        for key, field in self.fields.items():
            val = self.secrets.get(key)
            if not val and key == "TELEGRAM_CHAT_ID":
                val = self.secrets.get("TELEGRAM_DEFAULT_CHAT_ID")
            if val:
                field.setText(val)

    def _refresh_statuses(self) -> None:
        keys = list(self.fields.keys())
        status = get_key_status(self.secrets, keys)
        for k in keys:
            st = status.get(k, "missing")
            label = self.status_labels.get(k)
            if not label:
                continue
            if st == "present":
                label.setText("OK")
                label.setStyleSheet("color:#16a34a;")
            elif st == "invalid_pattern":
                label.setText("INVALID")
                label.setStyleSheet("color:#dc2626;")
            else:
                if k == "TELEGRAM_CHAT_ID":
                    label.setText("MISSING (optional)")
                else:
                    label.setText("MISSING")
                label.setStyleSheet("color:#d97706;")

        any_valid = any(status.get(k) == "present" for k in ["DEEPSEEK_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN"])
        self.run_check_btn.setEnabled(any_valid or self.skip_selected)

    def _import_api_keys(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import api.txt", self.project_root, "Text Files (*.txt)")
        if not path:
            return
        try:
            text = open(path, "r", encoding="utf-8", errors="replace").read()
            importer = ApiImporter(self.secrets, runner=self.runner, registry=self.registry)
            found = importer.detect_keys(text)
            importer.import_from_text(text)
            if "TELEGRAM_DEFAULT_CHAT_ID" in found and "TELEGRAM_CHAT_ID" not in found:
                found["TELEGRAM_CHAT_ID"] = found["TELEGRAM_DEFAULT_CHAT_ID"]
            red = ApiImporter.redact_map(found)
            parts = []
            parts.append(f"DeepSeek {'OK' if red.get('DEEPSEEK_API_KEY') else 'MISS'}")
            parts.append(f"Gemini {'OK' if red.get('GEMINI_API_KEY') else 'MISS'}")
            parts.append(f"Telegram {'OK' if red.get('TELEGRAM_BOT_TOKEN') else 'MISS'}")
            parts.append(f"OpenAI {'OK' if red.get('OPENAI_API_KEY') else 'MISS'}")
            self.import_msg.setText("Imported: " + ", ".join(parts))
            for k, v in found.items():
                if k in self.fields:
                    self.fields[k].setText(v)
            self._refresh_statuses()
            self.refresh_banner()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _skip(self) -> None:
        self.skip_selected = True
        self.note_label.setText("You can set keys later.")
        self._refresh_statuses()

    def _skip_forever(self) -> None:
        self.skip_selected = True
        self.note_label.setText("You can set keys later.")
        marker = os.path.join(self.workspace_root, ".api_setup_skipped")
        self.safe_writer.write_text(marker, "ok\n")
        self._refresh_statuses()

    def _run_quick_check(self) -> None:
        verify_tool = self.registry.tools.get("verify.smoke")
        if not verify_tool:
            QMessageBox.warning(self, "Missing Tool", "verify.smoke not available.")
            return
        target_root = self.project_root
        project_id = self.get_project_id()
        if project_id:
            paths = self.project_manager.get_project_paths(project_id)
            target_root = paths.working
        try:
            res = self.runner.execute_registered_tool(verify_tool, target_root=target_root, write_reports=True)
            totals = res.get("totals") or {}
            failed = totals.get("failed_count", 0)
            verify_status = "PASS" if failed == 0 else "FAIL"
            report_paths = res.get("report_paths") or []
            summary = f"Verify {verify_status}. Reports: {', '.join([os.path.basename(p) for p in report_paths])}"
            if project_id:
                convo = self.registry.tools.get("conversation.chat")
                if convo:
                    self.runner.execute_registered_tool(
                        convo,
                        user_message="analyze",
                        project_path=target_root,
                        session_id=project_id,
                        write_reports=True,
                    )
                    summary += " | Analyze completed."
            else:
                summary += " | Select or create a project to analyze."
            self.summary_label.setText(summary)
            if self.append_message:
                self.append_message("System", summary)
            self._mark_first_run_done()
            QMessageBox.information(self, "Quick Check", summary)
            self.accept()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Quick Check Error", str(e))

    def _mark_first_run_done(self) -> None:
        marker = os.path.join(self.workspace_root, ".first_run_done")
        self.safe_writer.write_text(marker, "ok\n")


class QuickPanelWindow(QMainWindow):
    ipcEventReceived = Signal(object)
    ipcConnectionChanged = Signal(bool, str)

    def __init__(self, project_root: str):
        super().__init__()
        self.project_root = project_root
        self.setWindowTitle("Nova Hub Quick Panel")
        self.resize(1400, 800)

        self.registry = PluginRegistry()
        PluginLoader(self.project_root).load_enabled(
            os.path.join(self.project_root, "configs", "plugins_enabled.yaml"),
            self.registry,
        )

        profile = os.environ.get("NH_PROFILE", "engineering")
        tool_policy = ToolPolicy(
            os.path.join(self.project_root, "configs", "tool_policy.yaml"),
            active_profile=profile,
            ui_mode=True,
        )
        approvals = ApprovalFlow(
            tool_policy,
            os.path.join(self.project_root, "configs", "approvals.yaml"),
        )
        self.runner = Runner(approval_flow=approvals, approval_callback=self._approval_callback)

        self.session_id = "default"
        self.project_path = ""
        self.current_project_id = ""
        self.workspace_root = os.environ.get("NH_WORKSPACE", os.path.join(self.project_root, "workspace"))
        self.project_manager = ProjectManager(self.workspace_root)
        self.secrets = SecretsManager(workspace_root=self.workspace_root)
        self.safe_writer = SafeWorkspaceWriter(self.workspace_root)
        self.ingest = IngestManager(self.workspace_root, runner=self.runner, registry=self.registry)
        self.job_controller = JobController(self.runner, self.registry, approvals, self.workspace_root)
        self.tool_policy = tool_policy
        self.general_chat_id = "chat_quick_panel_general"
        self.current_task_mode = normalize_task_mode("general")
        self.task_modes = allowed_user_task_modes(self.registry, include_unavailable=False)
        self.tools_catalog: dict[str, object] = {}
        self.tools_menu = QMenu(self)
        self.voice_config = VoiceConfig.from_env()
        self.voice_loop: VoiceLoop | None = None
        self.voice_enabled = False
        self.voice_muted = False
        self._approval_session_allowed = False
        self._ipc_enabled = ipc_enabled()
        self._ipc_host = IPC_DEFAULT_HOST
        self._ipc_port = resolve_ipc_port(None)
        self._ipc_events_port = resolve_ipc_events_port(None, rpc_port=self._ipc_port)
        self._ipc_token = str(os.environ.get("NH_IPC_TOKEN") or "").strip()
        self._ipc_client: IpcClient | None = None
        self._ipc_events_client: EventsClient | None = None
        self._ipc_start_error = ""
        self._ipc_progress_label = ""
        self._ipc_progress_pct = 0

        self.conversation_tool = self.registry.tools.get("conversation.chat")
        self._wire_conversation_context()
        self._wire_security_context()
        self.ipcEventReceived.connect(self._on_ipc_event)
        self.ipcConnectionChanged.connect(self._on_ipc_connection_changed)

        # Left: project list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("Search projects...")
        self.show_archived_toggle = QCheckBox("Show archived")
        self.project_list = QListWidget()
        self.new_project_btn = QPushButton("+ New Project")
        left_layout.addWidget(self.project_search)
        left_layout.addWidget(self.show_archived_toggle)
        left_layout.addWidget(self.project_list)
        left_layout.addWidget(self.new_project_btn)

        # Center: chat
        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.conv_mode_toggle = QPushButton("Conversational Mode: ON")
        self.conv_mode_toggle.setCheckable(True)
        self.conv_mode_toggle.setChecked(True)
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.confirm_action_bar = QWidget()
        confirm_action_layout = QHBoxLayout(self.confirm_action_bar)
        confirm_action_layout.setContentsMargins(0, 0, 0, 0)
        self.confirm_action_label = QLabel("Ready to proceed?")
        self.confirm_action_btn = QPushButton("Confirm")
        self.cancel_action_btn = QPushButton("Cancel")
        confirm_action_layout.addWidget(self.confirm_action_label)
        confirm_action_layout.addStretch(1)
        confirm_action_layout.addWidget(self.confirm_action_btn)
        confirm_action_layout.addWidget(self.cancel_action_btn)
        self.confirm_action_bar.setVisible(False)
        self.attach_button = QPushButton("Attach")
        self.mic_button = QPushButton("Mic")
        self.task_mode_combo = QComboBox()
        self.task_mode_combo.setMinimumWidth(150)
        self.tools_button = QPushButton("Tools")
        self.health_button = QPushButton("Health")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message...")
        self.voice_stop_button = QPushButton("Stop Voice")
        self.voice_stop_button.setEnabled(False)
        self.send_button = QPushButton("Send")
        input_row = QHBoxLayout()
        input_row.addWidget(self.attach_button)
        input_row.addWidget(self.mic_button)
        input_row.addWidget(self.task_mode_combo)
        input_row.addWidget(self.tools_button)
        input_row.addWidget(self.health_button)
        input_row.addWidget(self.input)
        input_row.addWidget(self.voice_stop_button)
        input_row.addWidget(self.send_button)
        self.explain_label = QLabel("Explanation:")
        self.explain_combo = QComboBox()
        self.explain_combo.addItems(["short", "normal", "detailed"])
        self.risk_label = QLabel("Risk:")
        self.risk_combo = QComboBox()
        self.risk_combo.addItems(["conservative", "balanced", "aggressive"])
        self.just_do_toggle = QCheckBox("Just do")
        self.speaker_toggle = QCheckBox("Speak")
        prefs_row = QHBoxLayout()
        prefs_row.addWidget(self.explain_label)
        prefs_row.addWidget(self.explain_combo)
        prefs_row.addSpacing(8)
        prefs_row.addWidget(self.risk_label)
        prefs_row.addWidget(self.risk_combo)
        prefs_row.addSpacing(8)
        prefs_row.addWidget(self.just_do_toggle)
        prefs_row.addSpacing(8)
        prefs_row.addWidget(self.speaker_toggle)
        prefs_row.addStretch(1)
        center_layout.addWidget(self.conv_mode_toggle)
        center_layout.addWidget(self.transcript)
        center_layout.addWidget(self.confirm_action_bar)
        center_layout.addLayout(prefs_row)
        center_layout.addLayout(input_row)

        # Right: tabs
        # Jobs tab
        self.jobs_tab = QWidget()
        jobs_layout = QVBoxLayout(self.jobs_tab)
        self.jobs_list = QListWidget()
        self.jobs_status = QLabel("Select a job to view details.")
        jobs_layout.addWidget(self.jobs_list)
        jobs_layout.addWidget(self.jobs_status)
        self.job_waiting_panel = QWidget()
        wait_layout = QHBoxLayout(self.job_waiting_panel)
        wait_layout.setContentsMargins(0, 0, 0, 0)
        self.job_waiting_label = QLabel("Waiting to apply diff")
        self.job_open_diff_btn = QPushButton("Open Diff")
        self.job_confirm_apply_btn = QPushButton("Confirm Apply")
        self.job_skip_btn = QPushButton("Skip")
        self.job_stop_btn = QPushButton("Stop")
        wait_layout.addWidget(self.job_waiting_label)
        wait_layout.addStretch(1)
        wait_layout.addWidget(self.job_open_diff_btn)
        wait_layout.addWidget(self.job_confirm_apply_btn)
        wait_layout.addWidget(self.job_skip_btn)
        wait_layout.addWidget(self.job_stop_btn)
        self.job_waiting_panel.setVisible(False)
        jobs_layout.addWidget(self.job_waiting_panel)
        btn_row = QHBoxLayout()
        self.create_job_btn = QPushButton("Create Job")
        self.start_job_btn = QPushButton("Start")
        self.pause_job_btn = QPushButton("Pause")
        self.resume_job_btn = QPushButton("Resume")
        self.cancel_job_btn = QPushButton("Cancel")
        self.preview_job_btn = QPushButton("Request Preview")
        self.view_logs_btn = QPushButton("View Logs")
        self.open_artifacts_btn = QPushButton("Open Artifacts")
        for b in [self.create_job_btn, self.start_job_btn, self.pause_job_btn, self.resume_job_btn, self.cancel_job_btn]:
            btn_row.addWidget(b)
        jobs_layout.addLayout(btn_row)
        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(self.preview_job_btn)
        btn_row2.addWidget(self.view_logs_btn)
        btn_row2.addWidget(self.open_artifacts_btn)
        btn_row2.addStretch(1)
        jobs_layout.addLayout(btn_row2)
        self.jobs_log = QTextEdit()
        self.jobs_log.setReadOnly(True)
        jobs_layout.addWidget(self.jobs_log)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.tabs = QTabWidget()

        # Suggestions tab
        self.suggestions_tab = QWidget()
        sug_layout = QVBoxLayout(self.suggestions_tab)
        self.refresh_suggestions_btn = QPushButton("Refresh Suggestions")
        sug_layout.addWidget(self.refresh_suggestions_btn)
        self.suggestions_scroll = QScrollArea()
        self.suggestions_scroll.setWidgetResizable(True)
        self.suggestions_container = QWidget()
        self.suggestions_list_layout = QVBoxLayout(self.suggestions_container)
        self.suggestions_list_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestions_scroll.setWidget(self.suggestions_container)
        sug_layout.addWidget(self.suggestions_scroll)
        self.confirm_bar = QWidget()
        confirm_layout = QHBoxLayout(self.confirm_bar)
        self.confirm_label = QLabel("Diff ready.")
        self.confirm_apply_btn = QPushButton("Confirm Apply")
        self.confirm_cancel_btn = QPushButton("Cancel")
        confirm_layout.addWidget(self.confirm_label)
        confirm_layout.addStretch(1)
        confirm_layout.addWidget(self.confirm_apply_btn)
        confirm_layout.addWidget(self.confirm_cancel_btn)
        self.confirm_bar.setVisible(False)
        sug_layout.addWidget(self.confirm_bar)

        # Artifacts tab
        self.artifacts_tab = QWidget()
        art_layout = QVBoxLayout(self.artifacts_tab)
        self.artifacts_reports = ArtifactList("Reports (last 5)")
        self.artifacts_patches = ArtifactList("Patches (last 3)")
        self.artifacts_snapshots = ArtifactList("Snapshots (last 3)")
        self.artifacts_releases = ArtifactList("Releases (last 3)")
        art_layout.addWidget(self.artifacts_reports)
        art_layout.addWidget(self.artifacts_patches)
        art_layout.addWidget(self.artifacts_snapshots)
        art_layout.addWidget(self.artifacts_releases)

        # Docs tab
        self.docs_tab = QWidget()
        docs_layout = QVBoxLayout(self.docs_tab)
        self.docs_summary = QLabel("Docs: 0")
        self.open_docs = QPushButton("Open docs")
        self.open_extracted = QPushButton("Open extracted")
        docs_layout.addWidget(self.docs_summary)
        docs_layout.addWidget(self.open_docs)
        docs_layout.addWidget(self.open_extracted)

        # Sketch tab
        self.sketch_tab = QWidget()
        sketch_layout = QVBoxLayout(self.sketch_tab)
        self.sketch_summary = QLabel("Sketch: 0 entities")
        self.sketch_view = SketchView()
        self.sketch_entities_list = QListWidget()
        self.sketch_export_btn = QPushButton("Export DXF")
        sketch_layout.addWidget(self.sketch_summary)
        sketch_layout.addWidget(self.sketch_view, 1)
        sketch_layout.addWidget(self.sketch_entities_list)
        sketch_layout.addWidget(self.sketch_export_btn)

        # 3D tab
        self.geometry3d_tab = QWidget()
        g3_layout = QVBoxLayout(self.geometry3d_tab)
        self.geometry3d_summary = QLabel("3D: no model")
        self.geometry3d_view = Geometry3DView()
        self.geometry3d_entities_list = QListWidget()
        self.geometry3d_assumptions = QListWidget()
        self.geometry3d_warnings = QListWidget()
        self.geometry3d_confirm_btn = QPushButton("Confirm Geometry")
        self.geometry3d_assumptions_btn = QPushButton("Modify Assumptions")
        self.geometry3d_export_btn = QPushButton("Export STL")
        self.geometry3d_export_btn.setEnabled(False)
        g3_layout.addWidget(self.geometry3d_summary)
        g3_layout.addWidget(self.geometry3d_view, 1)
        g3_layout.addWidget(QLabel("Entities"))
        g3_layout.addWidget(self.geometry3d_entities_list)
        g3_layout.addWidget(QLabel("Assumptions"))
        g3_layout.addWidget(self.geometry3d_assumptions)
        g3_layout.addWidget(QLabel("Warnings"))
        g3_layout.addWidget(self.geometry3d_warnings)
        btn_row_g3 = QHBoxLayout()
        btn_row_g3.addWidget(self.geometry3d_confirm_btn)
        btn_row_g3.addWidget(self.geometry3d_assumptions_btn)
        btn_row_g3.addWidget(self.geometry3d_export_btn)
        g3_layout.addLayout(btn_row_g3)

        # Engineering tab
        self.engineering_tab = QWidget()
        eng_layout = QVBoxLayout(self.engineering_tab)
        self.engineering_summary = QLabel("Engineering: no analysis")
        self.engineering_findings = QListWidget()
        self.engineering_assumptions = QListWidget()
        self.engineering_report_btn = QPushButton("Generate Design Report")
        self.engineering_edit_assumptions_btn = QPushButton("Edit Assumptions")
        eng_layout.addWidget(self.engineering_summary)
        eng_layout.addWidget(QLabel("Findings"))
        eng_layout.addWidget(self.engineering_findings)
        eng_layout.addWidget(QLabel("Assumptions"))
        eng_layout.addWidget(self.engineering_assumptions)
        btn_row_eng = QHBoxLayout()
        btn_row_eng.addWidget(self.engineering_edit_assumptions_btn)
        btn_row_eng.addWidget(self.engineering_report_btn)
        eng_layout.addLayout(btn_row_eng)

        # Run tab
        self.run_tab = QWidget()
        run_layout = QVBoxLayout(self.run_tab)
        self.run_preview_btn = QPushButton("Run Preview")
        self.stop_preview_btn = QPushButton("Stop")
        self.stop_preview_btn.setEnabled(False)
        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        run_layout.addWidget(self.run_preview_btn)
        run_layout.addWidget(self.stop_preview_btn)
        run_layout.addWidget(self.preview_output)

        # Security tab
        self.security_tab = QWidget()
        security_layout = QVBoxLayout(self.security_tab)
        self.security_run_btn = QPushButton("Run Audit")
        self.security_fix_plan_btn = QPushButton("Generate Fix Plan")
        self.security_fix_plan_btn.setEnabled(False)
        self.security_summary = QLabel("No security audit run yet.")
        self.security_scroll = QScrollArea()
        self.security_scroll.setWidgetResizable(True)
        self.security_container = QWidget()
        self.security_list_layout = QVBoxLayout(self.security_container)
        self.security_list_layout.setContentsMargins(0, 0, 0, 0)
        self.security_scroll.setWidget(self.security_container)
        security_layout.addWidget(self.security_run_btn)
        security_layout.addWidget(self.security_fix_plan_btn)
        security_layout.addWidget(self.security_summary)
        security_layout.addWidget(self.security_scroll)

        # Timeline tab
        self.timeline_tab = QWidget()
        timeline_layout = QVBoxLayout(self.timeline_tab)
        self.timeline_filter = QComboBox()
        self.timeline_filter.addItems(["all", "message", "approval", "tool", "job", "security", "preview", "sketch", "geometry3d", "engineering", "other"])
        self.timeline_refresh_btn = QPushButton("Refresh")
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        filter_row.addWidget(self.timeline_filter)
        filter_row.addWidget(self.timeline_refresh_btn)
        filter_row.addStretch(1)
        self.timeline_list = QListWidget()
        timeline_layout.addLayout(filter_row)
        timeline_layout.addWidget(self.timeline_list)

        # Health/Stats tab
        self.health_tab = QWidget()
        health_layout = QVBoxLayout(self.health_tab)
        self.health_summary = QLabel("Health stats unavailable (IPC disabled).")
        self.health_refresh_btn = QPushButton("Refresh Health Stats")
        self.health_stats_list = QListWidget()
        health_layout.addWidget(self.health_summary)
        health_layout.addWidget(self.health_refresh_btn)
        health_layout.addWidget(self.health_stats_list)

        # Settings tab
        self.settings_tab = QWidget()
        settings_layout = QVBoxLayout(self.settings_tab)
        self.api_keys_btn = QPushButton("API Keys")
        settings_layout.addWidget(self.api_keys_btn)
        settings_layout.addStretch(1)

        self.tabs.addTab(self.suggestions_tab, "Suggestions")
        self.tabs.addTab(self.artifacts_tab, "Artifacts")
        self.tabs.addTab(self.docs_tab, "Docs")
        self.tabs.addTab(self.sketch_tab, "Sketch")
        self.tabs.addTab(self.geometry3d_tab, "3D")
        self.tabs.addTab(self.engineering_tab, "Engineering")
        self.tabs.addTab(self.run_tab, "Run")
        self.tabs.addTab(self.security_tab, "Security")
        self.tabs.addTab(self.timeline_tab, "Timeline")
        self.tabs.addTab(self.health_tab, "Health/Stats")
        self.tabs.addTab(self.jobs_tab, "Jobs")
        self.tabs.addTab(self.settings_tab, "Settings")
        right_layout.addWidget(self.tabs)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 2)

        self.api_banner = QWidget()
        banner_layout = QHBoxLayout(self.api_banner)
        banner_layout.setContentsMargins(4, 4, 4, 4)
        self.chip_deepseek = QLabel("DeepSeek: ?")
        self.chip_gemini = QLabel("Gemini: ?")
        self.chip_telegram = QLabel("Telegram: ?")
        self.import_keys_btn = QPushButton("Import api.txt")
        self.save_keys_btn = QPushButton("Save Keys")
        banner_layout.addWidget(self.chip_deepseek)
        banner_layout.addWidget(self.chip_gemini)
        banner_layout.addWidget(self.chip_telegram)
        banner_layout.addStretch(1)
        banner_layout.addWidget(self.import_keys_btn)
        banner_layout.addWidget(self.save_keys_btn)
        self.api_banner.setVisible(False)
        self.api_banner_header = QWidget()
        header_layout = QHBoxLayout(self.api_banner_header)
        header_layout.setContentsMargins(4, 4, 4, 4)
        self.api_status_label = QLabel("API: ?")
        self.api_toggle_btn = QPushButton("Show")
        self.online_toggle = QCheckBox("Online AI: OFF")
        self.online_toggle.setToolTip("Allows DeepSeek/Gemini/OpenAI calls with approval")
        self.scope_session = QRadioButton("This session only")
        self.scope_project = QRadioButton("Remember for this project")
        self.scope_session.setChecked(True)
        self.online_chip_deepseek = QLabel("DeepSeek")
        self.online_chip_gemini = QLabel("Gemini")
        self.online_chip_openai = QLabel("OpenAI")
        for lbl in (self.online_chip_deepseek, self.online_chip_gemini, self.online_chip_openai):
            lbl.setStyleSheet("color:#6b7280;")
            lbl.setVisible(False)
        header_layout.addWidget(self.api_status_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.api_toggle_btn)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.online_toggle)
        header_layout.addWidget(self.scope_session)
        header_layout.addWidget(self.scope_project)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.online_chip_deepseek)
        header_layout.addWidget(self.online_chip_gemini)
        header_layout.addWidget(self.online_chip_openai)
        self.api_banner_header.setVisible(True)
        self._api_banner_expanded = False

        self.security_banner = QWidget()
        sec_layout = QHBoxLayout(self.security_banner)
        sec_layout.setContentsMargins(4, 4, 4, 4)
        self.security_banner_label = QLabel("Security warning: audit required.")
        self.security_banner_label.setStyleSheet("color:#b91c1c;font-weight:bold;")
        self.security_banner_run_btn = QPushButton("Run Audit")
        self.security_banner_open_btn = QPushButton("Open Security")
        sec_layout.addWidget(self.security_banner_label)
        sec_layout.addStretch(1)
        sec_layout.addWidget(self.security_banner_run_btn)
        sec_layout.addWidget(self.security_banner_open_btn)
        self.security_banner.setVisible(False)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.api_banner_header)
        layout.addWidget(self.api_banner)
        layout.addWidget(self.security_banner)
        layout.addWidget(splitter)
        self.setCentralWidget(container)
        self.setAcceptDrops(True)

        # Signals
        self.project_search.textChanged.connect(self._refresh_project_list)
        self.project_list.currentItemChanged.connect(self._on_project_selected)
        self.project_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(self._project_context_menu)
        self.new_project_btn.clicked.connect(self._add_project)
        self.show_archived_toggle.toggled.connect(self._refresh_project_list)
        self.send_button.clicked.connect(self._send_message)
        self.input.returnPressed.connect(self._send_message)
        self.attach_button.clicked.connect(self._attach_files)
        self.mic_button.clicked.connect(self._record_voice)
        self.task_mode_combo.currentIndexChanged.connect(self._on_task_mode_changed)
        self.tools_button.clicked.connect(self._show_tools_menu)
        self.health_button.clicked.connect(self._open_health_stats)
        self.voice_stop_button.clicked.connect(self._voice_stop_speaking)
        self.explain_combo.currentTextChanged.connect(self._update_prefs_from_ui)
        self.risk_combo.currentTextChanged.connect(self._update_prefs_from_ui)
        self.just_do_toggle.toggled.connect(self._toggle_just_do)
        self.speaker_toggle.toggled.connect(self._toggle_speaker)
        self.refresh_suggestions_btn.clicked.connect(self._refresh_suggestions_panel)
        self.confirm_apply_btn.clicked.connect(self._confirm_apply)
        self.confirm_cancel_btn.clicked.connect(self._cancel_apply)
        self.confirm_action_btn.clicked.connect(self._confirm_pending_action)
        self.cancel_action_btn.clicked.connect(self._cancel_pending_action)
        self.open_docs.clicked.connect(lambda: self._open_folder("docs"))
        self.open_extracted.clicked.connect(lambda: self._open_folder("extracted"))
        self.sketch_export_btn.clicked.connect(self._export_sketch)
        self.geometry3d_confirm_btn.clicked.connect(self._confirm_geometry3d)
        self.geometry3d_assumptions_btn.clicked.connect(self._edit_geometry3d_assumptions)
        self.geometry3d_export_btn.clicked.connect(self._export_geometry3d)
        self.geometry3d_entities_list.itemChanged.connect(self._geometry3d_entity_toggled)
        self.engineering_report_btn.clicked.connect(self._generate_engineering_report)
        self.engineering_edit_assumptions_btn.clicked.connect(self._edit_engineering_assumptions)
        self.run_preview_btn.clicked.connect(self._run_preview)
        self.stop_preview_btn.clicked.connect(self._stop_preview)
        self.security_run_btn.clicked.connect(self._run_security_audit)
        self.security_fix_plan_btn.clicked.connect(self._security_fix_plan)
        self.security_banner_run_btn.clicked.connect(self._run_security_audit)
        self.security_banner_open_btn.clicked.connect(lambda: self.tabs.setCurrentWidget(self.security_tab))
        self.timeline_refresh_btn.clicked.connect(self._refresh_timeline)
        self.timeline_filter.currentTextChanged.connect(lambda _=None: self._refresh_timeline())
        self.health_refresh_btn.clicked.connect(self._refresh_health_stats)
        self.jobs_list.currentItemChanged.connect(self._on_job_selected)
        self.create_job_btn.clicked.connect(self._create_job)
        self.start_job_btn.clicked.connect(self._start_job)
        self.pause_job_btn.clicked.connect(self._pause_job)
        self.resume_job_btn.clicked.connect(self._resume_job)
        self.cancel_job_btn.clicked.connect(self._cancel_job)
        self.preview_job_btn.clicked.connect(self._request_job_preview)
        self.view_logs_btn.clicked.connect(self._view_job_logs)
        self.open_artifacts_btn.clicked.connect(self._open_job_artifacts)
        self.import_keys_btn.clicked.connect(self._import_api_keys)
        self.save_keys_btn.clicked.connect(self._save_keys)
        self.api_toggle_btn.clicked.connect(self._toggle_api_banner)
        self.api_keys_btn.clicked.connect(self._open_api_keys_dialog)
        self.online_toggle.toggled.connect(self._toggle_online_mode)
        self.scope_session.toggled.connect(self._toggle_online_scope)
        self.scope_project.toggled.connect(self._toggle_online_scope)
        self.job_confirm_apply_btn.clicked.connect(self._confirm_job_apply)
        self.job_skip_btn.clicked.connect(self._skip_job_apply)
        self.job_stop_btn.clicked.connect(self._stop_job_now)
        self.job_open_diff_btn.clicked.connect(self._open_job_diff)

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1000)
        self._preview_timer.timeout.connect(self._refresh_preview_output)
        self._jobs_timer = QTimer(self)
        self._jobs_timer.setInterval(2000)
        self._jobs_timer.timeout.connect(self._refresh_jobs_panel)
        self._jobs_timer.start()

        self.preview_run_id = ""
        self.preview_log_path = ""
        self._api_setup_open = False
        self._pending_action = {}
        self._geometry3d_preview = {}
        self._geometry3d_visibility = {}
        self._engineering_preview = {}
        self._engineering_assumptions_edited = False
        self._jarvis_action = {}
        self._jarvis_topic_hash = ""
        self._brain = ConversationalBrain(router=LLMRouter(runner=self.runner, registry=self.registry))
        self._prefs = ConversationPrefs()
        self._online_state = OnlineModeState()
        self._security_gate = {}
        self._last_security_report = {}

        self._refresh_project_list()
        self._maybe_show_api_setup()
        self._refresh_api_banner()
        self._refresh_task_modes_ui()
        self._refresh_tools_menu()
        self._refresh_online_chips()
        self._refresh_security_state()
        self._refresh_sketch()
        self._refresh_geometry3d()
        self._refresh_engineering()
        self._refresh_timeline()
        if self._ipc_enabled:
            self._init_ipc_if_enabled()
            if self._ipc_start_error:
                self._append("System", f"Core service failed to start: {self._ipc_start_error}")
        else:
            self._refresh_health_stats()

    def _wire_conversation_context(self) -> None:
        try:
            import importlib
            mod = importlib.import_module("integrations.conversation.plugin")
            if hasattr(mod, "set_ui_context"):
                mod.set_ui_context(self.runner, self.registry, self.project_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _wire_security_context(self) -> None:
        try:
            import importlib
            mod = importlib.import_module("integrations.security_doctor.plugin")
            if hasattr(mod, "set_ui_context"):
                mod.set_ui_context(self.runner, self.registry, self.project_root, self.workspace_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _init_ipc_if_enabled(self) -> None:
        if not self._ipc_enabled:
            return
        try:
            ensure_core_running_with_events(
                host=self._ipc_host,
                port=self._ipc_port,
                events_port=self._ipc_events_port,
                token=self._ipc_token,
                project_root=self.project_root,
                workspace_root=self.workspace_root,
            )
            self._ipc_client = IpcClient(
                host=self._ipc_host,
                port=self._ipc_port,
                token=self._ipc_token,
                timeout_s=1.0,
            )
            self._ensure_ipc_events_client()
            self._ipc_start_error = ""
            self._refresh_health_stats()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self._ipc_client = None
            self._ipc_start_error = str(exc)
            self.health_summary.setText("Health stats unavailable: core service failed to start.")

    def _ensure_ipc_client(self) -> IpcClient:
        if not self._ipc_enabled:
            raise RuntimeError("IPC mode is disabled.")
        if self._ipc_client is not None:
            try:
                self._ipc_client.call_ok("health.ping", {})
                self._ensure_ipc_events_client()
                return self._ipc_client
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                self._ipc_client = None
        ensure_core_running_with_events(
            host=self._ipc_host,
            port=self._ipc_port,
            events_port=self._ipc_events_port,
            token=self._ipc_token,
            project_root=self.project_root,
            workspace_root=self.workspace_root,
        )
        self._ipc_client = IpcClient(
            host=self._ipc_host,
            port=self._ipc_port,
            token=self._ipc_token,
            timeout_s=2.0,
        )
        self._ipc_client.call_ok("health.ping", {})
        self._ensure_ipc_events_client()
        return self._ipc_client

    def _ipc_subscription_scope(self) -> tuple[str, str]:
        session_id = str(self.session_id if self.current_project_id else self.general_chat_id)
        project_id = str(self.current_project_id or "")
        return session_id, project_id

    def _ensure_ipc_events_client(self) -> None:
        if not self._ipc_enabled:
            return
        session_id, project_id = self._ipc_subscription_scope()
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
                    project_root=self.project_root,
                    workspace_root=self.workspace_root,
                    startup_timeout_s=3.0,
                    health_timeout_s=0.8,
                ),
            )
            self._ipc_events_client.start(
                session_id=session_id,
                project_id=project_id,
                on_event=lambda evt: self.ipcEventReceived.emit(evt),
                on_connected=lambda: self.ipcConnectionChanged.emit(True, ""),
                on_disconnected=lambda reason: self.ipcConnectionChanged.emit(False, str(reason or "")),
            )
            return
        self._ipc_events_client.subscribe(session_id, project_id)

    def _restore_ipc_history(self) -> None:
        if not self._ipc_enabled or self._ipc_client is None:
            return
        if self.transcript.toPlainText().strip():
            return
        session_id, project_id = self._ipc_subscription_scope()
        try:
            history = self._ipc_client.call_ok(
                "conversation.history.get",
                {"session_id": session_id, "project_id": project_id, "limit": 50},
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return
        messages = history.get("messages")
        if not isinstance(messages, list):
            return
        for item in messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "")
            text = str(item.get("text") or "")
            if not text:
                continue
            who = "Nova" if role == "assistant" else "You"
            self.transcript.append(f"{who}: {text}")

    def _on_ipc_connection_changed(self, connected: bool, reason: str) -> None:
        if connected:
            self.health_summary.setText("Core reconnected")
            self._restore_ipc_history()
            return
        msg = "Core disconnected; reconnecting..."
        if reason:
            msg = f"{msg} {reason}"
        self.health_summary.setText(msg)

    def _on_ipc_event(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        topic = str(payload.get("topic") or "").strip().lower()
        data = payload.get("data")
        data_map = data if isinstance(data, dict) else {}
        if topic == "progress":
            self._ipc_progress_pct = int(data_map.get("pct") or 0)
            self._ipc_progress_label = str(data_map.get("label") or "")
            if self._ipc_progress_label:
                self.health_summary.setText(f"{self._ipc_progress_label} ({self._ipc_progress_pct}%)")
            return
        if topic == "thinking":
            state = str(data_map.get("state") or "")
            if state == "start":
                self.health_summary.setText("Core is thinking...")
            elif state == "end":
                self.health_summary.setText("Core response ready")
            return
        if topic == "tool_start":
            tool_name = str(data_map.get("tool") or "")
            if tool_name:
                self.health_summary.setText(f"Tool started: {tool_name}")
            return
        if topic == "tool_end":
            tool_name = str(data_map.get("tool") or "")
            tool_status = str(data_map.get("status") or "ok")
            if tool_name:
                self.health_summary.setText(f"Tool {tool_name}: {tool_status}")
            return
        if topic == "error":
            msg = str(data_map.get("error_msg") or "")
            if msg:
                self.health_summary.setText(f"Core error: {msg}")

    def _ipc_chat_send(self, routed_message: str) -> dict:
        client = self._ensure_ipc_client()
        payload = {
            "text": str(routed_message or ""),
            "mode": str(self.current_task_mode or "general"),
            "project_path": self.project_path if self.current_project_id else "",
            "session_id": self.session_id if self.current_project_id else self.general_chat_id,
            "write_reports": True,
            "ui": "quick_panel",
            "online_enabled": bool(self._online_enabled()),
        }
        return client.call_ok("chat.send", payload)

    def _approval_callback(self, req, res) -> bool:
        if self._approval_session_allowed:
            return True
        tool_id = None
        if isinstance(req.meta, dict):
            tool_id = req.meta.get("tool_id")
        details = (
            f"Tool ID: {tool_id or '(unknown)'}\n"
            f"ToolGroup: {req.tool_group}\n"
            f"Op: {req.op}\n"
            f"Target: {req.target}\n"
            f"Policy reason: {res.reason}\n"
            f"Risk score: {res.risk_score}\n"
            f"Matched rules: {', '.join(res.matched_rules) if res.matched_rules else '(none)'}"
        )
        box = QMessageBox(self)
        box.setWindowTitle("Approval Required")
        box.setIcon(QMessageBox.Warning)
        box.setText("This action is gated by Nova policy.")
        box.setInformativeText("Choose approval scope for this request.")
        box.setDetailedText(details)
        approve_once = box.addButton("Approve Once", QMessageBox.AcceptRole)
        approve_session = box.addButton("Approve for Session", QMessageBox.AcceptRole)
        deny_btn = box.addButton("Deny", QMessageBox.RejectRole)
        box.setDefaultButton(deny_btn)
        box.exec()
        clicked = box.clickedButton()
        approved = clicked in (approve_once, approve_session)
        if clicked == approve_session:
            self._approval_session_allowed = True
        self._emit_timeline(
            "approval",
            {
                "tool_id": tool_id or "(unknown)",
                "tool_group": req.tool_group,
                "op": req.op,
                "target": req.target,
                "approved": approved,
                "scope": "session" if clicked == approve_session else ("once" if clicked == approve_once else "deny"),
                "reason": res.reason,
            },
        )
        return approved

    def _refresh_task_modes_ui(self) -> None:
        self.task_modes = allowed_user_task_modes(self.registry, include_unavailable=False)
        if not self.task_modes:
            self.task_modes = [{"id": "general", "title": "General", "description": "Default mode", "available": True, "reason": ""}]
        self.task_mode_combo.blockSignals(True)
        self.task_mode_combo.clear()
        current_idx = 0
        for idx, row in enumerate(self.task_modes):
            mode_id = str(row.get("id") or "general")
            title = str(row.get("title") or mode_id)
            self.task_mode_combo.addItem(title, mode_id)
            if mode_id == self.current_task_mode:
                current_idx = idx
        self.task_mode_combo.setCurrentIndex(current_idx)
        self.task_mode_combo.blockSignals(False)

    def _on_task_mode_changed(self, index: int) -> None:
        mode_id = str(self.task_mode_combo.itemData(index) or "general")
        if is_auto_mode(mode_id):
            self.current_task_mode = auto_fallback_mode(self.registry, project_context=bool(self.current_project_id))
        else:
            self.current_task_mode = normalize_task_mode(mode_id)
        self._append("System", f"Task mode: {self.current_task_mode}")
        self._refresh_tools_menu()

    def _refresh_tools_menu(self) -> None:
        self.tools_catalog = build_tools_catalog(
            self.registry,
            policy=self.tool_policy,
            project_context=bool(self.current_project_id),
            task_mode=self.current_task_mode,
        )
        self.tools_menu = QMenu(self)
        curated_menu = self.tools_menu.addMenu("Curated")
        for item in filter_codex_tool_rows(self.tools_catalog.get("curated") or []):
            if not isinstance(item, dict):
                continue
            action = curated_menu.addAction(f"{item.get('id')} [{item.get('badge')}]")
            action.setEnabled(bool(item.get("enabled")))
            action.triggered.connect(lambda _checked=False, tid=str(item.get("id") or ""): self._on_tools_action(tid))
        advanced_root = self.tools_menu.addMenu("Advanced")
        for group in self.tools_catalog.get("groups") or []:
            if not isinstance(group, dict):
                continue
            gname = str(group.get("group") or "Other")
            group_menu = advanced_root.addMenu(gname)
            for item in filter_codex_tool_rows(group.get("items") or []):
                if not isinstance(item, dict):
                    continue
                action = group_menu.addAction(f"{item.get('id')} [{item.get('badge')}]")
                action.setEnabled(bool(item.get("enabled")))
                action.triggered.connect(lambda _checked=False, tid=str(item.get("id") or ""): self._on_tools_action(tid))

    def _show_tools_menu(self) -> None:
        self._refresh_tools_menu()
        self.tools_menu.exec(self.tools_button.mapToGlobal(self.tools_button.rect().bottomLeft()))

    def _on_tools_action(self, tool_id: str) -> None:
        tid = str(tool_id or "").strip()
        if not tid:
            return
        command_map = {
            "verify.smoke": "verify",
            "project.scan_repo": "analyze",
            "repo.search": "search ",
            "patch.plan": "plan ",
            "patch.apply": "apply ",
            "pipeline.run": "pipeline ",
        }
        preset = command_map.get(tid, "")
        if preset:
            self.input.setText(preset)
            self.input.setFocus()
            return
        self._append("System", f"Selected tool from catalog: {tid}")

    def _build_voice_loop(self) -> VoiceLoop:
        stt_provider = FasterWhisperSttProvider(model_name=self.voice_config.stt_model)
        tts_provider = PiperTtsProvider(
            voice_id=self.voice_config.tts_voice,
            sentence_pause_ms=self.voice_config.tts_sentence_pause_ms,
        )
        audio_input = SoundDeviceAudioInput(
            sample_rate=self.voice_config.sample_rate,
            device=self.voice_config.device,
        )
        return VoiceLoop(
            stt_provider=stt_provider,
            tts_provider=tts_provider,
            config=self.voice_config,
            audio_input=audio_input,
            on_transcript=lambda text: QTimer.singleShot(0, lambda: self._on_voice_transcript(text)),
            on_error=lambda msg: QTimer.singleShot(0, lambda: self._on_voice_error(msg)),
        )

    def _toggle_voice_enabled_internal(self, enabled: bool) -> None:
        want = bool(enabled)
        if want:
            try:
                if self.voice_loop is None:
                    self.voice_loop = self._build_voice_loop()
                ok = self.voice_loop.start()
                if not ok:
                    raise RuntimeError("Voice loop failed to start.")
                self.voice_enabled = True
                self.voice_loop.set_muted(self.voice_muted)
                self.mic_button.setText("Mic On")
                self.voice_stop_button.setEnabled(True)
                self._append("System", "Voice loop enabled (local faster-whisper + piper).")
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                self.voice_enabled = False
                self.mic_button.setText("Mic")
                self.voice_stop_button.setEnabled(False)
                QMessageBox.warning(self, "Voice Error", f"Could not enable local voice loop:\n{exc}")
            return
        if self.voice_loop is not None:
            try:
                self.voice_loop.stop()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        self.voice_enabled = False
        self.mic_button.setText("Mic")
        self.voice_stop_button.setEnabled(False)
        self._append("System", "Voice loop disabled.")

    def _voice_stop_speaking(self) -> None:
        if self.voice_loop is None:
            return
        self.voice_loop.stop_speaking()

    def _on_voice_transcript(self, text: str) -> None:
        payload = str(text or "").strip()
        if not payload:
            return
        self._send_message(text=payload)

    def _on_voice_error(self, message: str) -> None:
        msg = str(message or "").strip()
        if not msg:
            return
        self._append("System", f"Voice error: {msg}")

    def _refresh_project_list(self) -> None:
        query = self.project_search.text().strip().lower()
        self.project_list.clear()
        projects = self.project_manager.list_projects(include_archived=self.show_archived_toggle.isChecked())
        for p in projects:
            name = p.get("name") or p.get("id")
            archived = bool(p.get("archived"))
            if archived:
                name = f"{name} [Archived]"
            if query and query not in name.lower():
                continue
            preview, ts = ("(archived)", p.get("last_opened") or "") if archived else self._last_message_preview(p.get("id"))
            badge = self._status_badge(p.get("status_summary", ""), p.get("id"))
            item = QListWidgetItem()
            widget = ProjectListItem(name, preview, ts, badge)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.UserRole, p.get("id"))
            item.setData(Qt.UserRole + 1, archived)
            self.project_list.addItem(item)
            self.project_list.setItemWidget(item, widget)

    def _on_project_selected(self, current: QListWidgetItem) -> None:
        if not current:
            return
        project_id = current.data(Qt.UserRole)
        if current.data(Qt.UserRole + 1):
            QMessageBox.information(self, "Archived Project", "Archived projects cannot be opened.")
            return
        if not project_id:
            return
        self._switch_project(project_id)

    def _project_context_menu(self, pos) -> None:
        item = self.project_list.itemAt(pos)
        if not item:
            return
        project_id = item.data(Qt.UserRole)
        archived = bool(item.data(Qt.UserRole + 1))
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        archive_action = menu.addAction("Archive")
        delete_action = menu.addAction("Delete")
        clear_action = menu.addAction("Clear Files (Keep Chat)")
        restore_action = menu.addAction("Restore from Snapshot")
        if archived:
            rename_action.setEnabled(False)
            archive_action.setEnabled(False)
            delete_action.setEnabled(False)
            clear_action.setEnabled(False)
            restore_action.setEnabled(False)
        action = menu.exec(self.project_list.mapToGlobal(pos))
        if not action:
            return
        if action == rename_action:
            self._rename_project(project_id)
        elif action == archive_action:
            self._archive_project(project_id)
        elif action == delete_action:
            self._delete_project(project_id)
        elif action == clear_action:
            self._clear_project_files(project_id)
        elif action == restore_action:
            self._restore_project(project_id)

    def _switch_project(self, project_id: str) -> None:
        self._flush_current_project_state()
        info = self.project_manager.open_project(project_id)
        self.current_project_id = project_id
        self.session_id = project_id
        self.project_path = str(info.get("working") or "")
        self._pending_action = {}
        self._geometry3d_preview = {}
        self._geometry3d_visibility = {}
        self._engineering_preview = {}
        self._engineering_assumptions_edited = False
        self._clear_jarvis_flow()
        self._prefs = load_prefs(project_id, self.workspace_root)
        self._apply_prefs_to_ui()
        self.transcript.setPlainText(info.get("transcript") or "")
        self.setWindowTitle(f"Nova Hub Quick Panel - {info.get('name')}")
        self._append("System", f"Opened project: {info.get('name')}")
        self._maybe_recap_project(info.get("name") or project_id)
        self._refresh_project_list()
        self._maybe_show_api_setup()
        self._refresh_api_banner()
        self._refresh_docs_summary()
        self._refresh_artifacts()
        self._refresh_security_state()
        self._refresh_suggestions_panel()
        self._refresh_jobs_panel()
        self._refresh_tools_menu()
        self._refresh_sketch()
        self._refresh_geometry3d()
        self._refresh_timeline()
        if self._ipc_enabled:
            try:
                self._ensure_ipc_events_client()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def _add_project(self) -> None:
        options = ["Import Folder (recommended)", "Import ZIP"]
        choice, ok = QInputDialog.getItem(self, "Add Project", "Choose import method:", options, 0, False)
        if not ok or not choice:
            return
        if choice.startswith("Import Folder"):
            source = QFileDialog.getExistingDirectory(self, "Select Project Folder", self.project_root)
            if not source:
                return
            try:
                project_id = self.project_manager.add_project_from_folder(source)
                self._switch_project(project_id)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.critical(self, "Import Error", str(e))
        else:
            zip_path, _ = QFileDialog.getOpenFileName(self, "Select Zip File", self.project_root, "Zip Files (*.zip)")
            if not zip_path:
                return
            try:
                project_id = self.project_manager.add_project_from_zip(zip_path)
                self._switch_project(project_id)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.critical(self, "Import Error", str(e))

    def _rename_project(self, project_id: str) -> None:
        name, ok = QInputDialog.getText(self, "Rename Project", "New name:")
        if not ok or not name.strip():
            return
        try:
            self.project_manager.rename_project(project_id, name.strip())
            self._refresh_project_list()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Rename Error", str(e))

    def _archive_project(self, project_id: str) -> None:
        res = QMessageBox.question(self, "Archive Project", "Move this project to archived folder?", QMessageBox.Yes | QMessageBox.No)
        if res != QMessageBox.Yes:
            return
        try:
            self.project_manager.archive_project(project_id)
            if self.current_project_id == project_id:
                self._clear_current_project()
            self._refresh_project_list()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Archive Error", str(e))

    def _delete_project(self, project_id: str) -> None:
        res = QMessageBox.warning(
            self,
            "Delete Project",
            "This will permanently delete the project from workspace.\nType DELETE to confirm.",
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if res != QMessageBox.Ok:
            return
        token, ok = QInputDialog.getText(self, "Confirm Delete", "Type DELETE:")
        if not ok:
            return
        try:
            self.project_manager.delete_project(project_id, token.strip())
            if self.current_project_id == project_id:
                self._clear_current_project()
            self._refresh_project_list()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Delete Error", str(e))

    def _clear_project_files(self, project_id: str) -> None:
        res = QMessageBox.warning(
            self,
            "Clear Project Files",
            "This will clear working files and artifacts but keep chat/state.\nContinue?",
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if res != QMessageBox.Ok:
            return
        try:
            self.project_manager.clear_project_files(project_id)
            if self.current_project_id == project_id:
                self._refresh_docs_summary()
                self._refresh_artifacts()
                self._refresh_suggestions_panel()
            QMessageBox.information(self, "Cleared", "Project files cleared.")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Clear Error", str(e))

    def _restore_project(self, project_id: str) -> None:
        paths = self.project_manager.get_project_paths(project_id)
        snap_dir = paths.snapshots
        if not os.path.isdir(snap_dir):
            QMessageBox.warning(self, "Restore", "No snapshots folder found.")
            return
        files = [f for f in os.listdir(snap_dir) if f.lower().endswith(".zip")]
        if not files:
            QMessageBox.warning(self, "Restore", "No snapshot files found.")
            return
        files.sort(reverse=True)
        choice, ok = QInputDialog.getItem(self, "Restore Snapshot", "Select snapshot:", files, 0, False)
        if not ok or not choice:
            return
        res = QMessageBox.warning(
            self,
            "Restore Snapshot",
            "This will replace working files from the selected snapshot.\nContinue?",
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if res != QMessageBox.Ok:
            return
        try:
            self.project_manager.restore_project_from_snapshot(project_id, os.path.join(snap_dir, choice))
            if self.current_project_id == project_id:
                self._refresh_docs_summary()
                self._refresh_artifacts()
            QMessageBox.information(self, "Restored", "Snapshot restored to working.")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Restore Error", str(e))

    def _clear_current_project(self) -> None:
        self.current_project_id = ""
        self.session_id = "default"
        self.project_path = ""
        self.transcript.clear()
        self.setWindowTitle("Nova Hub Quick Panel")
        self._refresh_docs_summary()
        self._refresh_artifacts()
        self._refresh_security_state()
        self._refresh_suggestions_panel()
        self._refresh_jobs_panel()
        self._refresh_sketch()
        self._refresh_geometry3d()
        self._refresh_timeline()
        self._jarvis_action = {}
        self._jarvis_topic_hash = ""
        if self._ipc_enabled:
            try:
                self._ensure_ipc_events_client()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def _load_jarvis_context(self) -> dict:
        jarvis: dict = {}
        if self.current_project_id:
            try:
                state = self.project_manager.load_state(self.current_project_id)
                jarvis = dict(getattr(state, "jarvis", {}) or {})
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                jarvis = {}
        if getattr(self, "_prefs", None):
            if self._prefs.pinned_goal:
                jarvis["pinned_goal"] = self._prefs.pinned_goal
            if self._prefs.risk_posture:
                jarvis["risk_posture"] = self._prefs.risk_posture
        return {"jarvis": jarvis}

    def _persist_jarvis_context(self, ctx: dict) -> None:
        if not self.current_project_id:
            return
        try:
            state = self.project_manager.load_state(self.current_project_id)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return
        state.jarvis = dict((ctx or {}).get("jarvis") or {})
        self._save_project_state(state)

    def _clear_jarvis_flow(self) -> None:
        self._jarvis_action = {}
        self._jarvis_topic_hash = ""

    def _audit_spine(self) -> ProjectAuditSpine | None:
        if not self.current_project_id:
            return None
        try:
            return ProjectAuditSpine(self.current_project_id, workspace_root=self.workspace_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return None

    def _emit_timeline(self, event_type: str, payload: dict) -> None:
        spine = self._audit_spine()
        if not spine:
            return
        try:
            spine.emit(event_type, payload or {})
            self._refresh_timeline()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _send_message(self, text: str | None = None, allow_execute: bool = False) -> None:
        if not self.conversation_tool:
            QMessageBox.warning(self, "Chat Unavailable", "conversation.chat tool not found.")
            return
        message = text if text is not None else self.input.text().strip()
        if not message:
            return
        if text is None:
            self.input.clear()
        self._append("You", message)
        routed_message = route_message_for_mode(
            self.current_task_mode,
            message,
            {
                "ui": "quick_panel",
                "scope": self.current_project_id or self.general_chat_id,
            },
        )

        if self.conv_mode_toggle.isChecked() and not allow_execute:
            if self._pending_action:
                if is_confirmation(message):
                    self._confirm_pending_action()
                    return
                if is_rejection(message):
                    self._cancel_pending_action()
                    return
            if self._handle_engineering_message(message):
                return
            if self._handle_geometry3d_message(message):
                return
            if self._handle_sketch_message(message):
                return
            if self._jarvis_action:
                ctx = self._load_jarvis_context()
                if jarvis_core.is_user_adjusting(message):
                    jarvis = dict((ctx or {}).get("jarvis") or {})
                    jarvis.pop("last_disagreement", None)
                    jarvis["warning_state"] = {"level": 0, "last_topic_hash": "", "count": 0}
                    ctx["jarvis"] = jarvis
                    self._persist_jarvis_context(ctx)
                    self._append("Nova", "تمام، نعدّل المسار. تحب نركز على إيه بدل كده؟")
                    self._clear_jarvis_flow()
                    return
                if jarvis_core.is_user_insisting(message) or is_confirmation(message):
                    level = jarvis_core.warning_level(
                        ctx,
                        {"topic_hash": self._jarvis_topic_hash, "insist": True, "risky": True},
                    )
                    warning = jarvis_core.warning_text(level)
                    if warning:
                        self._append("Nova", warning)
                    if level >= 3:
                        jarvis_core.record_documentary_warning(ctx)
                        self._persist_jarvis_context(ctx)
                        self._pending_action = self._jarvis_action
                        self._clear_jarvis_flow()
                        self._show_confirmation(self._pending_action)
                        return
                    self._persist_jarvis_context(ctx)
                    return
                self._clear_jarvis_flow()
                ctx = self._load_jarvis_context()
                jarvis = dict((ctx or {}).get("jarvis") or {})
                jarvis.pop("last_disagreement", None)
                ctx["jarvis"] = jarvis
                self._persist_jarvis_context(ctx)
            intent = parse_intent_soft(message)
            ctx = self._load_jarvis_context()
            intent_result = jarvis_core.assess_intent(message, ctx)
            action: dict = {}
            if intent.get("confidence") == "HIGH":
                action = self._action_from_intent(intent, allow_prompt=False)
            if action and (intent_result.conflict or intent_result.risk_signal == "high"):
                if intent_result.conflict:
                    disagree, question = jarvis_core.manage_disagreement(ctx, action)
                    jarvis_core.update_last_disagreement(ctx, intent_result.topic_hash, disagree)
                    jarvis_core.warning_level(
                        ctx,
                        {"topic_hash": intent_result.topic_hash, "insist": False, "risky": True},
                    )
                    self._persist_jarvis_context(ctx)
                    self._jarvis_action = action
                    self._jarvis_topic_hash = intent_result.topic_hash
                    self._append("Nova", f"{disagree} {question}")
                    return
                level = jarvis_core.warning_level(
                    ctx,
                    {"topic_hash": intent_result.topic_hash, "insist": False, "risky": True},
                )
                warning = jarvis_core.warning_text(level)
                if warning:
                    self._append("Nova", warning)
                self._persist_jarvis_context(ctx)
                self._jarvis_action = action
                self._jarvis_topic_hash = intent_result.topic_hash
                return
            state_ctx = None
            if self.current_project_id:
                try:
                    state_ctx = self.project_manager.load_state(self.current_project_id)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    state_ctx = None
            brain_result = self._brain.respond(
                message,
                context={
                    "intent": intent,
                    "prefs": self._prefs.to_dict(),
                    "state": state_ctx,
                    "online_enabled": self._online_enabled(),
                    "project_id": self.current_project_id,
                    "workspace_root": self.workspace_root,
                    "project_path": self.project_path,
                },
            )
            if brain_result.reply_text:
                self._append("Nova", brain_result.reply_text)
            if intent.get("confidence") == "HIGH":
                action = self._action_from_intent(intent)
                if action:
                    self._pending_action = action
                    self._show_confirmation(action)
            return

        try:
            if self._ipc_enabled:
                result = self._ipc_chat_send(routed_message)
            else:
                result = self.runner.execute_registered_tool(
                    self.conversation_tool,
                    user_message=routed_message,
                    project_path=self.project_path if self.current_project_id else "",
                    session_id=self.session_id if self.current_project_id else self.general_chat_id,
                    write_reports=True,
                )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            title = "Core service failed to start" if self._ipc_enabled else "Chat Error"
            QMessageBox.critical(self, title, str(e))
            return

        if isinstance(result, dict):
            response = result.get("response") or "(no response)"
            self._append("Nova", response)
            state = result.get("state") or {}
            self._update_state(state)
        else:
            self._append("Nova", str(result))

    def _is_sketch_prompt(self, message: str) -> bool:
        low = (message or "").lower()
        keys = ["draw", "sketch", "circle", "rect", "rectangle", "line", "ارسم", "رسم", "دائرة", "مستطيل", "خط"]
        return any(k in low for k in keys)

    def _is_geometry3d_prompt(self, message: str) -> bool:
        return geometry3d_intent.is_3d_prompt(message)

    def _is_engineering_prompt(self, message: str) -> bool:
        return engineering_extract.is_engineering_query(message)

    def _handle_engineering_message(self, message: str) -> bool:
        if not self._is_engineering_prompt(message):
            return False
        result = engineering_extract.run_engineering_brain(
            message,
            project_id=self.current_project_id or "",
            workspace_root=self.workspace_root,
            project_path=self.project_path,
            online_enabled=self._online_enabled(),
            router=self._brain.router,
        )
        reply = result.get("reply") or ""
        if reply:
            self._append("Nova", reply)
        if result.get("blocked"):
            return True
        self._engineering_preview = {
            "state": result.get("state") or {},
            "findings": result.get("findings") or [],
            "report": result.get("report") or "",
        }
        self._engineering_assumptions_edited = False
        self._update_engineering_preview()
        self._emit_timeline("engineering.preview", {"risk": (result.get("risk") or {}).get("risk_posture")})
        return True

    def _handle_geometry3d_message(self, message: str) -> bool:
        if not self.current_project_id:
            return False
        if not self._is_geometry3d_prompt(message):
            return False
        intent = geometry3d_intent.parse_intent(message)
        if intent.get("disallowed"):
            self._append("Nova", intent.get("reason") or "ده خارج حدود المساعدة الهندسية المبدئية.")
            return True
        entities = intent.get("entities") or []
        confidence = float(intent.get("confidence") or 0.0)
        if not entities or confidence < 0.6:
            if self._online_enabled():
                self._append("Nova", "التحليل المحلي مش كفاية. تحب أستخدم Online AI لاستخلاص الشكل؟")
                self._pending_action = {"type": "geometry3d_parse_online", "description": "تحليل 3D Online", "text": message}
                self._show_confirmation(self._pending_action)
                return True
            self._append("Nova", "الوصف غير كافي لبناء مجسم واضح. حدّد النوع والأبعاد بدقة أكتر.")
            return True
        assumptions = intent.get("assumptions") or []
        model = {"entities": entities, "operations": intent.get("operations") or []}
        warnings, reasoning = geometry3d_reasoning.analyze(model, assumptions)
        self._geometry3d_preview = {
            "model": model,
            "assumptions": assumptions,
            "warnings": warnings,
            "reasoning": reasoning,
        }
        self._update_geometry3d_preview()
        summary = _geometry3d_summary(entities, assumptions, warnings)
        self._append("Nova", summary)
        self._pending_action = {"type": "geometry3d_apply", "description": "تأكيد المجسم ثلاثي الأبعاد"}
        self._show_confirmation(self._pending_action)
        self._emit_timeline("geometry3d.preview", {"count": len(entities)})
        return True

    def _handle_sketch_message(self, message: str) -> bool:
        if not self.current_project_id:
            return False
        if not self._is_sketch_prompt(message):
            return False
        ops = sketch_parser.parse_ops(message)
        if ops:
            summary = sketch_parser.summarize_ops(ops)
            self._append("Nova", "ده تفسير الرسم:\n" + summary)
            self._pending_action = {"type": "sketch_apply", "description": "تطبيق الرسم", "ops": ops}
            self._show_confirmation(self._pending_action)
            self._emit_timeline("sketch.preview", {"count": len(ops)})
            return True
        # offline parse failed
        if self._online_enabled():
            self._append("Nova", "المحلل المحلي مش كفاية. تحب أستخدم Online AI لتحويل الوصف؟")
            self._pending_action = {"type": "sketch_parse_online", "description": "تحليل الرسم Online", "text": message}
            self._show_confirmation(self._pending_action)
            return True
        self._append("Nova", "مش قادر أفهم الرسم محليًا. فعّل Online AI لو تحب أستخدمه.")
        return True

    def _action_from_intent(self, intent: dict, allow_prompt: bool = True) -> dict:
        action = {"type": intent.get("intent"), "description": ""}
        if intent.get("intent") == "analyze":
            action["description"] = "Analyze the current project"
        elif intent.get("intent") == "search":
            action["description"] = "Find task-marker hotspots"
        elif intent.get("intent") == "verify":
            action["description"] = "Run verification checks"
        elif intent.get("intent") == "plan":
            goal = intent.get("goal") or ""
            if not goal:
                if allow_prompt:
                    self._append("Nova", "What goal should I use for the plan?")
                return {}
            action["description"] = f"Plan fixes for: {goal}"
            action["goal"] = goal
        elif intent.get("intent") == "apply":
            diff_path = intent.get("diff_path") or ""
            if not diff_path:
                if allow_prompt:
                    self._append("Nova", "Which diff should I apply? Provide a .diff path.")
                return {}
            action["description"] = f"Apply diff: {diff_path}"
            action["diff_path"] = diff_path
        elif intent.get("intent") == "pipeline":
            goal = intent.get("goal") or ""
            if not goal:
                if allow_prompt:
                    self._append("Nova", "What is the pipeline goal?")
                return {}
            action["description"] = f"Run pipeline: {goal}"
            action["goal"] = goal
        elif intent.get("intent") == "execute":
            num = intent.get("number") or ""
            if not num:
                return {}
            action["description"] = f"Execute suggestion {num}"
            action["number"] = num
        else:
            return {}
        return action

    def _show_confirmation(self, action: dict) -> None:
        summary = self._action_summary(action)
        self.confirm_action_label.setText(f"{build_prompt(action)}\n{summary}")
        labels = action_labels(action)
        self.confirm_action_btn.setText(labels.get("confirm", "Confirm"))
        self.cancel_action_btn.setText(labels.get("cancel", "Cancel"))
        self.confirm_action_bar.setVisible(True)

    def _confirm_pending_action(self) -> None:
        if not self._pending_action:
            return
        action = self._pending_action
        self._pending_action = {}
        self.confirm_action_bar.setVisible(False)
        self._append("System", f"Confirmed: {action.get('description')}")
        self._emit_timeline("confirm.accept", {"action": action.get("type")})
        self._execute_action(action)

    def _cancel_pending_action(self) -> None:
        if not self._pending_action:
            return
        self._pending_action = {}
        self.confirm_action_bar.setVisible(False)
        self._append("System", "Cancelled.")
        self._emit_timeline("confirm.reject", {})

    def _action_summary(self, action: dict) -> str:
        typ = (action.get("type") or "").lower()
        if typ == "analyze":
            return "هعمل scan + search + verify على المشروع الحالي."
        if typ == "search":
            return "هبحث عن task markers والـ hotspots."
        if typ == "verify":
            return "هشغّل تحقق سريع للتأكد من سلامة المشروع."
        if typ == "plan":
            return "هطلع خطة تعديل مبدئية بدون تطبيق."
        if typ == "apply":
            return "هطبّق التعديل بعد الموافقات المطلوبة."
        if typ == "pipeline":
            return "هشغّل المسار الكامل بالخطوات الأساسية."
        if typ == "execute":
            return "هبدأ تنفيذ الاقتراح المختار."
        if typ == "sketch_apply":
            return "هطبّق الرسم على اللوحة."
        if typ == "sketch_parse_online":
            return "هستخدم Online AI لتحويل الوصف إلى أوامر رسم."
        if typ == "sketch_export":
            return "هصدّر الرسم إلى ملف DXF."
        if typ == "geometry3d_apply":
            return "هثبّت المجسم ثلاثي الأبعاد واحفظه في المشروع."
        if typ == "geometry3d_parse_online":
            return "هستخدم Online AI لاستخلاص نية 3D من الوصف."
        if typ == "geometry3d_export":
            return "هصدّر المجسم إلى ملف STL."
        return "هبدأ الإجراء المطلوب."

    def _apply_prefs_to_ui(self) -> None:
        level = (self._prefs.explanation_level or "normal").lower()
        risk = (self._prefs.risk_posture or "balanced").lower()
        if level not in ("short", "normal", "detailed"):
            level = "normal"
        if risk not in ("conservative", "balanced", "aggressive"):
            risk = "balanced"
        self.explain_combo.setCurrentText(level)
        self.risk_combo.setCurrentText(risk)
        self.just_do_toggle.setChecked(level == "short")
        if self.scope_project.isChecked():
            if self._security_blocked():
                self.scope_session.setChecked(True)
                self._online_state.scope = "session"
                self.online_toggle.setChecked(False)
            else:
                self._online_state.scope = "project"
                self.online_toggle.setChecked(bool(self._prefs.online_enabled))
        else:
            self._online_state.scope = "session"
            self.online_toggle.setChecked(bool(self._online_state.online_enabled))
        self._refresh_online_chips()

    def _update_prefs_from_ui(self) -> None:
        if not self.current_project_id:
            return
        self._prefs.explanation_level = self.explain_combo.currentText()
        self._prefs.risk_posture = self.risk_combo.currentText()
        if self.just_do_toggle.isChecked():
            self._prefs.explanation_level = "short"
        self._save_prefs()

    def _toggle_online_mode(self, checked: bool) -> None:
        if self.scope_project.isChecked() and self._security_blocked() and checked:
            QMessageBox.warning(self, "Security Gate", "Online AI is blocked for this project until security issues are resolved.")
            self.online_toggle.setChecked(False)
            return
        if self.scope_project.isChecked():
            if self.current_project_id:
                self._prefs.online_enabled = bool(checked)
                self._save_prefs()
        else:
            self._online_state.online_enabled = bool(checked)
        self._online_state.scope = "project" if self.scope_project.isChecked() else "session"
        self.online_toggle.setText("Online AI: ON" if checked else "Online AI: OFF")
        self._refresh_online_chips()

    def _toggle_online_scope(self) -> None:
        if self.scope_project.isChecked() and self._security_blocked():
            QMessageBox.warning(self, "Security Gate", "Project-scope Online AI is blocked until security issues are resolved.")
            self.scope_session.setChecked(True)
            self._online_state.scope = "session"
            self.online_toggle.setChecked(False)
            self._refresh_online_chips()
            return
        self._online_state.scope = "project" if self.scope_project.isChecked() else "session"
        if self._online_state.scope == "project":
            self._online_state.online_enabled = False
            self.online_toggle.setChecked(bool(self._prefs.online_enabled))
        else:
            self.online_toggle.setChecked(bool(self._online_state.online_enabled))
        self._refresh_online_chips()

    def _refresh_online_chips(self) -> None:
        enabled = self._online_enabled()
        for lbl in (self.online_chip_deepseek, self.online_chip_gemini, self.online_chip_openai):
            lbl.setVisible(enabled)

    def _online_enabled(self) -> bool:
        if self._security_blocked() and self._online_state.scope == "project":
            return False
        return self._online_state.is_enabled(bool(self._prefs.online_enabled))

    def _toggle_just_do(self, checked: bool) -> None:
        if checked:
            self.explain_combo.setCurrentText("short")
        self._update_prefs_from_ui()

    def _save_prefs(self) -> None:
        if not self.current_project_id:
            return
        def _writer(path: str, text: str) -> None:
            if not self.safe_writer.write_text(path, text):
                tool = self.registry.tools.get("fs.write_text")
                if tool:
                    self.runner.execute_registered_tool(tool, path=path, text=text, target=path)
        save_prefs(self.current_project_id, self._prefs, writer=_writer, workspace_root=self.workspace_root)

    def _maybe_recap_project(self, name: str) -> None:
        from datetime import datetime, timedelta, timezone
        last = self._prefs.last_recapped_at
        if last:
            try:
                ts = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - ts < timedelta(minutes=10):
                    return
            except (TypeError, ValueError):
                pass
        status = self._project_status_lines()
        recap = "\n".join(
            [
                f"رجعنا للمشروع: {name}. آخر وضع:",
                *status,
                "تحب نكمّل من آخر نقطة ولا نعمل تحليل سريع؟",
            ]
        )
        self._append("System", recap)
        self._prefs = update_recapped(self._prefs)
        self._save_prefs()

    def _project_status_lines(self) -> list[str]:
        lines = []
        state = self.project_manager.load_state(self.current_project_id)
        verify_status = "غير معروف"
        report = self._find_verify_report()
        if report:
            try:
                import json
                with open(report, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                totals = data.get("totals") or {}
                verify_status = "PASS" if totals.get("failed_count", 0) == 0 else "FAIL"
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                verify_status = "غير معروف"
        lines.append(f"- آخر verify: {verify_status}")
        diff_status = "موجود" if state.last_diff_path else "مش موجود"
        lines.append(f"- آخر diff: {diff_status}")
        jobs = self.job_controller.list_jobs(self.current_project_id)
        job_status = "مفيش"
        if jobs:
            j = jobs[0]
            if j.get("status") == "waiting_for_user":
                job_status = "منتظر موافقة"
            elif j.get("status") == "running":
                job_status = "شغال"
            else:
                job_status = j.get("status") or "موجود"
        lines.append(f"- Jobs: {job_status}")
        return lines

    def _find_verify_report(self) -> str:
        paths = self.project_manager.get_project_paths(self.current_project_id)
        if not os.path.isdir(paths.reports):
            return ""
        for f in os.listdir(paths.reports):
            if "verify_smoke" in f and f.endswith(".json"):
                return os.path.join(paths.reports, f)
        return ""

    def _execute_action(self, action: dict) -> None:
        typ = action.get("type")
        if typ == "analyze":
            self._send_message(text="analyze", allow_execute=True)
        elif typ == "search":
            self._send_message(text="search", allow_execute=True)
        elif typ == "verify":
            self._send_message(text="verify", allow_execute=True)
        elif typ == "plan":
            goal = action.get("goal") or ""
            self._send_message(text=f"plan {goal}", allow_execute=True)
        elif typ == "apply":
            diff_path = action.get("diff_path") or ""
            self._send_message(text=f"apply {diff_path}", allow_execute=True)
        elif typ == "pipeline":
            goal = action.get("goal") or ""
            self._send_message(text=f"pipeline {goal}", allow_execute=True)
        elif typ == "execute":
            num = action.get("number") or ""
            self._send_message(text=f"نفّذ {num}", allow_execute=True)
        elif typ == "sketch_apply":
            tool = self.registry.tools.get("sketch.apply")
            if not tool:
                QMessageBox.warning(self, "Missing Tool", "sketch.apply not available.")
                return
            ops = action.get("ops") or []
            try:
                res = self.runner.execute_registered_tool(tool, project_id=self.current_project_id, ops=ops)
                self._append("System", f"Sketch applied. Entities: {res.get('count', 0)}")
                self._emit_timeline("sketch.apply", {"count": res.get("count", 0)})
                self._refresh_sketch()
                self._refresh_geometry3d()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.critical(self, "Sketch Apply Error", str(e))
        elif typ == "sketch_parse_online":
            text = action.get("text") or ""
            router = self._brain.router
            system = (
                "Return JSON only. Format: {\"ops\": [{\"op\":\"add_circle\",\"cx\":0,\"cy\":0,\"r\":50}] } "
                "Supported ops: add_circle(cx,cy,r), add_rect(cx,cy,w,h), add_line(x1,y1,x2,y2), clear."
            )
            res = router.route(
                "sketch_parse",
                prompt=text,
                system=system,
                online_enabled=self._online_enabled(),
                project_id=self.current_project_id,
                offline_confidence="low",
                parser_ok=False,
            )
            if res.get("mode") == "offline" and res.get("need_online"):
                self._append("Nova", res.get("text") or "Online AI required for sketch parsing.")
                return
            ops = sketch_parser.parse_ops_from_json(res.get("text") or "")
            if not ops:
                self._append("Nova", "مش قادر أستنتج أوامر رسم واضحة من الوصف.")
                return
            summary = sketch_parser.summarize_ops(ops)
            self._append("Nova", "مع Online AI، ده التفسير:\n" + summary)
            self._pending_action = {"type": "sketch_apply", "description": "تطبيق الرسم", "ops": ops}
            self._show_confirmation(self._pending_action)
        elif typ == "sketch_export":
            tool = self.registry.tools.get("sketch.export_dxf")
            if not tool:
                QMessageBox.warning(self, "Missing Tool", "sketch.export_dxf not available.")
                return
            try:
                res = self.runner.execute_registered_tool(tool, project_id=self.current_project_id)
                path = res.get("output_path") or ""
                self._append("System", f"DXF exported: {path}")
                self._emit_timeline("sketch.export", {"output_path": path})
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.critical(self, "Sketch Export Error", str(e))
        elif typ == "geometry3d_apply":
            data = self._geometry3d_preview or {}
            model = data.get("model") or {}
            if not model.get("entities"):
                QMessageBox.warning(self, "No Preview", "لا يوجد مجسم لتأكيده.")
                return
            try:
                res = geometry3d_store.save_model(
                    self.current_project_id,
                    model=model,
                    assumptions=data.get("assumptions") or [],
                    warnings=data.get("warnings") or [],
                    reasoning=data.get("reasoning") or "",
                    workspace_root=self.workspace_root,
                )
                self._geometry3d_preview = {}
                self.geometry3d_export_btn.setEnabled(True)
                self._refresh_geometry3d()
                self._append("System", f"3D model saved: {res.get('model_path')}")
                self._emit_timeline("geometry3d.apply", {"path": res.get("model_path")})
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.critical(self, "3D Apply Error", str(e))
        elif typ == "geometry3d_parse_online":
            text = action.get("text") or ""
            router = self._brain.router
            system = (
                "Return JSON only. Format: {\"entities\":[{\"type\":\"box\",\"dims\":{\"x\":100,\"y\":80,\"z\":60},"
                "\"position\":{\"x\":0,\"y\":0,\"z\":0},\"material\":\"steel\",\"support\":\"fixed_base\",\"load\":\"axial\"}],"
                "\"operations\":[],\"confidence\":0.8,\"missing_info\":[],\"assumptions\":[]}"
            )
            res = router.route(
                "geometry3d_parse",
                prompt=text,
                system=system,
                online_enabled=self._online_enabled(),
                project_id=self.current_project_id,
                offline_confidence="low",
                parser_ok=False,
            )
            if res.get("mode") == "offline" and res.get("need_online"):
                self._append("Nova", res.get("text") or "Online AI required for 3D parsing.")
                return
            intent = geometry3d_intent.parse_intent_from_json(res.get("text") or "")
            entities = intent.get("entities") or []
            if not entities:
                self._append("Nova", "مش قادر أستنتج مجسم واضح من الوصف.")
                return
            assumptions = intent.get("assumptions") or []
            model = {"entities": entities, "operations": intent.get("operations") or []}
            warnings, reasoning = geometry3d_reasoning.analyze(model, assumptions)
            self._geometry3d_preview = {
                "model": model,
                "assumptions": assumptions,
                "warnings": warnings,
                "reasoning": reasoning,
            }
            self._update_geometry3d_preview()
            summary = _geometry3d_summary(entities, assumptions, warnings)
            self._append("Nova", "مع Online AI، ده التفسير:\n" + summary)
            self._pending_action = {"type": "geometry3d_apply", "description": "تأكيد المجسم ثلاثي الأبعاد"}
            self._show_confirmation(self._pending_action)
        elif typ == "geometry3d_export":
            state = geometry3d_store.load_model(self.current_project_id, workspace_root=self.workspace_root)
            model = state.get("model") or {}
            if not model.get("entities"):
                QMessageBox.warning(self, "No Model", "لا يوجد مجسم محفوظ للتصدير.")
                return
            try:
                out_dir = os.path.join(self.workspace_root, "projects", self.current_project_id, "geometry3d", "exports")
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"{self.current_project_id}_model.stl")
                geometry3d_export.export_stl(model, out_path, name=self.current_project_id)
                self._append("System", f"STL exported: {out_path}")
                self._emit_timeline("geometry3d.export", {"output_path": out_path})
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.critical(self, "3D Export Error", str(e))

    def _record_voice(self) -> None:
        self._toggle_voice_enabled_internal(not self.voice_enabled)
        self._emit_timeline("voice.toggle", {"enabled": self.voice_enabled})

    def _toggle_speaker(self, checked: bool) -> None:
        self.voice_muted = not bool(checked)
        if self.voice_loop is not None:
            self.voice_loop.set_muted(self.voice_muted)
        if checked:
            self._append("System", "Voice output enabled.")
        else:
            self._append("System", "Voice output disabled.")

    def _speak_text(self, text: str) -> None:
        payload = str(text or "").strip()
        if not payload:
            return
        if self.voice_enabled and self.voice_loop is not None and not self.voice_muted:
            try:
                self.voice_loop.notify_assistant_text(payload)
                return
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        tool = self.registry.tools.get("voice.tts_speak")
        if not tool:
            return
        try:
            res = self.runner.execute_registered_tool(tool, text=payload)
            if isinstance(res, dict) and res.get("status") != "ok":
                self._append("System", "TTS غير متاح حاليًا.")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _refresh_sketch(self) -> None:
        if not self.current_project_id:
            self.sketch_view.set_entities([])
            self.sketch_entities_list.clear()
            self.sketch_summary.setText("Sketch: 0 entities")
            return
        state = sketch_store.load_sketch(self.current_project_id, workspace_root=self.workspace_root)
        entities = state.get("entities") or []
        self.sketch_view.set_entities(entities)
        self.sketch_entities_list.clear()
        for e in entities:
            self.sketch_entities_list.addItem(entity_summary(e))
        self.sketch_summary.setText(f"Sketch: {len(entities)} entities")

    def _export_sketch(self) -> None:
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        self._pending_action = {"type": "sketch_export", "description": "تصدير DXF"}
        self._show_confirmation(self._pending_action)

    def _update_engineering_preview(self) -> None:
        data = self._engineering_preview or {}
        state = data.get("state") or {}
        if not state:
            self._refresh_engineering()
            return
        self._populate_engineering_ui(state, data.get("findings") or [])
        summary = _engineering_summary(state, data.get("findings") or [])
        if self._engineering_assumptions_edited:
            summary += " (Preview)"
        self.engineering_summary.setText(summary)

    def _refresh_engineering(self) -> None:
        if self._engineering_preview:
            self._update_engineering_preview()
            return
        self._engineering_assumptions_edited = False
        if not self.current_project_id:
            self.engineering_summary.setText("Engineering: no analysis")
            self.engineering_findings.clear()
            self.engineering_assumptions.clear()
            return
        state = engineering_store.load_state(self.current_project_id, workspace_root=self.workspace_root)
        if not state.get("state"):
            self.engineering_summary.setText("Engineering: no analysis")
            self.engineering_findings.clear()
            self.engineering_assumptions.clear()
            return
        self._populate_engineering_ui(state.get("state") or {}, state.get("warnings") or [])
        self.engineering_summary.setText(_engineering_summary(state.get("state") or {}, state.get("warnings") or []))

    def _populate_engineering_ui(self, state: dict, findings: list) -> None:
        self.engineering_findings.clear()
        if findings:
            for f in findings:
                sev = f.get("severity", "WARN")
                title = f.get("title") or ""
                detail = f.get("detail") or ""
                self.engineering_findings.addItem(f"[{sev}] {title} - {detail}")
        else:
            self.engineering_findings.addItem("(no findings)")
        self.engineering_assumptions.clear()
        assumptions = (state.get("assumptions") or {}).get("assumed_values") or []
        if assumptions:
            for a in assumptions:
                self.engineering_assumptions.addItem(f"{a.get('field')}: {a.get('value')} ({a.get('rationale')})")
        else:
            self.engineering_assumptions.addItem("(no assumptions)")

    def _edit_engineering_assumptions(self) -> None:
        if not self._engineering_preview:
            QMessageBox.information(self, "No Preview", "No engineering analysis to edit.")
            return
        state = self._engineering_preview.get("state") or {}
        current = (state.get("assumptions") or {}).get("assumed_values") or []
        text = "\n".join([f"{a.get('field')}={a.get('value')}" for a in current])
        new_text, ok = QInputDialog.getMultiLineText(self, "Assumptions", "Edit assumptions (field=value):", text)
        if not ok:
            return
        new_list = []
        for line in (new_text or "").splitlines():
            if "=" in line:
                field, value = line.split("=", 1)
                new_list.append({"field": field.strip(), "value": value.strip(), "rationale": "User override"})
        state.setdefault("assumptions", {})["assumed_values"] = new_list
        self._engineering_preview["state"] = state
        self._engineering_assumptions_edited = True
        self._update_engineering_preview()
        self._append("System", "تم تعديل الافتراضات كمعاينة فقط. لتثبيتها وحفظها استخدم Generate Design Report.")

    def _generate_engineering_report(self) -> None:
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        data = self._engineering_preview
        if not data:
            QMessageBox.information(self, "No Analysis", "No engineering analysis to report.")
            return
        state = data.get("state") or {}
        findings = data.get("findings") or []
        report = data.get("report") or ""
        try:
            res = engineering_store.save_state(
                self.current_project_id,
                state=state,
                assumptions=state.get("assumptions") or {},
                warnings=findings,
                report=report,
                workspace_root=self.workspace_root,
            )
            self._append("System", f"Engineering report saved: {res.get('report_path')}")
            self._emit_timeline("engineering.report", {"path": res.get("report_path")})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Engineering Report Error", str(e))

    def _update_geometry3d_preview(self) -> None:
        data = self._geometry3d_preview or {}
        model = data.get("model") or {}
        entities = model.get("entities") or []
        if not entities:
            self._refresh_geometry3d()
            return
        self._geometry3d_visibility = {}
        self.geometry3d_summary.setText(f"3D: Preview ({len(entities)} entities)")
        self._populate_geometry3d_ui(model, data.get("assumptions") or [], data.get("warnings") or [])
        self.geometry3d_export_btn.setEnabled(False)

    def _refresh_geometry3d(self) -> None:
        if self._geometry3d_preview:
            self._update_geometry3d_preview()
            return
        if not self.current_project_id:
            self.geometry3d_view.clear()
            self.geometry3d_entities_list.clear()
            self.geometry3d_assumptions.clear()
            self.geometry3d_warnings.clear()
            self.geometry3d_summary.setText("3D: no model")
            self.geometry3d_export_btn.setEnabled(False)
            return
        state = geometry3d_store.load_model(self.current_project_id, workspace_root=self.workspace_root)
        model = state.get("model") or {}
        entities = model.get("entities") or []
        if not entities:
            self.geometry3d_view.clear()
            self.geometry3d_entities_list.clear()
            self.geometry3d_assumptions.clear()
            self.geometry3d_warnings.clear()
            self.geometry3d_summary.setText("3D: no model")
            self.geometry3d_export_btn.setEnabled(False)
            return
        self.geometry3d_summary.setText(f"3D: {len(entities)} entities")
        self._populate_geometry3d_ui(model, state.get("assumptions") or [], state.get("warnings") or [])
        self.geometry3d_export_btn.setEnabled(True)

    def _populate_geometry3d_ui(self, model: dict, assumptions: list, warnings: list) -> None:
        entities = model.get("entities") or []
        self.geometry3d_view.set_model(model)
        self.geometry3d_entities_list.blockSignals(True)
        self.geometry3d_entities_list.clear()
        if not self._geometry3d_visibility:
            self._geometry3d_visibility = {str(e.get("id") or i): True for i, e in enumerate(entities)}
        for e in entities:
            eid = str(e.get("id") or "")
            name = f"{eid} ({e.get('type')})"
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, eid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if self._geometry3d_visibility.get(eid, True) else Qt.Unchecked)
            self.geometry3d_entities_list.addItem(item)
        self.geometry3d_entities_list.blockSignals(False)
        self.geometry3d_assumptions.clear()
        if assumptions:
            for a in assumptions:
                self.geometry3d_assumptions.addItem(str(a))
        else:
            self.geometry3d_assumptions.addItem("(no assumptions)")
        self.geometry3d_warnings.clear()
        if warnings:
            for w in warnings:
                sev = w.get("severity", "WARN")
                detail = w.get("detail", "")
                self.geometry3d_warnings.addItem(f"[{sev}] {detail}")
        else:
            self.geometry3d_warnings.addItem("(no warnings)")

    def _geometry3d_entity_toggled(self, item: QListWidgetItem) -> None:
        eid = item.data(Qt.UserRole)
        visible = item.checkState() == Qt.Checked
        self._geometry3d_visibility[str(eid)] = visible
        self.geometry3d_view.set_visibility(str(eid), visible)

    def _confirm_geometry3d(self) -> None:
        if not self._geometry3d_preview:
            QMessageBox.information(self, "No Preview", "لا يوجد معاينة ثلاثية الأبعاد لتأكيدها.")
            return
        if not self._pending_action or self._pending_action.get("type") != "geometry3d_apply":
            self._pending_action = {"type": "geometry3d_apply", "description": "تأكيد المجسم ثلاثي الأبعاد"}
            self._show_confirmation(self._pending_action)
            return
        self._confirm_pending_action()

    def _edit_geometry3d_assumptions(self) -> None:
        data = self._geometry3d_preview or {}
        model = data.get("model") or {}
        if not model.get("entities"):
            if self.current_project_id:
                state = geometry3d_store.load_model(self.current_project_id, workspace_root=self.workspace_root)
                model = state.get("model") or {}
                data = {
                    "model": model,
                    "assumptions": state.get("assumptions") or [],
                    "warnings": state.get("warnings") or [],
                    "reasoning": state.get("reasoning") or "",
                }
            if not model.get("entities"):
                QMessageBox.information(self, "No Model", "لا يوجد مجسم لتعديل الافتراضات.")
                return
        mats = ["steel", "aluminum", "concrete", "wood", "unknown"]
        mat, ok = QInputDialog.getItem(self, "Assumptions", "Material:", mats, 0, False)
        if not ok:
            return
        supports = ["fixed_base", "simple", "cantilever", "unsupported", "unspecified"]
        sup, ok = QInputDialog.getItem(self, "Assumptions", "Support:", supports, 0, False)
        if not ok:
            return
        loads = ["axial", "lateral", "bending", "torsion", "compression", "tension", "unknown"]
        load, ok = QInputDialog.getItem(self, "Assumptions", "Load:", loads, 0, False)
        if not ok:
            return
        for e in model.get("entities") or []:
            e["material"] = "" if mat == "unknown" else mat
            e["support"] = "" if sup == "unspecified" else sup
            e["load"] = "" if load == "unknown" else load
        assumptions = []
        if mat == "unknown":
            assumptions.append("Material assumed: steel")
        else:
            assumptions.append(f"Material set: {mat}")
        if sup == "unspecified":
            assumptions.append("Support assumed: unspecified")
        else:
            assumptions.append(f"Support set: {sup}")
        if load == "unknown":
            assumptions.append("Load assumed: unknown")
        else:
            assumptions.append(f"Load set: {load}")
        warnings, reasoning = geometry3d_reasoning.analyze(model, assumptions)
        self._geometry3d_preview = {
            "model": model,
            "assumptions": assumptions,
            "warnings": warnings,
            "reasoning": reasoning,
        }
        self._update_geometry3d_preview()

    def _export_geometry3d(self) -> None:
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        self._pending_action = {"type": "geometry3d_export", "description": "تصدير STL"}
        self._show_confirmation(self._pending_action)

    def _refresh_timeline(self) -> None:
        if not self.current_project_id:
            self.timeline_list.clear()
            self.timeline_list.addItem("(no project)")
            return
        spine = self._audit_spine()
        if not spine:
            return
        events = spine.read_events(limit=200)
        filt = (self.timeline_filter.currentText() or "all").lower()
        self.timeline_list.clear()
        if not events:
            self.timeline_list.addItem("(no events)")
            return
        for e in events:
            et = str(e.get("event_type") or "")
            if filt != "all":
                if filt == "message" and not et.startswith("message"):
                    continue
                if filt == "approval" and "approval" not in et:
                    continue
                if filt == "tool" and not et.startswith("tool"):
                    continue
                if filt == "job" and not et.startswith("job"):
                    continue
                if filt == "security" and not et.startswith("security"):
                    continue
                if filt == "preview" and not et.startswith("preview"):
                    continue
                if filt == "sketch" and not et.startswith("sketch"):
                    continue
                if filt == "geometry3d" and not et.startswith("geometry3d"):
                    continue
                if filt == "engineering" and not et.startswith("engineering"):
                    continue
                if filt == "other" and et.startswith(("message", "approval", "tool", "job", "security", "preview", "sketch", "geometry3d", "engineering")):
                    continue
            ts = e.get("recorded_at") or ""
            summary = e.get("payload") or {}
            self.timeline_list.addItem(f"{ts} | {et} | {summary}")

    def _open_health_stats(self) -> None:
        self.tabs.setCurrentWidget(self.health_tab)
        self._refresh_health_stats()

    def _refresh_health_stats(self) -> None:
        self.health_stats_list.clear()
        if not self._ipc_enabled:
            self.health_summary.setText("Health stats unavailable (IPC disabled).")
            self.health_stats_list.addItem("Enable NH_IPC_ENABLED=1 to fetch core telemetry scoreboard.")
            return
        try:
            client = self._ensure_ipc_client()
            payload = client.call_ok(
                "telemetry.scoreboard.get",
                {"mode": str(self.current_task_mode or "general")},
            )
            rows = payload.get("providers")
            if not isinstance(rows, list):
                rows = []
            self.health_summary.setText(f"Providers tracked: {len(rows)}")
            if not rows:
                self.health_stats_list.addItem("(no provider telemetry yet)")
                return
            for item in rows:
                if not isinstance(item, dict):
                    continue
                provider = str(item.get("provider") or "unknown")
                calls = int(item.get("calls") or 0)
                success = float(item.get("success_rate") or 0.0) * 100.0
                latency = int(item.get("avg_latency_ms") or 0)
                last_error = str(item.get("last_error") or "")
                line = f"{provider} | calls={calls} | success={success:.1f}% | latency={latency}ms"
                self.health_stats_list.addItem(line)
                if last_error:
                    self.health_stats_list.addItem(f"  last_error: {last_error}")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self.health_summary.setText("Health stats unavailable.")
            self.health_stats_list.addItem(f"Failed to load scoreboard: {exc}")

    def _append(self, who: str, text: str) -> None:
        self.transcript.append(f"{who}: {text}")
        if self.current_project_id:
            self._append_project_chat(who, text)
            self._refresh_project_list()
        if who == "Nova" and self.speaker_toggle.isChecked():
            self._speak_text(text)
        kind = "message.system"
        if who.lower().startswith("you"):
            kind = "message.user"
        elif who.lower().startswith("nova"):
            kind = "message.nova"
        self._emit_timeline(kind, {"text": text})
        self._maybe_show_api_setup()
        self._refresh_api_banner()

    def _attach_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Attach Files", self.project_root)
        if files:
            self._ingest_paths(files)

    def _ingest_paths(self, paths):
        try:
            if self.current_project_id:
                res = self.ingest.ingest_project(self.current_project_id, paths)
                scope = f"project:{self.current_project_id}"
            else:
                res = self.ingest.ingest_general(self.general_chat_id, paths)
                scope = "general"
            normalized = normalize_ingest_result(res if isinstance(res, dict) else {})
            counts = normalized.get("counts") if isinstance(normalized.get("counts"), dict) else {}
            accepted = int(counts.get("accepted") or 0)
            rejected = int(counts.get("rejected") or 0)
            summary = (
                f"[{scope}] Ingested {counts.get('files_ingested', 0)} files "
                f"(accepted={accepted}, rejected={rejected}), "
                f"extracted {counts.get('files_extracted', 0)} texts, "
                f"keys imported {counts.get('keys_imported', 0)} (memory-only)."
            )
            preview = rejected_preview_lines(normalized, max_items=3)
            if preview:
                summary += " Rejected -> " + " | ".join(preview)
            self._append("Nova", summary)
            if self.current_project_id:
                self._refresh_docs_summary()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Ingest Error", str(e))

    def _update_state(self, state):
        if self.current_project_id:
            existing = self.project_manager.load_state(self.current_project_id)
            ps = ProjectState(
                last_diff_path=str(state.get("last_diff_path") or ""),
                suggestions=list(state.get("suggestions") or state.get("last_recommendations") or []),
                last_reports=list(state.get("last_reports") or []),
                suggestion_status=dict(state.get("suggestion_status") or {}),
                security_gate=getattr(existing, "security_gate", {}) or {},
                jarvis=getattr(existing, "jarvis", {}) or {},
            )
            self._save_project_state(ps)
        self._refresh_suggestions_panel()
        self._refresh_artifacts()
        self._update_confirm_bar(state.get("pending_apply_diff_path") or "")

    def _refresh_suggestions_panel(self) -> None:
        while self.suggestions_list_layout.count():
            item = self.suggestions_list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not self.current_project_id:
            self.suggestions_list_layout.addWidget(QLabel("No project selected."))
            return

        state = self.project_manager.load_state(self.current_project_id)
        suggestions = state.suggestions or []
        status_map = state.suggestion_status or {}

        if not suggestions:
            self.suggestions_list_layout.addWidget(QLabel("No suggestions yet. Run Analyze."))
            return

        for idx, s in enumerate(suggestions, 1):
            title = s.get("title") if isinstance(s, dict) else str(s)
            reason = s.get("rationale") if isinstance(s, dict) else ""
            if not reason and isinstance(s, dict):
                reason = s.get("reason") or ""
            status_entry = status_map.get(str(idx), {}) if isinstance(status_map, dict) else {}
            status = (status_entry.get("status") or "ready").upper()
            diff_path = status_entry.get("last_diff_path") or ""
            risk = self._risk_for_suggestion(title, reason)

            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 4)

            header = QHBoxLayout()
            header.addWidget(QLabel(f"#{idx} {title}"))
            badge = QLabel(risk.upper())
            badge.setStyleSheet(self._risk_badge_style(risk))
            status_label = QLabel(status)
            status_label.setStyleSheet(self._status_badge_style(status))
            header.addWidget(badge)
            header.addWidget(status_label)
            header.addStretch(1)
            row_layout.addLayout(header)

            if reason:
                row_layout.addWidget(QLabel(reason))

            btn_row = QHBoxLayout()
            exec_btn = QPushButton("Execute")
            exec_btn.clicked.connect(lambda _=None, n=idx, t=title: self._execute_suggestion(n, t))
            btn_row.addWidget(exec_btn)
            if status.lower() == "diff_ready" and diff_path:
                apply_btn = QPushButton("Apply Diff")
                apply_btn.clicked.connect(lambda _=None, p=diff_path, n=idx: self._apply_diff_path(p, n))
                open_btn = QPushButton("Open Diff")
                open_btn.clicked.connect(lambda _=None, p=diff_path: self._open_path(p))
                btn_row.addWidget(apply_btn)
                btn_row.addWidget(open_btn)
            btn_row.addStretch(1)
            row_layout.addLayout(btn_row)

            self.suggestions_list_layout.addWidget(row)

    def _risk_for_suggestion(self, title: str, reason: str) -> str:
        low = (title + " " + reason).lower()
        if "fail" in low or "verify" in low or "error" in low:
            return "high"
        if "todo" in low or "fixme" in low or "hotspot" in low:
            return "med"
        return "low"

    def _risk_badge_style(self, risk: str) -> str:
        if risk == "high":
            return "background:#b91c1c;color:#ffffff;padding:2px 6px;border-radius:8px;"
        if risk == "med":
            return "background:#d97706;color:#ffffff;padding:2px 6px;border-radius:8px;"
        return "background:#2d6a4f;color:#ffffff;padding:2px 6px;border-radius:8px;"

    def _status_badge_style(self, status: str) -> str:
        if status == "FAILED":
            return "background:#991b1b;color:#ffffff;padding:2px 6px;border-radius:8px;"
        if status == "APPLIED":
            return "background:#15803d;color:#ffffff;padding:2px 6px;border-radius:8px;"
        if status == "DIFF_READY":
            return "background:#1d4ed8;color:#ffffff;padding:2px 6px;border-radius:8px;"
        return "background:#6b7280;color:#ffffff;padding:2px 6px;border-radius:8px;"

    def _execute_suggestion(self, number: int, title: str) -> None:
        self._append("System", f"Executing suggestion #{number}: {title}")
        self._send_message(text=f"نفّذ {number}", allow_execute=True)

    def _apply_diff_path(self, diff_path: str, number: int) -> None:
        self._append("System", f"Apply diff: {diff_path}")
        self._send_message(text=f"apply {diff_path} suggestion:{number}", allow_execute=True)

    def _update_confirm_bar(self, diff_path: str) -> None:
        if diff_path:
            self.confirm_label.setText(f"Diff ready: {diff_path}")
            self.confirm_bar.setVisible(True)
        else:
            self.confirm_bar.setVisible(False)

    def _confirm_apply(self) -> None:
        self._send_message(text="yes", allow_execute=True)

    def _cancel_apply(self) -> None:
        self._send_message(text="no")

    def _refresh_artifacts(self) -> None:
        if not self.current_project_id:
            self.artifacts_reports.set_items([])
            self.artifacts_patches.set_items([])
            self.artifacts_snapshots.set_items([])
            self.artifacts_releases.set_items([])
            return
        paths = self.project_manager.get_project_paths(self.current_project_id)
        self.artifacts_reports.set_items(self._artifact_items(paths.reports, ".md", 5))
        self.artifacts_patches.set_items(self._artifact_items(paths.patches, ".diff", 3))
        self.artifacts_snapshots.set_items(self._artifact_items(paths.snapshots, ".zip", 3))
        self.artifacts_releases.set_items(self._artifact_items(paths.releases, ".zip", 3))

    def _refresh_security_state(self) -> None:
        self._load_last_security_report()
        if self.current_project_id:
            state = self.project_manager.load_state(self.current_project_id)
            self._security_gate = getattr(state, "security_gate", {}) or {}
        else:
            self._security_gate = {}
        self._apply_security_gate()

    def _load_last_security_report(self) -> None:
        path = os.path.join(self.workspace_root, "reports", "security_audit.json")
        report = {}
        if os.path.exists(path):
            try:
                import json
                with open(path, "r", encoding="utf-8") as f:
                    report = json.load(f) or {}
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                report = {}
        self._last_security_report = report
        self._update_security_view(report)

    def _update_security_view(self, report: dict) -> None:
        while self.security_list_layout.count():
            item = self.security_list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not report:
            self.security_summary.setText("No security audit run yet.")
            self.security_list_layout.addWidget(QLabel("Run an audit to see findings."))
            self.security_fix_plan_btn.setEnabled(bool(self.current_project_id))
            return

        summary = report.get("summary") or {}
        self.security_summary.setText(
            f"OK: {summary.get('OK', 0)} | WARNING: {summary.get('WARNING', 0)} | CRITICAL: {summary.get('CRITICAL', 0)}"
        )
        findings = report.get("findings") or []
        if not findings:
            self.security_list_layout.addWidget(QLabel("No findings."))
            self.security_fix_plan_btn.setEnabled(bool(self.current_project_id))
            return

        buckets = {"CRITICAL": [], "WARNING": [], "OK": []}
        for f in findings:
            sev = str(f.get("severity") or "").upper()
            if sev not in buckets:
                sev = "WARNING"
            buckets[sev].append(f)

        for sev in ("CRITICAL", "WARNING", "OK"):
            if not buckets[sev]:
                continue
            header = QLabel(sev)
            header.setStyleSheet("font-weight:bold;")
            self.security_list_layout.addWidget(header)
            for f in buckets[sev]:
                title = f.get("title") or ""
                check_id = f.get("checkId") or ""
                detail = f.get("detail") or ""
                remediation = f.get("remediation") or ""
                text = f"{check_id}: {title}"
                if detail:
                    text += f"\n  {detail}"
                if remediation:
                    text += f"\n  Fix: {remediation}"
                evidence = f.get("evidence") or []
                if evidence:
                    ev = evidence[0]
                    ev_path = ev.get("path") or ""
                    ev_line = ev.get("line")
                    ev_excerpt = ev.get("excerpt") or ""
                    ev_text = f"  Evidence: {ev_path}"
                    if ev_line:
                        ev_text += f":{ev_line}"
                    if ev_excerpt:
                        ev_text += f" — {ev_excerpt}"
                    text += "\n" + ev_text
                self.security_list_layout.addWidget(QLabel(text))

        self.security_fix_plan_btn.setEnabled(bool(self.current_project_id))

    def _run_security_audit(self) -> None:
        tool = self.registry.tools.get("security.audit")
        if not tool:
            QMessageBox.warning(self, "Missing Tool", "security.audit not available.")
            return
        try:
            res = self.runner.execute_registered_tool(
                tool,
                project_id=self.current_project_id,
                write_reports=True,
            )
            if isinstance(res, dict):
                self._last_security_report = res
                self._update_security_view(res)
                self._emit_timeline("security.audit", {"summary": res.get("summary")})
                if self.current_project_id:
                    state = self.project_manager.load_state(self.current_project_id)
                    gate = res.get("security_gate") or {}
                    state.security_gate = gate
                    self._save_project_state(state)
                    self._security_gate = gate
                    self._apply_security_gate()
            QMessageBox.information(self, "Security Audit", "Security audit completed.")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Security Audit Error", str(e))

    def _security_fix_plan(self) -> None:
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        tool = self.registry.tools.get("patch.plan")
        if not tool:
            QMessageBox.warning(self, "Missing Tool", "patch.plan not available.")
            return
        paths = self.project_manager.get_project_paths(self.current_project_id)
        goal = "Address Security Audit findings"
        if self._last_security_report:
            gate = self._last_security_report.get("security_gate") or {}
            crits = gate.get("critical_findings") or []
            if crits:
                goal += " (critical: " + ", ".join(crits[:5]) + ")"
        try:
            self.runner.execute_registered_tool(
                tool,
                target_root=paths.working,
                goal=goal,
                max_files=10,
                write_reports=True,
            )
            QMessageBox.information(self, "Fix Plan", "Patch plan generated.")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Fix Plan Error", str(e))

    def _security_blocked(self) -> bool:
        return bool((self._security_gate or {}).get("blocked_online_project"))

    def _apply_security_gate(self) -> None:
        blocked = self._security_blocked()
        if blocked:
            crits = (self._security_gate or {}).get("critical_findings") or []
            self.security_banner_label.setText(
                f"Security warning: {len(crits)} critical issue(s) block project Online AI."
            )
        else:
            self.security_banner_label.setText("Security warning: audit required.")
        self.security_banner.setVisible(blocked)

        if blocked:
            self.scope_project.setEnabled(False)
            self.scope_project.setToolTip("Blocked by Security Gate")
            if self.scope_project.isChecked():
                self.scope_session.setChecked(True)
                self.online_toggle.setChecked(False)
                self._online_state.scope = "session"
        else:
            self.scope_project.setEnabled(True)
            self.scope_project.setToolTip("")

    def _artifact_items(self, folder: str, ext: str, limit: int):
        if not os.path.isdir(folder):
            return []
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(ext)]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        items = []
        for path in files[:limit]:
            label = os.path.basename(path)
            items.append((label, lambda p=path: self._open_path(p)))
        return items

    def _refresh_docs_summary(self) -> None:
        if not self.current_project_id:
            self.docs_summary.setText("Docs: 0")
            return
        paths = self.project_manager.get_project_paths(self.current_project_id)
        index_path = os.path.join(paths.project_root, "index.json")
        count = 0
        last_batch = ""
        if os.path.exists(index_path):
            try:
                import json
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or []
                if isinstance(data, list):
                    count = len(data)
                if os.path.isdir(paths.docs):
                    batches = [d for d in os.listdir(paths.docs) if os.path.isdir(os.path.join(paths.docs, d))]
                    if batches:
                        batches.sort(reverse=True)
                        last_batch = batches[0]
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        text = f"Docs: {count}"
        if last_batch:
            text += f" | last batch: {last_batch}"
        self.docs_summary.setText(text)

    def _run_preview(self) -> None:
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        paths = self.project_manager.get_project_paths(self.current_project_id)
        profiles = detect_run_profiles(paths.working)
        if not profiles:
            QMessageBox.warning(self, "No Entrypoints", "No runnable entrypoints detected.")
            return
        labels = [p["label"] for p in profiles]
        choice, ok = QInputDialog.getItem(self, "Run Preview", "Select run profile:", labels, 0, False)
        if not ok or not choice:
            return
        selected = None
        for p in profiles:
            if p["label"] == choice:
                selected = p
                break
        if not selected:
            return
        tool = self.registry.tools.get("run.preview")
        if not tool:
            QMessageBox.warning(self, "Missing Tool", "run.preview not available.")
            return
        try:
            result = self.runner.execute_registered_tool(
                tool,
                project_id=self.current_project_id,
                profile_id=selected["id"],
            )
            self.preview_run_id = str(result.get("run_id") or "")
            self.preview_log_path = str(result.get("log_path") or "")
            self.preview_output.setPlainText(f"Started preview: {result.get('entry')}\nLog: {self.preview_log_path}")
            self.stop_preview_btn.setEnabled(bool(self.preview_run_id))
            self._preview_timer.start()
            self._emit_timeline("preview.start", {"run_id": self.preview_run_id, "entry": result.get("entry")})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Run Preview Error", str(e))

    def _stop_preview(self) -> None:
        if not self.preview_run_id:
            return
        tool = self.registry.tools.get("run.stop")
        if not tool:
            QMessageBox.warning(self, "Missing Tool", "run.stop not available.")
            return
        try:
            result = self.runner.execute_registered_tool(tool, run_id=self.preview_run_id)
            self.preview_run_id = ""
            self.stop_preview_btn.setEnabled(False)
            self._preview_timer.stop()
            if isinstance(result, dict) and result.get("summary"):
                self.preview_output.append("\n" + result.get("summary"))
            if isinstance(result, dict):
                status = result.get("status")
                exit_code = result.get("exit_code")
                self._emit_timeline("preview.stop", {"status": status, "exit_code": exit_code})
                if status == "crashed" or (exit_code not in (None, 0) and status not in ("stopped", "not_found")):
                    ctx = self._load_jarvis_context()
                    jarvis_core.update_last_outcome(ctx, "preview_crashed", resolved=False)
                    plan, _ = jarvis_core.recovery_mode(ctx, {"type": "preview_crashed"})
                    if plan:
                        self._append("Nova", plan)
                    self._persist_jarvis_context(ctx)
                    self._emit_timeline("preview.crash", {"exit_code": exit_code})
                elif status == "stopped":
                    ctx = self._load_jarvis_context()
                    jarvis = dict((ctx or {}).get("jarvis") or {})
                    last = jarvis.get("last_outcome") or {}
                    if last and last.get("type") == "preview_crashed" and not last.get("resolved"):
                        _, reminder = jarvis_core.recovery_mode(ctx, {"type": "preview_crashed"})
                        if reminder:
                            self._append("Nova", reminder)
                        jarvis_core.update_last_outcome(ctx, "preview_crashed", resolved=True)
                        self._persist_jarvis_context(ctx)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Stop Preview Error", str(e))

    def _refresh_preview_output(self) -> None:
        if not self.preview_log_path or not os.path.exists(self.preview_log_path):
            return
        try:
            with open(self.preview_log_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            self.preview_output.setPlainText(text)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _open_folder(self, name: str) -> None:
        if not self.current_project_id:
            return
        paths = self.project_manager.get_project_paths(self.current_project_id)
        target = {
            "docs": paths.docs,
            "extracted": paths.extracted,
        }.get(name)
        if not target:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    def _open_path(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _save_project_state(self, state: ProjectState) -> None:
        paths = self.project_manager.get_project_paths(self.current_project_id)
        payload = __import__("json").dumps(state.to_dict(), indent=2, ensure_ascii=True)
        if not self.safe_writer.write_text(paths.state_path, payload):
            tool = self.registry.tools.get("fs.write_text")
            self.runner.execute_registered_tool(tool, path=paths.state_path, text=payload, target=paths.state_path)

    def _append_project_chat(self, who: str, text: str) -> None:
        paths = self.project_manager.get_project_paths(self.current_project_id)
        existing = ""
        if os.path.exists(paths.chat_path):
            try:
                with open(paths.chat_path, "r", encoding="utf-8") as f:
                    existing = f.read()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                existing = ""
        block = f"{who}: {text}\n"
        if not self.safe_writer.write_text(paths.chat_path, existing + block):
            tool = self.registry.tools.get("fs.write_text")
            self.runner.execute_registered_tool(tool, path=paths.chat_path, text=existing + block, target=paths.chat_path)

    def _flush_current_project_state(self) -> None:
        if not self.current_project_id:
            return
        state = self.project_manager.load_state(self.current_project_id)
        self._save_project_state(state)

    def _last_message_preview(self, project_id: str):
        try:
            paths = self.project_manager.get_project_paths(project_id)
            if os.path.exists(paths.chat_path):
                with open(paths.chat_path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                lines = [l for l in lines if not l.startswith("System:")]
                if lines:
                    last = lines[-1]
                    ts = datetime.fromtimestamp(os.path.getmtime(paths.chat_path)).strftime("%Y-%m-%d %H:%M")
                    return (last[:60] + ("..." if len(last) > 60 else ""), ts)
            meta = next((p for p in self.project_manager.list_projects() if p.get("id") == project_id), None)
            if meta and meta.get("last_opened"):
                return ("(no messages)", meta.get("last_opened"))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        return ("(no messages)", "")

    def _status_badge(self, summary: str, project_id: str | None = None) -> str:
        if project_id:
            try:
                jobs = self.job_controller.list_jobs(project_id)
                for j in jobs:
                    if j.get("status") == "waiting_for_user" and j.get("waiting_reason") == "confirm_apply":
                        return "WAIT"
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        s = summary or ""
        if "verified" in s:
            return "OK"
        if "diff_ready" in s:
            return "DIFF"
        if "reports" in s:
            return "WARN"
        return ""

    def _maybe_show_api_setup(self) -> None:
        marker = os.path.join(self.workspace_root, ".first_run_done")
        skip_marker = os.path.join(self.workspace_root, ".api_setup_skipped")
        if os.path.exists(marker) or os.path.exists(skip_marker) or self._api_setup_open:
            return
        self._api_setup_open = True
        dlg = ApiSetupDialog(
            self,
            secrets=self.secrets,
            runner=self.runner,
            registry=self.registry,
            project_manager=self.project_manager,
            workspace_root=self.workspace_root,
            project_root=self.project_root,
            safe_writer=self.safe_writer,
            get_project_id=lambda: self.current_project_id,
            append_message=self._append,
            refresh_banner=self._refresh_api_banner,
        )
        dlg.exec()
        self._api_setup_open = False

    def _refresh_api_banner(self) -> None:
        deep = provider_ready(self.secrets, "deepseek")
        gem = provider_ready(self.secrets, "gemini")
        tel = provider_ready(self.secrets, "telegram")
        self.chip_deepseek.setText(f"DeepSeek: {'OK' if deep else 'MISS'}")
        self.chip_gemini.setText(f"Gemini: {'OK' if gem else 'MISS'}")
        self.chip_telegram.setText(f"Telegram: {'OK' if tel else 'MISS'}")
        required = required_secrets.required_keys_for_tools([t.tool_id for t in self.registry.list_tools()])
        status = get_key_status(self.secrets, required)
        missing = [k for k, v in status.items() if v != "present"]
        # enable save if any temp-only keys
        temp_only = any(self.secrets.has_temp_only(k) for k in self.secrets.temp_keys().keys())
        all_ok = not missing
        self.api_status_label.setText("API: OK" if all_ok else "API: Attention")
        if all_ok:
            self._api_banner_expanded = False
        if missing or temp_only:
            self._api_banner_expanded = True
        self.api_banner.setVisible(self._api_banner_expanded)
        self.api_toggle_btn.setText("Hide" if self._api_banner_expanded else "Show")
        self.save_keys_btn.setEnabled(temp_only)

    def _toggle_api_banner(self) -> None:
        self._api_banner_expanded = not self._api_banner_expanded
        self.api_banner.setVisible(self._api_banner_expanded)
        self.api_toggle_btn.setText("Hide" if self._api_banner_expanded else "Show")

    def _open_api_keys_dialog(self) -> None:
        dlg = ApiSetupDialog(
            self,
            secrets=self.secrets,
            runner=self.runner,
            registry=self.registry,
            project_manager=self.project_manager,
            workspace_root=self.workspace_root,
            project_root=self.project_root,
            safe_writer=self.safe_writer,
            get_project_id=lambda: self.current_project_id,
            append_message=self._append,
            refresh_banner=self._refresh_api_banner,
        )
        dlg.exec()

    def _import_api_keys(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import api.txt", self.project_root, "Text Files (*.txt)")
        if not path:
            return
        try:
            text = open(path, "r", encoding="utf-8", errors="replace").read()
            importer = ApiImporter(self.secrets, runner=self.runner, registry=self.registry)
            found = importer.detect_keys(text)
            count = importer.import_from_text(text)
            red = ApiImporter.redact_map(found)
            msg = "Imported keys: " + ", ".join([f"{k}={v}" for k, v in red.items()])
            self._append("System", msg)
            self._refresh_api_banner()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _save_keys(self) -> None:
        temp = self.secrets.temp_keys()
        if not temp:
            return
        try:
            importer = ApiImporter(self.secrets, runner=self.runner, registry=self.registry)
            importer.persist_keys(temp)
            self._append("System", f"Saved {len(temp)} keys to workspace secrets.")
            self._refresh_api_banner()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Save Keys Error", str(e))

    def _refresh_jobs_panel(self) -> None:
        if not self.current_project_id:
            self.jobs_list.clear()
            return
        self.jobs_list.clear()
        jobs = self.job_controller.list_jobs(self.current_project_id)
        for j in jobs:
            awaiting = j.get("status") == "waiting_for_user" and j.get("waiting_reason") == "confirm_apply"
            badge = " [Awaiting Confirm]" if awaiting else ""
            label = f"{j.get('title')} | {j.get('status')}{badge} | {j.get('steps_done')}/{j.get('steps_total')} | {j.get('current_step_label')}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, j.get("job_id"))
            self.jobs_list.addItem(item)

    def _on_job_selected(self, current: QListWidgetItem) -> None:
        if not current or not self.current_project_id:
            return
        job_id = current.data(Qt.UserRole)
        if not job_id:
            return
        job = self.job_controller.get_job(self.current_project_id, job_id)
        self.jobs_status.setText(
            f"Status: {job.status} | Step {job.steps_done}/{job.steps_total} | {job.current_step_label} | "
            f"Safe: {job.last_safe_point_label} @ {job.last_safe_point_at}"
        )
        self.jobs_log.setPlainText("\n".join(job.log_tail))

    def _selected_job_id(self) -> str:
        item = self.jobs_list.currentItem()
        if not item:
            return ""
        return item.data(Qt.UserRole) or ""

    def _create_job(self) -> None:
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        recipes = ["Quick Fix", "Auto Improve", "Pipeline"]
        choice, ok = QInputDialog.getItem(self, "Create Job", "Choose recipe:", recipes, 0, False)
        if not ok or not choice:
            return
        recipe_id = {"Quick Fix": "quick_fix", "Auto Improve": "auto_improve", "Pipeline": "pipeline"}[choice]
        required = required_secrets.required_keys_for_feature(recipe_id)
        missing = [k for k, v in get_key_status(self.secrets, required).items() if v != "present"]
        if missing:
            QMessageBox.warning(
                self,
                "Missing API Keys",
                "Missing keys: " + ", ".join(missing) + "\nImport api.txt to continue.",
            )
            return
        options = {}
        if recipe_id == "auto_improve":
            val, ok2 = QInputDialog.getInt(self, "Auto Improve", "Max suggestions:", 3, 1, 10)
            if not ok2:
                return
            options["max_suggestions"] = val
        if recipe_id == "pipeline":
            goal, ok3 = QInputDialog.getText(self, "Pipeline", "Goal:")
            if not ok3:
                return
            options["goal"] = goal or "Pipeline run"
        job = self.job_controller.enqueue_job(self.current_project_id, choice, recipe_id, options)
        self.job_controller.start_job(self.current_project_id, job.job_id)
        self._refresh_jobs_panel()

    def _start_job(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            return
        job = self.job_controller.get_job(self.current_project_id, job_id)
        required = required_secrets.required_keys_for_feature(job.recipe)
        missing = [k for k, v in get_key_status(self.secrets, required).items() if v != "present"]
        if missing:
            QMessageBox.warning(
                self,
                "Missing API Keys",
                "Missing keys: " + ", ".join(missing) + "\nImport api.txt to continue.",
            )
            return
        self.job_controller.start_job(self.current_project_id, job_id)

    def _pause_job(self) -> None:
        job_id = self._selected_job_id()
        if job_id:
            self.job_controller.pause_job(self.current_project_id, job_id)

    def _resume_job(self) -> None:
        job_id = self._selected_job_id()
        if job_id:
            self.job_controller.resume_job(self.current_project_id, job_id)

    def _cancel_job(self) -> None:
        job_id = self._selected_job_id()
        if job_id:
            self.job_controller.cancel_job(self.current_project_id, job_id)

    def _request_job_preview(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            return
        job = self.job_controller.get_job(self.current_project_id, job_id)
        if job.status == "running":
            self.job_controller.request_preview(self.current_project_id, job_id)
            QMessageBox.information(self, "Preview", "Preview will be prepared at next safe point.")
        else:
            self._run_preview()

    def _view_job_logs(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            return
        job = self.job_controller.get_job(self.current_project_id, job_id)
        self.jobs_log.setPlainText("\n".join(job.log_tail))

    def _open_job_artifacts(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            return
        job = self.job_controller.get_job(self.current_project_id, job_id)
        path = job.artifacts.last_diff_path or job.artifacts.last_verify_report or job.artifacts.last_plan_report or job.artifacts.last_apply_report
        if path:
            self._open_path(path)

    def _confirm_job_apply(self) -> None:
        job_id = self._selected_job_id()
        if job_id:
            self.job_controller.confirm_apply(self.current_project_id, job_id)

    def _skip_job_apply(self) -> None:
        job_id = self._selected_job_id()
        if job_id:
            self.job_controller.skip_pending(self.current_project_id, job_id)

    def _stop_job_now(self) -> None:
        job_id = self._selected_job_id()
        if job_id:
            self.job_controller.stop_job(self.current_project_id, job_id)

    def _open_job_diff(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            return
        job = self.job_controller.get_job(self.current_project_id, job_id)
        if job.pending_diff_path:
            self._open_path(job.pending_diff_path)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            if self.voice_loop is not None:
                self.voice_loop.stop()
            if self._ipc_events_client is not None:
                self._ipc_events_client.stop()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        try:
            self._preview_timer.stop()
            self._jobs_timer.stop()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        super().closeEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            return
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p:
                paths.append(p)
        if paths:
            self._ingest_paths(paths)


def _geometry3d_summary(entities: list, assumptions: list, warnings: list) -> str:
    type_names = {
        "box": "صندوق",
        "cylinder": "أسطوانة",
        "sphere": "كرة",
        "cone": "مخروط",
    }
    lines = ["ده تصور مجسم مبدئي:"]
    for e in entities:
        typ = str(e.get("type") or "").lower()
        name = type_names.get(typ, typ or "شكل")
        dims = e.get("dims") or {}
        if typ == "box":
            lines.append(f"- {name} {dims.get('x')}×{dims.get('y')}×{dims.get('z')}")
        elif typ in ("cylinder", "cone"):
            lines.append(f"- {name} قطر {dims.get('diameter')} وارتفاع {dims.get('height')}")
        elif typ == "sphere":
            lines.append(f"- {name} قطر {dims.get('diameter')}")
        else:
            lines.append(f"- {name}")
    if assumptions:
        lines.append("افتراضات: " + " | ".join(assumptions))
    if warnings:
        lines.append("تحذيرات: " + " | ".join([w.get("detail", "") for w in warnings if w.get("detail")]))
    lines.append("لو مناسب، أكّد علشان أحفظه.")
    return "\n".join(lines)


def _engineering_summary(state: dict, findings: list) -> str:
    material = (state.get("materials") or {}).get("selected_material") or "غير محدد"
    loads = state.get("loads") or []
    tolerances = state.get("tolerances") or []
    safety = (state.get("safety") or {}).get("safety_factor_target")
    lines = [
        f"خامة: {material}",
        f"أحمال: {len(loads)}",
        f"تلرانسات: {len(tolerances)}",
        f"عامل أمان: {safety if safety is not None else 'غير محدد'}",
    ]
    if findings:
        critical = len([f for f in findings if str(f.get("severity") or "").upper() == "CRITICAL"])
        lines.append(f"تحذيرات: {len(findings)} (حرجة: {critical})")
    return " | ".join(lines)


WhatsAppWindow = QuickPanelWindow


if __name__ == "__main__":
    import sys
    from core.portable.paths import detect_base_dir, ensure_workspace_dirs, default_workspace_dir

    base_dir = detect_base_dir()
    ensure_workspace_dirs(base_dir)
    os.environ["NH_BASE_DIR"] = base_dir
    os.environ["NH_WORKSPACE"] = default_workspace_dir(base_dir)
    os.chdir(base_dir)
    app = QApplication(sys.argv)
    window = QuickPanelWindow(project_root=base_dir)
    window.show()
    sys.exit(app.exec())
