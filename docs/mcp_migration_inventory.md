# MCP Migration Inventory

Static inventory generated from `configs/plugins_enabled.yaml` and AST parsing of `integrations/*/plugin.py`.
No runtime plugin loading, no core/HUD startup, deterministic ordering.

## Tool Registry (Static)

| tool_id | tool_group | plugin_id | op | handler | plugin_file | default_target |
| --- | --- | --- | --- | --- | --- | --- |
| cad.dxf.generate | fs_write | cad_pipeline | cad_dxf_generate | cad_dxf_generate | integrations/cad_pipeline/plugin.py | outputs/generated_shape.dxf |
| cad.step.generate | fs_write | cad_pipeline | cad_step_generate | cad_step_generate | integrations/cad_pipeline/plugin.py | outputs/generated_part.step |
| conical.generate_helix | fs_write | conical_app | conical_generate_helix | generate_helix | integrations/conical_app/plugin.py | outputs/conical_helix_xy.dxf |
| conversation.chat | fs_read | conversation | conversation_chat | conversation_chat | integrations/conversation/plugin.py |  |
| deepseek.chat | deepseek | deepseek | deepseek_chat | chat | integrations/deepseek/plugin.py |  |
| desktop.open_chrome | process_exec | desktop | desktop_open_chrome | open_chrome | integrations/desktop/plugin.py |  |
| desktop.open_folder | process_exec | desktop | desktop_open_folder | open_folder | integrations/desktop/plugin.py |  |
| desktop.open_vscode | process_exec | desktop | desktop_open_vscode | open_vscode | integrations/desktop/plugin.py |  |
| fs.list_dir | fs_read | fs_read_tools | fs_list_dir | list_dir | integrations/fs_read_tools/plugin.py | . |
| fs.read_text | fs_read | fs_read_tools | fs_read_text | read_text | integrations/fs_read_tools/plugin.py |  |
| fs.write_text | fs_write | core_examples | fs_write | write_text | integrations/core_examples/plugin.py | outputs/hello.txt |
| gemini.prompt | gemini | gemini | gemini_prompt | prompt | integrations/gemini/plugin.py |  |
| git.commit | git | git | git_commit | commit | integrations/git/plugin.py |  |
| git.diff | git | git | git_diff | diff | integrations/git/plugin.py |  |
| git.status | git | git | git_status | status | integrations/git/plugin.py |  |
| halftone.generate_pattern | fs_write | halftone_app | halftone_generate_pattern | halftone_gradient | integrations/halftone_app/plugin.py | outputs/halftone_gradient.dxf |
| nesting.solve_rectangles | fs_write | nesting_app | nesting_solve_rectangles | solve | integrations/nesting_app/plugin.py | outputs/nesting_result.dxf |
| ollama.chat | ollama | ollama | ollama_chat | chat | integrations/ollama/plugin.py |  |
| ollama.health.ping | ollama | ollama | ollama_health_ping | health_ping | integrations/ollama/plugin.py |  |
| ollama.models.list | ollama | ollama | ollama_models_list | models_list | integrations/ollama/plugin.py |  |
| openai.chat | openai | openai | openai_chat | chat | integrations/openai/plugin.py |  |
| patch.apply | fs_write | patch_apply | patch_apply | patch_apply | integrations/patch_apply/plugin.py |  |
| patch.plan | fs_write | patch_planner | patch_plan | patch_plan | integrations/patch_planner/plugin.py |  |
| pipeline.run | fs_write | pipeline | pipeline_run | pipeline_run | integrations/pipeline/plugin.py |  |
| project.scan_repo | fs_read | project_scanner | project_scan | scan_repo | integrations/project_scanner/plugin.py | . |
| repo.search | fs_read | fs_read_tools | repo_search | repo_search | integrations/fs_read_tools/plugin.py | . |
| run.preview | process_exec | run_preview | run_preview | run_preview | integrations/run_preview/plugin.py |  |
| run.stop | process_exec | run_preview | run_stop | stop_preview | integrations/run_preview/plugin.py |  |
| security.audit | fs_read | security_doctor | security_audit | security_audit | integrations/security_doctor/plugin.py |  |
| sketch.apply | fs_write | sketch | sketch_apply | sketch_apply | integrations/sketch/plugin.py |  |
| sketch.export_dxf | fs_write | sketch | sketch_export_dxf | sketch_export_dxf | integrations/sketch/plugin.py |  |
| sketch.parse | fs_read | sketch | sketch_parse | sketch_parse | integrations/sketch/plugin.py |  |
| stable_diffusion.generate | media_gen | stable_diffusion | generate_image | generate_image | integrations/stable_diffusion/plugin.py | outputs |
| stable_diffusion.upscale | media_gen | stable_diffusion | upscale_image | upscale_image | integrations/stable_diffusion/plugin.py | outputs |
| telegram.send | telegram | telegram | telegram_send | send | integrations/telegram/plugin.py |  |
| verify.smoke | process_exec | verify | verify_smoke | verify_smoke | integrations/verify/plugin.py |  |
| voice.stt_record | fs_write | voice | voice_stt_record | voice_stt_record | integrations/voice/plugin.py |  |
| voice.tts_speak | process_exec | voice | voice_tts_speak | voice_tts_speak | integrations/voice/plugin.py |  |

## MCP Candidate Buckets

### patch.*
- `patch.apply`
- `patch.plan`

### fs.* + repo/project scan
- `fs.list_dir`
- `fs.read_text`
- `fs.write_text`
- `project.scan_repo`
- `repo.search`

### sketch.* / cad.*
- `cad.dxf.generate`
- `cad.step.generate`
- `sketch.apply`
- `sketch.export_dxf`
- `sketch.parse`

### stable_diffusion.*
- `stable_diffusion.generate`
- `stable_diffusion.upscale`

### voice.*
- `voice.stt_record`
- `voice.tts_speak`

## Notes

- `engineering.*` group is not present in current static registry.
- Total tools parsed: 38
- Project root: `.`
