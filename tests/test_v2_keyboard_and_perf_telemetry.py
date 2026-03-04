from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject

from ui.hud_qml.app_qml import build_engine as build_hud_engine
from ui.quick_panel_v2.app import build_engine as build_quick_engine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")


def _require_child(root_obj: QObject, object_name: str) -> QObject:
    child = root_obj.findChild(QObject, object_name)
    assert child is not None, f"missing objectName={object_name}"
    return child


def _read_ui_events(workspace: str) -> list[dict]:
    path = Path(workspace) / "runtime" / "logs" / "ui_events.jsonl"
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def test_v2_drawer_shortcuts_are_defined_for_hud_and_quick_panel() -> None:
    root = Path(__file__).resolve().parents[1]
    hud = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellFull.qml").read_text(encoding="utf-8")
    quick = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellCompact.qml").read_text(encoding="utf-8")

    for seq in ("Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5"):
        assert f'sequence: "{seq}"' in hud
        assert f'sequence: "{seq}"' in quick

    assert 'win._openDrawer("tools")' in hud
    assert 'win._openDrawer("voice")' in hud
    assert 'win._openDrawer("tools")' in quick
    assert 'win._openDrawer("voice")' in quick


def test_hud_v2_logs_stall_telemetry_for_slow_memory_search() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        app, engine, controller = build_hud_engine(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            ui_version="v2",
        )
        win = engine.rootObjects()[0]
        try:
            controller._ipc_enabled = True  # type: ignore[attr-defined]

            def _slow_call_core(op: str, payload: dict):
                assert op == "memory.search"
                time.sleep(0.14)
                return {"status": "ok", "hits": [{"source": "synthetic", "snippet": "stall check"}], "total": 1}

            controller._network.call_core = _slow_call_core  # type: ignore[attr-defined]

            win.setProperty("activeDrawer", "history")
            app.processEvents()

            search_input = _require_child(win, "hudV2MemorySearchInput")
            search_input.setProperty("text", "stall check")
            app.processEvents()

            search_btn = _require_child(win, "hudV2MemorySearchButton")
            assert bool(QMetaObject.invokeMethod(search_btn, "click"))
            app.processEvents()

            events = _read_ui_events(workspace)
            assert any(e.get("event_key") == "ui.command.execute" and str(e.get("source", "")).startswith("memory_search") for e in events)
            assert any(e.get("event_key") == "ui.performance.stall_ms" and str(e.get("source", "")).startswith("memory_search") for e in events)
        finally:
            for obj in engine.rootObjects():
                obj.setProperty("visible", False)
                obj.deleteLater()
            app.processEvents()


def test_quick_panel_v2_logs_stall_telemetry_for_slow_memory_search() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        app, engine, controller = build_quick_engine(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
        )
        win = engine.rootObjects()[0]
        try:
            controller._ipc_enabled = True  # type: ignore[attr-defined]

            def _slow_call_core(op: str, payload: dict):
                assert op == "memory.search"
                time.sleep(0.14)
                return {"status": "ok", "hits": [{"source": "synthetic", "snippet": "stall check"}], "total": 1}

            controller._network.call_core = _slow_call_core  # type: ignore[attr-defined]

            win.setProperty("activeDrawer", "history")
            app.processEvents()

            search_input = _require_child(win, "quickPanelV2MemorySearchInput")
            search_input.setProperty("text", "stall check")
            app.processEvents()

            search_btn = _require_child(win, "quickPanelV2MemorySearchButton")
            assert bool(QMetaObject.invokeMethod(search_btn, "click"))
            app.processEvents()

            events = _read_ui_events(workspace)
            assert any(e.get("event_key") == "ui.command.execute" and str(e.get("source", "")).startswith("memory_search") for e in events)
            assert any(e.get("event_key") == "ui.performance.stall_ms" and str(e.get("source", "")).startswith("memory_search") for e in events)
        finally:
            for obj in engine.rootObjects():
                obj.setProperty("visible", False)
                obj.deleteLater()
            app.processEvents()
