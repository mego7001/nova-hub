from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "run_hud_qml",
        "run_chat",
        "run_whatsapp",
        "ui.chat.app",
        "ui.whatsapp.app",
    ],
)
def test_entrypoints_import_clean(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None
