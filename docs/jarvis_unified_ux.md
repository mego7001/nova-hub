# Jarvis Unified UX

## What Changed

Nova now exposes one unified input model across:

- `ui/hud_qml`
- `ui/chat`
- `ui/quick_panel`

`run_whatsapp.py` remains only a compatibility launcher alias for Quick Panel.

Core behavior is shared by `core/ux/*` and routes through existing message send boundaries (no direct unsafe bypass of apply/approval flows).

## Unified Input Surface

Each UI now provides the same functional blocks near message input:

- `Attach`: add files into memory context.
- `Task Mode`: select execution intent (`general`, `build_software`, `gen_3d_step`, `gen_2d_dxf`).
- `Tools`: open curated + advanced registry-backed tool catalog.

## File Memory Policy

Two memory scopes are enforced:

- `General memory`
  - Limit: `25 files`
  - Size: `150 MB`
  - TTL: `14 days`
  - Storage: `workspace/chat/sessions/<chat_id>/...`
- `Project memory`
  - Limit: `200 files`
  - Size: `2 GB`
  - TTL: none
  - Storage: project-local `docs/extracted/index`

## General -> Project Conversion

HUD conversion now migrates:

- chat history messages
- ingested docs
- extracted text artifacts
- index records metadata

Migration uses the same existing conversion entrypoints and remains approval-safe.

## Voice UX (Local-First)

Voice is local by default:

- STT: `faster-whisper`
- TTS: `piper`

HUD keeps the full Voice panel; chat and quick panel expose minimal controls aligned to the same local voice loop behavior.

## Safety and Governance

No patch/apply safety bypass was added.

- Approvals still flow through existing policy + confirmation paths.
- Task mode routing and tools menu only annotate/route input through existing boundaries.
- Dangerous operations remain gated exactly as before.

## Migration Notes

If you were using previous UI-specific behavior:

1. Switch to `Task Mode` instead of implicit intent-only flow.
2. Use `Tools` menu as the catalog source of truth.
3. Use `Attach` in either General or Project context; policy limits now return explicit rejection reasons.
