from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

UI_PROFILE_FULL = "full"
UI_PROFILE_COMPACT = "compact"
UI_PROFILES = (UI_PROFILE_FULL, UI_PROFILE_COMPACT)

APP_STATE_IDLE = "idle"
APP_STATE_THINKING = "thinking"
APP_STATE_AWAITING_APPROVAL = "awaiting_approval"
APP_STATE_VOICE_ACTIVE = "voice_active"
APP_STATE_ERROR_DEGRADED = "error_degraded"
APP_STATES = (
    APP_STATE_IDLE,
    APP_STATE_THINKING,
    APP_STATE_AWAITING_APPROVAL,
    APP_STATE_VOICE_ACTIVE,
    APP_STATE_ERROR_DEGRADED,
)


@dataclass(frozen=True)
class PanelDescriptor:
    id: str
    title: str
    icon: str
    visible: bool = True
    priority: int = 100
    requires_project_context: bool = False
    status_badge: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InteractionContract:
    action_id: str
    source_panel: str
    requires_approval: bool
    fallback_behavior: str
    telemetry_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_ui_profile(raw_value: str | None) -> str:
    raw = str(raw_value or "").strip().lower()
    if raw in UI_PROFILES:
        return raw
    return UI_PROFILE_FULL


def default_panel_descriptors() -> tuple[PanelDescriptor, ...]:
    return (
        PanelDescriptor(id="chat", title="Chat", icon="chat", priority=10),
        PanelDescriptor(id="tools", title="Tools", icon="tool", priority=20),
        PanelDescriptor(id="attach", title="Attach", icon="attach", priority=30),
        PanelDescriptor(id="health", title="Health", icon="health", priority=40),
        PanelDescriptor(id="history", title="History", icon="history", priority=50),
        PanelDescriptor(id="voice", title="Voice", icon="voice", priority=60),
    )


def default_interaction_contracts() -> tuple[InteractionContract, ...]:
    return (
        InteractionContract(
            action_id="apply_queue",
            source_panel="tools",
            requires_approval=True,
            fallback_behavior="show_reason",
            telemetry_key="action.tools.apply_queue",
        ),
        InteractionContract(
            action_id="apply_confirm",
            source_panel="tools",
            requires_approval=True,
            fallback_behavior="show_reason",
            telemetry_key="action.tools.apply_confirm",
        ),
        InteractionContract(
            action_id="apply_reject",
            source_panel="tools",
            requires_approval=True,
            fallback_behavior="show_reason",
            telemetry_key="action.tools.apply_reject",
        ),
        InteractionContract(
            action_id="voice_toggle",
            source_panel="voice",
            requires_approval=False,
            fallback_behavior="show_status",
            telemetry_key="action.voice.toggle",
        ),
        InteractionContract(
            action_id="memory_search",
            source_panel="history",
            requires_approval=False,
            fallback_behavior="show_empty",
            telemetry_key="action.memory.search",
        ),
    )


def load_panel_contract(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("panel contract must be a JSON object")
    return payload

