# Phase 2 Inventory (General/Project Memory + TTL + Migration + Search)

## Existing baseline
- `IngestManager.ingest_general(chat_id, paths)` موجود.
- `IngestManager.ingest_project(project_id, paths)` موجود.
- Quotas policy موجودة في `core/ux/upload_policy.py`:
  - General: `25 files / 150MB / TTL 14 days`
  - Project: `200 files / 2GB / no TTL`
- Cleanup TTL موجود في `IngestManager.cleanup_general_storage()` ويعمل startup + post-ingest.
- Migration موجودة في `IngestManager.migrate_general_to_project(...)` لكن baseline كانت non-idempotent.

## Session identifiers across UIs
- HUD: `GENERAL_CHAT_ID="__general__"` أو `chat_*` أو `project_id`.
- Chat UI: `general_chat_id="chat_desktop_general"` أو `current_project_id`.
- Quick Panel/WhatsApp: `general_chat_id="chat_quick_panel_general"` أو `current_project_id`.

## Gaps identified before Phase 2 patches
1. migration تحتاج dedupe/idempotency guarantees.
2. TTL كان hardcoded بدل الرجوع لقيم policy الرسمية.
3. لا يوجد API موحّد search عبر `scope=general|project` مع pagination من خلال IPC.
