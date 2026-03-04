# Nova Development Roadmap

Generated: 2026-02-18
Basis: post-IPC stabilization + source-driven dissection

## Phase A: Stabilize

Goal: keep runtime consistent and remove entrypoint drift regressions.

### Changes

1. Keep `main.py` as canonical runtime contract.
2. Maintain compatibility wrappers and add wrapper-specific regression tests.
3. Add docs command smoke checks in CI.
4. Keep IPC startup checks in pre-release gate.

### Impacted Files

- `main.py`
- `core/ipc/spawn.py`
- `run_*.py` wrappers
- `launchers/*`
- `docs/*` launch sections
- `tests/test_ipc_*`, new wrapper/doc smoke tests

### Test Gates

- IPC autospawn + health + chat smoke pass.
- HUD offscreen wrapper smoke pass.
- docs launch smoke pass.

### Rollback

- If wrapper issues appear, keep canonical `main.py` paths available and rollback wrapper changes independently.

## Phase B: Harden

Goal: improve reliability and operational confidence for daily use.

### Changes

1. Add runtime preflight command:
   - checks optional dependencies, local model connectivity, voice binaries.
2. Add explicit release audit command:
   - verify required entrypoints/docs/runtime files before packaging.
3. Improve error taxonomy in telemetry:
   - distinguish startup/config/dependency failures.
4. Replace timezone-deprecated datetime usage.

### Impacted Files

- `core/ipc/*`
- `core/telemetry/*`
- `scripts/*` (new preflight/release audit scripts)
- selected plugin integrations

### Test Gates

- Preflight returns deterministic structured JSON.
- Doctor report includes clear remediation status.
- No deprecation warnings in core regression suite.

### Rollback

- Keep additive behavior only; any new check can be feature-flagged off.

## Phase C: Scale

Goal: support larger project throughput with lower operational friction.

### Changes

1. Telemetry-driven optimization loop:
   - daily provider/tool scorecards with trend export.
2. Extended end-to-end scenario tests:
   - Build software mode full cycle (scan -> plan -> apply -> verify).
3. UI workflow acceleration:
   - session/project switching and history restoration stress tests.
4. Domain regression packs:
   - CAD/Sketch/3D/Engineering composite scenarios.

### Impacted Files

- `core/llm/*`
- `core/telemetry/*`
- `ui/hud_qml/*`, `ui/quick_panel/*`
- `tests/*`
- `reports/*` generated artifacts

### Test Gates

- Stable pass rate across composite integration scenarios.
- No regressions in IPC + HUD + telemetry core path.
- Acceptable performance envelope for daily multi-project usage.

### Rollback

- Keep phase changes behind small toggles where possible.
- Preserve phase A stable baseline as recovery profile.

## Priority Order

1. Stabilize (must-have)
2. Harden (high-value reliability)
3. Scale (throughput and product velocity)
