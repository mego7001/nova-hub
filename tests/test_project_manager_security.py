import os
import tempfile
import unittest

from core.projects.manager import ProjectManager


class TestProjectManagerSecurity(unittest.TestCase):
    def test_get_project_paths_blocks_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            workspace = os.path.join(base, "workspace")
            os.makedirs(workspace, exist_ok=True)
            manager = ProjectManager(workspace_root=workspace)
            with self.assertRaises(ValueError):
                manager.get_project_paths(r"..\..\escape")

    def test_delete_project_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            workspace = os.path.join(base, "workspace")
            os.makedirs(workspace, exist_ok=True)
            manager = ProjectManager(workspace_root=workspace)

            victim = os.path.join(base, "victim")
            os.makedirs(victim, exist_ok=True)
            marker = os.path.join(victim, "keep.txt")
            with open(marker, "w", encoding="utf-8") as f:
                f.write("still here")

            with self.assertRaises(ValueError):
                manager.delete_project(r"..\..\victim", "DELETE")

            self.assertTrue(os.path.isdir(victim))
            self.assertTrue(os.path.isfile(marker))


if __name__ == "__main__":
    unittest.main()
