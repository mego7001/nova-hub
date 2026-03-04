# Final UI Transition Verification (Foundation Gate)

## Commands

1. `python -B -m py_compile nova_hub/core/ux/ui_contracts.py nova_hub/core/ux/__init__.py nova_hub/ui/hud_qml/app_qml.py nova_hub/ui/quick_panel_v2/app.py nova_hub/tests/test_main_hud_ui_selector.py nova_hub/tests/test_quick_panel_v2_shell_path.py nova_hub/tests/test_ui_contracts.py`
2. `python -m pytest -q -p no:cacheprovider nova_hub/tests/test_ui_contracts.py nova_hub/tests/test_main_hud_ui_selector.py nova_hub/tests/test_quick_panel_v2_shell_path.py`
3. `python -m pytest -q -p no:cacheprovider`
4. `python nova_hub/scripts/smoke_test.py`
5. `python nova_hub/main.py call --op doctor.report`
6. `python nova_hub/main.py call --op ollama.health.ping`
7. `NH_UI_SHELL_V3=1`:
   - `python -m pytest -q -p no:cacheprovider nova_hub/tests/test_hud_qml_v2_offscreen_ironman.py nova_hub/tests/test_quick_panel_v2_offscreen_smoke.py`

## Results

1. `py_compile`: PASS
2. Targeted tests: PASS (`12 passed`)
3. Full suite: PASS (`255 passed`)
4. Smoke test: PASS
5. Doctor report: PASS
6. Ollama health ping: PASS
7. Offscreen with shell v3 flag: PASS (`2 passed`)

