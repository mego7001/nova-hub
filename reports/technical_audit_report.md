# Technical Audit Report

Generated: 2026-02-09T04:23:46.455705Z

## 1. Executive Summary
- Scope analyzed: **257 files** (`Source + Workspace Projects` lock)
- Python modules analyzed: **210**
- Primary entrypoints checked: **12**
- Unused Python files (definitive): **21**
- Findings: **3 high / 3 medium / 2 low**
- Overall Efficiency & Health Score: **71.5 / 100**
- Baseline blocker confirmed: `ui/whatsapp/app.py` syntax error breaks `run_whatsapp.py` startup path.

## 2. Audit Scope and Methodology
### Locked Scope
- Included: `main.py`, `run_*.py`, `core/**`, `ui/**`, `integrations/**`, `scripts/**`, `tests/**`, `configs/**`, `workspace/projects/**/*.py`, `workspace/projects/**/launchers/**`, `workspace/projects/**/ui/**/*.qml`, plugin manifests.
- Excluded: runtime caches/artifacts (`.venv`, `.pytest_cache`, `__pycache__`, `tmp_*`, binary outputs, workspace chat/report dumps).
### Reachability Method
- Static AST import graph + dynamic plugin entrypoint roots (enabled + detected manifests).
- Primary runtime roots = root entry scripts + workspace project entry scripts.
- Runtime health = compile checks for all roots + import checks for root importable entries.

## 3. Dead Code and Orphaned Files
### Unused Files (Definitive)
| Component | Path | Class | Inbound | Outbound | Rationale |
| --- | --- | --- | --- | --- | --- |
| CMP-00032 | core/geometry3d/assembly.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00074 | core/security/online_mode.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00084 | core/sketch/renderer.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00138 | scripts/engineering_qa.py | unreachable | 0 | 3 | No inbound imports and unreachable from locked roots |
| CMP-00139 | scripts/geometry3d_qa.py | unreachable | 0 | 3 | No inbound imports and unreachable from locked roots |
| CMP-00140 | scripts/jarvis_core_qa.py | unreachable | 0 | 3 | No inbound imports and unreachable from locked roots |
| CMP-00141 | scripts/seed_security_critical.py | unreachable | 0 | 2 | No inbound imports and unreachable from locked roots |
| CMP-00142 | scripts/sketch_qa.py | unreachable | 0 | 5 | No inbound imports and unreachable from locked roots |
| CMP-00143 | scripts/timeline_qa.py | unreachable | 0 | 2 | No inbound imports and unreachable from locked roots |
| CMP-00144 | scripts/voice_qa.py | unreachable | 0 | 2 | No inbound imports and unreachable from locked roots |
| CMP-00198 | ui/whatsapp/widgets.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00200 | workspace/projects/7---copy---copy-ec9e31c8/preview/exporter_3d.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00201 | workspace/projects/7---copy---copy-ec9e31c8/preview/exporter_3d_fixed.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00204 | workspace/projects/7---copy---copy-ec9e31c8/preview/panels_dxf.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00206 | workspace/projects/7---copy---copy-ec9e31c8/preview/ui_controller.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00208 | workspace/projects/7---copy---copy-ec9e31c8/working/exporter_3d.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00209 | workspace/projects/7---copy---copy-ec9e31c8/working/exporter_3d_fixed.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00212 | workspace/projects/7---copy---copy-ec9e31c8/working/panels_dxf.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00215 | workspace/projects/7---copy---copy-ec9e31c8/working/ui_controller.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00216 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/intents.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |
| CMP-00228 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/security/secrets.py | unreachable | 0 | 0 | No inbound imports and unreachable from locked roots |

