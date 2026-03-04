import inspect
import re

import ui.hud_qml.controller as hud_controller_module


def _count_defs(source: str, name: str) -> int:
    return len(re.findall(rf"^\s*def\s+{re.escape(name)}\s*\(", source, flags=re.MULTILINE))


def test_hud_controller_no_duplicate_defs():
    cls = hud_controller_module.HUDController
    source = inspect.getsource(cls)
    module_source = inspect.getsource(hud_controller_module)

    required_single_defs = [
        "_init_backend",
        "_approval_callback",
        "_append_message",
        "toggleMode",
        "busy",
        "wiringStatus",
        "currentProjectId",
        "selectedProjectId",
        "queue_apply",
        "confirm_pending",
        "reject_pending",
    ]
    for name in required_single_defs:
        assert hasattr(cls, name), f"HUDController missing {name}"
        assert _count_defs(source, name) == 1, f"HUDController has duplicate def for {name}"

    dict_model_imports = re.findall(
        r"^\s*from\s+.+\s+import\s+.*\bDictListModel\b.*$",
        module_source,
        flags=re.MULTILINE,
    )
    assert len(dict_model_imports) == 1, "Expected a single DictListModel import source"
