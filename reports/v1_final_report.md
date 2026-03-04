# Nova Hub v1 Final Report

## Executive Summary

Nova Hub was hardened toward a v1 Final baseline with HUD-first launch, unified task modes/tools metadata, quick-panel naming cleanup, canonical CAD module relocation, and release/smoke automation. Safety/approval boundaries were preserved, and full test suite + HUD offscreen smoke passed.

## Included in This Update

### UI and UX Unification
- HUD remains primary entrypoint (`main.py` defaults to HUD).
- Quick Panel naming introduced (`ui/quick_panel`) with compatibility launcher `run_whatsapp.py`.
- Shared task modes standardized to:
  - `general`
  - `build_software`
  - `gen_3d_step`
  - `gen_2d_dxf`
- Mode routing remains through same message boundary (`[[NOVA_MODE ...]]` wrapper).
- Tools catalog now mode-aware and policy-aware with curated + advanced sections.

### Governance and Safety
- Approval UX improved in desktop chat and quick panel:
  - `Approve Once`
  - `Approve for Session`
  - `Deny`
- No bypass introduced for gated actions (`patch.plan`/`patch.apply` semantics preserved).

### Toolchain Catalog Closure
- Added `core/ux/tools_registry.py` as a source of truth for mode-tags and curated mappings.
- Added deterministic tools index generation:
  - `core/ux/tools_index.py`
  - `scripts/generate_tools_index.py`
  - output: `reports/tools_index.json`

### CAD / 2D / 3D Pipeline Progress
- Added canonical package: `core/cad_pipeline/`
  - migrated core DXF/pattern modules used by tests
  - tests now import canonical package (not workspace copy path)
- Added new tools:
  - `cad.dxf.generate` (local DXF generation)
  - `cad.step.generate` (local STEP generation with graceful optional dependency fallback)
- Added plugin:
  - `integrations/cad_pipeline/plugin.py`
  - `integrations/cad_pipeline/novahub.plugin.json`
  - enabled in `configs/plugins_enabled.yaml`

### Release Engineering and Install Matrix
- Added version file: `core/version.py`
- Added smoke script: `scripts/smoke_test.py`
- Added release builder: `scripts/build_release.py`
- Added split dependency files:
  - `requirements-base.txt`
  - `requirements-ui.txt`
  - `requirements-cad.txt`
  - `requirements-3d.txt`
  - `requirements-voice.txt`
- Added docs:
  - `docs/NOVA_V1_MAP.md` (updated)
  - `docs/INSTALL.md`
  - `docs/USER_GUIDE.md`
  - `docs/CHANGELOG.md` (updated)

## Verification Summary

### Compile
- `python -B -m py_compile` passed for all touched entrypoints/modules/scripts.

### Tests
- Targeted suites for UX/tools/CAD passed.
- Full suite passed:
  - `82 passed`

### HUD Smoke
- Offscreen smoke passed:
  - `QT_QPA_PLATFORM=offscreen`
  - `NH_HUD_AUTOCLOSE_MS=120`
  - `python run_hud_qml.py`

### Smoke and Release Scripts
- `python scripts/smoke_test.py` -> `PASS`
- `python scripts/build_release.py` produced:
  - `releases/nova_hub_1.0.0-final.zip`
- Extracted release sanity check:
  - `python main.py --help` from extracted archive returned success.

## Exclusions / Known Limitations

- `cad.step.generate` depends on optional `cadquery`; when unavailable it returns actionable error (no crash).
- Existing codebase still contains legacy `datetime.utcnow()` patterns (warnings only; functional behavior unchanged).

## Scope Notes

This update focused on stability and closure of core v1 paths while preserving no-regression behavior and existing approval invariants.

## P0 Closure Patch (v1.0.0-final)

### 1) Workspace-copy dependency removed from tests
- Canonical CAD behavior tests now import only from `core.cad_pipeline.*`.
- No `workspace/projects/.../working` test imports or path hacks are required for execution.

### 2) Modes hygiene finalized
- User-facing modes are now only:
  - `general`
  - `build_software`
  - `gen_3d_step`
  - `gen_2d_dxf`
- Legacy values (`auto`, `chat`, `deep_research`, `engineering`, `verify`, `sketch`) remain compatibility aliases through normalization only and are not exposed as UI mode options.

### 3) Quick Panel de-WhatsApp completed
- `ui/quick_panel/app.py` now contains the real implementation.
- `ui/whatsapp/app.py` is compatibility alias-only:
  - imports `QuickPanelWindow`
  - defines `WhatsAppWindow = QuickPanelWindow`
- `ui/quick_panel/widgets.py` is explicit (no wildcard re-export from `ui.whatsapp.widgets`).
- `run_whatsapp.py` remains a compatibility launcher alias for Quick Panel.

### Validation snapshot
- `python -B -m py_compile main.py run_hud_qml.py run_chat.py run_quick_panel.py run_whatsapp.py` passed.
- `pytest -q` passed (`82 passed`).
- `python scripts/smoke_test.py` passed.
