# UI-0.1 Iron-Man Theme + Palette + Status Pill + Execution Chips (V2)

## Scope Completed
- Implemented V2-only UI path behind `NH_UI_V2=1`.
- Kept legacy HUD path unchanged when `NH_UI_V2` is unset/`0`.
- Added shared amber/gold theme tokens in `ui/common_ui/Theme.qml`.
- Added V2 components and integration in `ui/hud_qml_v2`.
- Added quick panel V2 shell reusing theme + command palette in `ui/quick_panel_v2/MainV2.qml`.
- Added V2 offscreen smoke test.

## Theme Tokens (Amber/Gold)
Defined in `ui/common_ui/Theme.qml`:
- `bgGlass`, `bgSolid`
- `textPrimary`, `textSecondary`, `textMuted`
- `accentPrimary`, `accentSecondary`, `accentSoft`
- `borderSoft`, `borderHard`
- `dangerMuted`, `successMuted`
- `glowSoft`, `glowStrong`
- `radiusSm`, `radiusMd`, `radiusLg`
- `animFastMs=120`, `animMedMs=180`

Visual direction (screenshot-free):
- Dark metallic base with warm amber/copper borders and restrained glow.
- Chat glass surfaces use low-alpha dark amber overlays.
- Accent is used on outlines/highlights/chips, not as large fills.
- Text hierarchy uses cream primary, muted bronze secondary.

## Command Palette (Ctrl+K)
Implemented in `ui/hud_qml_v2/components/CommandPalette.qml` and wired in `ui/hud_qml_v2/MainV2.qml`.

Keyboard:
- `Ctrl+K`: open/close
- `Esc`: close
- `Up/Down`: navigate
- `Enter`: execute selected command

Command list (static registry):
- Switch Mode: `general`
- Switch Mode: `build_software`
- Switch Mode: `gen_3d_step`
- Switch Mode: `gen_2d_dxf`
- Open Drawer: `Tools`
- Open Drawer: `Attach`
- Open Drawer: `Health`
- Open Drawer: `History`
- Run Doctor Report
- Toggle IPC enabled hint

Execution behavior:
- Mode commands call `hudController.setTaskMode(...)`.
- Drawer commands set local drawer state.
- Doctor command calls `hudController.refreshHealthStats()` when IPC appears enabled.
- If IPC is disabled, toast shows `IPC disabled`.
- Toggle IPC hint is read-only UI state (no core mutation).

## Status Pill State Machine
Implemented in `ui/hud_qml_v2/components/StatusPill.qml` and integrated above composer via `ChatPane.qml`.

States:
- `idle`
- `thinking`
- `running`
- `done`
- `error`

Heuristic transitions (UI-only):
- On send: `thinking`
- On assistant message with tool-like trace (`patch.plan`, `patch.apply`, `verify`, `tool`): `running` briefly, then `done`
- On assistant response without tool trace: `done`
- Done timer returns to `idle`
- If waiting and status text includes fail/error: `error` then auto-return to `idle` after 2s

## Execution Chips
Implemented in `ui/hud_qml_v2/components/ExecutionChips.qml` and rendered only in assistant bubbles (`MessageBubble.qml`).

Fields:
- `Mode`
- `Provider`
- `Tool`
- `Latency`

Fallback behavior:
- Prefer `meta` values if available.
- Mode fallback: current selected mode (`currentTaskMode`).
- Provider fallback: infer from message text tokens (`DeepSeek`, `Gemini`, `OpenAI`).
- Tool fallback: infer from message text tokens (`patch.plan`, `patch.apply`, `verify`, `security.audit`).
- Latency shown only when `latency_ms` exists.
- Chips hidden when no meaningful values are available.

## Files Added/Updated
- Added: `ui/common_ui/Theme.qml`
- Added: `ui/hud_qml_v2/MainV2.qml`
- Added: `ui/hud_qml_v2/components/CommandPalette.qml`
- Added: `ui/hud_qml_v2/components/StatusPill.qml`
- Added: `ui/hud_qml_v2/components/ExecutionChips.qml`
- Added: `ui/hud_qml_v2/components/Toast.qml`
- Added: `ui/hud_qml_v2/components/Composer.qml`
- Added: `ui/hud_qml_v2/components/MessageBubble.qml`
- Added: `ui/hud_qml_v2/components/ChatPane.qml`
- Added: `ui/quick_panel_v2/MainV2.qml`
- Updated: `ui/hud_qml/app_qml.py` (`NH_UI_V2` path routing)
- Added test: `tests/test_hud_qml_v2_offscreen_ironman.py`

## Commands Run + Results
1. Preflight baseline:
- Command: `pytest -q -p no:cacheprovider`
- Result: failed in current environment with permissions (Temp/workspace access), `33 failed, 32 passed, 28 errors`.

2. V2 offscreen HUD gate:
- Command:
  - `QT_QPA_PLATFORM=offscreen`
  - `NH_HUD_AUTOCLOSE_MS=200`
  - `NH_UI_V2=1`
  - `python run_hud_qml.py`
- Result: exit code `0`.

3. Legacy HUD sanity gate:
- Command:
  - `QT_QPA_PLATFORM=offscreen`
  - `NH_HUD_AUTOCLOSE_MS=200`
  - `NH_UI_V2` unset
  - `python run_hud_qml.py`
- Result: exit code `0`.

4. Focused V2 smoke:
- Command: `pytest -q -p no:cacheprovider tests/test_hud_qml_smoke.py tests/test_hud_qml_v2_offscreen_ironman.py`
- Result: V2 test passed; legacy smoke failed due existing Temp permission issue.

5. Full suite after changes:
- Command: `pytest -q -p no:cacheprovider`
- Result: still blocked by same environment permission issue, `33 failed, 33 passed, 28 errors`.

## Future Hook
Status pill and execution chips are intentionally event-ready. When Pro-3 streaming events are surfaced to QML, the current UI state/chip API can be driven directly by live event metadata without structural UI changes.