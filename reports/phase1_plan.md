# Phase 1 Plan (Execution)

## Scope
1. Add PPTX support end-to-end in ingest.
2. Unify attach summary contract across HUD/chat/whatsapp(quick panel).
3. Harden ZIP extraction with policy-driven deterministic rejections.

## Modules to change
- `core/ingest/file_types.py`
- `core/ingest/parsers/pptx_parser.py` (new)
- `core/ingest/ingest_manager.py`
- `core/ingest/summary_contract.py` (new)
- `core/ingest/zip_policy.py` (new)
- `core/ingest/unzip.py`
- `ui/chat/app.py`
- `ui/quick_panel/app.py`
- `ui/hud_qml/controller.py`
- `requirements-base.txt`

## UI wiring
1. Keep existing attach buttons and routing unchanged.
2. Standardize summary rendering from one normalized schema:
   - `accepted/rejected` counts
   - deterministic reject previews
   - same summary sentence across all UIs.

## Summary payload schema (target)
- Top-level:
  - `status`, `target`, `scope_id`, `batch_id`
  - `accepted[]`, `rejected[]`
  - `counts`, `errors`, `ttl_cleanup`, `ttl_cleanup_after`
- `accepted[]` fields:
  - `path`, `stored_path`, `type`, `size`, `doc_id`
  - `extracted_text_path`, `ocr_status`, `index_status`
  - `source_zip`, `zip_member`
- `rejected[]` fields:
  - `path`, `reason`, `reason_code`
- `counts` fields:
  - `files_ingested`, `files_extracted`, `accepted`, `rejected`, `keys_imported`
  - `zip_members`, `ocr_ok`, `ocr_empty`, `ocr_missing_dependency`, `ocr_error`

## Test plan
1. Parser:
   - `test_pptx_parser_extracts_text.py`
2. Ingest dispatch:
   - `test_ingest_accepts_pptx.py`
3. Summary contract:
   - `test_attach_summary_semantics.py`
4. ZIP policy:
   - `test_unzip_policy_limits.py`
   - `test_unzip_policy_reasons_deterministic.py`
