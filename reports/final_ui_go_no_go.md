# Final UI GO/NO-GO Decision (Unified Shell V3)

## Decision
- **FULL GO**

## Why FULL GO
1. Gate-2/3/5/6 are closed at 100% with runtime evidence.
2. Entry routing now defaults to V3:
`run_quick_panel.py` launches `quick_panel_v2`; `main.py whatsapp` launches V3 compact.
3. Acceptance pack passed with current baseline:
targeted UI/V3 tests (`45 passed`) and full suite (`275 passed`).
4. Smoke and IPC validation commands passed.
5. Safety semantics unchanged (`apply/patch` still approval-gated).

## Runtime Path (What to launch)
1. Full V3 HUD:
`python run_hud_qml.py`
2. Compact V3 QuickPanel:
`python run_quick_panel_v2.py`
3. Alias entry (now V3 compact):
`python run_quick_panel.py`
4. CLI route (now V3 compact):
`python main.py whatsapp`

## Rollback (Emergency only)
1. Set `NH_UI_LEGACY_WHATSAPP=1` to force legacy quick panel path for `main.py whatsapp`.
2. Keep `NH_UI_SHELL_V3=0` only for shell rollback troubleshooting.

## Known Operational Note
1. If local Ollama service is down, health returns `status=unavailable` and UI degrades gracefully.
   This is non-blocking for GO.
