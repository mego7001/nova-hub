from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject

from ui.quick_panel_v2.app import build_engine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")


def _require_child(root_obj: QObject, object_name: str) -> QObject:
    child = root_obj.findChild(QObject, object_name)
    assert child is not None, f"missing objectName={object_name}"
    return child


def test_quick_panel_v2_runtime_button_matrix_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        app, engine, _controller = build_engine(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
        )
        win = engine.rootObjects()[0]

        try:
            _require_child(win, "quickPanelV2TopMinimizeButton")
            _require_child(win, "quickPanelV2TopCloseButton")

            _require_child(win, "quickPanelV2DrawerToolsButton")
            _require_child(win, "quickPanelV2DrawerAttachButton")
            _require_child(win, "quickPanelV2DrawerHealthButton")
            _require_child(win, "quickPanelV2DrawerHistoryButton")
            _require_child(win, "quickPanelV2DrawerVoiceButton")

            _require_child(win, "quickPanelV2ToolsCatalogList")
            _require_child(win, "quickPanelV2ToolsToggleMenuButton")
            _require_child(win, "quickPanelV2ToolsQueueApplyButton")
            _require_child(win, "quickPanelV2ToolsConfirmPendingButton")
            _require_child(win, "quickPanelV2ToolsRejectPendingButton")
            _require_child(win, "quickPanelV2ToolsRunSecurityButton")
            _require_child(win, "quickPanelV2ToolsRefreshTimelineButton")

            win.setProperty("activeDrawer", "attach")
            app.processEvents()
            _require_child(win, "quickPanelV2AttachSummaryLabel")
            _require_child(win, "quickPanelV2AttachChooseFilesButton")
            _require_child(win, "quickPanelV2AttachSummaryList")

            win.setProperty("activeDrawer", "health")
            app.processEvents()
            _require_child(win, "quickPanelV2HealthRefreshButton")
            _require_child(win, "quickPanelV2HealthDoctorButton")
            _require_child(win, "quickPanelV2OllamaRefreshModelsButton")
            _require_child(win, "quickPanelV2OllamaModelCombo")
            _require_child(win, "quickPanelV2HealthStatsList")

            win.setProperty("activeDrawer", "history")
            app.processEvents()
            _require_child(win, "quickPanelV2HistoryRefreshButton")
            _require_child(win, "quickPanelV2TimelineList")
            _require_child(win, "quickPanelV2MemorySearchInput")
            _require_child(win, "quickPanelV2MemorySearchScopeCombo")
            _require_child(win, "quickPanelV2MemorySearchButton")
            _require_child(win, "quickPanelV2MemorySearchResultsList")
            _require_child(win, "quickPanelV2MemorySearchPrevButton")
            _require_child(win, "quickPanelV2MemorySearchNextButton")

            win.setProperty("activeDrawer", "voice")
            app.processEvents()
            _require_child(win, "quickPanelV2VoiceReadinessButton")
            _require_child(win, "quickPanelV2VoiceDrawerMicButton")
            _require_child(win, "quickPanelV2VoiceDrawerMuteButton")
            _require_child(win, "quickPanelV2VoiceDrawerStopButton")
            _require_child(win, "quickPanelV2VoiceDrawerReplayButton")
            _require_child(win, "quickPanelV2VoiceDeviceCombo")
            _require_child(win, "quickPanelV2VoiceRefreshDevicesButton")
        finally:
            for obj in engine.rootObjects():
                obj.setProperty("visible", False)
                obj.deleteLater()
            app.processEvents()

