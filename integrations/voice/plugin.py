from __future__ import annotations

import os
from typing import Any, Dict

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.portable.paths import detect_base_dir, default_workspace_dir
from core.voice.engine import record_audio, transcribe_audio, speak_text


def _workspace_root() -> str:
    base = detect_base_dir()
    return os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def voice_stt_record(project_id: str, seconds: int = 4) -> Dict[str, Any]:
        if not project_id:
            raise ValueError("project_id is required")
        ws = _workspace_root()
        audio_dir = os.path.join(ws, "projects", project_id, "temp", "audio")
        os.makedirs(audio_dir, exist_ok=True)
        path = os.path.join(audio_dir, "voice_input.wav")
        rec = record_audio(path, seconds=seconds)
        text, stt_info = transcribe_audio(path)
        return {
            "status": rec.get("status"),
            "audio_path": rec.get("audio_path"),
            "transcript": text,
            "record_engine": rec.get("engine"),
            "stt": stt_info,
        }

    def voice_tts_speak(text: str) -> Dict[str, Any]:
        return speak_text(text or "")

    registry.register_tool(
        ToolRegistration(
            tool_id="voice.stt_record",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="voice_stt_record",
            handler=voice_stt_record,
            description="Record audio (optional STT) into workspace",
            default_target=None,
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="voice.tts_speak",
            plugin_id=manifest.id,
            tool_group="process_exec",
            op="voice_tts_speak",
            handler=voice_tts_speak,
            description="Speak text using offline TTS if available",
            default_target=None,
        )
    )
