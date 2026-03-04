# Install Matrix

## Python Version

- Recommended: Python `3.11+`

## Minimal (HUD + core plugins)

```powershell
pip install -r requirements-ui.txt
```

Run:

```powershell
python main.py hud
```

Quick panel runtimes:

```powershell
python main.py whatsapp
python main.py quick_panel_v2
```

Compatibility wrapper:

```powershell
python run_hud_qml.py
python run_quick_panel.py
python run_quick_panel_v2.py
```

## CAD / DXF

```powershell
pip install -r requirements-cad.txt
```

Includes:

- `ezdxf`
- `shapely`
- `numpy`

## 3D / STEP (optional)

```powershell
pip install -r requirements-3d.txt
```

## Voice (optional, local-first)

```powershell
pip install -r requirements-voice.txt
```

Voice dependencies are optional. If they are missing, Nova still runs normally in text mode and only live voice capture/playback is disabled at runtime.

Python 3.13 example:

```powershell
C:/Users/Victus/AppData/Local/Programs/Python/Python313/python.exe -m pip install -r requirements-voice.txt
```

## Full install (v1 target)

```powershell
pip install -r requirements-ui.txt
pip install -r requirements-cad.txt
pip install -r requirements-3d.txt
pip install -r requirements-voice.txt
pip install pytest
```

## Routing/Budget Config

- Routing policy file: `configs/llm_routing.yaml`
- Optional runtime env:
  - `NH_SESSION_TOKEN_BUDGET`
  - `NH_DAILY_TOKEN_BUDGET`
  - `NH_OLLAMA_ENABLED` (default: `1`)
  - `NH_OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
  - `NH_OLLAMA_DEFAULT_MODEL_GENERAL` (default: `gemma3:4b`)
  - `NH_OLLAMA_DEFAULT_MODEL_CODE` (default: `qwen2.5-coder:7b-instruct`)
  - `NH_OLLAMA_DEFAULT_MODEL_VISION` (default: `llava`)
  - `NH_OLLAMA_MODEL_OVERRIDE` (optional session override)
  - `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
  - `OLLAMA_MODEL` (global fallback model)
  - `OLLAMA_VISION_MODEL` (legacy vision model override)
  - `OLLAMA_MODEL_GENERAL` (recommended: `gemma3:4b`)
  - `OLLAMA_MODEL_CODER` (recommended: `qwen2.5-coder:7b-instruct`)
  - `OLLAMA_MODEL_VISION` (recommended: `llava`)

Secrets note:

- `GITHUB_API_KEY` is not used by default in the current enabled plugin set. Keep it unset unless a GitHub integration plugin is explicitly added.

IPC debug operations for Ollama:

- `python main.py call --op ollama.health.ping`
- `python main.py call --op ollama.models.list`
- `python main.py call --op ollama.chat --payload-json "{\"prompt\":\"hello\"}"`
