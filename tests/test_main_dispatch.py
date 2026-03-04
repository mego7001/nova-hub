from pathlib import Path
import os
import tempfile
import unittest

import main as cli_main
from core.plugin_engine.loader import PluginLoader
from core.plugin_engine.registry import PluginRegistry


class _DummyRunner:
    def __init__(self) -> None:
        self.calls = []

    def execute_registered_tool(self, tool, **kwargs):
        self.calls.append(kwargs)
        return tool.handler(**kwargs)


class TestMainDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls._registry = PluginRegistry()
        PluginLoader(str(root)).load_enabled(str(root / "configs" / "plugins_enabled.yaml"), cls._registry)

    def test_dispatch_filters_target_for_fs_list_dir(self) -> None:
        tool = self._registry.tools["fs.list_dir"]
        runner = _DummyRunner()
        with tempfile.TemporaryDirectory() as tmp:
            result = cli_main._execute_tool_with_filtered_kwargs(
                runner,
                tool,
                {"path": tmp, "target": tmp},
                policy_target=tmp,
            )
            self.assertEqual(result["path"], os.path.abspath(tmp))
            self.assertTrue(runner.calls)
            self.assertNotIn("target", runner.calls[-1])

    def test_dispatch_filters_target_for_repo_search(self) -> None:
        tool = self._registry.tools["repo.search"]
        runner = _DummyRunner()
        with tempfile.TemporaryDirectory() as tmp:
            sample = os.path.join(tmp, "sample.py")
            with open(sample, "w", encoding="utf-8") as f:
                f.write("print('ok')\n")
            result = cli_main._execute_tool_with_filtered_kwargs(
                runner,
                tool,
                {
                    "root_path": tmp,
                    "query": None,
                    "write_reports": False,
                    "target": tmp,
                },
                policy_target=tmp,
            )
            self.assertIn("total_matches", result)
            self.assertTrue(runner.calls)
            self.assertNotIn("target", runner.calls[-1])


if __name__ == "__main__":
    unittest.main()
