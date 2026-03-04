# Nova Test Coverage Map

Generated: 2026-02-18

## 1) Test Suite Snapshot

- Test files in `tests/`: `52`
- Heaviest groups by filename prefix:
  - `hud*`: 17
  - `ipc*`: 6
  - `ux*`: 5
  - `telemetry*`: 2
  - other domain-specific tests: CAD/chat/voice/selector/project/plugin/main/jobs/ingest/system/session/etc.

## 2) Coverage by Subsystem

### Runtime and Dispatch

- `tests/test_main_dispatch.py`
- Covers command dispatch and filtered tool argument behavior.

### IPC Layer

- `tests/test_ipc_server_health.py`
- `tests/test_ipc_autospawn.py`
- `tests/test_ipc_chat_send_smoke.py`
- `tests/test_ipc_chat_emits_events.py`
- `tests/test_ipc_events_channel_basic.py`
- `tests/test_ipc_reconnect_respawn.py`

Coverage focus:

- health ping
- autospawn/startup
- RPC roundtrip
- events channel
- reconnect behavior

### HUD / UI Wiring

- `tests/test_hud_qml_smoke.py`
- `tests/test_hud_qml_models.py`
- `tests/test_hud_qml_controller.py`
- `tests/test_hud_qml_general_chat.py`
- `tests/test_hud_qml_palette.py`
- `tests/test_hud_qml_v2_offscreen_ironman.py`
- and other HUD QML wiring tests

Coverage focus:

- model wiring
- controller actions
- offscreen launch smoke
- quick UX integration paths

### Telemetry / Selector

- `tests/test_telemetry_db_migrations.py`
- `tests/test_telemetry_record_and_query.py`
- `tests/test_selector_weighted_deterministic.py`

Coverage focus:

- SQLite schema init/migration behavior
- recorder/query correctness
- provider pick determinism

### Security / Gating

- `tests/test_gating.py`
- `tests/test_doctor_report.py`
- `tests/test_project_manager_security.py`

Coverage focus:

- approval and policy guardrails
- doctor report structure
- project path safety

### Domain Features

- CAD/geometry/sketch/pattern tests
- voice loop tests
- ingest manager tests
- patch pipeline integrity tests

## 3) Verification Executed for IPC Stabilization

Command run:

```powershell
pytest -q tests/test_ipc_autospawn.py tests/test_hud_qml_v2_offscreen_ironman.py tests/test_main_dispatch.py tests/test_ipc_server_health.py tests/test_ipc_chat_send_smoke.py -p no:cacheprovider
```

Result:

- `6 passed`
- `1 warning` (datetime deprecation, non-blocking)

## 4) Manual Runtime Checks Executed

- `python main.py core --port <port>` -> core starts.
- `python main.py call --op health.ping --port <port> --payload-json '{}'` -> valid health JSON.
- `python main.py call --op doctor.report --port <port> --payload-json '{}'` -> valid report JSON.

## 5) Remaining Coverage Gaps

1. Wrapper parity tests:
   - No dedicated tests that all compatibility wrappers execute expected canonical command.
2. Docs command validation:
   - No automated test that every documented launch command is executable.
3. Full matrix integration:
   - Limited end-to-end tests combining HUD + IPC + provider tool + apply/verify chain in a single flow.

## 6) Recommended Additional Test Gates

1. `test_entrypoint_wrappers.py`:
   - Validate `run_*.py` wrappers route to the right `main.py` command.
2. `test_docs_launch_smoke.py`:
   - Parse docs launch snippets and run smoke `--help`/short execution.
3. `test_ipc_spawn_command_path.py`:
   - Assert spawn command uses `main.py core` and not stale script names.
