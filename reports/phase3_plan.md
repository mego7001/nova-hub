# Phase 3 Plan (Execution)

## Tools polish
1. Extend tool metadata with dependency/env/context requirements.
2. Compute user-facing reasons in tools catalog:
   - policy block / approval
   - missing dependency
   - missing secret/env
   - context mismatch
3. Keep governance unchanged for approvals.

## Task modes usability
1. Add explicit `Auto` user mode row.
2. Implement deterministic fallback resolver to executable mode.
3. Apply resolver in HUD + chat + quick panel mode selection.

## Voice productization
1. Add readiness probe API: dependencies/devices/backend/model path.
2. Expose IPC op `voice.readiness`.
3. Add HUD readiness action + summary line.
4. Strengthen anti-echo UX with headset warning.
5. Add stage latency metrics fields (capture/stt/llm/tts/playback).

## Safe refactor
1. Split shared HUD controller helpers into dedicated modules:
   - `controller_core.py`
   - `controller_ingest.py`
   - `controller_tools.py`
   - `controller_voice.py`
2. Keep `HUDController` public API/slots stable.
3. Add import smoke test for split modules.
