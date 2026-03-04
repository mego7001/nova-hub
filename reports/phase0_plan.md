# Phase0 Plan (Decision-Complete)

Date: 2026-02-22
Scope: Windows stabilization + long-running robustness, no safety regression.

## Step Plan (14 steps)

1. Freeze baseline inventory and blocker map in `reports/phase0_inventory.md`.
2. Add `reports/phase0_plan.md` with exact files/tests/risks/checkpoints.
3. Patch A: add regression import tests for launch entrypoints and UI modules.
4. Patch A: keep runtime code unchanged unless a real import blocker appears.
5. Patch B: add `core/utils/optional_deps.py`:
   - `FeatureUnavailable`
   - `require(...) -> (ok, message)` or raise.
6. Patch B: integrate optional guards into voice stack:
   - `core/voice/audio_io.py`
   - `core/voice/providers/stt_faster_whisper.py`
7. Patch B: integrate optional guards into ingest parsers:
   - `core/ingest/parsers/image_parser.py`
   - `core/ingest/parsers/docx_parser.py`
   - `core/ingest/parsers/pdf_parser.py`
   - `core/ingest/parsers/xlsx_parser.py`
8. Patch B: integrate optional guards into CAD optional paths:
   - `core/cad_pipeline/step_generator.py`
   - `core/cad_pipeline/dxf_generator.py`
9. Patch B: guard `core/cad_pipeline/__init__.py` so missing `shapely` does not crash package import; fail controlled only when feature is used.
10. Patch B: add tests for guard utility and graceful-degradation behavior.
11. Patch C: add bounded JSONL helper `core/utils/jsonl_tail.py`.
12. Patch C: update `core/audit_spine.py` with bounded tail read + cursor paging API.
13. Patch C: update `ui/hud_qml/managers/chat_manager.py` to bounded message loading.
14. Run strict verification order and publish `reports/phase0_verification.md` with command outputs and pass/fail summary.

## Files expected to change

- Add:
  - `core/utils/optional_deps.py`
  - `core/utils/jsonl_tail.py`
  - `tests/test_entrypoints_import_clean.py`
  - `tests/test_optional_deps_guards.py`
  - `tests/test_ingest_optional_deps_graceful.py`
  - `tests/test_cad_optional_deps_graceful.py`
  - `tests/test_audit_spine_bounded_read.py`
  - `tests/test_audit_spine_cursor_paging.py`
  - `tests/test_chat_manager_bounded_log_read.py`
- Update:
  - `core/audit_spine.py`
  - `core/cad_pipeline/__init__.py`
  - `core/cad_pipeline/dxf_generator.py`
  - `core/cad_pipeline/step_generator.py`
  - `core/ingest/parsers/image_parser.py`
  - `core/ingest/parsers/docx_parser.py`
  - `core/ingest/parsers/pdf_parser.py`
  - `core/ingest/parsers/xlsx_parser.py`
  - `core/voice/audio_io.py`
  - `core/voice/providers/stt_faster_whisper.py`
  - `ui/hud_qml/managers/chat_manager.py`
  - `reports/phase0_inventory.md`
  - `reports/phase0_plan.md`
  - `reports/phase0_verification.md`

## Risk of breaking UX (and mitigations)

1. Timeline ordering drift after bounded reads.
- Mitigation: add deterministic ordering tests and keep oldest->newest within returned window.

2. Existing tests asserting specific error strings may fail.
- Mitigation: keep existing key phrases (`missing dependency`, dep name, install hint), update tests only where contract is intentionally improved.

3. CAD package import behavior may change if `shapely` is missing.
- Mitigation: keep import non-fatal at package level and fail only on feature usage with controlled error.

4. Voice device fallback path might regress.
- Mitigation: include `test_hud_controller_voice_device_slot.py` and `test_voice_manager_config_update.py` in targeted verification.

## Checkpoints and deliverables

- Checkpoint 0: `reports/phase0_inventory.md`
- Checkpoint 1: `reports/phase0_plan.md`
- Checkpoint 2 (Patch A): entrypoint import regression tests
- Checkpoint 3 (Patch B): optional dependency guard utility + integrations + tests
- Checkpoint 4 (Patch C): bounded timeline/log reading + stress/cursor tests
- Checkpoint 5: strict verification + `reports/phase0_verification.md`

## Commit intents (if git available)

- `fix(core): unblock entrypoints`
- `feat(core): optional dependency guards`
- `perf(core): bounded timeline/log reading`

Note: if no `.git` repository is present in current workspace, changes will be delivered without local commits.
