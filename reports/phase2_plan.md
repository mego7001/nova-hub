# Phase 2 Plan (Execution)

## Goals
1. تثبيت tiers General/Project بربط كامل مع policy الرسمية.
2. جعل migration lossless + idempotent.
3. إضافة search بسيط وموثوق على extracted text مع scope وpagination.

## Data layout
- General:
  - `workspace/chat/sessions/<chat_id>/docs`
  - `workspace/chat/sessions/<chat_id>/extracted`
  - `workspace/chat/sessions/<chat_id>/index.json`
- Project:
  - `workspace/projects/<project_id>/docs`
  - `workspace/projects/<project_id>/extracted`
  - `workspace/projects/<project_id>/index.json`
- Migration manifest:
  - `workspace/projects/<project_id>/migrations/general_<chat_id>.json`

## Cleanup schedule
1. عند إنشاء `IngestManager`.
2. قبل ingest_general.
3. بعد ingest_general.

## Modules targeted
- `core/ingest/ingest_manager.py`
- `core/memory/migration.py` (new)
- `core/memory/search_service.py` (new)
- `core/ipc/service.py`
- `ui/hud_qml/controller.py` (read-only search hook)

## Tests planned
- `test_general_ttl_cleanup.py`
- `test_general_quota_enforcement.py`
- `test_migration_lossless.py`
- `test_migration_idempotent.py`
- `test_search_returns_expected_hits.py`
- `test_ipc_memory_search.py`
