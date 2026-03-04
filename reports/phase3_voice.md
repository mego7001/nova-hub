# Phase 3 - Voice Mode (Offline-first)

## Delivered
- Voice tools: `voice.stt_record` (fs_write), `voice.tts_speak` (process_exec).
- Mic button (record) and Speak toggle in WhatsApp UI.
- Offline-first behavior with graceful degradation when engines are missing.

## QA
- `scripts/voice_qa.py` PASS (degraded mode acceptable).
- Reports: `reports/voice_qa.md`, `reports/voice_qa.json`.
