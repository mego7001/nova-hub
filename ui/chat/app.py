from __future__ import annotations
import os
import json
from typing import Any, Dict, Optional, List

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QInputDialog,
    QTextEdit,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QWizard,
    QWizardPage,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QScrollArea,
)

from core.plugin_engine.registry import PluginRegistry
from core.plugin_engine.loader import PluginLoader
from core.permission_guard.tool_policy import ToolPolicy
from core.permission_guard.approval_flow import ApprovalFlow
from core.task_engine.runner import Runner

from ui.chat.widgets import StatusChip, ArtifactList
from core.security.secrets import SecretsManager
from ui.dashboard.widgets import ParamForm
from core.projects.manager import ProjectManager
from core.projects.models import ProjectState
from core.run.smart_runner import detect_run_profiles
from core.fs.safe_workspace_writer import SafeWorkspaceWriter
from core.ingest.ingest_manager import IngestManager
from core.ingest.summary_contract import normalize_ingest_result, rejected_preview_lines
from core.ux.mode_routing import route_message_for_mode
from core.ux.task_modes import allowed_user_task_modes, auto_fallback_mode, is_auto_mode, normalize_task_mode
from core.ux.tools_catalog import build_tools_catalog, filter_codex_tool_rows
from core.voice.audio_io import SoundDeviceAudioInput
from core.voice.providers import FasterWhisperSttProvider, PiperTtsProvider
from core.voice.schemas import VoiceConfig
from core.voice.voice_loop import VoiceLoop


