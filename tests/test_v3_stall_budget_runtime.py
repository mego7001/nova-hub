from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject

from ui.hud_qml.app_qml import build_engine as build_hud_engine


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
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _run_memory_search_once(workspace: str, delay_sec: float) -> tuple[str, list[dict]]:
    root = Path(__file__).resolve().parents[1]
    app, engine, controller = build_hud_engine(
        project_root=str(root),
        workspace_root=workspace,
        backend_enabled=False,
        ui_version="v2",
    )
    win = engine.rootObjects()[0]
    try:
        controller._ipc_enabled = True  # type: ignore[attr-defined]

        def _call_core(op: str, payload: dict):
            assert op == "memory.search"
            if delay_sec > 0:
                time.sleep(delay_sec)
            return {"status": "ok", "hits": [{"source": "synthetic", "snippet": "stall budget"}], "total": 1}

        controller._network.call_core = _call_core  # type: ignore[attr-defined]

        win.setProperty("activeDrawer", "history")
        app.processEvents()
        search_input = _require_child(win, "hudV2MemorySearchInput")
        search_btn = _require_child(win, "hudV2MemorySearchButton")
        search_input.setProperty("text", "stall-budget")
        app.processEvents()
        assert bool(QMetaObject.invokeMethod(search_btn, "click"))
        app.processEvents()

        return str(win.property("effectiveEffectsProfile")), _read_ui_events(workspace)
    finally:
        for obj in engine.rootObjects():
            obj.setProperty("visible", False)
            obj.deleteLater()
        app.processEvents()


def test_v3_fast_path_does_not_activate_degraded_mode() -> None:
    with tempfile.TemporaryDirectory() as workspace:
        profile, events = _run_memory_search_once(workspace, delay_sec=0.0)
        assert profile != "degraded"
        assert not any(e.get("event_key") == "ui.effects.degraded_activated" for e in events)


def test_v3_single_slow_path_logs_stall_without_degrade() -> None:
    with tempfile.TemporaryDirectory() as workspace:
        profile, events = _run_memory_search_once(workspace, delay_sec=0.14)
        assert profile != "degraded"
        stall_events = [e for e in events if e.get("event_key") == "ui.performance.stall_ms"]
        assert stall_events
        assert any(int(str(e.get("value", "0")) or "0") >= 100 for e in stall_events)
