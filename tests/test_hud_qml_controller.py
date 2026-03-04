from pathlib import Path
import tempfile
import unittest

from core.audit_spine import ProjectAuditSpine
from core.projects.manager import ProjectManager
from ui.hud_qml.controller import HUDController


class TestHUDController(unittest.TestCase):
    def _create_seed_project(self, workspace: str) -> tuple[ProjectManager, str]:
        seed = Path(workspace) / "seed_src"
        seed.mkdir(parents=True, exist_ok=True)
        (seed / "main.py").write_text("print('seed')\n", encoding="utf-8")
        pm = ProjectManager(workspace_root=workspace)
        project_id = pm.add_project_from_folder(str(seed))
        return pm, project_id

    def test_apply_pipeline_creates_pending_then_applies_and_audits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as workspace:
            pm, project_id = self._create_seed_project(workspace)
            working = Path(pm.get_project_paths(project_id).working)
            gitignore = working / ".gitignore"
            gitignore.write_text("__pycache__/\n", encoding="utf-8")

            controller = HUDController(
                project_root=str(root),
                workspace_root=workspace,
                backend_enabled=True,
                background_tasks=False,
            )
            controller.select_project(project_id)
            self.assertTrue(controller.applyEnabled, controller.toolsBadge)

            before = gitignore.read_text(encoding="utf-8")
            controller.queue_apply()
            self.assertTrue(controller.hasPendingApproval)
            self.assertFalse(controller.confirmationReadOnly)
            self.assertIn("I will execute: patch.apply", controller.confirmationSummary)

            controller.confirm_pending()
            after = gitignore.read_text(encoding="utf-8")

            self.assertFalse(controller.hasPendingApproval)
            self.assertNotEqual(before, after)
            self.assertIn(".env", after)
            self.assertIn("reports/", after)
            self.assertIn("patches/", after)

            events = ProjectAuditSpine(project_id, workspace_root=workspace).read_events(limit=200)
            event_types = [str(x.get("event_type") or "") for x in events]
            self.assertIn("hud.apply.candidate_created", event_types)
            self.assertIn("hud.apply.completed", event_types)

    def test_missing_tools_disables_apply_and_shows_readonly_notice(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as workspace:
            _pm, project_id = self._create_seed_project(workspace)
            controller = HUDController(
                project_root=str(root),
                workspace_root=workspace,
                backend_enabled=False,
                background_tasks=False,
            )
            controller.select_project(project_id)

            self.assertFalse(controller.applyEnabled)
            self.assertIn("MISSING(", controller.toolsBadge)

            controller.queue_apply()
            self.assertTrue(controller.hasPendingApproval)
            self.assertTrue(controller.confirmationReadOnly)
            self.assertIn("missing tools", controller.confirmationSummary.lower())


if __name__ == "__main__":
    unittest.main()
