# Dependency & Reachability Audit

Generated: 2026-02-09T04:26:29.728565Z

## Entrypoint Baseline
- Root entry scripts: `main.py`, `run_hud_qml.py`, `run_ui.py`, `run_chat.py`, `run_whatsapp.py`
- Workspace entry roots: `workspace/projects/**/main.py`, `workspace/projects/**/run_*.py`, `workspace/projects/**/ui/**/app.py`
- Dynamic roots: plugin entrypoints from enabled config + detected manifests

### Entrypoint Health
| Entrypoint | Scope | Compile | Import | Error (truncated) |
| --- | --- | --- | --- | --- |
| main.py | root | ok | ok |  |
| run_chat.py | root | ok | ok |  |
| run_hud_qml.py | root | ok | ok |  |
| run_ui.py | root | ok | ok |  |
| run_whatsapp.py | root | ok | failed | Traceback (most recent call last):   File "<string>", line 1, in <module>     import run_whatsapp; print('OK')     ^^^^^^^^^^^^^^^^^^^   File "D:\nouva hub\nova_hub_v1_release\nova |
| workspace/projects/7---copy---copy-ec9e31c8/preview/main.py | workspace | ok | skipped |  |
| workspace/projects/7---copy---copy-ec9e31c8/working/main.py | workspace | ok | skipped |  |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/main.py | workspace | ok | skipped |  |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/run_chat.py | workspace | ok | skipped |  |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/run_ui.py | workspace | ok | skipped |  |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/chat/app.py | workspace | failed | skipped |   File "D:\nouva hub\nova_hub_v1_release\nova_hub\workspace\projects\novahub_review-6c9090df\working\nova_hub\ui\chat\app.py", line 31     )     ^ SyntaxError: unmatched ')'  |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | workspace | ok | skipped |  |

## Graph Summary
- Python modules in scope: **210**
- Scope files (all types): **257**
- Directed import edges: **367**
- Parse errors: **2**
- Primary reachable modules: **79**
- Dynamic reachable modules: **68**
- Union reachable modules: **118**

### Classification Counts (Python)
- reachable: 86
- entrypoint-only: 12
- dynamic-only: 20
- test-only: 65
- duplicate-shadow: 6
- unreachable: 21

### Classification Counts (Non-Python)
- entrypoint-only: 4
- reachable: 26
- unreachable: 17

## Definitive Unused Files (Primary Flow)
- `core/geometry3d/assembly.py`
- `core/security/online_mode.py`
- `core/sketch/renderer.py`
- `scripts/engineering_qa.py`
- `scripts/geometry3d_qa.py`
- `scripts/jarvis_core_qa.py`
- `scripts/seed_security_critical.py`
- `scripts/sketch_qa.py`
- `scripts/timeline_qa.py`
- `scripts/voice_qa.py`
- `ui/whatsapp/widgets.py`
- `workspace/projects/7---copy---copy-ec9e31c8/preview/exporter_3d.py`
- `workspace/projects/7---copy---copy-ec9e31c8/preview/exporter_3d_fixed.py`
- `workspace/projects/7---copy---copy-ec9e31c8/preview/panels_dxf.py`
- `workspace/projects/7---copy---copy-ec9e31c8/preview/ui_controller.py`
- `workspace/projects/7---copy---copy-ec9e31c8/working/exporter_3d.py`
- `workspace/projects/7---copy---copy-ec9e31c8/working/exporter_3d_fixed.py`
- `workspace/projects/7---copy---copy-ec9e31c8/working/panels_dxf.py`
- `workspace/projects/7---copy---copy-ec9e31c8/working/ui_controller.py`
- `workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/intents.py`
- `workspace/projects/novahub_review-6c9090df/working/nova_hub/core/security/secrets.py`

