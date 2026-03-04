# HUD v2 Parity Gap Audit

Date: 2026-02-18
Scope: `ui/hud_qml_v2/*` vs current `HUDController` capability surface.

## Before

- Voice controls were available in `HUD v1` panel, but not directly present in `HUD v2` composer.
- `HUD v2` drawer set lacked a dedicated voice panel.
- `main.py hud` had no explicit `--ui` selector; runtime switching relied on legacy env path.

## Implemented in This Cycle

- Added voice quick controls to `ui/hud_qml_v2/components/Composer.qml`.
- Added signal forwarding through `ui/hud_qml_v2/components/ChatPane.qml`.
- Wired all voice actions into `ui/hud_qml_v2/MainV2.qml` using existing controller slots.
- Added full `voice` drawer in `ui/hud_qml_v2/MainV2.qml` with device picker + transcript/spoken previews.
- Expanded tools/health/history drawers to expose apply/security/timeline/doctor parity actions.
- Added canonical UI selector in `main.py` and `ui/hud_qml/app_qml.py`:
  - `python main.py hud --ui auto|v2|v1`
  - `NH_UI_VERSION=auto|v2|v1`
  - default `auto` with fallback behavior.

## Wiring Matrix

| Surface | UI Trigger | Wiring Target |
|---|---|---|
| Composer | Mic On/Off | `hudController.toggle_voice_enabled()` |
| Composer | Mute/Unmute | `hudController.voice_mute()` / `hudController.voice_unmute()` |
| Composer | Stop Voice | `hudController.voice_stop_speaking()` |
| Composer | Replay | `hudController.voice_replay_last()` |
| Composer | Voice Panel | `win._openDrawer(\"voice\")` |
| Voice Drawer | Device Select | `hudController.set_voice_device(...)` |
| Tools Drawer | Queue Apply | `hudController.queue_apply()` |
| Tools Drawer | Confirm/Reject | `hudController.confirm_pending()` / `hudController.reject_pending()` |
| Tools Drawer | Security Audit | `hudController.run_security_audit()` |
| Health Drawer | Refresh/Doctor | `hudController.refreshHealthStats()` |
| History Drawer | Refresh Timeline | `hudController.refresh_timeline()` |

## Remaining Gaps

- Doctor action currently uses `refreshHealthStats()` path (no separate explicit UI-level IPC op control).
- `HUD v2` visual layout is now feature-complete for core parity, but UX polish and density tuning can improve on narrow widths.
- End-to-end voice hardware validation remains environment-dependent and requires runtime QA on target machines.

## Acceptance Focus

- Voice buttons must be visible in `HUD v2` composer.
- Voice actions must mutate `voiceStatusLine` and related state.
- `main.py hud` defaults to selector mode and supports explicit override with `--ui`.
