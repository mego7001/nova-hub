from __future__ import annotations

from pathlib import Path


def test_hud_and_quick_panel_memory_search_use_same_status_semantics() -> None:
    root = Path(__file__).resolve().parents[1]
    hud = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellFull.qml").read_text(encoding="utf-8")
    quick = (root / "ui" / "hud_qml_v2" / "shell" / "MainShellCompact.qml").read_text(encoding="utf-8")

    expected_phrases = [
        "Memory search ready.",
        "Memory search returned no results.",
        "Memory search failed:",
        "Memory search returned ",
    ]
    for phrase in expected_phrases:
        assert phrase in hud
        assert phrase in quick

    # Both UIs rely on the same controller contract for page results.
    assert "memorySearchPage(" in hud
    assert "memorySearchPage(" in quick
