from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.plugin_engine.loader import PluginLoader
from core.plugin_engine.registry import PluginRegistry
from core.ux.tools_index import write_tools_index_report


def main() -> int:
    registry = PluginRegistry()
    PluginLoader(str(ROOT)).load_enabled(str(ROOT / "configs" / "plugins_enabled.yaml"), registry)
    output_path = ROOT / "reports" / "tools_index.json"
    written = write_tools_index_report(registry, str(output_path))
    print(f"tools_index written: {written}")
    print(f"tools_total: {len(registry.list_tools())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
