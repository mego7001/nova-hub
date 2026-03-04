from __future__ import annotations
import json
import os
import tempfile
import zipfile
from typing import Any, Dict, List, Optional
import inspect

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from PySide6.QtGui import QDesktopServices

from core.plugin_engine.registry import PluginRegistry
from core.plugin_engine.loader import PluginLoader
from core.permission_guard.tool_policy import ToolPolicy
from core.permission_guard.approval_flow import ApprovalFlow
from core.task_engine.runner import Runner

from ui.dashboard.widgets import ParamForm, ChatPanel


class DashboardWindow(QMainWindow):
    def __init__(self, project_root: str):
        super().__init__()
        self.project_root = project_root
        self.setWindowTitle("Nova Hub Dashboard")
        self.resize(1100, 700)

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

        self.tools = sorted(self.registry.list_tools(), key=lambda t: t.tool_id)

        self.tool_list = QListWidget()
        for t in self.tools:
            item = QListWidgetItem(f"{t.tool_id} [{t.tool_group}]")
            item.setData(Qt.UserRole, t.tool_id)
            self.tool_list.addItem(item)

        self.form = ParamForm()
        self.preview_label = QLabel("Select a tool to see details.")
        self.preview_label.setWordWrap(True)

        self.run_button = QPushButton("Run Tool")
        self.run_button.clicked.connect(self._run_tool)

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        self.paths_label = QLabel("")
        self.paths_label.setWordWrap(True)

        tools_left = QWidget()
        tools_left_layout = QVBoxLayout(tools_left)
        tools_left_layout.addWidget(QLabel("Tools"))
        tools_left_layout.addWidget(self.tool_list)

        tools_right = QWidget()
        tools_right_layout = QVBoxLayout(tools_right)
        tools_right_layout.addWidget(QLabel("Parameters"))
        tools_right_layout.addWidget(self.form)
        tools_right_layout.addWidget(self.preview_label)
        tools_right_layout.addWidget(self.run_button)
        tools_right_layout.addWidget(QLabel("Output"))
        tools_right_layout.addWidget(self.output)
        tools_right_layout.addWidget(QLabel("Detected Paths"))
        tools_right_layout.addWidget(self.paths_label)

        tools_splitter = QSplitter()
        tools_splitter.addWidget(tools_left)
        tools_splitter.addWidget(tools_right)
        tools_splitter.setStretchFactor(1, 2)

        tools_panel = QWidget()
        tools_panel_layout = QHBoxLayout(tools_panel)
        tools_panel_layout.addWidget(tools_splitter)

        self.chat_panel = ChatPanel()
        self.chat_project_path = ""
        self.session_id = "default"

        tabs = QTabWidget()
        tabs.addTab(tools_panel, "Tools")
        tabs.addTab(self.chat_panel, "Chat")

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(tabs)
        self.setCentralWidget(container)

        self.tool_list.currentItemChanged.connect(self._on_tool_selected)

        toolbar = self.addToolBar("Folders")
        open_reports = QAction("Open reports", self)
        open_outputs = QAction("Open outputs", self)
        open_patches = QAction("Open patches", self)
        open_reports.triggered.connect(lambda: self._open_folder("reports"))
        open_outputs.triggered.connect(lambda: self._open_folder("outputs"))
        open_patches.triggered.connect(lambda: self._open_folder("patches"))
        toolbar.addAction(open_reports)
        toolbar.addAction(open_outputs)
        toolbar.addAction(open_patches)

        if self.tools:
            self.tool_list.setCurrentRow(0)

        self.chat_panel.set_status(self.chat_project_path, profile)
        self.chat_panel.send_requested.connect(self._on_chat_send)
        self.chat_panel.select_project_button.clicked.connect(self._select_project)
        self.chat_panel.load_zip_button.clicked.connect(self._load_zip)

        self._conversation_tool = self.registry.tools.get("conversation.chat")
        self._wire_conversation_context()

    def _open_folder(self, name: str) -> None:
        path = os.path.join(self.project_root, name)
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _tool_by_id(self, tool_id: str):
        for t in self.tools:
            if t.tool_id == tool_id:
                return t
        return None

    def _on_tool_selected(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        if not current:
            return
        tool_id = current.data(Qt.UserRole)
        tool = self._tool_by_id(tool_id)
        if not tool:
            return
        self.form.set_handler(tool.handler)
        target = tool.default_target
        self.preview_label.setText(
            f"Tool: {tool.tool_id}\nGroup: {tool.tool_group}\nOp: {tool.op}\nTarget: {target}"
        )

    def _approval_callback(self, req, res) -> bool:
        tool_id = None
        if isinstance(req.meta, dict):
            tool_id = req.meta.get("tool_id")
        matched = ", ".join(res.matched_rules) if res.matched_rules else "(none)"
        msg = (
            f"Tool ID: {tool_id or '(unknown)'}\n"
            f"ToolGroup: {req.tool_group}\n"
            f"Op: {req.op}\n"
            f"Target: {req.target}\n"
            f"Command: {(req.meta or {}).get('command', '(n/a)')}\n"
            f"Reason: {res.reason}\n"
            f"Risk: {res.risk_score}\n"
            f"Matched Rules: {matched}"
        )
        return QMessageBox.question(self, "Approval Required", msg) == QMessageBox.Yes

    def _run_tool(self) -> None:
        item = self.tool_list.currentItem()
        if not item:
            return
        tool_id = item.data(Qt.UserRole)
        tool = self._tool_by_id(tool_id)
        if not tool:
            return

        try:
            kwargs = self.form.collect_values()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Parameters", str(e))
            return

        target = kwargs.get("target") or kwargs.get("target_root") or tool.default_target
        self.preview_label.setText(
            f"Tool: {tool.tool_id}\nGroup: {tool.tool_group}\nOp: {tool.op}\nTarget: {target}"
        )

        try:
            sig = inspect.signature(tool.handler)
            accepts_target = "target" in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if accepts_target:
                result = self.runner.execute_registered_tool(tool, target=target, **kwargs)
            else:
                if target is not None:
                    original_target = tool.default_target
                    tool.default_target = target
                    try:
                        result = self.runner.execute_registered_tool(tool, **kwargs)
                    finally:
                        tool.default_target = original_target
                else:
                    result = self.runner.execute_registered_tool(tool, **kwargs)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Tool Error", str(e))
            return

        self.output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        self.paths_label.setText(self._extract_paths(result))

    def _wire_conversation_context(self) -> None:
        try:
            import importlib
            mod = importlib.import_module("integrations.conversation.plugin")
            if hasattr(mod, "set_ui_context"):
                mod.set_ui_context(self.runner, self.registry, self.project_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _select_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder", self.project_root)
        if not path:
            return
        self.chat_project_path = path
        self.chat_panel.set_status(self.chat_project_path, os.environ.get("NH_PROFILE", "engineering"))
        self.chat_panel.append_message("assistant", f"Project selected: {path}")

    def _load_zip(self) -> None:
        zip_path, _ = QFileDialog.getOpenFileName(self, "Select Zip File", self.project_root, "Zip Files (*.zip)")
        if not zip_path:
            return
        dest = tempfile.mkdtemp(prefix="nova_hub_")
        try:
            self._safe_extract_zip(zip_path, dest)
            self.chat_project_path = dest
            self.chat_panel.set_status(self.chat_project_path, os.environ.get("NH_PROFILE", "engineering"))
            self.chat_panel.append_message("assistant", f"Zip extracted to: {dest}")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Zip Error", str(e))

    def _safe_extract_zip(self, zip_path: str, dest: str) -> None:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                target = os.path.abspath(os.path.join(dest, member))
                if not target.startswith(os.path.abspath(dest) + os.sep):
                    raise ValueError("Unsafe path in zip file")
            zf.extractall(dest)

    def _on_chat_send(self, message: str) -> None:
        if not self._conversation_tool:
            QMessageBox.warning(self, "Chat Unavailable", "conversation.chat tool not found (plugin not enabled).")
            return
        self.chat_panel.append_message("user", message)

        project_path = self.chat_project_path or ""
        try:
            result = self.runner.execute_registered_tool(
                self._conversation_tool,
                user_message=message,
                project_path=project_path,
                session_id=self.session_id,
                write_reports=True,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            QMessageBox.critical(self, "Chat Error", str(e))
            return

        response = ""
        if isinstance(result, dict):
            response = str(result.get("response") or "")
        if not response:
            response = "(no response)"
        self.chat_panel.append_message("assistant", response)

    def _extract_paths(self, result: Any) -> str:
        paths: List[str] = []
        if isinstance(result, dict):
            for key in ("report_paths", "diff_path", "out_dxf", "path", "out_file"):
                val = result.get(key)
                if isinstance(val, list):
                    paths.extend([str(v) for v in val])
                elif isinstance(val, str):
                    paths.append(val)
            for key in ("files", "results"):
                items = result.get(key)
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict):
                            p = it.get("path") or it.get("backup_path")
                            if p:
                                paths.append(str(p))
        if not paths:
            return "(none)"
        return "\n".join(sorted(set(paths)))
