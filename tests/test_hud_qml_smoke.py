from pathlib import Path
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")

from ui.hud_qml.app_qml import build_engine  # noqa: E402


def test_hud_qml_loads_without_exception():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        app, engine, _controller = build_engine(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
        )
        assert engine.rootObjects()
        for obj in engine.rootObjects():
            obj.setProperty("visible", False)
            obj.deleteLater()
        app.processEvents()
