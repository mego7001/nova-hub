from __future__ import annotations

from pathlib import Path


def test_candidate_models_use_bindable_property_signature() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "ui" / "hud_qml" / "controller.py").read_text(encoding="utf-8")

    assert "@Property(QObject, notify=candidateChanged)" in text
    assert "def diffFilesModel(self) -> QObject:" in text
    assert "def qaFindingsModel(self) -> QObject:" in text
    assert "def qaMetricsModel(self) -> QObject:" in text
