from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest

from ui.hud_qml.app_qml import build_engine as build_hud_engine
from ui.quick_panel_v2.app import build_engine as build_quick_engine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")


def _require_child(root_obj: QObject, object_name: str) -> QObject:
    child = root_obj.findChild(QObject, object_name)
    assert child is not None, f"missing objectName={object_name}"
    return child


def test_v3_keyboard_shortcuts_runtime_hud() -> None:
    root = Path(__file__).resolve().parents[1]
    app, engine, _controller = build_hud_engine(
        project_root=str(root),
        backend_enabled=False,
        ui_version="v2",
    )
    win = engine.rootObjects()[0]
    try:
        palette = _require_child(win, "hudV3CommandPalette")
        assert not bool(palette.property("visible"))

        QTest.keyClick(win, Qt.Key_K, Qt.ControlModifier)
        app.processEvents()
        assert bool(palette.property("visible"))

        QTest.keyClick(win, Qt.Key_Escape)
        app.processEvents()
        assert not bool(palette.property("visible"))

        QTest.keyClick(win, Qt.Key_5, Qt.AltModifier)
        app.processEvents()
        assert win.property("activeDrawer") == "voice"
    finally:
        for obj in engine.rootObjects():
            obj.setProperty("visible", False)
            obj.deleteLater()
        app.processEvents()


def test_v3_keyboard_shortcuts_runtime_quick_panel() -> None:
    root = Path(__file__).resolve().parents[1]
    app, engine, _controller = build_quick_engine(
        project_root=str(root),
        backend_enabled=False,
    )
    win = engine.rootObjects()[0]
    try:
        palette = _require_child(win, "quickPanelV3CommandPalette")
        assert not bool(palette.property("visible"))

        QTest.keyClick(win, Qt.Key_K, Qt.ControlModifier)
        app.processEvents()
        assert bool(palette.property("visible"))

        QTest.keyClick(win, Qt.Key_Escape)
        app.processEvents()
        assert not bool(palette.property("visible"))

        QTest.keyClick(win, Qt.Key_3, Qt.AltModifier)
        app.processEvents()
        assert win.property("activeDrawer") == "health"
    finally:
        for obj in engine.rootObjects():
            obj.setProperty("visible", False)
            obj.deleteLater()
        app.processEvents()
