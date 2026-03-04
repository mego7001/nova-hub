from __future__ import annotations

from typing import Dict


def headset_warning(device_name: str, *, enabled: bool) -> str:
    if not enabled:
        return ""
    name = str(device_name or "").strip().lower()
    if not name:
        return ""
    if any(token in name for token in ("headset", "headphone", "earbud", "bluetooth")):
        return ""
    return " [Headset recommended]"


def latency_summary(metrics: Dict[str, str]) -> str:
    return (
        f"capture={metrics.get('capture_latency_ms', '0')}ms "
        f"stt={metrics.get('stt_latency_ms', '0')}ms "
        f"llm={metrics.get('llm_latency_ms', '0')}ms "
        f"tts={metrics.get('tts_latency_ms', '0')}ms "
        f"playback={metrics.get('playback_latency_ms', '0')}ms"
    )
