# NOVA Current Map

Generated: 2026-02-18

## 1) Active Runtime Entrypoints

- Canonical launcher: `main.py`
  - `python main.py hud` -> HUD selector (`auto` by default)
  - `python main.py hud --ui auto|v2|v1` -> explicit HUD variant
  - `python main.py whatsapp` -> Quick Panel (`ui/quick_panel/app.py`)
  - `python main.py chat` -> standalone chat UI (`ui/chat/app.py`)
  - `python main.py dashboard` -> legacy dashboard (`ui/dashboard/app.py`)
  - `python main.py core` -> IPC core service
  - `python main.py call ...` -> one-off IPC client call
  - `python main.py cli --list-tools` -> tool catalog
- Compatibility wrappers (thin pass-through to `main.py`):
  - `run_hud_qml.py`, `run_quick_panel.py`, `run_whatsapp.py`
  - `run_chat.py`, `run_ui.py`, `run_core_service.py`, `run_ipc_cli.py`

## 2) HUD UI Selection Policy

- Resolver location: `ui/hud_qml/app_qml.py`
- Resolution order:
  - CLI `--ui`
  - `NH_UI_VERSION`
  - default `auto`
- `auto` load order:
  - first `ui/hud_qml_v2/MainV2.qml`
  - fallback `ui/hud_qml/qml/Main.qml`
- Legacy compatibility:
  - `NH_UI_V2=1` still supported when `NH_UI_VERSION` is not set.

## 3) IPC Runtime Truth

- Autospawn source: `core/ipc/spawn.py`
- Spawn command: `python main.py core --host ... --port ... --events-port ...`
- Core service dispatch: `core/ipc/service.py`
- Supported ops:
  - `health.ping`
  - `tools.list`
  - `projects.list`
  - `projects.open`
  - `approvals.respond`
  - `chat.send`
  - `conversation.history.get`
  - `telemetry.scoreboard.get`
  - `telemetry.provider.stats`
  - `doctor.report`
  - `selector.pick_provider`

## 4) HUD v2 Capability Surface

- Composer:
  - attach/tools/mode/send
  - voice quick controls: mic, mute, stop, replay, panel open
- Drawers:
  - tools, attach, health, history, voice
- Voice wiring:
  - `toggle_voice_enabled`
  - `voice_mute` / `voice_unmute`
  - `voice_stop_speaking`
  - `voice_replay_last`
  - `voice_input_devices`
  - `set_voice_device`

## 5) LLM Routing and Selector

- Router: `core/llm/router.py`
- Selector: `core/llm/selector.py`
- Policy: `core/llm/selection_policy.py`
- Online decision: `core/llm/online_policy.py`
- Config source: `configs/llm_routing.yaml`
- Optional token budgets:
  - `NH_SESSION_TOKEN_BUDGET`
  - `NH_DAILY_TOKEN_BUDGET`

## 6) Runtime Artifacts

- PID: `workspace/runtime/core_service_<port>.pid`
- Log: `workspace/runtime/core_service_<port>.log`
- Telemetry DB: `workspace/runtime/telemetry/nova_telemetry.sqlite3`
- Reports: `reports/*`
