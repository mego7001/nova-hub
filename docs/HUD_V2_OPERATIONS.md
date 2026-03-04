# HUD V2 Operations Map

## Launch and Selection

- Canonical command: `python main.py hud`
- Explicit UI selection: `python main.py hud --ui auto|v2|v1`
- Environment selection: `NH_UI_VERSION=auto|v2|v1`
- Legacy compatibility: `NH_UI_V2=1`
- Unified Shell V3 is now default for V2.
- Rollback selector: `NH_UI_SHELL_V3=0` (loads compatibility wrapper path).
- Emergency legacy quick-panel path: `NH_UI_LEGACY_WHATSAPP=1` with `python main.py whatsapp`.
- Visual effects profile: `NH_UI_EFFECTS_PROFILE=high_effects|balanced|degraded` (default: `high_effects`).
- Theme variant: `NH_UI_THEME_VARIANT=jarvis_cyan|amber_industrial` (default: `jarvis_cyan`).
- Motion intensity: `NH_UI_MOTION_INTENSITY=cinematic|normal|reduced` (default: `cinematic`).

## Composer Controls

| UI Control | QML Signal | Controller Slot | Effect |
|---|---|---|---|
| Attach | `attachRequested()` | `attachFiles(...)` via dialog | Attach files into chat/project context |
| Tools | `toolsRequested()` | `toggleToolsMenu()` | Open/close tools menu state |
| Mic On/Off | `voiceToggleRequested()` | `toggle_voice_enabled()` | Start/stop local voice loop |
| Mute/Unmute | `voiceMuteToggleRequested()` | `voice_mute()` / `voice_unmute()` | Toggle TTS mute state |
| Stop Voice | `voiceStopRequested()` | `voice_stop_speaking()` | Stop current spoken output |
| Replay | `voiceReplayRequested()` | `voice_replay_last()` | Replay last spoken assistant output |
| Voice | `voicePanelRequested()` | drawer switch (`voice`) | Open voice drawer panel |
| Send | `sendRequested(message)` | `send_message(message)` | Unified text boundary for local/IPC path |

## Top Controls (Frameless)

| UI Control | Binding | Effect |
|---|---|---|
| Minimize | `win._appMinimize()` | Minimize HUD window |
| Exit Menu | `⏻ Exit` | Opens menu with `Shutdown Nova` (default), `Exit HUD only`, and `Keep Ollama running` toggle |
| Shutdown Nova | `hudController.shutdownNova(...)` | Calls `system.shutdown`, watchdog-waits for IPC close, force-kills only returned core PID if needed, then closes HUD |
| Exit HUD only | `win._appClose()` | Close HUD window only |
| Close Nova | `win._appClose()` | Close HUD window only |
| Shortcut | `Ctrl+Q`, `Ctrl+W` | Close HUD window |

## Drawer Controls

| Drawer | Main Controls | Backend Binding |
|---|---|---|
| Tools | queue/confirm/reject apply, security audit, refresh timeline | `queue_apply()`, `confirm_pending()`, `reject_pending()`, `run_security_audit()`, `refresh_timeline()` |
| Attach | choose files, attach summary | `attachFiles(...)`, `attachLastSummary` |
| Health | refresh + doctor trigger + provider list | `refreshHealthStats()`, `healthStatsModel`, `healthStatsSummary` |
| History | timeline refresh + events list | `refresh_timeline()`, `timelineModel`, `timelineSummary`, `latestReplyPreview` |
| Voice | voice state/actions + input device selector | `voice*` properties/slots, `voice_input_devices()`, `set_voice_device(...)` |

## Command Palette Actions

- Mode switch: `switch_mode`
- Drawer open: `open_drawer`
- Doctor trigger: `run_doctor`
- Apply flow: `apply_queue`, `apply_confirm`, `apply_reject`
- Security: `security_audit`
- Timeline: `refresh_timeline`
- Voice: `voice_toggle`, `voice_mute_toggle`, `voice_stop`, `voice_replay`
- Window: `app_minimize`, `app_close`

## IPC and Tool Contracts

- IPC ops are unchanged and non-breaking:
  - `health.ping`
  - `chat.send`
  - `doctor.report`
  - `system.shutdown`
  - and the rest of existing `core/ipc/service.py` ops.
- Tool apply/security paths stay approval-gated via existing backend policy.
