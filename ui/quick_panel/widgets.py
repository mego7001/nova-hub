from __future__ import annotations
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget


class ProjectListItem(QWidget):
    def __init__(self, name: str, preview: str, timestamp: str, badge: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        header = QHBoxLayout()
        self.name_label = QLabel(name)
        self.badge_label = QLabel(badge)
        self.badge_label.setStyleSheet("color:#10b981;")
        header.addWidget(self.name_label)
        header.addStretch(1)
        header.addWidget(self.badge_label)
        layout.addLayout(header)

        self.preview_label = QLabel(preview)
        self.preview_label.setStyleSheet("color:#6b7280;")
        layout.addWidget(self.preview_label)

        self.time_label = QLabel(timestamp)
        self.time_label.setStyleSheet("color:#9ca3af;font-size:11px;")
        layout.addWidget(self.time_label)

    def update_content(self, name: str, preview: str, timestamp: str, badge: str) -> None:
        self.name_label.setText(name)
        self.preview_label.setText(preview)
        self.time_label.setText(timestamp)
        self.badge_label.setText(badge)