### Redundant Modules (Duplicate-Shadow)
| Primary Path | Shadow Paths (sample) | Copies |
| --- | --- | --- |
| core/permission_guard/approval_flow.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/approval_flow.py | 2 |
| core/permission_guard/policies.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/policies.py | 2 |
| core/permission_guard/risk.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/risk.py | 2 |
| core/permission_guard/tool_policy.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/tool_policy.py | 2 |
| core/plugin_engine/loader.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/plugin_engine/loader.py | 2 |
| core/plugin_engine/registry.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/plugin_engine/registry.py | 2 |
| core/plugin_engine/schema.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/plugin_engine/schema.py | 2 |
| core/portable/paths.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/portable/paths.py | 2 |
| core/task_engine/runner.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/task_engine/runner.py | 2 |
| core/utils/dxf_min.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/utils/dxf_min.py | 2 |
| integrations/conical_app/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conical_app/plugin.py | 2 |
| integrations/conversation/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conversation/plugin.py | 2 |
| integrations/deepseek/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/deepseek/plugin.py | 2 |
| integrations/gemini/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/gemini/plugin.py | 2 |
| integrations/git/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/git/plugin.py | 2 |
| integrations/halftone_app/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/halftone_app/plugin.py | 2 |
| integrations/nesting_app/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/nesting_app/plugin.py | 2 |
| integrations/telegram/plugin.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/telegram/plugin.py | 2 |
| run_chat.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/run_chat.py | 2 |
| run_ui.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/run_ui.py | 2 |
| ui/chat/widgets.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/chat/widgets.py | 2 |
| ui/dashboard/app.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | 2 |
| ui/dashboard/widgets.py | workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/widgets.py | 2 |

## 4. Comprehensive Functional Matrix
- Full matrix is in `reports/functional_matrix.md`.
- Module rows: **257**
- Symbol rows: **1513**

## 5. Architecture and Workflow Map
### High-Level Architecture
- Nova Hub is a plugin-driven modular monolith with multiple desktop frontends.
- Core layers: entrypoints -> orchestrators/controllers -> policy/approval gate -> plugin handlers -> workspace persistence.
- Runtime backbone: `Runner`, `ApprovalFlow`, `PluginRegistry`, `PluginLoader`, `ChatOrchestrator`, `HUDController`.

### Data Flow Map
- Input: UI text, CLI prompts, files/docs, plugin actions, optional external API calls.
- Processing: intent parsing, policy/risk checks, plugin dispatch, domain engines (engineering/sketch/3D/security).
- Storage: `workspace/projects/<id>/...` state, reports, patches, releases, chats, audit spine.
- Output: UI updates, reports, diffs/patches, verification outcomes, preview artifacts.

### Execution Lifecycle
1. Entrypoint bootstraps environment/workspace.
2. Policy + approval config loaded.
3. Plugins loaded and tools registered.
4. User action parsed into intent.
5. Runner enforces policy/approval and dispatches tool.
6. Tool updates artifacts/state/audit logs.
7. UI refreshes models from persisted state.

## 6. Performance and Structural Integrity
| Metric | Value |
| --- | --- |
| Python files | 210 |
| Total lines >79 | 2176 |
| Total lines >100 | 632 |
| Total lines >120 | 162 |
| Trailing-whitespace files | 19 |
| Parse errors | 2 |
| Largest class | ui/hud_qml/controller.py:176 (HUDController, 2542 lines) |
| Largest function | core/chat/orchestrator.py:60 (ChatOrchestrator.handle_message, 413 lines) |

