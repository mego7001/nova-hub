from __future__ import annotations

from core.ux.mode_routing import parse_mode_wrapped_message, route_message_for_mode


def test_mode_routing_wrapper_is_reversible_with_context():
    wrapped = route_message_for_mode(
        "gen_3d_step",
        "build a shaft model",
        {"ui": "hud", "scope": "project:p1", "auto": "resolved"},
    )
    parsed = parse_mode_wrapped_message(wrapped)
    assert parsed.wrapped is True
    assert parsed.mode == "gen_3d_step"
    assert parsed.text == "build a shaft model"
    assert parsed.context.get("ui") == "hud"
    assert parsed.context.get("scope") == "project:p1"
