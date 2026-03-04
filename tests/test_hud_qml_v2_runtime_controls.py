from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject

from ui.hud_qml.app_qml import build_engine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")


def _require_child(root_obj: QObject, object_name: str) -> QObject:
    child = root_obj.findChild(QObject, object_name)
    assert child is not None, f"missing objectName={object_name}"
    return child


def test_hud_v2_runtime_button_matrix_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        app, engine, _controller = build_engine(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            ui_version="v2",
        )
        win = engine.rootObjects()[0]

        try:
            # Top controls
            _require_child(win, "hudV2TopMinimizeButton")
            _require_child(win, "hudV2TopCloseButton")

            # Composer matrix
            _require_child(win, "hudV2ComposerAttachButton")
            _require_child(win, "hudV2ComposerTaskModeCombo")
            _require_child(win, "hudV2ComposerToolsButton")
            _require_child(win, "hudV2ComposerMicButton")
            _require_child(win, "hudV2ComposerMuteButton")
            _require_child(win, "hudV2ComposerStopVoiceButton")
            _require_child(win, "hudV2ComposerReplayButton")
            _require_child(win, "hudV2ComposerVoicePanelButton")
            _require_child(win, "hudV2ComposerSendButton")

            # Tools drawer (default)
            _require_child(win, "hudV2ToolsToggleMenuButton")
            _require_child(win, "hudV2ToolsQueueApplyButton")
            _require_child(win, "hudV2ToolsConfirmPendingButton")
            _require_child(win, "hudV2ToolsRejectPendingButton")
            _require_child(win, "hudV2ToolsRunSecurityButton")
            _require_child(win, "hudV2ToolsRefreshTimelineButton")

            # Attach drawer
            win.setProperty("activeDrawer", "attach")
            app.processEvents()
            _require_child(win, "hudV2AttachChooseFilesButton")

            # Health drawer
            win.setProperty("activeDrawer", "health")
            app.processEvents()
            _require_child(win, "hudV2HealthRefreshButton")
            _require_child(win, "hudV2HealthDoctorButton")
            _require_child(win, "hudV2OllamaRefreshModelsButton")
            _require_child(win, "hudV2OllamaModelCombo")

            # History drawer
            win.setProperty("activeDrawer", "history")
            app.processEvents()
            _require_child(win, "hudV2HistoryRefreshButton")
            _require_child(win, "hudV2MemorySearchInput")
            _require_child(win, "hudV2MemorySearchScopeCombo")
            _require_child(win, "hudV2MemorySearchButton")
            _require_child(win, "hudV2MemorySearchResultsList")
            _require_child(win, "hudV2MemorySearchPrevButton")
            _require_child(win, "hudV2MemorySearchNextButton")

            # Voice drawer
            win.setProperty("activeDrawer", "voice")
            app.processEvents()
            _require_child(win, "hudV2VoiceDrawerMicButton")
            _require_child(win, "hudV2VoiceDrawerMuteButton")
            _require_child(win, "hudV2VoiceDrawerStopButton")
            _require_child(win, "hudV2VoiceDrawerReplayButton")
            _require_child(win, "hudV2VoiceDeviceCombo")
            _require_child(win, "hudV2VoiceRefreshDevicesButton")
            _require_child(win, "hudV2VoiceDrawerReadinessButton")
        finally:
            for obj in engine.rootObjects():
                obj.setProperty("visible", False)
                obj.deleteLater()
            app.processEvents()


def test_hud_v2_top_controls_minimize_and_close_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        app, engine, _controller = build_engine(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            ui_version="v2",
        )
        win = engine.rootObjects()[0]

        try:
            minimize_btn = _require_child(win, "hudV2TopMinimizeButton")
            close_btn = _require_child(win, "hudV2TopCloseButton")

            assert bool(QMetaObject.invokeMethod(minimize_btn, "click"))
            app.processEvents()
            assert "Minimized" in str(win.property("visibility"))

            assert bool(QMetaObject.invokeMethod(close_btn, "click"))
            app.processEvents()
            assert bool(win.property("visible")) is False
        finally:
            for obj in engine.rootObjects():
                obj.setProperty("visible", False)
                obj.deleteLater()
            app.processEvents()


class _FakeVoiceConfig:
    def __init__(self) -> None:
        self.stt_model = "small"
        self.device = "default"
        self.push_to_talk = True


class _FailingVoiceManager:
    def __init__(self) -> None:
        self.enabled = False
        self.muted = False
        self.state = "idle"
        self.last_error = ""
        self.last_transcript = ""
        self.last_spoken_text = ""
        self.last_voice_error_kind = "missing_dependency"
        self.config = _FakeVoiceConfig()
        self.push_to_talk_active = False

    def set_config(self, **kwargs) -> None:
        self.config.device = str(kwargs.get("device") or "default")

    def start_loop(self) -> bool:
        raise ModuleNotFoundError("No module named 'ctranslate2'")

    def stop_loop(self) -> None:
        self.enabled = False

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)

    def stop_speaking(self) -> None:
        return

    def replay_last(self) -> None:
        return

    def set_push_to_talk_active(self, active: bool) -> None:
        self.push_to_talk_active = bool(active)


def test_hud_v2_voice_button_does_not_break_ui_when_voice_deps_missing() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        app, engine, controller = build_engine(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            ui_version="v2",
        )
        win = engine.rootObjects()[0]
        controller._voice_manager = _FailingVoiceManager()  # type: ignore[assignment]

        try:
            win.setProperty("activeDrawer", "voice")
            app.processEvents()
            mic_btn = _require_child(win, "hudV2VoiceDrawerMicButton")

            assert bool(QMetaObject.invokeMethod(mic_btn, "click"))
            app.processEvents()
            assert bool(win.property("visible")) is True
            assert "Voice unavailable: missing dependency" in controller.statusText
        finally:
            for obj in engine.rootObjects():
                obj.setProperty("visible", False)
                obj.deleteLater()
            app.processEvents()
