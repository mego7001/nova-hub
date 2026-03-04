from __future__ import annotations

from core.voice.schemas import VoiceConfig


def test_voice_push_to_talk_defaults_enabled():
    cfg = VoiceConfig()
    assert cfg.push_to_talk is True


def test_voice_push_to_talk_env_override(monkeypatch):
    monkeypatch.setenv("VOICE_PUSH_TO_TALK", "0")
    cfg = VoiceConfig.from_env()
    assert cfg.push_to_talk is False
