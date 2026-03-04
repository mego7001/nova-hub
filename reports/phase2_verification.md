# Phase 2 Verification

## A) Compile check
```bash
python -B -m py_compile \
  nova_hub/core/memory/__init__.py \
  nova_hub/core/memory/migration.py \
  nova_hub/core/memory/search_service.py \
  nova_hub/core/ingest/ingest_manager.py \
  nova_hub/core/ipc/service.py \
  nova_hub/ui/hud_qml/controller.py \
  nova_hub/tests/test_general_ttl_cleanup.py \
  nova_hub/tests/test_general_quota_enforcement.py \
  nova_hub/tests/test_migration_lossless.py \
  nova_hub/tests/test_migration_idempotent.py \
  nova_hub/tests/test_search_returns_expected_hits.py \
  nova_hub/tests/test_ipc_memory_search.py
```
- Result: `PASS`

## B) Targeted tests
```bash
pytest -q \
  nova_hub/tests/test_general_ttl_cleanup.py \
  nova_hub/tests/test_general_quota_enforcement.py \
  nova_hub/tests/test_migration_lossless.py \
  nova_hub/tests/test_migration_idempotent.py \
  nova_hub/tests/test_search_returns_expected_hits.py \
  nova_hub/tests/test_ipc_memory_search.py \
  -p no:cacheprovider
```
- Result: `6 passed`

## C) Full suite
```bash
pytest -q -p no:cacheprovider
```
- Result: `226 passed`

## D) Offscreen HUD smoke
- Not required in this phase (no QML file modifications).
