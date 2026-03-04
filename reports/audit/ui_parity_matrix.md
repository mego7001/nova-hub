# UI Parity Matrix (Quick Panel v1 vs Quick Panel v2)

Generated: 2026-02-22

| Capability | quick_panel (v1) | quick_panel_v2 (new) | Evidence |
| --- | --- | --- | --- |
| Official launcher command | ✅ `main.py whatsapp` | ✅ `main.py quick_panel_v2` | `main.py`, `run_quick_panel.py`, `run_quick_panel_v2.py` |
| Backend runtime object | ✅ QWidget backend | ✅ QML backend with Python controller | `ui/quick_panel/app.py`, `ui/quick_panel_v2/app.py`, `ui/quick_panel_v2/controller.py` |
| Chat send (end-to-end) | ✅ | ✅ | `ui/quick_panel_v2/MainV2.qml` (`send_message`) |
| Mode switching | ✅ | ✅ | `ui/quick_panel_v2/MainV2.qml` (`setTaskMode`) |
| Pending apply queue/confirm/reject | ✅ | ✅ | `ui/quick_panel_v2/MainV2.qml` buttons + controller slots |
| Health stats refresh | ✅ | ✅ | `ui/quick_panel_v2/MainV2.qml` + `refreshHealthStats` |
| Ollama health visibility | ⚠️ partial | ✅ explicit summary line | `ui/quick_panel_v2/MainV2.qml`, `ui/hud_qml/controller.py` |
| Voice controls (toggle/mute/stop/replay) | ✅ | ✅ | `ui/quick_panel_v2/MainV2.qml` ChatPane bindings |
| File attach flow | ✅ | ✅ | `ui/quick_panel_v2/MainV2.qml` FileDialog -> `attachFiles` |
| Command palette actions | limited | ✅ shared HUD v2 palette | `ui/hud_qml_v2/components/CommandPalette.qml` |
| Minimize/Close controls | window frame | ✅ explicit top buttons + Ctrl+Q/Ctrl+W | `ui/quick_panel_v2/MainV2.qml` |

## Notes

1. `quick_panel_v2` now runs with a real backend (`QuickPanelV2Controller`) and does not fallback to v1 runtime.
2. Backend logic is intentionally shared from `HUDController` to keep behavior consistent across HUD and panel surfaces.
3. Any remaining UI deltas are UX-level, not backend absence.
