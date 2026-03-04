# Nova Hub v1 Map

## Default Run Commands

- Primary UI (HUD/QML): `python main.py hud`
- Legacy Dashboard UI: `python main.py dashboard`
- Standalone Chat UI: `python main.py chat`
- Legacy Quick Panel UI: `python main.py whatsapp`
- IPC Core Service: `python main.py core`
- IPC CLI Call: `python main.py call --op health.ping`
- List enabled tools: `python main.py cli --list-tools`

## Compatibility Wrappers

- `python run_hud_qml.py`
- `python run_quick_panel.py`
- `python run_whatsapp.py`
- `python run_chat.py`
- `python run_ui.py`
- `python run_core_service.py`
- `python run_ipc_cli.py`

## Core Subsystems

- Plugin engine:
  - `core/plugin_engine/loader.py`
  - `core/plugin_engine/registry.py`
  - `core/plugin_engine/manifest.py`
- Permissions/approvals:
  - `core/permission_guard/tool_policy.py`
  - `core/permission_guard/approval_flow.py`
  - `configs/tool_policy.yaml`
  - `configs/approvals.yaml`
- IPC:
  - `core/ipc/protocol.py`
  - `core/ipc/spawn.py`
  - `core/ipc/server.py`
  - `core/ipc/client.py`
  - `core/ipc/service.py`
- LLM/selector:
  - `core/llm/router.py`
  - `core/llm/selector.py`
  - `core/llm/selection_policy.py`
  - `configs/llm_routing.yaml`

## Artifacts and Logs

- `reports/`: analysis, verification, QA, catalog outputs
- `patches/`: generated diffs
- `outputs/`: generated artifacts
- `releases/`: release bundles and rollback snapshots
- `logs/`: runtime logs
- `workspace/runtime/telemetry/nova_telemetry.sqlite3`: telemetry db
