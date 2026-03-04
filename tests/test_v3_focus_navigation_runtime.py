from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from ui.hud_qml.app_qml import build_engine as build_hud_engine
from ui.quick_panel_v2.app import build_engine as build_quick_engine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")


def _assert_focus_cycle(app, win) -> None:
    win.setProperty("focusRegion", "header")
    app.processEvents()

    QTest.keyClick(win, Qt.Key_F6)
    app.processEvents()
    assert win.property("focusRegion") == "nav"

    QTest.keyClick(win, Qt.Key_F6)
    app.processEvents()
    assert win.property("focusRegion") == "content"

    QTest.keyClick(win, Qt.Key_F6)
    app.processEvents()
    assert win.property("focusRegion") == "rail"

    QTest.keyClick(win, Qt.Key_F6)
    app.processEvents()
    assert win.property("focusRegion") == "header"

    QTest.keyClick(win, Qt.Key_F6, Qt.ShiftModifier)
    app.processEvents()
    assert win.property("focusRegion") == "rail"


def test_v3_focus_cycle_runtime_hud() -> None:
    root = Path(__file__).resolve().parents[1]
    app, engine, _controller = build_hud_engine(
        project_root=str(root),
        backend_enabled=False,
        ui_version="v2",
    )
    win = engine.rootObjects()[0]
    try:
        win.setProperty("activeDrawer", "history")
        app.processEvents()
        _assert_focus_cycle(app, win)
    finally:
        for obj in engine.rootObjects():
            obj.setProperty("visible", False)
            obj.deleteLater()
        app.processEvents()


def test_v3_focus_cycle_runtime_quick_panel() -> None:
    root = Path(__file__).resolve().parents[1]
    app, engine, _controller = build_quick_engine(
        project_root=str(root),
        backend_enabled=False,
    )
    win = engine.rootObjects()[0]
    try:
        win.setProperty("activeDrawer", "tools")
        app.processEvents()
        _assert_focus_cycle(app, win)
    finally:
        for obj in engine.rootObjects():
            obj.setProperty("visible", False)
            obj.deleteLater()
        app.processEvents()
