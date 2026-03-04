from __future__ import annotations

from core.voice.readiness import probe_voice_readiness


def test_voice_readiness_degraded_when_dependencies_missing(monkeypatch):
    monkeypatch.setattr("core.voice.readiness.importlib.util.find_spec", lambda _name: None)
    monkeypatch.setattr("core.voice.readiness.shutil.which", lambda _name: None)
    monkeypatch.setattr("core.voice.readiness.list_input_devices", lambda: ["default"])

    report = probe_voice_readiness(sample_rate=16000)

    assert report["status"] == "degraded"
    issues = report.get("issues") or []
    assert any("faster_whisper" in str(x) for x in issues)


def test_voice_readiness_ready_when_backends_available(monkeypatch):
    monkeypatch.setattr("core.voice.readiness.importlib.util.find_spec", lambda _name: object())
    monkeypatch.setattr("core.voice.readiness.shutil.which", lambda _name: "C:/bin/piper.exe")
    monkeypatch.setattr("core.voice.readiness.list_input_devices", lambda: ["Mic 1"])

    report = probe_voice_readiness(sample_rate=22050)

    assert report["status"] == "ready"
    assert report["sample_rate"] == 22050
    assert report["devices"] == ["Mic 1"]
