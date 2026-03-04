# Developer Guide

## Architecture Overview
- `ui/hud_qml/app_qml.py` is the primary UI entrypoint for Nova Hub.
- `ui/quick_panel/app.py` provides the legacy quick panel UX.
- `run_whatsapp.py` is a compatibility launcher alias to Quick Panel.
- `core/chat/orchestrator.py` manages conversation tools and tool execution.
- `core/llm/router.py` enforces Online AI policy and approvals.
- `core/security/security_doctor.py` runs workspace security audits.

## Jarvis Core
- `core/conversation/jarvis_core.py` defines disagreement, warning levels, and recovery.
- Per-project state is stored in `workspace/projects/<id>/state.json`.

## Sketch
- `core/sketch/` includes parser, store, renderer, and DXF exporter.
- Sketch data is stored at `workspace/projects/<id>/sketch/sketch.json`.
- Integration tools are in `integrations/sketch/`.

## Voice
- `core/voice/engine.py` provides offline-first record/transcribe/speak helpers.
- Integration tools are in `integrations/voice/`.

## Timeline (Audit Spine)
- `core/audit_spine.py` includes `ProjectAuditSpine`.
- Events are appended to `workspace/projects/<id>/audit/audit_spine.jsonl`.
- The Timeline tab reads the JSONL file.

## QA Scripts
- `scripts/jarvis_core_qa.py`
- `scripts/sketch_qa.py`
- `scripts/voice_qa.py`
- `scripts/timeline_qa.py`

All scripts write reports under `reports/`.
