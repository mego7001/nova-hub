# Phase 1 Verification

## A) Compile check
```bash
python -B -m py_compile \
  nova_hub/core/ingest/file_types.py \
  nova_hub/core/ingest/parsers/pptx_parser.py \
  nova_hub/core/ingest/summary_contract.py \
  nova_hub/core/ingest/zip_policy.py \
  nova_hub/core/ingest/unzip.py \
  nova_hub/core/ingest/ingest_manager.py \
  nova_hub/ui/chat/app.py \
  nova_hub/ui/quick_panel/app.py \
  nova_hub/ui/hud_qml/controller.py
```
- Result: `PASS`

## B) Targeted tests
```bash
pytest -q \
  nova_hub/tests/test_pptx_parser_extracts_text.py \
  nova_hub/tests/test_ingest_accepts_pptx.py \
  nova_hub/tests/test_attach_summary_semantics.py \
  nova_hub/tests/test_unzip_policy_limits.py \
  nova_hub/tests/test_unzip_policy_reasons_deterministic.py \
  nova_hub/tests/test_ingest_manager_unified.py \
  -p no:cacheprovider
```
- Result: `9 passed`

## C) Full suite
```bash
pytest -q -p no:cacheprovider
```
- Result: `220 passed`

## D) Offscreen HUD smoke
- Not required in this phase (no QML file modifications).
