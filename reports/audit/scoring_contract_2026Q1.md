# Scoring Contract 2026Q1 (Report+Reality)

## Purpose
This contract defines what "100%" means for Nova Hub closure in this cycle.
The score is evidence-driven, not narrative-driven.

## Scoring Rubric (10/10 each axis)

1. Code Completeness
- `10/10` requires no open `critical/high` implementation gaps in release scope.
- Evidence: closed gap register items + runtime/compile checks.

2. Architecture Integrity
- `10/10` requires stable package/import structure and no unresolved packaging drift.
- Evidence: normalization manifest, compile/import smoke.

3. Security & Secrets Hygiene
- `10/10` requires no uncontrolled secret leakage path and clear env handling policy.
- Evidence: docs + ignore rules + doctor outputs where applicable.

4. UI Functional Readiness
- `10/10` requires active supported UI paths to run with wired backend flows.
- Evidence: runtime smoke for `hud`, `chat`, `dashboard`, `whatsapp`, `quick_panel_v2`.

5. Test Readiness
- `10/10` requires full acceptance pack pass and critical-path rerun stability.
- Evidence: pytest outputs + smoke outputs.

6. Documentation Fidelity
- `10/10` requires docs matching current runtime behavior (no stale contracts).
- Evidence: updated install/user docs + feature notes.

7. Release Readiness
- `10/10` requires strict gate pass and GO decision with reproducible evidence.
- Evidence: final scoring JSON + go/no-go decision report.

## Gate Rules

1. No "closed" finding without machine-verifiable evidence, explicit file reference, or test output.
2. `critical/high` findings can only be:
- `closed_by_fix`, or
- `closed_by_evidence` with direct contradictory proof in code/runtime.
3. `open` findings block full 100% scoring in their affected axis.
4. Overall 100% requires:
- All axes `10/10`
- No open `critical/high/medium` from the adopted register scope
- Acceptance pack stable across rerun.

## Evidence Minimum Schema

Each closure decision must carry:
- `id`
- `status`
- `owner`
- `evidence` (file paths and/or command outputs)
- `closure_criteria`
- `verification_command` (where applicable)

## Calculation

- Axis score: integer `[0..10]`, evidence-based.
- Final score: all axes must be `10`.
- If any axis < `10`, final status is `NO-GO`.
