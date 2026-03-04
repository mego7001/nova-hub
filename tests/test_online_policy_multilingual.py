from __future__ import annotations

from core.llm.online_policy import decide_online


def test_deep_reasoning_arabic_phrase_triggers_online_need() -> None:
    decision = decide_online(
        task_type="deep_reasoning",
        user_msg="عايز تحليل عميق وسبب جذري للمشكلة",
        offline_confidence="high",
    )
    assert decision.need_online is True


def test_conversation_arabic_detail_phrase_triggers_online_need() -> None:
    decision = decide_online(
        task_type="conversation",
        user_msg="اشرح بالتفصيل ليه النظام بيفشل",
        offline_confidence="high",
    )
    assert decision.need_online is True
