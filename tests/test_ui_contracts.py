from __future__ import annotations

import json
from pathlib import Path

from core.ux.ui_contracts import (
    APP_STATES,
    UI_PROFILE_COMPACT,
    UI_PROFILE_FULL,
    default_interaction_contracts,
    default_panel_descriptors,
    load_panel_contract,
    normalize_ui_profile,
)


def test_normalize_ui_profile_defaults_to_full() -> None:
    assert normalize_ui_profile(None) == UI_PROFILE_FULL
    assert normalize_ui_profile("unknown") == UI_PROFILE_FULL
    assert normalize_ui_profile("compact") == UI_PROFILE_COMPACT


def test_default_panel_descriptors_have_expected_ids() -> None:
    panels = default_panel_descriptors()
    ids = [p.id for p in panels]
    assert ids == ["chat", "tools", "attach", "health", "history", "voice"]


def test_default_interactions_require_approval_for_patch_actions() -> None:
    contracts = {c.action_id: c for c in default_interaction_contracts()}
    assert contracts["apply_queue"].requires_approval is True
    assert contracts["apply_confirm"].requires_approval is True
    assert contracts["apply_reject"].requires_approval is True
    assert contracts["voice_toggle"].requires_approval is False


def test_load_panel_contract_reads_json(tmp_path) -> None:
    path = tmp_path / "panel_contract.json"
    payload = {"profiles": {"full": {"panels": ["chat"]}}, "states": list(APP_STATES)}
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_panel_contract(path)
    assert loaded["profiles"]["full"]["panels"] == ["chat"]


def test_repo_panel_contract_v3_contains_expected_profiles() -> None:
    config_path = Path(__file__).resolve().parents[1] / "configs" / "panel_contract_v3.json"
    payload = load_panel_contract(config_path)
    assert payload["strategy"] == "unified_hud_base"
    assert "full" in payload["profiles"]
    assert "compact" in payload["profiles"]
    assert payload["capability_to_panel_map"]["memory.search"] == "history"
