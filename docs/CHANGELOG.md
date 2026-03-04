# Changelog

## v1 Final Unification
- Set HUD/QML as default launch path via `main.py`.
- Added Quick Panel naming path (`ui/quick_panel`) with compatibility launcher `run_whatsapp.py`.
- Unified task modes to `general`, `build_software`, `gen_3d_step`, `gen_2d_dxf` with reversible routing wrapper.
- Added mode-aware tools metadata and deterministic `reports/tools_index.json` generation.
- Improved approval UX in desktop chat/quick panel with `Approve Once`, `Approve for Session`, `Deny`.
- Added canonical CAD package `core/cad_pipeline` and moved DXF/pattern core modules out of workspace-copy dependency.
- Added new tools: `cad.dxf.generate`, `cad.step.generate` (STEP tool degrades gracefully without optional dependency).
- Split dependencies into `requirements-base/ui/cad/3d/voice`.
- Added release and smoke scripts: `scripts/build_release.py`, `scripts/smoke_test.py`.

## Jarvis Core
- Added Jarvis Core disagreement protocol with a single clarifying question before changing direction.
- Added graduated warnings (levels 1-3) with documentary logging on proceed-anyway decisions.
- Added Recovery Mode messaging for verify/apply/pipeline/preview failures with a calm reminder after stabilization.
- Added per-project Jarvis state persistence (warnings, last disagreement, last outcome).
- Added `scripts/jarvis_core_qa.py` and QA reports in `reports/jarvis_core_qa.*`.

## Sketch
- Added 2D sketch parser, store, renderer, and DXF export.
- Added Sketch tab and chat preview/confirm flow.
- Added `scripts/sketch_qa.py` and QA reports in `reports/sketch_qa.*`.

## Voice
- Added offline-first voice recording and TTS integration with graceful degradation.
- Added mic button and speaker toggle in Quick Panel UI.
- Added `scripts/voice_qa.py` and QA reports in `reports/voice_qa.*`.

## Timeline
- Added per-project audit spine and Timeline tab with filters.
- Added `scripts/timeline_qa.py` and QA reports in `reports/timeline_qa.*`.

## Geometry 3D
- Added 3D intent parsing, preview panel, and STL export with confirm gating.
- Added preliminary geometry reasoning warnings and assumptions.
- Added `scripts/geometry3d_qa.py` and QA reports in `reports/geometry3d_qa.*`.

## Engineering Brain
- Added engineering intent extraction from chat/docs/repo with offline-first logic.
- Added materials library, loads/supports/tolerances models, rules engine, and risk scoring.
- Added Engineering panel with findings/assumptions and report generation.
- Added `scripts/engineering_qa.py` and QA reports in `reports/engineering_qa.*`.
