# Nova Capability Map

Generated: 2026-02-18
Scope root: `D:\nouva hub\nova_hub_v1_release\nova_hub`

## 1) Inventory Snapshot

- Total scoped files (`core|integrations|ui|scripts|tests|configs|docs`): `661`
- Python files: `231`
- QML files: `32`
- Enabled tools (from `reports/tools_index.json`): `36`
- IPC operations: `11` (`health.ping`, `tools.list`, `projects.list`, `projects.open`, `approvals.respond`, `chat.send`, `conversation.history.get`, `telemetry.scoreboard.get`, `telemetry.provider.stats`, `doctor.report`, `selector.pick_provider`)

## 2) Runtime Surface

Canonical entrypoint:

- `main.py`

Supported runtime commands:

- `python main.py hud`
- `python main.py whatsapp`
- `python main.py chat`
- `python main.py dashboard`
- `python main.py core --host ... --port ...`
- `python main.py call --op ...`
- `python main.py cli --list-tools`

Compatibility wrappers (thin pass-through):

- `run_hud_qml.py`
- `run_quick_panel.py`
- `run_whatsapp.py`
- `run_chat.py`
- `run_ui.py`
- `run_core_service.py`
- `run_ipc_cli.py`

## 3) Tooling Capabilities (36 tools)

Tool groups by count:

- `fs_write`: 12
- `process_exec`: 7
- `fs_read`: 7
- `git`: 3
- `media_gen`: 2
- `openai`: 1
- `deepseek`: 1
- `gemini`: 1
- `ollama`: 1
- `telegram`: 1

High-value tool clusters:

- Build/change pipeline:
  - `project.scan_repo`
  - `repo.search`
  - `patch.plan`
  - `patch.apply`
  - `verify.smoke`
  - `pipeline.run`
- CAD + geometry:
  - `cad.dxf.generate`
  - `cad.step.generate`
  - `sketch.parse|apply|export_dxf`
  - `nesting.solve_rectangles`
  - `conical.generate_helix`
  - `halftone.generate_pattern`
- AI providers:
  - `openai.chat`
  - `gemini.prompt`
  - `deepseek.chat`
  - `ollama.chat`
- Runtime/system:
  - `run.preview`
  - `run.stop`
  - `desktop.open_*`
  - `git.status|diff|commit`
- Media/voice:
  - `stable_diffusion.generate|upscale`
  - `voice.stt_record|voice.tts_speak`

## 4) Core Subsystem Map

Top modules by Python LOC:

- `core/cad_pipeline` ~3052 lines
- `core/ipc` ~1625 lines
- `core/chat` ~1233 lines
- `core/voice` ~1133 lines
- `core/engineering` ~1115 lines
- `core/geometry3d` ~983 lines
- `core/ux` ~846 lines
- `core/security` ~746 lines
- `core/telemetry` ~735 lines
- `core/ingest` ~714 lines

Subsystem role summary:

- `core/ipc/*`: local RPC/event transport, autospawn, service dispatch, health.
- `core/llm/*`: provider routing, online/offline decision, weighted selector.
- `core/permission_guard/*`: policy + approval gating.
- `core/telemetry/*`: SQLite schema, recorders, provider/tool stats and scoreboards.
- `core/conversation/*`: intent parsing, response orchestration.
- `core/chat/*`: high-level project conversation orchestration and actions.
- `core/engineering/*`: extraction, materials/loads/tolerances logic, reports.
- `core/sketch/*`: parser/store/render/export for 2D sketch.
- `core/geometry3d/*`: 3D intent parsing and artifact flow.
- `core/cad_pipeline/*`: CAD output generation and adapters.

## 5) UI Capability Map

- `ui/hud_qml/*`: primary UI, IPC integration, timeline, approvals, project/session handling.
- `ui/quick_panel/*`: legacy UX with IPC support and voice controls.
- `ui/chat/*`: standalone chat desktop window.
- `ui/dashboard/*`: legacy dashboard UI path.
- `ui/hud_qml_v2/*.qml`: v2 visual layer experiments.

## 6) External Dependencies

Base:

- `pyyaml`
- `requests`

UI:

- `PySide6`

CAD:

- `ezdxf`
- `shapely`
- `numpy`

3D optional:

- `cadquery`
- `pyvista`

Voice optional:

- `faster-whisper`
- `sounddevice`
- `pyttsx3`

## 7) Capability Boundaries

Strong:

- Local IPC service + event stream.
- Approval-gated tool execution.
- Multi-domain tooling (software + CAD + sketch + voice + media).
- Telemetry-based provider scoring.

Current boundaries:

- Some features rely on optional local binaries/models (`piper`, local LLM server, optional CAD deps).
- Release snapshots may include historical docs that lag behind current runtime entrypoints.
