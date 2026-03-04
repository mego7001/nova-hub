from __future__ import annotations

import importlib
from pathlib import Path

import core.llm.selection_policy as selection_policy


def test_llm_routing_yaml_overrides_selector_and_fallback(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "llm_routing.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "selector:",
                "  window_days: 3",
                "  max_calls_per_group: 55",
                "  min_calls_for_dynamic: 7",
                "  cooldown_minutes: 5",
                "  build_min_success_rate: 0.9",
                "fallback_order:",
                "  general: [ollama, deepseek, gemini, openai]",
                "mode_weights:",
                "  general:",
                "    quality: 0.5",
                "    cost: 0.2",
                "    latency: 0.2",
                "    error_rate: 0.1",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NH_LLM_ROUTING_CONFIG", str(cfg_path))
    mod = importlib.reload(selection_policy)
    try:
        assert mod.selector_window_days() == 3
        assert mod.selector_max_calls_per_group() == 55
        assert mod.selector_min_calls_for_dynamic() == 7
        assert mod.selector_cooldown_minutes() == 5
        assert abs(mod.selector_build_min_success_rate() - 0.9) < 1e-9
        assert mod.fallback_order("general")[0] == "ollama"
        weights = mod.mode_weights("general")
        assert abs(weights.quality - 0.5) < 1e-9
        assert abs(weights.cost - 0.2) < 1e-9
    finally:
        monkeypatch.delenv("NH_LLM_ROUTING_CONFIG", raising=False)
        importlib.reload(selection_policy)


def test_llm_routing_yaml_exposes_router_local_policy_and_task_models(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "llm_routing.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "router:",
                "  local_first: true",
                "  external_backup_only: true",
                "  task_model_map:",
                "    conversation: gemma3:4b",
                "    build_software: qwen2.5-coder:7b-instruct",
                "    vision: llava",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NH_LLM_ROUTING_CONFIG", str(cfg_path))
    mod = importlib.reload(selection_policy)
    try:
        data = mod.load_llm_routing_config()
        router = data.get("router") or {}
        assert router.get("local_first") is True
        assert router.get("external_backup_only") is True
        tmm = router.get("task_model_map") or {}
        assert tmm.get("conversation") == "gemma3:4b"
        assert tmm.get("build_software") == "qwen2.5-coder:7b-instruct"
        assert tmm.get("vision") == "llava"
    finally:
        monkeypatch.delenv("NH_LLM_ROUTING_CONFIG", raising=False)
        importlib.reload(selection_policy)
