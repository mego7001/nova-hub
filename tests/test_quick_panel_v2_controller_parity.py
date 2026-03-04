from __future__ import annotations

from pathlib import Path
import tempfile

from ui.quick_panel_v2.controller import QuickPanelV2Controller


def test_quick_panel_v2_controller_exposes_ollama_and_memory_contracts() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = QuickPanelV2Controller(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )

        assert hasattr(controller, "ollamaHealthSummary")
        assert hasattr(controller, "ollamaSessionModelOverride")
        assert hasattr(controller, "setOllamaSessionModel")
        assert hasattr(controller, "memorySearch")
        assert hasattr(controller, "memorySearchPage")
        assert hasattr(controller, "toolsCatalogModel")
        assert hasattr(controller, "attachSummaryModel")
        assert hasattr(controller, "attachLastSummary")
        assert hasattr(controller, "timelineModel")
        assert hasattr(controller, "timelineSummary")
        assert hasattr(controller, "voice_input_devices")
        assert hasattr(controller, "set_voice_device")
