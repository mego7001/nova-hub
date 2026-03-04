from __future__ import annotations

from types import SimpleNamespace

from core.conversation.brain import ConversationalBrain


class _DummyRouter:
    def route(self, *_args, **_kwargs):
        return {"mode": "offline", "provider": "local", "text": "", "_routing": {"dummy": True}}


def test_brain_empty_message_uses_clean_arabic_text() -> None:
    brain = ConversationalBrain(router=_DummyRouter())
    result = brain.respond("")
    assert "أنا معاك" in result.reply_text


def test_brain_explain_suggestion_arabic_keyword_works() -> None:
    brain = ConversationalBrain(router=_DummyRouter())
    state = SimpleNamespace(
        suggestions=[
            {
                "title": "إصلاح التهيئة",
                "rationale": "يوجد تضارب في الإعدادات",
                "evidence": [{"path": "core/llm/router.py", "line": 12, "excerpt": "fallbacks"}],
            }
        ]
    )
    text = brain._explain_suggestion("اقتراح 1", state)
    assert "ليه الاقتراح #1" in text
    assert "core/llm/router.py:12" in text