## Cross-Project Dependency Edges
- Total cross-bucket import edges: **65**
| Source | Target | Edge Type |
| --- | --- | --- |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/chat/intents.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/chat/state.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/permission_guard/approval_flow.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/permission_guard/tool_policy.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/plugin_engine/loader.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/security/secrets.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | core/task_engine/runner.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/task_engine/runner.py | core/permission_guard/approval_flow.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/core/task_engine/runner.py | core/permission_guard/policies.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conical_app/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conical_app/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conical_app/plugin.py | core/utils/dxf_min.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conversation/plugin.py | core/chat/orchestrator.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conversation/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conversation/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/core_examples/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/core_examples/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/deepseek/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/deepseek/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/desktop/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/desktop/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/desktop/plugin.py | core/portable/paths.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/fs_read_tools/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/fs_read_tools/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/gemini/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/gemini/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/git/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/git/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/halftone_app/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/halftone_app/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/halftone_app/plugin.py | core/utils/dxf_min.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/nesting_app/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/nesting_app/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/nesting_app/plugin.py | core/utils/dxf_min.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/patch_apply/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/patch_apply/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/patch_planner/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/patch_planner/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/pipeline/plugin.py | core/permission_guard/approval_flow.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/pipeline/plugin.py | core/permission_guard/tool_policy.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/pipeline/plugin.py | core/plugin_engine/loader.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/pipeline/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/pipeline/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/pipeline/plugin.py | core/task_engine/runner.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/project_scanner/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/project_scanner/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/telegram/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/telegram/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/verify/plugin.py | core/plugin_engine/manifest.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/verify/plugin.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/main.py | core/permission_guard/approval_flow.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/main.py | core/permission_guard/tool_policy.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/main.py | core/plugin_engine/loader.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/main.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/main.py | core/task_engine/runner.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/run_chat.py | core/portable/paths.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/run_chat.py | ui/chat/app.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/run_ui.py | ui/dashboard/app.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | core/permission_guard/approval_flow.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | core/permission_guard/tool_policy.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | core/plugin_engine/loader.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | core/plugin_engine/registry.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | core/task_engine/runner.py | workspace::novahub_review-6c9090df -> root |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | ui/dashboard/widgets.py | workspace::novahub_review-6c9090df -> root |

## Parse/Resolution Evidence
| Source | Type | Details |
| --- | --- | --- |
| ui/whatsapp/app.py | parse_error | expected 'except' or 'finally' block at line 1614:8 |
| workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/chat/app.py | parse_error | unmatched ')' at line 31:1 |

