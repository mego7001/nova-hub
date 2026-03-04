# Nova Risk and Blockers

Generated: 2026-02-18

## Severity Key

- `Critical`: blocks core startup, IPC, or safe execution path.
- `High`: can break primary UX flow or cause misleading system behavior.
- `Medium`: limits reliability/maintainability; not immediate outage.
- `Low`: polish/documentation drift.

## 1) Critical

### R-001: IPC autospawn script mismatch (FIXED)

- Symptom:
  - `ensure_core_running(...)` tried to spawn `run_core_service.py` even when missing.
- Impact:
  - IPC autospawn failure, `main.py call` failure, UI IPC bootstrap failure.
- Root cause:
  - Hardcoded command path in `core/ipc/spawn.py` not aligned with canonical runtime.
- Fix applied:
  - Autospawn now executes `python main.py core ...`.
- Validation:
  - `tests/test_ipc_autospawn.py` passed.

### R-002: Missing release entrypoint scripts (FIXED)

- Symptom:
  - `run_hud_qml.py` and similar scripts absent in root snapshot.
- Impact:
  - Launchers/tests/docs referenced files that did not exist.
- Fix applied:
  - Added compatibility wrappers:
    - `run_hud_qml.py`
    - `run_quick_panel.py`
    - `run_whatsapp.py`
    - `run_chat.py`
    - `run_ui.py`
    - `run_core_service.py`
    - `run_ipc_cli.py`
- Validation:
  - `tests/test_hud_qml_v2_offscreen_ironman.py` passed.

## 2) High

### R-101: Doc/runtime drift risk

- Symptom:
  - Multiple docs and reports reference historical launch paths.
- Impact:
  - Operators may run stale commands, causing false incident reports.
- Mitigation:
  - Updated key docs and launchers to canonical `main.py` flow.
  - Keep wrappers for backward compatibility.

### R-102: Optional dependency gaps degrade features

- Symptom:
  - `doctor.report` can show missing voice/CAD extras.
- Impact:
  - Feature-level failures while core appears healthy.
- Mitigation:
  - Enforce environment checklists per profile before release signoff.

## 3) Medium

### R-201: Release snapshot includes legacy/workspace copies

- Symptom:
  - Historical working/preview copies under `workspace/projects/...`.
- Impact:
  - Potential confusion in audits and module discovery.
- Mitigation:
  - Treat root runtime modules as source of truth.
  - Keep workspace copies out of canonical runtime docs.

### R-202: Provider behavior ambiguity under no-telemetry startup

- Symptom:
  - `doctor.report` default provider scores can be static before telemetry builds.
- Impact:
  - Early routing decisions may not reflect empirical quality.
- Mitigation:
  - Explicit fallback policy documentation and warm-up calls for telemetry bootstrap.

## 4) Low

### R-301: Deprecation warning in fs tools tests

- Symptom:
  - `datetime.utcnow()` warning surfaced in tests.
- Impact:
  - No runtime break now; future maintenance overhead.
- Mitigation:
  - Replace with timezone-aware UTC usage in future hygiene pass.

## 5) Current Blockers Status

- IPC startup blockers: `Resolved`.
- Wrapper/entrypoint blockers: `Resolved`.
- Remaining blockers for full program operation: `None critical currently observed`.

## 6) Immediate Follow-up Actions

1. Keep CI gate for IPC + HUD wrapper smoke tests.
2. Add a release check that verifies canonical and wrapper entrypoints exist.
3. Add docs smoke script that executes all documented launch commands with `--help` or short smoke mode.
