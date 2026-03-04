from pathlib import Path
import unittest

from core.plugin_engine.loader import PluginLoader
from core.plugin_engine.registry import PluginRegistry


class TestPluginLoaderTools(unittest.TestCase):
    def test_run_preview_tools_registered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = PluginRegistry()
        PluginLoader(str(root)).load_enabled(str(root / "configs" / "plugins_enabled.yaml"), registry)
        self.assertIn("run.preview", registry.tools)
        self.assertIn("run.stop", registry.tools)


if __name__ == "__main__":
    unittest.main()
