from __future__ import annotations
import inspect
from typing import Any, Dict, List, Optional, get_args, get_origin

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ParamForm(QWidget):
    def __init__(self):
        super().__init__()
        self._layout = QFormLayout(self)
        self._layout.setLabelAlignment(Qt.AlignLeft)
        self._layout.setFormAlignment(Qt.AlignTop)
        self._widgets: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._annotations: Dict[str, Any] = {}
        self._changed: Dict[str, bool] = {}

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._widgets.clear()
        self._defaults.clear()
        self._annotations.clear()
        self._changed.clear()

    def set_handler(self, handler) -> None:
        self.clear()
        sig = inspect.signature(handler)
        for name, param in sig.parameters.items():
            if name == "self" or param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            ann = param.annotation
            default = param.default
            self._annotations[name] = ann
            self._defaults[name] = default
            self._changed[name] = False

            required = default is inspect._empty or (ann is str and default == "")
            label = name
            if not required and default is not inspect._empty:
                label = f"{name} (default {default})"

            if ann is bool:
                widget = QCheckBox()
                if default is not inspect._empty:
                    widget.setChecked(bool(default))
                widget.stateChanged.connect(lambda _v, n=name: self._mark_changed(n))
                self._layout.addRow(label, widget)
            elif ann is int:
                widget = QSpinBox()
                widget.setRange(-2147483648, 2147483647)
                if default is not inspect._empty:
                    try:
                        widget.setValue(int(default))
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                        widget.setValue(0)
                widget.valueChanged.connect(lambda _v, n=name: self._mark_changed(n))
                self._layout.addRow(label, widget)
            elif ann is float:
                widget = QDoubleSpinBox()
                widget.setRange(-1e12, 1e12)
                widget.setDecimals(6)
                if default is not inspect._empty:
                    try:
                        widget.setValue(float(default))
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                        widget.setValue(0.0)
                widget.valueChanged.connect(lambda _v, n=name: self._mark_changed(n))
                self._layout.addRow(label, widget)
            else:
                widget = QLineEdit()
                if default is not inspect._empty:
                    widget.setPlaceholderText(str(default))
                widget.textChanged.connect(lambda _v, n=name: self._mark_changed(n))
                self._layout.addRow(label, widget)
            self._widgets[name] = widget

    def collect_values(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for name, widget in self._widgets.items():
            ann = self._annotations.get(name)
            default = self._defaults.get(name, inspect._empty)
            required = default is inspect._empty or (ann is str and default == "")

            if isinstance(widget, QCheckBox):
                if required or self._changed.get(name):
                    values[name] = widget.isChecked()
                continue

            if isinstance(widget, QSpinBox):
                if required or self._changed.get(name):
                    values[name] = int(widget.value())
                continue

            if isinstance(widget, QDoubleSpinBox):
                if required or self._changed.get(name):
                    values[name] = float(widget.value())
                continue

            raw = widget.text().strip()
            if not raw:
                if required:
                    raise ValueError(f"{name} is required")
                continue

            values[name] = self._parse_value(raw, ann)
        return values

    def _parse_value(self, raw: str, ann):
        if ann is inspect._empty:
            return raw

        origin = get_origin(ann)
        args = get_args(ann)

        if origin is list or ann is list:
            return [x.strip() for x in raw.split(",") if x.strip()]

        if origin is not None and args:
            if any(get_origin(a) is list or a is list for a in args):
                return [x.strip() for x in raw.split(",") if x.strip()]

        if ann is int:
            return int(raw)
        if ann is float:
            return float(raw)
        if ann is bool:
            return raw.strip().lower() in ("y", "yes", "true", "1")
        return raw

    def _mark_changed(self, name: str) -> None:
        self._changed[name] = True


class ChatPanel(QWidget):
    send_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.project_path: str = ""
        self.profile: str = ""

        self.status_label = QLabel("Project: (none) | Profile: (unknown)")
        self.status_label.setWordWrap(True)

        self.history = QTextEdit()
        self.history.setReadOnly(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type your message to Nova...")

        self.send_button = QPushButton("Send")
        self.select_project_button = QPushButton("Select Project")
        self.load_zip_button = QPushButton("Load Zip")

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.select_project_button)
        buttons_row.addWidget(self.load_zip_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(self.send_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.history)
        layout.addWidget(self.input)
        layout.addLayout(buttons_row)

        self.send_button.clicked.connect(self._emit_send)
        self.input.returnPressed.connect(self._emit_send)

    def set_status(self, project_path: str, profile: str) -> None:
        self.project_path = project_path or ""
        self.profile = profile or ""
        pp = self.project_path if self.project_path else "(none)"
        pr = self.profile if self.profile else "(unknown)"
        self.status_label.setText(f"Project: {pp} | Profile: {pr}")

    def append_message(self, role: str, text: str) -> None:
        prefix = "You" if role == "user" else "Nova"
        self.history.append(f"{prefix}: {text}")

    def _emit_send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.send_requested.emit(text)
