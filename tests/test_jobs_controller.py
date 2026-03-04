import tempfile
import unittest

from core.jobs.controller import JobController
from core.jobs.models import Job
from core.plugin_engine.registry import PluginRegistry


class TestJobController(unittest.TestCase):
    def test_skip_pending_updates_suggestion_before_clear(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            controller = JobController(
                runner=None,
                registry=PluginRegistry(),
                approval_flow=None,
                workspace_root=workspace,
            )

            job = Job(
                job_id="job1",
                project_id="proj1",
                title="test",
                created_at="now",
                updated_at="now",
                status="waiting_for_user",
                steps_total=1,
                steps_done=0,
                current_step_label="",
                last_safe_point_label="",
                last_safe_point_at="",
                pause_requested=False,
                preview_requested=False,
                last_error=None,
                waiting_reason="confirm_apply",
                pending_diff_path="patches/plan_001.diff",
                pending_suggestion_n=2,
                recipe="auto_improve",
            )
            controller.storage.save_job(job)

            updates = []
            starts = []

            def _record_update(project_id: str, number: int, status: str, diff_path: str = "") -> None:
                updates.append((project_id, number, status, diff_path))

            controller._update_project_suggestion = _record_update  # type: ignore[method-assign]
            controller.start_job = lambda project_id, job_id: starts.append((project_id, job_id))  # type: ignore[method-assign]

            controller.skip_pending("proj1", "job1")

            saved = controller.storage.load_job("proj1", "job1")
            self.assertEqual(saved.status, "running")
            self.assertIsNone(saved.pending_suggestion_n)
            self.assertEqual(updates, [("proj1", 2, "ready", "")])
            self.assertEqual(starts, [("proj1", "job1")])


if __name__ == "__main__":
    unittest.main()
