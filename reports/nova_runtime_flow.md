# Nova Runtime Flow

Generated: 2026-02-18

## 1) Canonical Control Plane

Single canonical runtime entrypoint:

- `main.py`

Command routing:

- `main.py hud` -> `ui.hud_qml.app_qml.main`
- `main.py whatsapp` -> `ui.quick_panel.app.main`
- `main.py chat` -> `ui.chat.app.ChatWindow`
- `main.py dashboard` -> `ui.dashboard.app.DashboardWindow`
- `main.py core` -> local IPC servers + `NovaCoreService`
- `main.py call` -> one-off IPC client operation
- `main.py cli` -> interactive tool CLI

## 2) Compatibility Layer

Legacy wrapper scripts now map to canonical commands:

- `run_hud_qml.py` -> `main.py hud`
- `run_quick_panel.py` -> `main.py whatsapp`
- `run_whatsapp.py` -> `main.py whatsapp`
- `run_chat.py` -> `main.py chat`
- `run_ui.py` -> `main.py dashboard`
- `run_core_service.py` -> `main.py core`
- `run_ipc_cli.py` -> `main.py call`

## 3) IPC Startup Flow

Autospawn path:

1. UI requests IPC via `ensure_core_running_with_events(...)`.
2. `core/ipc/spawn.py` probes existing core.
3. If unavailable, it spawns:
   - `python main.py core --host ... --port ... --events-port ...`
4. Health probe validates RPC.
5. Events subscription probe validates events channel.
6. UI client proceeds with `IpcClient` and `EventsClient`.

Key persisted runtime files:

- PID: `workspace/runtime/core_service_<port>.pid`
- Log: `workspace/runtime/core_service_<port>.log`
- Telemetry DB: `workspace/runtime/telemetry/nova_telemetry.sqlite3`

## 4) Chat/Data Flow (IPC Mode)

1. UI emits user text.
2. Routed mode wrapper may be applied.
3. `chat.send` is sent to `NovaCoreService.dispatch(...)`.
4. Service emits events (`thinking`, `progress`, `tool_start`, `tool_end`).
5. `ConversationalBrain` + `LLMRouter` resolve response/tool path.
6. Telemetry is recorded (`llm_calls`, `tool_calls`, optional `task_runs`).
7. Assistant response and updated state are returned to UI.

## 5) Non-IPC Flow

When `NH_IPC_ENABLED=0`:

- UI paths run in-process where supported.
- No dependency on spawned core service.
- Approval and policy enforcement still apply through local runner paths.

## 6) Provider Routing Flow

`LLMRouter.route(...)`:

1. Build candidate provider order.
2. Apply online policy decision.
3. If online disabled/blocked, return local/offline guidance.
4. Execute provider tool through runner with approval/policy gates.
5. Record telemetry metrics:
   - input/output tokens (estimated)
   - latency
   - status/error kind
   - provider/model/profile/mode

## 7) Verification Evidence (current)

Manual check performed:

- `python main.py core --port <port>` starts successfully.
- `python main.py call --op health.ping --port <port>` returns valid JSON.
- `python main.py call --op doctor.report --port <port>` returns valid JSON.

Targeted tests passed after IPC fix:

- `tests/test_ipc_autospawn.py`
- `tests/test_hud_qml_v2_offscreen_ironman.py`
- `tests/test_main_dispatch.py`
- `tests/test_ipc_server_health.py`
- `tests/test_ipc_chat_send_smoke.py`

## 8) Runtime Failure Points (observed + expected)

Observed fixed issue:

- Autospawn referenced a missing root script (`run_core_service.py`) in release snapshot.

Remaining operational failure points:

- Missing optional local dependencies (voice/CAD/3D) degrade feature coverage.
- Misconfigured local model backends can cause provider failures.
- Stale docs/scripts in release snapshots can drift from runtime truth.
