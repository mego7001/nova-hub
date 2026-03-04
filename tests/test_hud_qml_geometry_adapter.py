from pathlib import Path
import tempfile

from core.geometry3d import store as geometry_store
from ui.hud_qml.geometry_adapter import GeometryAdapter


def test_geometry_adapter_loads_entities_from_store():
    with tempfile.TemporaryDirectory() as workspace:
        project_id = "geom_project"
        Path(workspace, "projects", project_id).mkdir(parents=True, exist_ok=True)

        model = {
            "entities": [
                {
                    "id": "box_1",
                    "type": "box",
                    "position": {"x": 12, "y": 7, "z": -3},
                    "dims": {"w": 30, "d": 40, "h": 50},
                }
            ]
        }
        geometry_store.save_model(
            project_id=project_id,
            model=model,
            assumptions=[],
            warnings=[],
            reasoning="",
            workspace_root=workspace,
        )

        adapter = GeometryAdapter()
        entities = adapter.load_entities(project_id, workspace_root=workspace)

        assert len(entities) == 1
        assert entities[0]["entity_id"] == "box_1"
        assert entities[0]["size_x"] > 0
        assert entities[0]["size_y"] > 0
        assert entities[0]["size_z"] > 0


def test_geometry_adapter_handles_missing_model_gracefully():
    with tempfile.TemporaryDirectory() as workspace:
        adapter = GeometryAdapter()
        entities = adapter.load_entities("missing_project", workspace_root=workspace)
        assert entities == []
