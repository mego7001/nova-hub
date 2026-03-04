# Run Guide

## Quick Start

1. Launch HUD (auto selector):
   - `python main.py hud`
   - `python main.py hud --ui auto|v2|v1`
2. Launch other UIs:
   - `python main.py whatsapp`
   - `python main.py chat`
   - `python main.py dashboard`
3. Launch core and test IPC:
   - `python main.py core`
   - `python main.py call --op health.ping`

## UI Version Selection

- Priority:
  - CLI `--ui` has highest priority.
  - `NH_UI_VERSION` is second.
  - default is `auto`.
- `auto` behavior:
  - try `ui/hud_qml_v2/MainV2.qml`
  - if load fails, fallback to `ui/hud_qml/qml/Main.qml`
- Legacy compatibility env:
  - `NH_UI_V2=1` still forces v2 selection when `NH_UI_VERSION` is not set.

## Compatibility Wrappers

- `python run_hud_qml.py`
- `python run_quick_panel.py`
- `python run_whatsapp.py`
- `python run_chat.py`
- `python run_ui.py`
- `python run_core_service.py`
- `python run_ipc_cli.py`

## IPC Operations

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

## Routing Debug

Use routing diagnostics with `chat.send`:

```powershell
python main.py call --op chat.send --debug-routing "hello"
```

## Non-IPC Mode

- Set `NH_IPC_ENABLED=0` to run supported UI logic without IPC startup dependency.

## Security and Budget

- Online providers are approval-gated.
- Optional token budgets:
  - `NH_SESSION_TOKEN_BUDGET`
  - `NH_DAILY_TOKEN_BUDGET`
