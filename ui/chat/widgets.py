from __future__ import annotations
from PySide6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget


class StatusChip(QLabel):
    def __init__(self, label: str):
        super().__init__(label)
        self.base_label = label
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        if active:
            self.setText(self.base_label + " ✓")
            self.setStyleSheet("background:#2d6a4f;color:#ffffff;padding:4px 8px;border-radius:10px;")
        else:
            self.setText(self.base_label)
            self.setStyleSheet("background:#dddddd;color:#333333;padding:4px 8px;border-radius:10px;")


class ArtifactList(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(QLabel(title))

    def set_items(self, items: list[tuple[str, callable]]) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()
        for label, handler in items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QLabel(label))
            btn = QPushButton("Open")
            btn.clicked.connect(handler)
            row_layout.addWidget(btn)
            self._layout.addWidget(row)
