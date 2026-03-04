# Phase 3 Verification

## A) Compile check
```bash
python -B -m py_compile \
  nova_hub/core/ux/tools_registry.py \
  nova_hub/core/ux/tools_catalog.py \
  nova_hub/core/ux/task_modes.py \
  nova_hub/core/voice/schemas.py \
  nova_hub/core/voice/voice_loop.py \
  nova_hub/core/voice/readiness.py \
  nova_hub/core/ipc/service.py \
  nova_hub/ui/hud_qml/controller_core.py \
  nova_hub/ui/hud_qml/controller_ingest.py \
  nova_hub/ui/hud_qml/controller_tools.py \
  nova_hub/ui/hud_qml/controller_voice.py \
  nova_hub/ui/hud_qml/managers/voice_manager.py \
  nova_hub/ui/hud_qml/controller.py \
  nova_hub/ui/chat/app.py \
  nova_hub/ui/quick_panel/app.py
```
- Result: `PASS`

## B) Targeted tests
```bash
pytest -q \
  nova_hub/tests/test_tools_catalog_badges_and_reasons.py \
  nova_hub/tests/test_ux_tools_catalog.py \
  nova_hub/tests/test_auto_mode_fallback.py \
  nova_hub/tests/test_ux_task_modes.py \
  nova_hub/tests/test_ux_mode_routing.py \
  nova_hub/tests/test_mode_routing_reversibility.py \
  nova_hub/tests/test_voice_readiness.py \
  nova_hub/tests/test_voice_latency_metrics.py \
  nova_hub/tests/test_voice_push_to_talk_default.py \
  nova_hub/tests/test_voice_loop.py \
  nova_hub/tests/test_hud_controller_split_imports.py \
  nova_hub/tests/test_ipc_voice_readiness.py \
  -p no:cacheprovider
```
- Result: `PASS`

## C) Full suite
```bash
pytest -q -p no:cacheprovider
```
- Result: `239 passed`

## D) Offscreen smoke
```bash
pytest -q nova_hub/tests/test_hud_qml_v2_offscreen_ironman.py -p no:cacheprovider
pytest -q nova_hub/tests/test_quick_panel_v2_offscreen_smoke.py -p no:cacheprovider
```
- Result: `PASS`
