# Final UI Contract Matrix (Unified Shell V3)

## Scope
- `HUD v2` (`profile=full`)
- `QuickPanel v2` (`profile=compact`)
- Shared backend: `ui/hud_qml/controller.py`
- Shared panel library: `ui/hud_qml_v2/panels/*.qml`
- Shared shell components: `ui/hud_qml_v2/components/TopHeader.qml`, `ui/hud_qml_v2/components/DrawerSelector.qml`

## Capability Matrix

| Capability | Surface (full) | Surface (compact) | Binding | Acceptance Tests |
|---|---|---|---|---|
| Chat send/receive | `ChatPane` + Composer | `ChatPane` + Composer | `send_message()` | `tests/test_hud_qml_v2_runtime_controls.py`, `tests/test_quick_panel_v2_runtime_controls.py` |
| Tool approvals | Tools drawer + palette | Tools drawer + palette | `queue_apply()`, `confirm_pending()`, `reject_pending()` | `tests/test_hud_qml_v2_drawer_parity.py`, `tests/test_quick_panel_v2_runtime_controls.py` |
| Attach ingest summary | Attach drawer | Attach drawer | `attachFiles()` + `attachSummaryModel` | `tests/test_attach_summary_semantics.py`, `tests/test_quick_panel_v2_runtime_controls.py` |
| Health/doctor | Health drawer | Health drawer | `refreshHealthStats()` | `tests/test_hud_qml_v2_runtime_controls.py`, `tests/test_quick_panel_v2_runtime_controls.py` |
| Ollama health/models | Health drawer | Health drawer | `refreshOllamaModels()`, `setOllamaSessionModel()` | `tests/test_ollama_health.py`, `tests/test_ollama_models_list.py`, `tests/test_quick_panel_v2_runtime_search.py` |
| Timeline/history | History drawer | History drawer | `refresh_timeline()` + `timelineModel` | `tests/test_hud_qml_v2_drawer_parity.py`, `tests/test_quick_panel_v2_runtime_controls.py` |
| Memory search | History drawer | History drawer | `memorySearchPage()` | `tests/test_ipc_memory_search.py`, `tests/test_quick_panel_v2_runtime_search.py`, `tests/test_cross_ui_memory_search_semantics.py` |
| Voice controls/PTT | Voice drawer + composer mic | Voice drawer + composer mic | `toggle_voice_enabled()`, `voicePushStart()`, `voicePushStop()` | `tests/test_hud_qml_v2_voice_controls.py`, `tests/test_voice_push_to_talk_runtime.py` |
| Voice readiness/device | Voice drawer | Voice drawer | `refreshVoiceReadiness()`, `set_voice_device()` | `tests/test_voice_readiness.py`, `tests/test_hud_controller_voice_device_slot.py` |
| Top controls | Minimize/Close | Minimize/Close | window handlers + palette actions | `tests/test_hud_qml_v2_command_palette_keys.py`, `tests/test_quick_panel_v2_offscreen_smoke.py` |
| Command layer | Command palette | Command palette | `_runPaletteCommand` + `isUiActionAllowed()` | `tests/test_hud_qml_v2_command_palette_keys.py`, `tests/test_hud_controller_ui_contract.py` |
| Shell profile activation | `uiProfile=full` | `uiProfile=compact` | app loaders (`app_qml.py`, `quick_panel_v2/app.py`) | `tests/test_main_hud_ui_selector.py`, `tests/test_quick_panel_v2_shell_path.py` |

## Contract Rules
1. Any runtime command action must exist in `configs/panel_contract_v3.json -> interaction_contract`.
2. Unknown/undefined action is rejected in UI with a visible status message.
3. Approval-gated actions keep existing backend approval semantics unchanged.
4. Keyboard drawer navigation is standardized in both profiles via `Alt+1..Alt+5`.

## Structural State
1. Drawer panels are extracted and shared across full/compact:
- `PanelTools.qml`
- `PanelAttach.qml`
- `PanelHealth.qml`
- `PanelHistory.qml`
- `PanelVoice.qml`
2. Main entry QML files now compose panel components instead of embedding full drawer bodies inline.
3. `PanelChatMain.qml` is used by both shells for the main conversation surface.