## Reachability Matrix
| Component | Path | Class | From Primary | From Dynamic | Inbound | Outbound |
| --- | --- | --- | --- | --- | --- | --- |
| CMP-00005 | core/analyze/dependency_graph.py | reachable | no | yes | 1 | 0 |
| CMP-00006 | core/analyze/entrypoints.py | reachable | no | yes | 1 | 0 |
| CMP-00007 | core/analyze/risk.py | reachable | no | yes | 1 | 0 |
| CMP-00008 | core/assistant/executor.py | reachable | no | yes | 1 | 0 |
| CMP-00009 | core/assistant/suggestions.py | reachable | no | yes | 1 | 0 |
| CMP-00010 | core/audit_spine.py | reachable | yes | yes | 6 | 2 |
| CMP-00011 | core/chat/intents.py | reachable | yes | yes | 3 | 0 |
| CMP-00012 | core/chat/orchestrator.py | reachable | no | yes | 4 | 25 |
| CMP-00013 | core/chat/state.py | reachable | no | yes | 4 | 0 |
| CMP-00014 | core/conversation/brain.py | reachable | yes | no | 1 | 4 |
| CMP-00015 | core/conversation/confirmation.py | test-only | no | no | 1 | 0 |
| CMP-00016 | core/conversation/intent_parser.py | reachable | yes | yes | 4 | 1 |
| CMP-00017 | core/conversation/jarvis_core.py | reachable | yes | yes | 3 | 1 |
| CMP-00018 | core/conversation/prefs.py | reachable | no | yes | 1 | 1 |
| CMP-00019 | core/engineering/__init__.py | reachable | yes | no | 5 | 2 |
| CMP-00020 | core/engineering/explain.py | reachable | yes | no | 1 | 1 |
| CMP-00021 | core/engineering/extract.py | reachable | yes | no | 3 | 8 |
| CMP-00022 | core/engineering/limits.py | reachable | yes | no | 1 | 0 |
| CMP-00023 | core/engineering/loads.py | test-only | no | no | 0 | 0 |
| CMP-00024 | core/engineering/materials.py | reachable | yes | no | 1 | 0 |
| CMP-00025 | core/engineering/model.py | reachable | yes | no | 2 | 2 |
| CMP-00026 | core/engineering/risk.py | reachable | yes | no | 1 | 0 |
| CMP-00027 | core/engineering/rules.py | reachable | yes | no | 1 | 2 |
| CMP-00028 | core/engineering/store.py | test-only | no | no | 0 | 3 |
| CMP-00029 | core/engineering/tolerances.py | reachable | yes | no | 1 | 0 |
| CMP-00030 | core/fs/safe_workspace_writer.py | reachable | yes | yes | 4 | 1 |
| CMP-00031 | core/geometry3d/__init__.py | reachable | yes | no | 8 | 2 |
| CMP-00032 | core/geometry3d/assembly.py | unreachable | no | no | 0 | 0 |
| CMP-00033 | core/geometry3d/export.py | reachable | yes | no | 1 | 3 |
| CMP-00034 | core/geometry3d/intent.py | reachable | yes | no | 2 | 2 |
| CMP-00035 | core/geometry3d/limits.py | reachable | yes | no | 1 | 0 |
| CMP-00036 | core/geometry3d/preview.py | test-only | no | no | 0 | 2 |
| CMP-00037 | core/geometry3d/primitives.py | reachable | yes | no | 4 | 0 |
| CMP-00038 | core/geometry3d/reasoning.py | reachable | yes | no | 2 | 2 |
| CMP-00039 | core/geometry3d/store.py | reachable | yes | no | 2 | 4 |
| CMP-00040 | core/ingest/file_types.py | reachable | yes | no | 1 | 0 |
| CMP-00041 | core/ingest/index_store.py | reachable | yes | yes | 3 | 0 |
| CMP-00042 | core/ingest/ingest_manager.py | reachable | yes | no | 1 | 11 |
| CMP-00043 | core/ingest/parsers/docx_parser.py | reachable | yes | no | 1 | 0 |
| CMP-00044 | core/ingest/parsers/image_parser.py | reachable | yes | no | 1 | 0 |
| CMP-00045 | core/ingest/parsers/pdf_parser.py | reachable | yes | no | 1 | 0 |
| CMP-00046 | core/ingest/parsers/text_parser.py | reachable | yes | no | 1 | 0 |
| CMP-00047 | core/ingest/parsers/xlsx_parser.py | reachable | yes | no | 1 | 0 |
| CMP-00048 | core/ingest/unzip.py | reachable | yes | no | 1 | 0 |
| CMP-00049 | core/jobs/controller.py | reachable | yes | no | 2 | 7 |
| CMP-00050 | core/jobs/models.py | reachable | yes | yes | 3 | 0 |
| CMP-00051 | core/jobs/storage.py | reachable | yes | yes | 2 | 2 |
| CMP-00052 | core/language/__init__.py | test-only | no | no | 0 | 1 |
| CMP-00053 | core/language/normalization.py | reachable | no | yes | 2 | 0 |
| CMP-00054 | core/llm/online_policy.py | reachable | yes | no | 1 | 0 |
| CMP-00055 | core/llm/router.py | reachable | yes | no | 1 | 2 |
| CMP-00056 | core/permission_guard/approval_flow.py | reachable | yes | yes | 12 | 3 |
| CMP-00057 | core/permission_guard/policies.py | reachable | yes | yes | 4 | 0 |
| CMP-00058 | core/permission_guard/risk.py | reachable | yes | yes | 1 | 1 |
| CMP-00059 | core/permission_guard/tool_policy.py | reachable | yes | yes | 11 | 0 |
| CMP-00060 | core/plugin_engine/loader.py | reachable | yes | yes | 13 | 3 |
| CMP-00061 | core/plugin_engine/manifest.py | reachable | yes | yes | 38 | 0 |
| CMP-00062 | core/plugin_engine/registry.py | reachable | yes | yes | 53 | 0 |
| CMP-00063 | core/plugin_engine/schema.py | reachable | yes | yes | 1 | 0 |
| CMP-00064 | core/portable/paths.py | reachable | yes | yes | 26 | 0 |
| CMP-00065 | core/projects/manager.py | reachable | yes | yes | 11 | 4 |
| CMP-00066 | core/projects/models.py | reachable | yes | yes | 3 | 0 |
| CMP-00067 | core/projects/storage.py | reachable | yes | yes | 1 | 1 |
| CMP-00068 | core/records/__init__.py | test-only | no | no | 0 | 1 |
| CMP-00069 | core/records/record_store.py | reachable | yes | yes | 5 | 0 |
| CMP-00070 | core/reporting/writer.py | reachable | yes | yes | 2 | 2 |
| CMP-00071 | core/retrieval/search.py | reachable | no | yes | 1 | 1 |
| CMP-00072 | core/run/smart_runner.py | reachable | yes | yes | 2 | 0 |
| CMP-00073 | core/security/api_importer.py | reachable | yes | no | 1 | 1 |
| CMP-00074 | core/security/online_mode.py | unreachable | no | no | 0 | 0 |
| CMP-00075 | core/security/process_allowlist.py | reachable | yes | yes | 4 | 0 |
| CMP-00076 | core/security/required_secrets.py | reachable | no | yes | 1 | 0 |
| CMP-00077 | core/security/secrets.py | reachable | yes | yes | 16 | 1 |
| CMP-00078 | core/security/security_doctor.py | reachable | yes | yes | 2 | 3 |
| CMP-00079 | core/security/status.py | reachable | no | yes | 1 | 1 |
| CMP-00080 | core/sketch/__init__.py | reachable | no | yes | 2 | 4 |
| CMP-00081 | core/sketch/dxf.py | reachable | no | yes | 3 | 0 |
| CMP-00082 | core/sketch/model.py | reachable | no | yes | 2 | 0 |
| CMP-00083 | core/sketch/parser.py | reachable | no | yes | 3 | 0 |
| CMP-00084 | core/sketch/renderer.py | unreachable | no | no | 0 | 0 |
| CMP-00085 | core/sketch/store.py | reachable | no | yes | 3 | 2 |
| CMP-00086 | core/system_state_machine.py | reachable | yes | yes | 5 | 0 |
| CMP-00087 | core/task_engine/runner.py | reachable | yes | yes | 10 | 2 |
| CMP-00088 | core/utils/dxf_min.py | reachable | no | yes | 6 | 0 |
| CMP-00089 | core/voice/__init__.py | test-only | no | no | 0 | 1 |
| CMP-00090 | core/voice/engine.py | reachable | no | yes | 3 | 0 |
| CMP-00092 | integrations/conical_app/plugin.py | dynamic-only | no | yes | 0 | 3 |
| CMP-00094 | integrations/conversation/plugin.py | dynamic-only | no | yes | 0 | 3 |
| CMP-00096 | integrations/core_examples/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00098 | integrations/deepseek/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00100 | integrations/desktop/plugin.py | dynamic-only | no | yes | 0 | 4 |
| CMP-00102 | integrations/fs_read_tools/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00104 | integrations/gemini/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00106 | integrations/git/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00108 | integrations/halftone_app/plugin.py | dynamic-only | no | yes | 0 | 3 |
| CMP-00110 | integrations/nesting_app/plugin.py | dynamic-only | no | yes | 0 | 3 |
| CMP-00112 | integrations/openai/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00114 | integrations/patch_apply/plugin.py | dynamic-only | no | yes | 1 | 2 |
| CMP-00116 | integrations/patch_planner/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00118 | integrations/pipeline/plugin.py | dynamic-only | no | yes | 0 | 6 |
| CMP-00120 | integrations/project_scanner/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00122 | integrations/run_preview/plugin.py | dynamic-only | no | yes | 0 | 6 |
| CMP-00124 | integrations/security_doctor/plugin.py | reachable | yes | yes | 1 | 6 |
| CMP-00126 | integrations/sketch/plugin.py | dynamic-only | no | yes | 0 | 8 |
| CMP-00128 | integrations/telegram/plugin.py | dynamic-only | no | yes | 0 | 2 |
| CMP-00130 | integrations/verify/plugin.py | dynamic-only | no | yes | 0 | 3 |
| CMP-00132 | integrations/voice/plugin.py | dynamic-only | no | yes | 0 | 4 |
| CMP-00133 | main.py | entrypoint-only | yes | no | 1 | 5 |
| CMP-00134 | run_chat.py | entrypoint-only | yes | no | 0 | 2 |
| CMP-00135 | run_hud_qml.py | entrypoint-only | yes | no | 0 | 1 |
| CMP-00136 | run_ui.py | entrypoint-only | yes | no | 0 | 1 |
| CMP-00137 | run_whatsapp.py | entrypoint-only | yes | no | 0 | 2 |
| CMP-00138 | scripts/engineering_qa.py | unreachable | no | no | 0 | 3 |
| CMP-00139 | scripts/geometry3d_qa.py | unreachable | no | no | 0 | 3 |
| CMP-00140 | scripts/jarvis_core_qa.py | unreachable | no | no | 0 | 3 |
| CMP-00141 | scripts/seed_security_critical.py | unreachable | no | no | 0 | 2 |
| CMP-00142 | scripts/sketch_qa.py | unreachable | no | no | 0 | 5 |
| CMP-00143 | scripts/timeline_qa.py | unreachable | no | no | 0 | 2 |
| CMP-00144 | scripts/voice_qa.py | unreachable | no | no | 0 | 2 |
| CMP-00145 | tests/conftest.py | test-only | no | no | 0 | 0 |
| CMP-00146 | tests/test_audit_spine.py | test-only | no | no | 0 | 6 |
| CMP-00147 | tests/test_dxf_reader_bulge_preserves_curvature.py | test-only | no | no | 0 | 0 |
| CMP-00148 | tests/test_gating.py | test-only | no | no | 0 | 5 |
| CMP-00149 | tests/test_hud_controller_no_duplicate_defs.py | test-only | no | no | 0 | 1 |
| CMP-00150 | tests/test_hud_qml_chat_sessions.py | test-only | no | no | 0 | 2 |
| CMP-00151 | tests/test_hud_qml_commandbar_handlers.py | test-only | no | no | 0 | 0 |
| CMP-00152 | tests/test_hud_qml_controller.py | test-only | no | no | 0 | 3 |
| CMP-00153 | tests/test_hud_qml_general_chat.py | test-only | no | no | 0 | 3 |
| CMP-00154 | tests/test_hud_qml_geometry_adapter.py | test-only | no | no | 0 | 3 |
| CMP-00155 | tests/test_hud_qml_jsonl_helpers.py | test-only | no | no | 0 | 1 |
| CMP-00156 | tests/test_hud_qml_models.py | test-only | no | no | 0 | 1 |
| CMP-00157 | tests/test_hud_qml_palette.py | test-only | no | no | 0 | 2 |
| CMP-00158 | tests/test_hud_qml_popouts_wired.py | test-only | no | no | 0 | 0 |
| CMP-00159 | tests/test_hud_qml_qa_panel_wired.py | test-only | no | no | 0 | 0 |
| CMP-00160 | tests/test_hud_qml_qa_report.py | test-only | no | no | 0 | 1 |
| CMP-00161 | tests/test_hud_qml_smoke.py | test-only | no | no | 0 | 1 |
| CMP-00162 | tests/test_jobs_controller.py | test-only | no | no | 0 | 3 |
| CMP-00163 | tests/test_main_dispatch.py | test-only | no | no | 0 | 3 |
| CMP-00164 | tests/test_patch_pipeline_integrity.py | test-only | no | no | 0 | 3 |
| CMP-00165 | tests/test_pattern_projector_closed_inside_safe_zone_unchanged.py | test-only | no | no | 0 | 0 |
| CMP-00166 | tests/test_pattern_projector_closed_loop_stays_closed_after_clip.py | test-only | no | no | 0 | 0 |
| CMP-00167 | tests/test_plugin_loader_tools.py | test-only | no | no | 0 | 2 |
| CMP-00168 | tests/test_project_manager_security.py | test-only | no | no | 0 | 1 |
| CMP-00169 | tests/test_system_state_machine.py | test-only | no | no | 0 | 1 |
| CMP-00170 | ui/chat/app.py | reachable | yes | no | 2 | 13 |
| CMP-00171 | ui/chat/widgets.py | reachable | yes | no | 1 | 0 |
| CMP-00172 | ui/dashboard/app.py | reachable | yes | no | 2 | 6 |
| CMP-00173 | ui/dashboard/widgets.py | reachable | yes | no | 3 | 0 |
| CMP-00174 | ui/hud_qml/__init__.py | test-only | no | no | 0 | 1 |
| CMP-00175 | ui/hud_qml/app_qml.py | reachable | yes | no | 3 | 2 |
| CMP-00176 | ui/hud_qml/controller.py | reachable | yes | no | 8 | 13 |
| CMP-00177 | ui/hud_qml/geometry_adapter.py | reachable | yes | no | 2 | 3 |
| CMP-00178 | ui/hud_qml/models.py | reachable | yes | no | 2 | 0 |
| CMP-00197 | ui/whatsapp/app.py | reachable | yes | no | 1 | 0 |
| CMP-00198 | ui/whatsapp/widgets.py | unreachable | no | no | 0 | 0 |
| CMP-00199 | workspace/projects/7---copy---copy-ec9e31c8/preview/dxf_handler.py | test-only | no | no | 0 | 0 |
| CMP-00200 | workspace/projects/7---copy---copy-ec9e31c8/preview/exporter_3d.py | unreachable | no | no | 0 | 0 |
| CMP-00201 | workspace/projects/7---copy---copy-ec9e31c8/preview/exporter_3d_fixed.py | unreachable | no | no | 0 | 0 |
| CMP-00202 | workspace/projects/7---copy---copy-ec9e31c8/preview/geometry_engine.py | test-only | no | no | 0 | 0 |
| CMP-00203 | workspace/projects/7---copy---copy-ec9e31c8/preview/main.py | entrypoint-only | yes | no | 0 | 0 |
| CMP-00204 | workspace/projects/7---copy---copy-ec9e31c8/preview/panels_dxf.py | unreachable | no | no | 0 | 0 |
| CMP-00205 | workspace/projects/7---copy---copy-ec9e31c8/preview/pattern_mapper.py | test-only | no | no | 0 | 0 |
| CMP-00206 | workspace/projects/7---copy---copy-ec9e31c8/preview/ui_controller.py | unreachable | no | no | 0 | 0 |
| CMP-00207 | workspace/projects/7---copy---copy-ec9e31c8/working/dxf_handler.py | test-only | no | no | 0 | 0 |
| CMP-00208 | workspace/projects/7---copy---copy-ec9e31c8/working/exporter_3d.py | unreachable | no | no | 0 | 0 |
| CMP-00209 | workspace/projects/7---copy---copy-ec9e31c8/working/exporter_3d_fixed.py | unreachable | no | no | 0 | 0 |
| CMP-00210 | workspace/projects/7---copy---copy-ec9e31c8/working/geometry_engine.py | test-only | no | no | 0 | 0 |
| CMP-00211 | workspace/projects/7---copy---copy-ec9e31c8/working/main.py | entrypoint-only | yes | no | 0 | 0 |
| CMP-00212 | workspace/projects/7---copy---copy-ec9e31c8/working/panels_dxf.py | unreachable | no | no | 0 | 0 |
| CMP-00213 | workspace/projects/7---copy---copy-ec9e31c8/working/pattern_mapper.py | test-only | no | no | 0 | 0 |
| CMP-00214 | workspace/projects/7---copy---copy-ec9e31c8/working/qa_report.py | test-only | no | no | 0 | 0 |
| CMP-00215 | workspace/projects/7---copy---copy-ec9e31c8/working/ui_controller.py | unreachable | no | no | 0 | 0 |
| CMP-00216 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/intents.py | unreachable | no | no | 0 | 0 |
| CMP-00217 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/orchestrator.py | test-only | no | no | 0 | 8 |
| CMP-00218 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/chat/state.py | test-only | no | no | 0 | 0 |
| CMP-00219 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/approval_flow.py | test-only | no | no | 0 | 0 |
| CMP-00220 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/policies.py | duplicate-shadow | no | no | 0 | 0 |
| CMP-00221 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/risk.py | duplicate-shadow | no | no | 0 | 0 |
| CMP-00222 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/permission_guard/tool_policy.py | duplicate-shadow | no | no | 0 | 0 |
| CMP-00223 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/plugin_engine/loader.py | test-only | no | no | 0 | 0 |
| CMP-00224 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/plugin_engine/manifest.py | test-only | no | no | 0 | 0 |
| CMP-00225 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/plugin_engine/registry.py | test-only | no | no | 0 | 0 |
| CMP-00226 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/plugin_engine/schema.py | test-only | no | no | 0 | 0 |
| CMP-00227 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/portable/paths.py | test-only | no | no | 0 | 0 |
| CMP-00228 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/security/secrets.py | unreachable | no | no | 0 | 0 |
| CMP-00229 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/task_engine/runner.py | test-only | no | no | 0 | 2 |
| CMP-00230 | workspace/projects/novahub_review-6c9090df/working/nova_hub/core/utils/dxf_min.py | duplicate-shadow | no | no | 0 | 0 |
| CMP-00231 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conical_app/plugin.py | test-only | no | no | 0 | 3 |
| CMP-00232 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/conversation/plugin.py | test-only | no | no | 0 | 3 |
| CMP-00233 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/core_examples/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00234 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/deepseek/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00235 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/desktop/plugin.py | test-only | no | no | 0 | 3 |
| CMP-00236 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/fs_read_tools/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00237 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/gemini/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00238 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/git/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00239 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/halftone_app/plugin.py | test-only | no | no | 0 | 3 |
| CMP-00240 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/nesting_app/plugin.py | test-only | no | no | 0 | 3 |
| CMP-00241 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/patch_apply/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00242 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/patch_planner/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00243 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/pipeline/plugin.py | test-only | no | no | 0 | 6 |
| CMP-00244 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/project_scanner/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00245 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/telegram/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00246 | workspace/projects/novahub_review-6c9090df/working/nova_hub/integrations/verify/plugin.py | test-only | no | no | 0 | 2 |
| CMP-00251 | workspace/projects/novahub_review-6c9090df/working/nova_hub/main.py | entrypoint-only | yes | no | 0 | 5 |
| CMP-00252 | workspace/projects/novahub_review-6c9090df/working/nova_hub/run_chat.py | entrypoint-only | yes | no | 0 | 2 |
| CMP-00253 | workspace/projects/novahub_review-6c9090df/working/nova_hub/run_ui.py | entrypoint-only | yes | no | 0 | 1 |
| CMP-00254 | workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/chat/app.py | entrypoint-only | yes | no | 0 | 0 |
| CMP-00255 | workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/chat/widgets.py | duplicate-shadow | no | no | 0 | 0 |
| CMP-00256 | workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/app.py | entrypoint-only | yes | no | 0 | 6 |
| CMP-00257 | workspace/projects/novahub_review-6c9090df/working/nova_hub/ui/dashboard/widgets.py | duplicate-shadow | no | no | 0 | 0 |
