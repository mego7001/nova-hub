from core.ux.mode_routing import parse_mode_wrapped_message, route_message_for_mode, unwrap_mode_wrapped_text


def test_mode_routing_roundtrip_reversible():
    wrapped = route_message_for_mode(
        "build_software",
        "find all callsites for approval flow",
        {"ui": "hud", "scope": "project:alpha"},
    )
    parsed = parse_mode_wrapped_message(wrapped)
    assert parsed.wrapped is True
    assert parsed.mode == "build_software"
    assert parsed.text == "find all callsites for approval flow"
    assert parsed.context.get("ui") == "hud"
    assert parsed.context.get("scope") == "project:alpha"


def test_mode_routing_parse_plain_message_defaults_general():
    parsed = parse_mode_wrapped_message("hello nova")
    assert parsed.wrapped is False
    assert parsed.mode == "general"
    assert parsed.text == "hello nova"
    assert unwrap_mode_wrapped_text("hello nova") == "hello nova"


def test_mode_routing_sanitizes_context_for_single_line_wrapper():
    wrapped = route_message_for_mode("verify", "run fast checks", {"note": "a=b;\nnext"})
    parsed = parse_mode_wrapped_message(wrapped)
    assert parsed.mode == "build_software"
    assert "\nrun fast checks" in wrapped
    assert "note=a:b, next" in wrapped
