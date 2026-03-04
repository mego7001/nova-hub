from pathlib import Path
import os
import tempfile
import unittest

from core.plugin_engine.loader import PluginLoader
from core.plugin_engine.registry import PluginRegistry
from integrations.patch_apply.plugin import PatchApplyError


class TestPatchPipelineIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls._root = root
        cls._registry = PluginRegistry()
        PluginLoader(str(root)).load_enabled(str(root / "configs" / "plugins_enabled.yaml"), cls._registry)

    def test_plan_apply_modifies_gitignore(self) -> None:
        plan_tool = self._registry.tools["patch.plan"]
        apply_tool = self._registry.tools["patch.apply"]

        with tempfile.TemporaryDirectory() as tmp:
            gitignore = os.path.join(tmp, ".gitignore")
            with open(gitignore, "w", encoding="utf-8") as f:
                f.write("__pycache__/\n")

            before = Path(gitignore).read_text(encoding="utf-8")
            plan = plan_tool.handler(target_root=tmp, goal="Harden gitignore", write_reports=False)
            diff_path = os.path.join(tmp, plan["diff_path"])
            result = apply_tool.handler(diff_path=diff_path, target_root=tmp, write_reports=False)
            after = Path(gitignore).read_text(encoding="utf-8")

            self.assertNotEqual(before, after)
            self.assertIn(".env", after)
            self.assertIn("reports/", after)
            self.assertIn("patches/", after)
            self.assertEqual(result["totals"]["success_count"], 1)
            self.assertEqual(result["totals"]["failed_count"], 0)

    def test_apply_rejects_zero_hunk_diff(self) -> None:
        apply_tool = self._registry.tools["patch.apply"]

        with tempfile.TemporaryDirectory() as tmp:
            diff_path = os.path.join(tmp, "bad.diff")
            with open(diff_path, "w", encoding="utf-8") as f:
                f.write("--- a/sample.txt\n+++ b/sample.txt\n")

            with self.assertRaises(PatchApplyError):
                apply_tool.handler(diff_path=diff_path, target_root=tmp, write_reports=False)


if __name__ == "__main__":
    unittest.main()
