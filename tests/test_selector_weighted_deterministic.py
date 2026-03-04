from pathlib import Path

from core.llm.selector import WeightedProviderSelector
from core.telemetry.db import TelemetryDB
from core.telemetry.recorders import TelemetryRecorder


def _seed_calls(
    recorder: TelemetryRecorder,
    *,
    mode: str,
    provider: str,
    ok_calls: int,
    error_calls: int,
    latency_ms: int,
    cost_usd: float,
) -> None:
    for idx in range(ok_calls):
        recorder.record_llm_call(
            session_id=f"{mode}_{provider}_ok_{idx}",
            project_id="proj",
            mode=mode,
            provider=provider,
            model=f"{provider}-model",
            profile="engineering",
            request_kind="chat",
            input_tokens=120,
            output_tokens=80,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status="ok",
        )
    for idx in range(error_calls):
        recorder.record_llm_call(
            session_id=f"{mode}_{provider}_err_{idx}",
            project_id="proj",
            mode=mode,
            provider=provider,
            model=f"{provider}-model",
            profile="engineering",
            request_kind="chat",
            input_tokens=120,
            output_tokens=0,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status="error",
            error_kind="other",
            error_msg=f"{provider} synthetic error",
        )


def test_weighted_selector_is_deterministic_and_mode_sensitive(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = TelemetryDB(workspace_root=str(workspace))
    recorder = TelemetryRecorder(db)
    selector = WeightedProviderSelector(db)

    # build_software should prioritize reliability.
    _seed_calls(
        recorder,
        mode="build_software",
        provider="deepseek",
        ok_calls=28,
        error_calls=2,
        latency_ms=450,
        cost_usd=0.025,
    )
    _seed_calls(
        recorder,
        mode="build_software",
        provider="gemini",
        ok_calls=20,
        error_calls=10,
        latency_ms=180,
        cost_usd=0.010,
    )

    # general should tolerate slightly lower quality for speed/cost.
    _seed_calls(
        recorder,
        mode="general",
        provider="deepseek",
        ok_calls=27,
        error_calls=3,
        latency_ms=520,
        cost_usd=0.030,
    )
    _seed_calls(
        recorder,
        mode="general",
        provider="gemini",
        ok_calls=26,
        error_calls=4,
        latency_ms=190,
        cost_usd=0.008,
    )

    build_pick_1 = selector.pick_provider(
        mode="build_software",
        request_kind="chat",
        candidates=["gemini", "deepseek"],
    )
    build_pick_2 = selector.pick_provider(
        mode="build_software",
        request_kind="chat",
        candidates=["gemini", "deepseek"],
    )
    assert build_pick_1["provider"] == "deepseek"
    assert build_pick_2["provider"] == "deepseek"

    general_pick = selector.pick_provider(
        mode="general",
        request_kind="chat",
        candidates=["deepseek", "gemini"],
    )
    assert general_pick["provider"] == "gemini"
