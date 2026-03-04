from __future__ import annotations

from pathlib import Path


def test_core_event_publisher_wrapper_is_explicit_none_return() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "main.py").read_text(encoding="utf-8")

    assert "def _publish_event(session_id: str, project_id: str, topic: str, data: Dict[str, Any]) -> None:" in text
    assert "service.set_event_publisher(_publish_event)" in text
    assert "events_server.publish_event(" in text
