# Nova Hub - P0 Closure Audit

## Summary Table

| Check | PASS/FAIL | Evidence |
|---|---|---|
| 1) Workspace Copy Dependency Eliminated From CAD Behavior Tests | PASS | CAD behavior tests import canonical modules directly: `tests/test_dxf_reader_bulge_preserves_curvature.py:7`, `tests/test_pattern_projector_closed_inside_safe_zone_unchanged.py:5`, `tests/test_pattern_projector_closed_inside_safe_zone_unchanged.py:6`, `tests/test_pattern_projector_closed_inside_safe_zone_unchanged.py:7`, `tests/test_pattern_projector_closed_loop_stays_closed_after_clip.py:6`, `tests/test_pattern_projector_closed_loop_stays_closed_after_clip.py:7`, `tests/test_pattern_projector_closed_loop_stays_closed_after_clip.py:8`. |
| 2) Canonical CAD Package Import Hygiene | PASS | Relative imports found (`from .qa_report`, `from .geometry_engine`, `from .pattern_mapper`, `from .dxf_handler`), no mixed absolute internal imports detected. Compile succeeded with Windows-safe equivalent. `dupes: []` for `core.cad_pipeline.__all__`. |
| 3) Task Modes Hygiene (User-facing 4 modes only) | PASS | `TASK_MODE_SPECS` includes only v1 modes in `core/ux/task_modes.py:27`; `LEGACY_ALIAS_MAP` exists at `core/ux/task_modes.py:54`; single `normalize_task_mode` at `core/ux/task_modes.py:89`; tests passed. |
| 4) UI Defaults Must Be `general` + No `include_unavailable=True` in UI Lists | PASS | Updated UI call sites now use `include_unavailable=False`: `ui/hud_qml/controller.py:678`, `ui/quick_panel/app.py:340`, `ui/quick_panel/app.py:880`. Re-audit grep (`rg -n "include_unavailable=True" ui core/ux tests`) returned no hits. |
| 5) Quick Panel Must Not Depend on `ui.whatsapp` Runtime Implementation | PASS | No `ui.whatsapp` imports inside `ui/quick_panel`; implementation class exists at `ui/quick_panel/app.py:303`; widgets are local in `ui/quick_panel/widgets.py`; compat alias remains in `ui/whatsapp/app.py:3`. |
| 6) Full Validation Gate (Optional) | PASS | `pytest -q` passed (`82 passed, 129 warnings`), `python scripts/smoke_test.py` passed, offscreen HUD smoke exited 0. |

## Check 4 Closure Evidence

Post-fix lines:

- `ui/hud_qml/controller.py:678`
```py
rows = available_task_modes(self._registry, include_unavailable=False)
```

- `ui/quick_panel/app.py:340`
```py
self.task_modes = available_task_modes(self.registry, include_unavailable=False)
```

- `ui/quick_panel/app.py:880`
```py
self.task_modes = available_task_modes(self.registry, include_unavailable=False)
```

Re-audit grep:

- `rg -n "include_unavailable=True" ui core/ux tests` -> no hits.

## Commands Executed (with exit codes)

- `Get-Location; Test-Path reports`  
  - Exit: `0`  
  - Snippet: repo root resolved, `reports_exists: yes`

- `rg -n "workspace/projects|WORKING_PROJECT|sys\.path\.insert\(|importlib\.import_module\(" tests`  
  - Exit: `0`  
  - Snippet: `tests/conftest.py:9: sys.path.insert(0, str(ROOT))`

- Inspected CAD behavior tests with line-numbered `Get-Content`  
  - Exit: `0`  
  - Snippet confirms canonical imports only in the three target files.

- `rg -n "from (qa_report|geometry_engine|pattern_mapper|dxf_handler) import|from \.qa_report import|from \.geometry_engine import|from \.pattern_mapper import|from \.dxf_handler import" core/cad_pipeline`  
  - Exit: `0`  
  - Snippet: relative imports only.

- `python -B -m py_compile core/cad_pipeline/*.py core/cad_pipeline/__init__.py`  
  - Exit: `1`  
  - Snippet: wildcard invalid on PowerShell argument expansion for this module call.

- Windows-safe equivalent used:  
  - Command: `$files = Get-ChildItem core/cad_pipeline -Filter *.py | % { $_.FullName }; python -B -m py_compile $files`  
  - Exit: `0`

- `python -c "import core.cad_pipeline as p; import collections; c=collections.Counter(p.__all__); d=[k for k,v in c.items() if v>1]; print('dupes:', d)"`  
  - Exit: `0`  
  - Snippet: `dupes: []`

- `pytest -q tests/test_ux_task_modes.py`  
  - Exit: `0`  
  - Snippet: `4 passed`

- `pytest -q tests/test_ux_mode_routing.py`  
  - Exit: `0`  
  - Snippet: `3 passed`

- `rg -n 'assert parsed\.mode == "auto"|assert parsed\.mode == "general"' tests/test_ux_mode_routing.py`  
  - Exit: `1`  
  - Snippet: no conflicting assertions found.

- `rg -n 'assert "auto" in ids|assert "chat" in ids|assert "deep_research" in ids|assert "verify" in ids' tests/test_ux_task_modes.py`  
  - Exit: `1`  
  - Snippet: no legacy selectable-mode assertions found.

- `rg -n 'include_unavailable=True' ui core/ux tests`  
  - Exit: `1`  
  - Snippet: no hits.

- `rg -n "ui\.whatsapp|from ui\.whatsapp|import ui\.whatsapp" ui/quick_panel`  
  - Exit: `1`  
  - Snippet: no hits.

- `pytest -q`  
  - Exit: `0`  
  - Snippet: `82 passed, 129 warnings`.

- `python scripts/smoke_test.py`  
  - Exit: `0`  
  - Snippet: `smoke_status: PASS`.

- `QT_QPA_PLATFORM=offscreen; NH_HUD_AUTOCLOSE_MS=120; python run_hud_qml.py`  
  - Exit: `0`  
  - Snippet: clean exit.

## Final Verdict

`READY_FOR_NEXT_PHASE: YES`
