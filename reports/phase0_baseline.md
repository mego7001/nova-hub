# Phase 0 Baseline Validation

Timestamp: 2026-02-06

## Repo Tree Summary
- `.venv/` (local)
- `configs/`
- `core/`
- `docs/`
- `integrations/`
- `launchers/`
- `logs/`
- `outputs/`
- `patches/`
- `reports/`
- `tests/`
- `ui/`
- `workspace/`
- Entry scripts: `main.py`, `run_whatsapp.py`, `run_ui.py`, `run_chat.py`

## Entrypoints
- `run_whatsapp.py` (WhatsApp-style UI)
- `run_ui.py` (dashboard UI)
- `run_chat.py` (chat UI)
- `main.py` (CLI tool runner / list tools)

## Baseline Checks
- `run_whatsapp.py` launch: started successfully and entered UI event loop; terminated by timeout in headless environment (no crash after fixes).
- Send appends `You:` immediately: confirmed via `ui/whatsapp/app.py::_send_message` (appends before tool execution).
- Analyze suggestions with evidence: confirmed via `core/chat/orchestrator.py` + `core/assistant/suggestions.py` (evidence paths included).
- Jobs safe points: confirmed via `core/jobs/controller.py` (safe point fields tracked).
- Online AI OFF by default: confirmed via `core/conversation/prefs.py` + UI toggle defaults.
- Approvals required per call: enforced by `configs/approvals.yaml` and `core/permission_guard`.
- Clear Files (Keep Chat) + Restore: confirmed in `core/projects/manager.py` + WhatsApp UI context menu.

## verify.smoke
- Ran `verify.smoke` via tool handler.
- Result: **FAIL** (compileall failed due to a SyntaxError inside `workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/chat/app.py`).
- This failure is in a workspace project copy, not the main Nova Hub source, so it is **not** a launch blocker.

## Known Issues / Notes
- UI interaction (send/analyze/jobs) cannot be fully exercised in a headless run; code paths confirm expected behavior.
- Workspace `verify.smoke` compileall traverses workspace project copies and can fail due to non-core files.

## Feature Status (Baseline)
- Security Doctor: **missing in baseline** (implemented in Phase 1).
- Voice Mode: **missing**.
- Sketch Mode: **missing**.
