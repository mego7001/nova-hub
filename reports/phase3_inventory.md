# Phase 3 Inventory (Tools + Modes + Voice + Maintainability)

## Task modes / routing baseline
- Canonical modes: `general`, `build_software`, `gen_3d_step`, `gen_2d_dxf`.
- Wrapper/unwrap موجود في `core/ux/mode_routing.py`.
- Mode availability تعتمد على required tools في `core/ux/task_modes.py`.

## Tools catalog baseline
- بناء catalog في `core/ux/tools_catalog.py`.
- Metadata tool UX في `core/ux/tools_registry.py`.
- Badge baseline: `available`, `approval`, `unavailable` من policy فقط قبل صقل reasons.

## Voice baseline
- إدارة الصوت: `ui/hud_qml/managers/voice_manager.py`
- loop: `core/voice/voice_loop.py`
- providers: `faster-whisper`, `piper`, `pyttsx3`.
- UI controls موجودة في HUD v2 Voice drawer.

## Maintainability hotspots
- `ui/hud_qml/controller.py` (~3200 lines)
- `ui/quick_panel/app.py` (~3196 lines)
- `ui/chat/app.py` (~1263 lines)
