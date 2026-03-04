from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject

from ui.hud_qml.controller import HUDController


class QuickPanelV2Controller(HUDController):
    """Quick Panel V2 backend built on top of the shared HUD controller."""

    def __init__(
        self,
        project_root: str,
        workspace_root: str,
        backend_enabled: bool = True,
        background_tasks: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(
            project_root=project_root,
            workspace_root=workspace_root,
            backend_enabled=backend_enabled,
            background_tasks=background_tasks,
            parent=parent,
        )
        self._set_status("Quick Panel V2 ready.")