### Top Structural Hotspots
- `ui/hud_qml/controller.py:176` class `HUDController` (2542 lines)
- `core/chat/orchestrator.py:43` class `ChatOrchestrator` (1083 lines)
- `ui/chat/app.py:49` class `ChatWindow` (1071 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/working/dxf_handler.py:35` class `PatternDXFReader` (715 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/working/ui_controller.py:14` class `MainUI` (600 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/working/pattern_mapper.py:40` class `PatternMapper` (587 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/preview/ui_controller.py:14` class `MainUI` (579 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/preview/panels_dxf.py:46` class `PanelDXFGenerator` (500 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/working/panels_dxf.py:46` class `PanelDXFGenerator` (500 lines)
- `core/jobs/controller.py:17` class `JobController` (461 lines)
- `core/chat/orchestrator.py:60` function `ChatOrchestrator.handle_message` (413 lines)
- `integrations/fs_read_tools/plugin.py:131` function `init_plugin` (285 lines)
- `workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/fs_read_tools/plugin.py:131` function `init_plugin` (281 lines)
- `ui/chat/app.py:50` function `ChatWindow.__init__` (272 lines)
- `ui/hud_qml/controller.py:1601` function `HUDController.getPaletteActions` (214 lines)
- `workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py:31` function `ChatOrchestrator.handle_message` (173 lines)
- `integrations/patch_planner/plugin.py:86` function `init_plugin` (159 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/working/pattern_mapper.py:665` function `batch_map_pattern_to_panels` (158 lines)
- `workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/patch_planner/plugin.py:79` function `init_plugin` (158 lines)
- `workspace/projects/7---copy---copy-ec9e31c8/preview/geometry_engine.py:147` function `ConicalHelixEngine.compute_panels_layout` (157 lines)

### Security & Logic Risk Notes
- Process execution and network providers exist; approval and policy gates are present but remain high-sensitivity surfaces.
- Workspace boundary/path checks are implemented in project and patch/apply flows.
- Broken WhatsApp entrypoint indicates startup regression not covered by current tests.

## 7. Efficiency and Health Score
| Domain | Score | Weight | Weighted Contribution |
| --- | --- | --- | --- |
| Reliability | 53.0 | 25% | 13.25 |
| Security | 82.0 | 25% | 20.50 |
| Maintainability | 64.0 | 20% | 12.80 |
| Performance | 88.0 | 15% | 13.20 |
| Testability | 78.0 | 15% | 11.70 |

**Overall Score: 71.5 / 100**

## 8. Prioritized Remediation Plan
1. Fix `ui/whatsapp/app.py` syntax error near line 1614 and add startup regression test for `run_whatsapp.py`.
2. Split monolithic controllers (`ui/hud_qml/controller.py`, `core/chat/orchestrator.py`, `ui/chat/app.py`).
3. Resolve/archive unreachable modules in dead-code inventory; keep only required primary-flow components.
4. De-duplicate workspace-project shadow code and define single source-of-truth modules.
5. Migrate `datetime.utcnow()` to timezone-aware UTC APIs.
6. Add explicit telemetry/audit for all `process_exec` and provider calls.

## 9. Evidence Appendix
### Primary Findings
- **[HIGH] Entrypoint import failure** (reliability)
  - run_whatsapp.py
  - Evidence: `Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import run_whatsapp; print('OK')
    ^^^^^^^^^^^^^^^^^^^
  File "D:\nouva hub\nova_hub_v1_release\nova_hub\run_whatsapp.py", line 5, in <module>
    from ui.whatsapp.app import WhatsAppWindow
  File "D:\nouva hub\nova_hub_v1_release\nova_hub\ui\whatsapp\app.py", line 1614
    self._refresh_geometry3d()
SyntaxError: expected 'except' or 'finally' block`
- **[HIGH] Entrypoint compile failure** (reliability)
  - workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/chat/app.py
  - Evidence: `  File "D:\nouva hub\nova_hub_v1_release\nova_hub\workspace\projects\novahub_review-6c9090df\working\nova_hub\ui\chat\app.py", line 31
    )
    ^
SyntaxError: unmatched ')'
`
- **[HIGH] Monolithic class risk** (maintainability)
  - ui/hud_qml/controller.py:176
  - Evidence: `HUDController (2542 lines)`
- **[MEDIUM] Unreachable modules in primary flow** (maintainability)
  - 21
  - Evidence: `See dead code section`
- **[MEDIUM] Process execution surface** (security)
  - multiple modules
  - Evidence: `Guarded but sensitive`
- **[MEDIUM] Network egress surface** (security)
  - provider plugins
  - Evidence: `Approval-gated`
- **[LOW] PEP8 line-length drift** (maintainability)
  - 162
  - Evidence: `lines >120`
- **[LOW] Deprecated UTC API usage** (reliability)
  - datetime.utcnow
  - Evidence: `use timezone-aware UTC`

### Acceptance Criteria Checks
| Check | Status | Details |
| --- | --- | --- |
| Inventory completeness | PASS | python_scope=210, module_rows_py=210, parse_errors=2 |
| Reachability correctness | PASS | unused=21 |
| Dynamic edge validation | PASS | plugins=21, tools=31, status=ok |
| Entrypoint health | FAIL | checked=12, failures=2 |
| Cross-project dependency scan | PASS | cross_edges=65 |
| Functional matrix integrity | PASS | rows=1513 |
| Architecture traceability | PASS | main + hud flow mapped |
| Health score reproducibility | PASS | findings=8 |

### Runtime Validation
- Plugin validation: `ok`
- Plugins loaded: 21
- Tools loaded: 31
- Pytest: ok; 43 passed, 119 warnings in 1.25s

### References
- Reachability details: `reports/dependency_reachability.md`
- Full decomposition matrix: `reports/functional_matrix.md`

