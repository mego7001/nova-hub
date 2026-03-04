# Pro-1 IPC Auto-Spawn Report

## Summary
Implemented a local IPC core service path for Nova with auto-spawn integration in HUD and Quick Panel, while preserving legacy in-process behavior when IPC is disabled.

- `NH_IPC_ENABLED=0` (default): existing single-process behavior remains active.
- `NH_IPC_ENABLED=1`: HUD and Quick Panel ensure core service availability, then route chat through local IPC (`127.0.0.1` only).

## Files Added

- `core/ipc/__init__.py`
- `core/ipc/protocol.py`
- `core/ipc/server.py`
- `core/ipc/client.py`
- `core/ipc/health.py`
- `core/ipc/service.py`
- `core/ipc/spawn.py`
- `run_core_service.py`
- `run_ipc_cli.py`
- `tests/test_ipc_server_health.py`
- `tests/test_ipc_autospawn.py`
- `tests/test_ipc_chat_send_smoke.py`

## Files Changed

- `ui/hud_qml/controller.py`
  - Added IPC configuration and startup path.
  - Added IPC chat reply branch (`chat.send`) behind `NH_IPC_ENABLED`.
- `ui/quick_panel/app.py`
  - Added IPC configuration and startup path.
  - `_send_message` now uses IPC when enabled; legacy local execution kept when disabled.

## How To Run

### Manual core service

```powershell
python run_core_service.py --host 127.0.0.1 --port 17840
```

Optional token:

```powershell
set NH_IPC_TOKEN=your-token
python run_core_service.py --host 127.0.0.1 --port 17840
```

### Auto-spawn via HUD / Quick Panel

```powershell
set NH_IPC_ENABLED=1
python run_hud_qml.py
```

```powershell
set NH_IPC_ENABLED=1
python run_quick_panel.py
```

### One-off IPC CLI

```powershell
set NH_IPC_ENABLED=1
python run_ipc_cli.py "hello nova" --mode general
```

## Verification

### Compile

```powershell
$files = Get-ChildItem core/ipc -Filter *.py | ForEach-Object { $_.FullName }; $files += (Resolve-Path run_core_service.py).Path; python -B -m py_compile $files
python -B -m py_compile ui/quick_panel/app.py ui/hud_qml/controller.py run_ipc_cli.py
```

Result: pass.

### IPC tests

```powershell
pytest -q tests/test_ipc_server_health.py tests/test_ipc_autospawn.py tests/test_ipc_chat_send_smoke.py -p no:cacheprovider
```

Result: `3 passed`.

### Full regression

```powershell
pytest -q -p no:cacheprovider
```

Result: `85 passed, 129 warnings`.

### Smoke

```powershell
python scripts/smoke_test.py
```

Result: `smoke_status: PASS`, `tools_loaded: 33`.

### HUD offscreen with IPC

```powershell
$env:QT_QPA_PLATFORM='offscreen'; $env:NH_HUD_AUTOCLOSE_MS='200'; $env:NH_IPC_ENABLED='1'; python run_hud_qml.py
```

Result: exit code `0`.

## Known Limitations (v1)

- Local-only transport is enforced (`127.0.0.1`); no remote/LAN mode.
- Shared token (`NH_IPC_TOKEN`) is optional in v1; if set, handshake enforces match.
- Event streaming is protocol-ready, but clients currently use request/response calls only.
- UI currently routes chat over IPC; deeper tool/progress event streaming can be expanded in next phase.