class ChatWindow(QMainWindow):
    def __init__(self, project_root: str):
        super().__init__()
        self.project_root = project_root
        self.setWindowTitle("Nova Hub Chat Console")
        self.resize(1200, 700)

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
        self.tool_policy = tool_policy
        approvals = ApprovalFlow(
            tool_policy,
            os.path.join(self.project_root, "configs", "approvals.yaml"),
        )
        self.runner = Runner(approval_flow=approvals, approval_callback=self._approval_callback)

        self.session_id = "default"
        self.project_path = ""
        self.last_state: Dict[str, Any] = {}
        self.workspace_root = os.environ.get("NH_WORKSPACE", os.path.join(self.project_root, "workspace"))
        self.project_manager = ProjectManager(self.workspace_root)
        self.secrets = SecretsManager(workspace_root=self.workspace_root)
        self.safe_writer = SafeWorkspaceWriter(self.workspace_root)
        self.ingest = IngestManager(self.workspace_root, runner=self.runner, registry=self.registry)
        self.current_project_id = ""
        self.general_chat_id = "chat_desktop_general"
        self.preview_run_id = ""
        self.preview_log_path = ""
        self._last_saved_project_state: Optional[ProjectState] = None
        self.current_task_mode = normalize_task_mode("general")
        self.task_modes = allowed_user_task_modes(self.registry, include_unavailable=False)
        self.tools_catalog: Dict[str, Any] = {}
        self.tools_menu = QMenu(self)
        self.voice_config = VoiceConfig.from_env()
        self.voice_loop: Optional[VoiceLoop] = None
        self.voice_enabled = False
        self.voice_muted = False
        self.voice_last_error = ""
        self._approval_session_allowed = False

        self.conversation_tool = self.registry.tools.get("conversation.chat")
        self._wire_conversation_context()

        self.tools = sorted(self.registry.list_tools(), key=lambda t: t.tool_id)

        # Left: transcript
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)

        # Right: project panel
        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("Select project folder...")
        self.project_input.setReadOnly(True)
        self.browse_button = QPushButton("Add Project")
        self.select_button = QPushButton("Select Project")
        self.attach_button = QPushButton("Attach Files")

        self.status_label = QLabel(f"Profile: {profile}")
        self.status_label.setWordWrap(True)

        self.scan_chip = StatusChip("Scanned")
        self.search_chip = StatusChip("Searched")
        self.plan_chip = StatusChip("Planned")
        self.diff_chip = StatusChip("Diff Ready")
        self.verify_chip = StatusChip("Verified")

        chips_row = QHBoxLayout()
        for chip in [self.scan_chip, self.search_chip, self.plan_chip, self.diff_chip, self.verify_chip]:
            chips_row.addWidget(chip)
        chips_row.addStretch(1)

        self.artifacts_label = QLabel("Artifacts")
        self.artifacts_label.setWordWrap(True)
        self.artifacts_reports = ArtifactList("Reports (last 5)")
        self.artifacts_patches = ArtifactList("Patches (last 3)")
        self.artifacts_snapshots = ArtifactList("Snapshots (last 3)")
        self.artifacts_releases = ArtifactList("Releases (last 3)")

        self.docs_label = QLabel("Docs")
        self.docs_summary = QLabel("Docs: 0")
        self.open_docs = QPushButton("Open docs")
        self.open_extracted = QPushButton("Open extracted")

        self.suggestions_group = QGroupBox("Suggestions")
        self.suggestions_group.setCheckable(True)
        self.suggestions_group.setChecked(True)
        sug_layout = QVBoxLayout(self.suggestions_group)
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
        confirm_layout.setContentsMargins(0, 0, 0, 0)
        self.confirm_label = QLabel("Diff ready.")
        self.confirm_apply_btn = QPushButton("Confirm Apply")
        self.confirm_cancel_btn = QPushButton("Cancel")
        confirm_layout.addWidget(self.confirm_label)
        confirm_layout.addStretch(1)
        confirm_layout.addWidget(self.confirm_apply_btn)
        confirm_layout.addWidget(self.confirm_cancel_btn)
        self.confirm_bar.setVisible(False)
        sug_layout.addWidget(self.confirm_bar)

        self.open_reports = QPushButton("Open reports")
        self.open_patches = QPushButton("Open patches")
        self.open_outputs = QPushButton("Open outputs")
        self.open_vscode = QPushButton("Open in VS Code")

        self.quick_label = QLabel("Quick Links")
        self.open_chatgpt = QPushButton("Open ChatGPT")
        self.open_gemini = QPushButton("Open Gemini")
        self.open_github = QPushButton("Open GitHub")

        self.scan_button = QPushButton("Analyze")
        self.search_button = QPushButton("Suggestions")
        self.apply_button = QPushButton("Apply by number")
        self.verify_button = QPushButton("Verify")
        self.pipeline_button = QPushButton("Pipeline")
        self.run_preview_button = QPushButton("Run Preview")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        self.preview_output.setPlaceholderText("Preview output will appear here...")
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1000)
        self._preview_timer.timeout.connect(self._refresh_preview_output)

        for btn in [self.scan_button, self.search_button, self.apply_button, self.verify_button, self.pipeline_button, self.run_preview_button, self.stop_button]:
            btn.setMinimumHeight(32)

        # Advanced panel (hidden by default)
        self.advanced_toggle = QCheckBox("Advanced Mode")
        self.advanced_panel = QWidget()
        self.advanced_panel.setVisible(False)
        adv_layout = QVBoxLayout(self.advanced_panel)
        adv_layout.addWidget(QLabel("Tools (Advanced)"))
        self.adv_tool_list = QListWidget()
        for t in self.tools:
            item = QListWidgetItem(f"{t.tool_id} [{t.tool_group}]")
            item.setData(Qt.UserRole, t.tool_id)
            self.adv_tool_list.addItem(item)
        self.adv_form = ParamForm()
        self.adv_run = QPushButton("Run Tool")
        self.adv_output = QTextEdit()
        self.adv_output.setReadOnly(True)
        adv_layout.addWidget(self.adv_tool_list)
        adv_layout.addWidget(self.adv_form)
        adv_layout.addWidget(self.adv_run)
        adv_layout.addWidget(QLabel("Output"))
        adv_layout.addWidget(self.adv_output)

        # Bottom input
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message to NOVA...")
        self.send_button = QPushButton("Send")
        self.task_mode_combo = QComboBox()
        self.task_mode_combo.setMinimumWidth(160)
        self.tools_button = QPushButton("Tools")
        self.voice_toggle_button = QPushButton("Voice Off")
        self.voice_toggle_button.setCheckable(True)
        self.voice_mute_button = QPushButton("Mute")
        self.voice_mute_button.setEnabled(False)
        self.voice_stop_button = QPushButton("Stop Voice")
        self.voice_stop_button.setEnabled(False)
        self.voice_replay_button = QPushButton("Replay")
        self.voice_replay_button.setEnabled(False)

        self.show_json = QCheckBox("View JSON")
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setVisible(False)
        self.show_json.setVisible(False)

        # Layouts
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Conversation"))
        left_layout.addWidget(self.transcript)
        left_layout.addWidget(self.show_json)
        left_layout.addWidget(self.json_view)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Project"))
        row = QHBoxLayout()
        row.addWidget(self.project_input)
        row.addWidget(self.browse_button)
        row.addWidget(self.select_button)
        row.addWidget(self.attach_button)
        right_layout.addLayout(row)
        right_layout.addWidget(self.status_label)
        right_layout.addLayout(chips_row)
        right_layout.addWidget(self.artifacts_label)
        right_layout.addWidget(self.artifacts_reports)
        right_layout.addWidget(self.artifacts_patches)
        right_layout.addWidget(self.artifacts_snapshots)
        right_layout.addWidget(self.artifacts_releases)
        right_layout.addWidget(self.docs_label)
        right_layout.addWidget(self.docs_summary)
        right_layout.addWidget(self.open_docs)
        right_layout.addWidget(self.open_extracted)
        right_layout.addWidget(self.suggestions_group)
        right_layout.addWidget(self.open_reports)
        right_layout.addWidget(self.open_patches)
        right_layout.addWidget(self.open_outputs)
        right_layout.addWidget(self.open_vscode)
        right_layout.addWidget(self.quick_label)
        right_layout.addWidget(self.open_chatgpt)
        right_layout.addWidget(self.open_gemini)
        right_layout.addWidget(self.open_github)
        right_layout.addWidget(self.advanced_toggle)
        right_layout.addWidget(self.advanced_panel)
        right_layout.addSpacing(8)
        right_layout.addWidget(self.scan_button)
        right_layout.addWidget(self.search_button)
        right_layout.addWidget(self.apply_button)
        right_layout.addWidget(self.verify_button)
        right_layout.addWidget(self.pipeline_button)
        right_layout.addWidget(self.run_preview_button)
        right_layout.addWidget(self.stop_button)
        right_layout.addWidget(QLabel("Preview Output"))
        right_layout.addWidget(self.preview_output)
        right_layout.addStretch(1)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(splitter)

        bottom = QHBoxLayout()
        bottom.addWidget(self.task_mode_combo)
        bottom.addWidget(self.tools_button)
        bottom.addWidget(self.input)
        bottom.addWidget(self.voice_toggle_button)
        bottom.addWidget(self.voice_mute_button)
        bottom.addWidget(self.voice_stop_button)
        bottom.addWidget(self.voice_replay_button)
        bottom.addWidget(self.send_button)
        layout.addLayout(bottom)

        self.setCentralWidget(container)
        self.setAcceptDrops(True)

        # Signals
        self.browse_button.clicked.connect(self._add_project)
        self.select_button.clicked.connect(self._select_project)
        self.attach_button.clicked.connect(self._attach_files)
        self.send_button.clicked.connect(self._send_message)
        self.input.returnPressed.connect(self._send_message)
        self.task_mode_combo.currentIndexChanged.connect(self._on_task_mode_changed)
        self.tools_button.clicked.connect(self._show_tools_menu)
        self.voice_toggle_button.toggled.connect(self._toggle_voice_enabled)
        self.voice_mute_button.clicked.connect(self._toggle_voice_mute)
        self.voice_stop_button.clicked.connect(self._voice_stop)
        self.voice_replay_button.clicked.connect(self._voice_replay)
        self.show_json.toggled.connect(self.json_view.setVisible)

        self.scan_button.clicked.connect(self._analyze)
        self.search_button.clicked.connect(lambda: self._send_command("search"))
        self.apply_button.clicked.connect(self._apply_diff)
        self.verify_button.clicked.connect(lambda: self._send_command("verify"))
        self.pipeline_button.clicked.connect(lambda: self._send_command("pipeline"))
        self.run_preview_button.clicked.connect(self._run_preview)
        self.stop_button.clicked.connect(self._stop_preview)

        self.open_reports.clicked.connect(lambda: self._open_folder("reports"))
        self.open_patches.clicked.connect(lambda: self._open_folder("patches"))
        self.open_outputs.clicked.connect(lambda: self._open_folder("outputs"))
        self.open_vscode.clicked.connect(self._open_in_vscode)
        self.open_docs.clicked.connect(lambda: self._open_folder("docs"))
        self.open_extracted.clicked.connect(lambda: self._open_folder("extracted"))
        self.refresh_suggestions_btn.clicked.connect(self._refresh_suggestions_panel)
        self.confirm_apply_btn.clicked.connect(self._confirm_apply)
        self.confirm_cancel_btn.clicked.connect(self._cancel_apply)
        self.open_chatgpt.clicked.connect(lambda: self._open_url("https://chatgpt.com"))
        self.open_gemini.clicked.connect(lambda: self._open_url("https://gemini.google.com"))
        self.open_github.clicked.connect(lambda: self._open_url("https://github.com"))
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        self.adv_tool_list.currentItemChanged.connect(self._on_adv_tool_selected)
        self.adv_run.clicked.connect(self._run_adv_tool)

        self._update_state({})
        self._maybe_run_first_run()
        if self.tools:
            self.adv_tool_list.setCurrentRow(0)
        self._refresh_task_modes_ui()
        self._refresh_tools_menu()

    def _wire_conversation_context(self) -> None:
        try:
            import importlib
            mod = importlib.import_module("integrations.conversation.plugin")
            if hasattr(mod, "set_ui_context"):
                mod.set_ui_context(self.runner, self.registry, self.project_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

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
        if clicked == approve_session:
            self._approval_session_allowed = True
            return True
        if clicked == approve_once:
            return True
        return False

    def _refresh_task_modes_ui(self) -> None:
        self.task_modes = allowed_user_task_modes(self.registry, include_unavailable=False)
        if not self.task_modes:
            self.task_modes = [{"id": "general", "title": "General", "description": "Default mode", "available": True, "reason": ""}]
        self.task_mode_combo.blockSignals(True)
        self.task_mode_combo.clear()
        current_index = 0
        for idx, row in enumerate(self.task_modes):
            mode_id = str(row.get("id") or "general")
            title = str(row.get("title") or mode_id)
            self.task_mode_combo.addItem(title, mode_id)
            if mode_id == self.current_task_mode:
                current_index = idx
        self.task_mode_combo.setCurrentIndex(current_index)
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
        curated = filter_codex_tool_rows(self.tools_catalog.get("curated") or [])
        for item in curated:
            if not isinstance(item, dict):
                continue
            action = curated_menu.addAction(f"{item.get('id')} [{item.get('badge')}]")
            action.setData(str(item.get("id") or ""))
            action.setEnabled(bool(item.get("enabled")))
            action.setToolTip(str(item.get("description") or ""))
            action.triggered.connect(lambda _checked=False, tid=str(item.get("id") or ""): self._on_tools_action(tid))

        advanced_root = self.tools_menu.addMenu("Advanced")
        groups = self.tools_catalog.get("groups") or []
        for group in groups:
            if not isinstance(group, dict):
                continue
            gname = str(group.get("group") or "Other")
            gmenu = advanced_root.addMenu(gname)
            for item in filter_codex_tool_rows(group.get("items") or []):
                if not isinstance(item, dict):
                    continue
                action = gmenu.addAction(f"{item.get('id')} [{item.get('badge')}]")
                action.setData(str(item.get("id") or ""))
                action.setEnabled(bool(item.get("enabled")))
                action.setToolTip(str(item.get("description") or ""))
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

    def _toggle_voice_enabled(self, enabled: bool) -> None:
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
                self.voice_toggle_button.setText("Voice On")
                self.voice_mute_button.setEnabled(True)
                self.voice_stop_button.setEnabled(True)
                self.voice_replay_button.setEnabled(True)
                self._append("System", "Voice loop enabled (local faster-whisper + piper).")
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                self.voice_enabled = False
                self.voice_last_error = str(exc)
                self.voice_toggle_button.blockSignals(True)
                self.voice_toggle_button.setChecked(False)
                self.voice_toggle_button.blockSignals(False)
                self.voice_toggle_button.setText("Voice Off")
                self.voice_mute_button.setEnabled(False)
                self.voice_stop_button.setEnabled(False)
                self.voice_replay_button.setEnabled(False)
                QMessageBox.warning(self, "Voice Error", f"Could not enable local voice loop:\n{exc}")
            return

        if self.voice_loop is not None:
            try:
                self.voice_loop.stop()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass
        self.voice_enabled = False
        self.voice_toggle_button.setText("Voice Off")
        self.voice_mute_button.setEnabled(False)
        self.voice_stop_button.setEnabled(False)
        self.voice_replay_button.setEnabled(False)
        self._append("System", "Voice loop disabled.")

    def _toggle_voice_mute(self) -> None:
        if self.voice_loop is None:
            return
        self.voice_muted = not self.voice_muted
        self.voice_loop.set_muted(self.voice_muted)
        self.voice_mute_button.setText("Unmute" if self.voice_muted else "Mute")

    def _voice_stop(self) -> None:
        if self.voice_loop is None:
            return
        self.voice_loop.stop_speaking()

    def _voice_replay(self) -> None:
        if self.voice_loop is None:
            return
        self.voice_loop.replay_last()

    def _on_voice_transcript(self, text: str) -> None:
        payload = str(text or "").strip()
        if not payload:
            return
        self._send_message(text=payload)

    def _on_voice_error(self, message: str) -> None:
        msg = str(message or "").strip()
        if not msg:
            return
        self.voice_last_error = msg
        self._append("System", f"Voice error: {msg}")

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

    def _select_project(self) -> None:
        projects = self.project_manager.list_projects()
        if not projects:
            QMessageBox.information(self, "No Projects", "No projects found. Use Add Project first.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Project")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select a project in workspace:"))

        list_widget = QListWidget()
        by_row: Dict[int, str] = {}
        for idx, p in enumerate(projects):
            status = p.get("status_summary", "idle")
            icon = "[OK]" if "verified" in status else ("[!]" if "diff_ready" in status else "[ ]")
            label = f"{icon} {p['name']} | {p.get('last_opened','')} | {status}"
            item = QListWidgetItem(label)
            list_widget.addItem(item)
            by_row[idx] = p["id"]
        layout.addWidget(list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Open).setEnabled(False)
        layout.addWidget(buttons)

        def _on_select() -> None:
            buttons.button(QDialogButtonBox.Open).setEnabled(list_widget.currentRow() >= 0)

        list_widget.currentRowChanged.connect(lambda _i: _on_select())

        def _open() -> None:
            row = list_widget.currentRow()
            if row < 0:
                return
            project_id = by_row.get(row)
            if not project_id:
                return
            self._switch_project(project_id)
            dialog.accept()

        buttons.accepted.connect(_open)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    def _switch_project(self, project_id: str) -> None:
        self._flush_current_project_state()
        info = self.project_manager.open_project(project_id)
        self.current_project_id = project_id
        self.session_id = project_id
        self.project_path = str(info.get("working") or "")
        self.project_input.setText(self.project_path)
        name = info.get("name") or project_id
        self.status_label.setText(f"Profile: {os.environ.get('NH_PROFILE', 'engineering')} | Project: {name} ({project_id})")
        transcript = info.get("transcript") or ""
        self.transcript.setPlainText(transcript)
        state = info.get("state") or {}
        state["project_path"] = self.project_path
        state["last_diff_path"] = state.get("last_diff_path") or ""
        self._update_state(state)
        self._refresh_artifacts()
        self._refresh_tools_menu()
        self.setWindowTitle(f"Nova Hub Chat Console - {name}")
        self._append("System", f"Opened project: {name}")

    def _flush_current_project_state(self) -> None:
        if not self.current_project_id:
            return
        existing = None
        try:
            existing = self.project_manager.load_state(self.current_project_id)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            existing = None
        ps = ProjectState(
            last_diff_path=str(self.last_state.get("last_diff_path") or ""),
            suggestions=list(self.last_state.get("last_recommendations") or []),
            last_reports=list(self.last_state.get("last_reports") or []),
            jarvis=getattr(existing, "jarvis", {}) or {},
        )
        try:
            self._save_project_state(ps)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _send_command(self, cmd: str) -> None:
        self._send_message(text=cmd)

    def _analyze(self) -> None:
        self._send_command("analyze")

    def _apply_diff(self) -> None:
        if self.last_state.get("diff_ready"):
            self._send_message(text="apply")
            return
        diff_path, ok = QInputDialog.getText(self, "Apply Diff", "Diff path:")
        if ok and diff_path:
            self._send_message(text=f"apply {diff_path}")

    def _attach_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Attach Files", self.project_root)
        if files:
            self._ingest_paths(files)

    def _ingest_paths(self, paths: List[str]) -> None:
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
            errs = normalized.get("errors") if isinstance(normalized.get("errors"), list) else []
            if errs:
                summary += f" Errors: {len(errs)}"
            preview = rejected_preview_lines(normalized, max_items=3)
            if preview:
                summary += " Rejected -> " + " | ".join(preview)
            self._append("Nova", summary)
            if self.current_project_id:
                self._refresh_docs_summary()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Ingest Error", str(e))

    def _send_message(self, text: Optional[str] = None) -> None:
        if not self.conversation_tool:
            QMessageBox.warning(self, "Chat Unavailable", "conversation.chat tool not found (plugin not enabled).")
            return
        message = text if text is not None else self.input.text().strip()
        if not message:
            return
        if text is None:
            self.input.clear()
        self._append("You", message)

        routed = route_message_for_mode(
            self.current_task_mode,
            message,
            {
                "ui": "chat",
                "scope": self.current_project_id or self.general_chat_id,
            },
        )
        session_id = self.session_id if self.current_project_id else self.general_chat_id
        project_path = self.project_path if self.current_project_id else ""

        try:
            result = self.runner.execute_registered_tool(
                self.conversation_tool,
                user_message=routed,
                project_path=project_path,
                session_id=session_id,
                write_reports=True,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Chat Error", str(e))
            return

        if isinstance(result, dict):
            display_user = result.get("display_user_message")
            if display_user and display_user != message:
                self._replace_last_user_message(display_user)
            response = result.get("response") or "(no response)"
            self._append("Nova", response)
            self._speak_voice(response)
            state = result.get("state") or {}
            self._update_state(state)
            self.json_view.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            text_out = str(result)
            self._append("Nova", text_out)
            self._speak_voice(text_out)

    def _speak_voice(self, text: str) -> None:
        if not self.voice_enabled or self.voice_loop is None or self.voice_muted:
            return
        payload = str(text or "").strip()
        if not payload:
            return
        try:
            self.voice_loop.notify_assistant_text(payload)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            self.voice_last_error = str(exc)
            self._append("System", f"Voice TTS error: {exc}")

    def _toggle_advanced(self, enabled: bool) -> None:
        self.advanced_panel.setVisible(enabled)
        self.show_json.setVisible(enabled)
        if not enabled:
            self.show_json.setChecked(False)
            self.json_view.setVisible(False)

    def _on_adv_tool_selected(self, current: QListWidgetItem, _prev: QListWidgetItem) -> None:
        if not current:
            return
        tool_id = current.data(Qt.UserRole)
        tool = self._tool_by_id(tool_id)
        if not tool:
            return
        self.adv_form.set_handler(tool.handler)

    def _run_adv_tool(self) -> None:
        item = self.adv_tool_list.currentItem()
        if not item:
            return
        tool_id = item.data(Qt.UserRole)
        tool = self._tool_by_id(tool_id)
        if not tool:
            return
        try:
            kwargs = self.adv_form.collect_values()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Parameters", str(e))
            return
        target = kwargs.get("target") or kwargs.get("target_root") or tool.default_target
        try:
            result = self.runner.execute_registered_tool(tool, target=target, **kwargs)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Tool Error", str(e))
            return
        self.adv_output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))

    def _tool_by_id(self, tool_id: str):
        for t in self.tools:
            if t.tool_id == tool_id:
                return t
        return None

    def _append(self, who: str, text: str) -> None:
        self.transcript.append(f"{who}: {text}")
        if self.current_project_id:
            try:
                self._append_project_chat(who, text)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def _replace_last_user_message(self, text: str) -> None:
        content = self.transcript.toPlainText().splitlines()
        for i in range(len(content) - 1, -1, -1):
            if content[i].startswith("You:"):
                content[i] = f"You: {text}"
                break
        self.transcript.setPlainText("\n".join(content))

    def _update_state(self, state: Dict[str, Any]) -> None:
        if state.get("project_path"):
            self.project_path = state.get("project_path")
            self.project_input.setText(self.project_path)
        self.last_state = state

        if self.current_project_id:
            existing = None
            try:
                existing = self.project_manager.load_state(self.current_project_id)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                existing = None
            ps = ProjectState(
                last_diff_path=str(state.get("last_diff_path") or ""),
                suggestions=list(state.get("suggestions") or state.get("last_recommendations") or []),
                last_reports=list(state.get("last_reports") or []),
                suggestion_status=dict(state.get("suggestion_status") or {}),
                jarvis=getattr(existing, "jarvis", {}) or {},
            )
            if self._last_saved_project_state != ps:
                try:
                    self._save_project_state(ps)
                    self._last_saved_project_state = ps
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass

        self.scan_chip.set_active(bool(state.get("scanned")))
        self.search_chip.set_active(bool(state.get("searched")))
        self.plan_chip.set_active(bool(state.get("planned")))
        self.diff_chip.set_active(bool(state.get("diff_ready")))
        self.verify_chip.set_active(bool(state.get("verified")))

        self._refresh_artifacts()
        self.apply_button.setEnabled(bool(state.get("diff_ready")))
        self._refresh_suggestions_panel()
        self._update_confirm_bar(state.get("pending_apply_diff_path") or "")

    def _open_folder(self, name: str) -> None:
        candidates: List[str] = []
        if self.current_project_id:
            paths = self.project_manager.get_project_paths(self.current_project_id)
            if name == "reports":
                candidates.append(paths.reports)
            elif name == "patches":
                candidates.append(paths.patches)
            elif name == "releases":
                candidates.append(paths.releases)
            elif name == "snapshots":
                candidates.append(paths.snapshots)
            elif name == "docs":
                candidates.append(paths.docs)
            elif name == "extracted":
                candidates.append(paths.extracted)
            elif name == "outputs":
                candidates.append(os.path.join(paths.working, "outputs"))
        candidates.append(os.path.join(self.workspace_root, name))

        path = None
        for c in candidates:
            if os.path.isdir(c):
                path = c
                break
        if path is None:
            path = candidates[-1]
            os.makedirs(path, exist_ok=True)
        if not self._is_within_workspace(path):
            QMessageBox.warning(self, "Workspace Only", "This folder is outside the workspace.")
            return
        tool = self.registry.tools.get("desktop.open_folder")
        if tool:
            try:
                self.runner.execute_registered_tool(tool, path=path, target=path)
                return
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.critical(self, "Open Folder Error", str(e))
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _open_in_vscode(self) -> None:
        if not self.project_path:
            QMessageBox.warning(self, "No Project", "Select a project folder first.")
            return
        tool = self.registry.tools.get("desktop.open_vscode")
        if not tool:
            QMessageBox.warning(self, "Missing Tool", "desktop.open_vscode not available.")
            return
        try:
            self.runner.execute_registered_tool(tool, path=self.project_path, target=self.project_path)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Open VS Code Error", str(e))

    def _open_url(self, url: str) -> None:
        tool = self.registry.tools.get("desktop.open_chrome")
        if not tool:
            QMessageBox.warning(self, "Missing Tool", "desktop.open_chrome not available.")
            return
        try:
            self.runner.execute_registered_tool(tool, url=url, target=url)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Open Link Error", str(e))

    def _maybe_run_first_run(self) -> None:
        marker = os.path.join(self.workspace_root, ".first_run_done")
        if os.path.exists(marker):
            return

        wizard = QWizard(self)
        wizard.setWindowTitle("Nova Hub First Run")

        page_lang = QWizardPage()
        page_lang.setTitle("Language")
        lang_layout = QVBoxLayout(page_lang)
        lang_layout.addWidget(QLabel("Choose language:"))
        lang_combo = QComboBox()
        lang_combo.addItems(["Egyptian Arabic (Simple)", "Arabic Fusha", "English"])
        lang_layout.addWidget(lang_combo)

        page_apps = QWizardPage()
        page_apps.setTitle("Desktop Apps")
        apps_layout = QVBoxLayout(page_apps)
        apps_layout.addWidget(QLabel("VS Code path (optional)"))
        vscode_path = QLineEdit()
        chrome_path = QLineEdit()
        apps_layout.addWidget(vscode_path)
        btn_vs = QPushButton("Browse VS Code")
        apps_layout.addWidget(btn_vs)
        apps_layout.addWidget(QLabel("Chrome path (optional)"))
        apps_layout.addWidget(chrome_path)
        btn_ch = QPushButton("Browse Chrome")
        apps_layout.addWidget(btn_ch)

        def _browse_exe(target: QLineEdit) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Select Executable", self.project_root, "Executable (*.exe)")
            if path:
                target.setText(path)

        btn_vs.clicked.connect(lambda: _browse_exe(vscode_path))
        btn_ch.clicked.connect(lambda: _browse_exe(chrome_path))

        page_keys = QWizardPage()
        page_keys.setTitle("API Keys")
        keys_layout = QVBoxLayout(page_keys)
        import_box = QCheckBox("Import api.txt now")
        keys_layout.addWidget(import_box)
        api_path = QLineEdit()
        api_path.setPlaceholderText("Path to api.txt")
        keys_layout.addWidget(api_path)
        browse_api = QPushButton("Browse api.txt")
        keys_layout.addWidget(browse_api)
        store_combo = QComboBox()
        store_combo.addItems(["Memory only", "Save to workspace secrets (.env)"])
        keys_layout.addWidget(QLabel("Storage option"))
        keys_layout.addWidget(store_combo)

        def _browse_api() -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Select api.txt", self.project_root, "Text Files (*.txt)")
            if path:
                api_path.setText(path)

        browse_api.clicked.connect(_browse_api)

        page_test = QWizardPage()
        page_test.setTitle("Quick Tests")
        test_layout = QVBoxLayout(page_test)
        test_status = QLabel("Run tests to verify setup.")
        btn_test_chrome = QPushButton("Test Chrome (ChatGPT)")
        btn_test_vscode = QPushButton("Test VS Code (workspace)")
        btn_test_verify = QPushButton("Test verify.smoke")
        test_layout.addWidget(test_status)
        test_layout.addWidget(btn_test_chrome)
        test_layout.addWidget(btn_test_vscode)
        test_layout.addWidget(btn_test_verify)

        def _run_test(tool_id: str, **kwargs) -> None:
            tool = self.registry.tools.get(tool_id)
            if not tool:
                test_status.setText(f"{tool_id} not available.")
                return
            try:
                self.runner.execute_registered_tool(tool, **kwargs)
                test_status.setText(f"{tool_id} OK")
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                test_status.setText(f"{tool_id} failed: {e}")

        btn_test_chrome.clicked.connect(lambda: _run_test("desktop.open_chrome", url="https://chatgpt.com", target="https://chatgpt.com"))
        btn_test_vscode.clicked.connect(lambda: _run_test("desktop.open_vscode", path=self.workspace_root, target=self.workspace_root))
        btn_test_verify.clicked.connect(lambda: _run_test("verify.smoke", target_root=self.project_root, write_reports=True))

        wizard.addPage(page_lang)
        wizard.addPage(page_apps)
        wizard.addPage(page_keys)
        wizard.addPage(page_test)

        if wizard.exec() != QWizard.Accepted:
            return

        # Save desktop paths
        vs = vscode_path.text().replace("\"", "\\\"")
        ch = chrome_path.text().replace("\"", "\\\"")
        cfg_text = f"version: 1\nvscode_path: \"{vs}\"\nchrome_path: \"{ch}\"\n"
        self._write_via_fs_tool(os.path.join(self.project_root, "configs", "desktop.yaml"), cfg_text)

        # Handle keys
        if import_box.isChecked() and api_path.text():
            try:
                with open(api_path.text(), "r", encoding="utf-8") as f:
                    raw = f.read()
                extracted = self._extract_keys(raw)
                if extracted:
                    if store_combo.currentIndex() == 1:
                        self._persist_keys(extracted)
                    else:
                        for k, v in extracted.items():
                            self.secrets.set_temp(k, v)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                QMessageBox.warning(self, "API Import", f"Failed to import api.txt: {e}")

        # Write marker
        self._write_via_fs_tool(marker, "ok\n")

    def _extract_keys(self, text: str) -> Dict[str, str]:
        allowed = {
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_DEFAULT_CHAT_ID",
            "GEMINI_API_KEY",
            "DEEPSEEK_API_KEY",
        }
        found: Dict[str, str] = {}
        for line in text.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"").strip("'")
            if k in allowed and v:
                found[k] = v
        return found

    def _persist_keys(self, values: Dict[str, str]) -> None:
        content = self.secrets._update_env_content(values)
        path = self.secrets.env_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._write_via_fs_tool(path, content)
        for k, v in values.items():
            self.secrets.set_temp(k, v)

    def _write_via_fs_tool(self, path: str, text: str) -> None:
        tool = self.registry.tools.get("fs.write_text")
        if not tool:
            raise RuntimeError("fs.write_text not available")
        self.runner.execute_registered_tool(tool, path=path, text=text, target=path)

    def _save_project_state(self, state: ProjectState) -> None:
        paths = self.project_manager.get_project_paths(self.current_project_id)
        payload = json.dumps(state.to_dict(), indent=2, ensure_ascii=True)
        if not self.safe_writer.write_text(paths.state_path, payload):
            self._write_via_fs_tool(paths.state_path, payload)

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
            self._write_via_fs_tool(paths.chat_path, existing + block)

    def _set_current_project(self, project_id: str) -> None:
        self._switch_project(project_id)

    def _run_preview(self) -> None:
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project", "Add a project first.")
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
            self.stop_button.setEnabled(bool(self.preview_run_id))
            self._preview_timer.start()
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
            self.stop_button.setEnabled(False)
            self._preview_timer.stop()
            if isinstance(result, dict) and result.get("summary"):
                self.preview_output.append("\n" + result.get("summary"))
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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            if self.voice_loop is not None:
                self.voice_loop.stop()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        try:
            self._preview_timer.stop()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        super().closeEvent(event)

    def _refresh_artifacts(self) -> None:
        if not self.current_project_id:
            self.artifacts_reports.set_items([])
            self.artifacts_patches.set_items([])
            self.artifacts_snapshots.set_items([])
            self.artifacts_releases.set_items([])
            self.docs_summary.setText("Docs: 0")
            return
        paths = self.project_manager.get_project_paths(self.current_project_id)
        self.artifacts_reports.set_items(self._artifact_items(paths.reports, ".md", 5))
        self.artifacts_patches.set_items(self._artifact_items(paths.patches, ".diff", 3))
        self.artifacts_snapshots.set_items(self._artifact_items(paths.snapshots, ".zip", 3))
        self.artifacts_releases.set_items(self._artifact_items(paths.releases, ".zip", 3))
        self._refresh_docs_summary()

    def _artifact_items(self, folder: str, ext: str, limit: int) -> List[tuple[str, callable]]:
        if not os.path.isdir(folder):
            return []
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(ext)]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        items: List[tuple[str, callable]] = []
        for path in files[:limit]:
            label = os.path.basename(path)
            items.append((label, lambda p=path: self._open_path(p)))
        return items

    def _open_path(self, path: str) -> None:
        if not self._is_within_workspace(path):
            QMessageBox.warning(self, "Workspace Only", "This item is outside the workspace.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

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


    def _refresh_suggestions_panel(self) -> None:
        # clear existing items
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
        self._send_message(text=f"???? {number}")

    def _apply_diff_path(self, diff_path: str, number: int) -> None:
        self._append("System", f"Apply diff: {diff_path}")
        self._send_message(text=f"apply {diff_path} suggestion:{number}")

    def _update_confirm_bar(self, diff_path: str) -> None:
        if diff_path:
            self.confirm_label.setText(f"Diff ready: {diff_path}")
            self.confirm_bar.setVisible(True)
        else:
            self.confirm_bar.setVisible(False)

    def _confirm_apply(self) -> None:
        self._send_message(text="yes")

    def _cancel_apply(self) -> None:
        self._send_message(text="no")

    def _is_within_workspace(self, path: str) -> bool:
        ws = os.path.abspath(self.workspace_root)
        ap = os.path.abspath(path)
        return ap.startswith(ws + os.sep) or ap == ws

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
