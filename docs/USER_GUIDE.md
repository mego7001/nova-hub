# Nova Hub v1 Final User Guide

## Launch

- Canonical launcher (HUD): `python main.py hud`
- Unified default (HUD): `python main.py`
- HUD selector: `python main.py hud --ui auto|v2|v1`
- Quick Panel (default V3 compact): `python main.py whatsapp`
- Quick Panel V3 compact (explicit): `python main.py quick_panel_v2`
- Standalone chat UI: `python main.py chat`
- Legacy dashboard UI: `python main.py dashboard`
- IPC core service: `python main.py core`
- One-off IPC call: `python main.py call --op health.ping`

Compatibility wrappers stay supported:

- `python run_hud_qml.py`
- `python run_quick_panel.py`
- `python run_quick_panel_v2.py`
- `python run_whatsapp.py` (legacy emergency path)
- `python run_chat.py`
- `python run_ui.py`
- `python run_core_service.py`
- `python run_ipc_cli.py`

## HUD Policy

- Default policy is `auto`: try `HUD v2` first, then fallback to `HUD v1` if v2 load fails.
- UI version priority:
  - CLI: `--ui auto|v2|v1`
  - ENV: `NH_UI_VERSION=auto|v2|v1`
  - Default: `auto`
- Legacy env `NH_UI_V2=1` is still supported for compatibility.
- Unified Shell V3 is default for V2 surfaces.
- Rollback selector: `NH_UI_SHELL_V3=0` (loads compatibility wrapper path).
- Emergency legacy quick-panel path: `NH_UI_LEGACY_WHATSAPP=1` with `python main.py whatsapp`.
- Visual effects profile: `NH_UI_EFFECTS_PROFILE=high_effects|balanced|degraded` (default: `high_effects`).
- Theme variant: `NH_UI_THEME_VARIANT=jarvis_cyan|amber_industrial` (default: `jarvis_cyan`).
- Motion intensity: `NH_UI_MOTION_INTENSITY=cinematic|normal|reduced` (default: `cinematic`).

## HUD v2 Command Bar + Voice

- Composer controls:
  - `Attach`
  - `Tools`
  - `Mic On/Off`
  - `Mute/Unmute`
  - `Stop Voice`
  - `Replay`
  - `Voice` (opens voice drawer)
  - `Send`
- Voice controls call existing `hudController` slots:
  - `toggle_voice_enabled`
  - `voice_mute` / `voice_unmute`
  - `voice_stop_speaking`
  - `voice_replay_last`
  - `set_voice_device`

Top controls in HUD v2 (frameless mode):

- `Minimize` button
- `Close Nova` button
- `Ctrl+Q` / `Ctrl+W` close shortcuts
- Close behavior is `UI-only` (does not stop external `main.py core` service).

## HUD v2 Drawers

- `Tools`: tools badge, apply queue/confirm/reject, security audit, timeline refresh.
- `Attach`: file attach dialog + attach summary.
- `Health`: health summary + provider list + doctor/refresh actions.
  - Includes `Local LLM: Ollama` status, model list refresh, and session model override.
- `History`: timeline summary + events list + latest reply preview.
- `Voice`: status, device picker, transcript/spoken preview, and full voice actions.
- Header capabilities ribbon shows: `Chat | Tools | Attach | Health | History | Voice | Security | Timeline`.

## IPC Quick Checks

- Start core: `python main.py core --port 17840`
- Health: `python main.py call --op health.ping --port 17840`
- Doctor: `python main.py call --op doctor.report --port 17840`
- Routing debug (chat.send): `python main.py call --op chat.send --debug-routing "hello"`

## LLM Routing Controls

- Routing policy file: `configs/llm_routing.yaml`
- Local-first policy:
  - `router.local_first: true`
  - `router.external_backup_only: true`
  - Local Ollama is attempted first; external providers are backup only.
- Task model mapping (Hybrid):
  - `conversation` -> `gemma3:4b`
  - `summarize_docs` -> `gemma3:4b`
  - `deep_reasoning` -> `qwen2.5-coder:7b-instruct`
  - `gen_2d_dxf`/`gen_3d_step` -> `qwen2.5-coder:7b-instruct`
  - `build_software`/`patch_planning` -> `qwen2.5-coder:7b-instruct`
  - `vision` -> `llava`
- Runtime env flags:
  - `NH_OLLAMA_ENABLED`
  - `NH_OLLAMA_BASE_URL`
  - `NH_OLLAMA_DEFAULT_MODEL_GENERAL`
  - `NH_OLLAMA_DEFAULT_MODEL_CODE`
  - `NH_OLLAMA_MODEL_OVERRIDE`
- Optional budget guards:
  - `NH_SESSION_TOKEN_BUDGET`
  - `NH_DAILY_TOKEN_BUDGET`
- `0` means no limit.

## Ollama IPC Ops

- Health: `python main.py call --op ollama.health.ping`
- Models: `python main.py call --op ollama.models.list`
- Chat debug: `python main.py call --op ollama.chat --payload-json "{\"prompt\":\"hello\"}"`
