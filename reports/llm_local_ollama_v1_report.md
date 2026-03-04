# LLM Local Ollama v1 Report

## Scope

- Added first-class Ollama local provider operations:
  - `ollama.health.ping`
  - `ollama.models.list`
  - `ollama.chat`
- Enabled local-first routing with task-aware model selection for `gemma3:4b` and `qwen2.5-coder:7b-instruct`.
- Added HUD v2 health visibility for Ollama status/models and session override.

## Environment Variables

Primary flags (new):

- `NH_OLLAMA_ENABLED` (default `1`)
- `NH_OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`)
- `NH_OLLAMA_DEFAULT_MODEL_GENERAL` (default `gemma3:4b`)
- `NH_OLLAMA_DEFAULT_MODEL_CODE` (default `qwen2.5-coder:7b-instruct`)
- `NH_OLLAMA_DEFAULT_MODEL_VISION` (default `llava`)
- `NH_OLLAMA_MODEL_OVERRIDE` (optional)

Backward-compatible flags (kept):

- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_MODEL_GENERAL`
- `OLLAMA_MODEL_CODER`
- `OLLAMA_MODEL_VISION`
- `OLLAMA_VISION_MODEL`

## Default Routing Table

- `general` / `conversation` / `summarize_docs` -> `gemma3:4b`
- `gen_2d_dxf` / `gen_3d_step` / `build_software` / `patch_planning` / `deep_reasoning` -> `qwen2.5-coder:7b-instruct`
- `vision` -> `llava`

Policy:

- `local_first=true`
- `external_backup_only=true`
- External providers are used only if local Ollama fails or returns empty output.

## Connectivity Verification

1. Direct HTTP probe:

```powershell
curl http://127.0.0.1:11434/api/tags
```

2. IPC probes:

```powershell
python main.py call --op ollama.health.ping
python main.py call --op ollama.models.list
python main.py call --op ollama.chat --payload-json "{\"prompt\":\"hello\"}"
```

3. Doctor summary:

```powershell
python main.py call --op doctor.report
```

## Tests Added

- `tests/test_ollama_health.py`
- `tests/test_ollama_models_list.py`
- `tests/test_ollama_chat_basic.py`
- `tests/test_router_prefers_ollama_offline.py`

## Verification Commands

```powershell
python -B -m py_compile integrations/ollama/plugin.py core/llm/providers/ollama_http.py
pytest -q -p no:cacheprovider --basetemp .\.pytest_tmp
python scripts/smoke_test.py
```

## Known Limitations

- No streaming response path yet.
- Token accounting for Ollama uses estimates unless explicit token counts are returned.
- Session model override is runtime/session-scoped and not persisted to config files.

