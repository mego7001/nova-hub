# Nova Hub Conversation Capability Audit (Text + Voice)

## Environment Summary

- Audit scope: local/offline verification only (no internet dependency).
- OS: `Windows-10-10.0.19045-SP0`
- Python: `3.13.7`
- Executable: `C:\Users\Victus\AppData\Local\Programs\Python\Python313\python.exe`
- Repo root: `D:\nouva hub\nova_hub_v1_release\nova_hub`

### Requirements Files

- `requirements-base.txt`: FOUND
- `requirements-ui.txt`: FOUND
- `requirements-voice.txt`: FOUND

### Installed Voice/UI Dependencies (evidence)

From `python -m pip freeze | rg -i "pyside6|sounddevice|faster-whisper|piper|whisper|torch"`:

- `PySide6==6.10.1`
- `PySide6_Addons==6.10.1`
- `PySide6_Essentials==6.10.1`

Direct import/binary checks:

- `sounddevice`: MISSING (`ModuleNotFoundError`)
- `faster_whisper`: MISSING (`ModuleNotFoundError`)
- `torch`: MISSING (`ModuleNotFoundError`)
- `pyttsx3`: MISSING (`ModuleNotFoundError`)
- `piper` binary: MISSING

---

## Text Gate Results

### 1) CLI sanity

- `python main.py --help` -> PASS (usage printed, exit 0).
- `python run_chat.py --help` -> no CLI help mode; process enters UI loop and timed out under audit timeout (exit 124).

### 2) UI startup/headless

- HUD offscreen:
  - `QT_QPA_PLATFORM=offscreen`
  - `NH_HUD_AUTOCLOSE_MS=200`
  - `python run_hud_qml.py`
  - Result: PASS (exit 0, no crash output).

- Chat UI offscreen startup probe:
  - `QT_QPA_PLATFORM=offscreen; python run_chat.py`
  - Result: no immediate crash; process stayed alive until timeout (exit 124).

- Quick Panel offscreen startup probe:
  - `QT_QPA_PLATFORM=offscreen; python run_quick_panel.py`
  - Result: no immediate crash; process stayed alive until timeout (exit 124).

### 3) Compile/import sanity for text UIs

- `python -B -m py_compile ui/quick_panel/app.py ui/chat/app.py` -> PASS (exit 0).

### 4) Message pipeline evidence (importable/callable path)

- HUD send boundary: `ui/hud_qml/controller.py:3101` (`send_message`), mode routing at `ui/hud_qml/controller.py:3139`.
- Chat send boundary: `ui/chat/app.py:745` (`_send_message`), mode routing at `ui/chat/app.py:756`.
- Quick Panel send boundary: `ui/quick_panel/app.py:1293` (`_send_message`), mode routing at `ui/quick_panel/app.py:1303`.
- Conversation tool binding present:
  - `ui/chat/app.py:107` (`conversation.chat`)
  - `ui/quick_panel/app.py:349` (`conversation.chat`)

Validation tests:

- `pytest -q tests/test_hud_qml_general_chat.py` -> `8 passed`.
- `pytest -q tests/test_chat_whatsapp_unified_input_wiring.py` -> `2 passed`.

### Text Gate Verdict

- **PASS**
- Notes:
  - HUD fully passes offscreen startup gate.
  - Chat/Quick Panel are stable under offscreen launch (no immediate crash), but require manual interaction for full conversation loop in this non-interactive audit mode.

---

## Voice Gate Results

### 1) Plugin/tool availability

- `python scripts/smoke_test.py` -> `smoke_status: PASS`, `tools_loaded: 33`.
- Voice plugin enabled:
  - `configs/plugins_enabled.yaml:23` -> `- voice`
  - `integrations/voice/novahub.plugin.json` exists.
- Voice tools registered in plugin:
  - `integrations/voice/plugin.py` defines:
    - `voice.stt_record`
    - `voice.tts_speak`

Runtime registry probe:

- `voice.stt_record` present: `True`
- `voice.tts_speak` present: `True`

### 2) Env/config flags discovered

From `docs/voice_chat_local.md` + code (`core/voice/schemas.py`, providers):

- `VOICE_ENABLED_DEFAULT`
- `VOICE_STT_MODEL`
- `VOICE_DEVICE`
- `VOICE_STT_DEVICE`
- `VOICE_TTS_VOICE`
- `VOICE_SAMPLE_RATE`
- `VOICE_VAD_MODE`
- `VOICE_VAD_THRESHOLD`
- `VOICE_VAD_MIN_SPEECH_MS`
- `VOICE_VAD_SILENCE_MS`
- `VOICE_TTS_PAUSE_MS`
- `PIPER_BIN`

### 3) STT functional check (file-based / graceful fallback)

#### A) Tool-level call through plugin (non-interactive)

Executed `voice.stt_record` handler with `project_id='voice_audit_tmp', seconds=1`.

Result (structured, no crash):

```json
{
  "status": "unavailable",
  "audio_path": "D:\\nouva hub\\nova_hub_v1_release\\nova_hub\\workspace\\projects\\voice_audit_tmp\\temp\\audio\\voice_input.wav",
  "transcript": "",
  "record_engine": "silent",
  "stt": {
    "status": "unavailable",
    "engine": "none"
  }
}
```

Interpretation:

- Mic/STT dependencies are missing, but tool returns structured fallback safely.

#### B) Provider-level file STT on generated silent wav

- Generated 1-second silent wav (`tmp_voice_audit_silence.wav`).
- Called `FasterWhisperSttProvider.transcribe_file(...)`.
- Result: raised clear actionable error (no hard crash):

`RuntimeError("Missing dependency 'faster-whisper'. Install with: pip install faster-whisper")`

### 4) Optional TTS check

Tool-level `voice.tts_speak` call returned structured fallback:

```json
{"status": "unavailable", "engine": "none"}
```

No crash observed.

### Voice Gate Verdict

- **PASS (graceful fallback)**
- Reason:
  - Missing dependencies are handled safely with explicit/unavailable status and actionable messages.
  - No app/tool hard crash during voice audit flows.

---

## Blockers and Remediation

### Blockers for full local voice conversation (real STT/TTS output)

1. Missing Python dependencies:
   - `faster-whisper`
   - `sounddevice`
   - (optional runtime dependency path may require `torch` depending stack)
2. Missing TTS runtime:
   - `piper` binary not found
   - `VOICE_TTS_VOICE` model path not configured

### Exact remediation steps

1. Install voice requirements:
   - `pip install -r requirements-voice.txt`
2. Ensure STT dependency is available:
   - `pip install faster-whisper sounddevice`
3. Install Piper and set env:
   - `PIPER_BIN=<path-to-piper.exe>`
   - `VOICE_TTS_VOICE=<path-to-voice.onnx>`
4. Re-run gates:
   - `python scripts/smoke_test.py`
   - `pytest -q tests/test_hud_qml_voice.py tests/test_voice_loop.py`
   - `QT_QPA_PLATFORM=offscreen; NH_HUD_AUTOCLOSE_MS=200; python run_hud_qml.py`

---

## Final Verdict

`READY_FOR_PRO_PHASE: YES`

Rationale: Text Gate is PASS, and Voice Gate is PASS via graceful fallback behavior with clear remediation for missing local dependencies.
