# Nova Hub — Project Context Pack (for new chat handoff)
Generated: 2026-02-07T03:00:00

## 1) What Nova Hub is (current)
Nova Hub is an **interactive engineering AI assistant** that runs locally with **workspace-only enforcement** and **explicit confirmation gating** for any execution/apply/write that could be risky.

Current interaction model (already implemented in the codebase you have):
- **Conversational Mode (default ON):** natural Egyptian‑Arabic dialog. Free chat never executes; it *suggests* and then waits for explicit confirm.
- **Project mode:** once a project is selected, Nova can analyze, ingest docs, generate evidence-based suggestions, run long jobs, and maintain state.
- **Offline-first:** Online AI is OFF by default and used only when policy says “needed”, and only after explicit opt-in + per-call approvals.

## 2) Key pillars we must not break
### Safety & Control
- **Workspace-only** projects under: `workspace/projects/<id>/...`
- Execution happens only in **preview**, never in working copy.
- **Approvals** remain required for:
  - patch.apply / fs.write_text outside safe writer allowlist
  - process_exec / desktop opens
  - any network/LLM calls (online mode)
- **Secrets redaction**: never echo secrets, never store them in transcripts/reports, redact in prompts.

### UX rules (Jarvis conversational guardrails)
- Ask before changing decisions; if disagree, **state disagreement + why**.
- Graduated warnings (3 levels) + **proceed-anyway** flow.
- Recovery mode on failures: fix-first, then calm reminder, then continue.

## 3) What’s implemented so far (capabilities present)
### Core workflow
- Project management: import folder/zip into workspace, select project, keep chat/state.
- Ingestion: attach/drag-drop, parse docs, create index, citations/evidence.
- Suggestions: numbered + panel, execute/plan/apply with confirm & verify.
- Jobs: long runs with safe points; waiting-for-confirm panel; persistence.

### Security Doctor + gating (Phase 1 + 1.5)
- `security.audit` creates redacted `security_audit.json/md`.
- CRITICAL findings can **block project-scoped online enablement** (persisted).

### Sketch (2D) and 3D Mind
- Sketch: parse → preview → confirm apply → export DXF.
- 3D: parse intent → preview → confirm apply → export STL (where present).

### Engineering Brain Expansion
- Extract signals for **materials/loads/tolerances**, apply rules, compute risk posture,
  ask one next question, and generate report under:
  `workspace/projects/<id>/engineering/`

## 4) Current pain points (what user requested now)
1) **WhatsApp UI is not the target** (feels heavy/old; not “Iron Man”).
2) Need a **digital HUD UI** that matches capabilities: floating cards, panes, live 3D, sketch, timeline.
3) Conversation is huge → need **clean handoff**:
   - create a ZIP snapshot + a compact context doc
   - start a fresh chat with all context loaded

## 5) The next step we will execute in the next chat
### A) Packaging / continuity
- Produce a release ZIP that includes:
  - the latest repo snapshot
  - `PROJECT_CONTEXT.md` (this document)
  - `STATE_OF_THE_UNION.md` (capabilities + QA status + known limits)
  - `NEXT_SPRINT.md` (UI redesign roadmap)
- Provide a **single “New Chat Prompt”** for the agent to continue work without questions.

### B) UI Redesign — “Nova HUD”
Replace WhatsApp UI with a modern “Jarvis/HUD” desktop UI using PySide6:
- **Dockable layout** (3–5 panels) + optional floating “cards”
- Left: Projects + Sessions
- Center: Chat + Command palette + “Confirm” strip
- Right: Tabs: Suggestions, Docs, Engineering, Security, Timeline
- Bottom/Side: **Live Sketch & 3D viewport** (toggle)
- **Timeline spine** as an always-available overlay
- Visual language: dark theme, neon accents, concise typography, status chips.

Implementation constraints:
- No raw tool params exposed.
- Reuse same orchestrator/runner; UI is a shell.

## 6) Acceptance criteria for “Nova HUD v1”
- App launches reliably.
- Send always appends immediately.
- Project selection is fast and persistent.
- Sketch + 3D previews render and can export.
- Engineering tab shows state + findings + generate report.
- Security tab runs audit + blocks online project scope if needed.
- Online AI remains opt‑in and only when policy requires.
- Timeline shows: messages, approvals, tool runs, job steps, preview events.

## 7) Files you have uploaded (reference)
- `nova_hub_final.zip`
- `NovaHub_REVIEW.zip`
- `nova_hub_snapshot_no_venv_20260202_0151.zip`
- `nova_hub_v1_release.zip`
- `openclaw-main.zip` (reference patterns only; do not blindly copy)

## 8) Non-negotiables
- Never execute from free chat without explicit confirmation.
- Never weaken approvals.
- Never leak secrets.
- Keep workspace boundary hard.
