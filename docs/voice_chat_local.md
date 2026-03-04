# Local Voice Chat (faster-whisper + Piper)

## Scope

Local voice loop is available across:

- HUD (`ui/hud_qml`)
- Desktop chat (`ui/chat`)
- Quick Panel (`ui/quick_panel`)

`run_whatsapp.py` remains only a compatibility launcher alias for Quick Panel.

Voice transcripts are injected through the same message send boundary used by typed input.

## Providers (Default)

- STT: `faster-whisper` (local)
- TTS: `piper` (local)

Cloud voice providers are not required for default operation.

## Install (Windows-first)

### Python dependencies

```powershell
pip install -r requirements-voice.txt
```

If you are on Python 3.13, install inside the same interpreter used to run Nova:

```powershell
C:/Users/Victus/AppData/Local/Programs/Python/Python313/python.exe -m pip install -r requirements-voice.txt
```

### Piper binary + voice model

Install Piper and download at least one `.onnx` voice.

Set:

- `PIPER_BIN` (or add Piper to `PATH`)
- `VOICE_TTS_VOICE` (path to `.onnx` voice)

Example:

```powershell
$env:PIPER_BIN = "C:\\tools\\piper\\piper.exe"
$env:VOICE_TTS_VOICE = "C:\\voices\\en_US-lessac-medium.onnx"
```

## Environment Config

- `VOICE_ENABLED_DEFAULT=false`
- `VOICE_STT_MODEL=small`
- `VOICE_DEVICE=default`
- `VOICE_TTS_VOICE=<voice-model.onnx>`
- `VOICE_SAMPLE_RATE=16000`
- `VOICE_VAD_MODE=energy`
- `VOICE_VAD_THRESHOLD=650`
- `VOICE_VAD_MIN_SPEECH_MS=260`
- `VOICE_VAD_SILENCE_MS=520`
- `VOICE_TTS_PAUSE_MS=35`

HUD persisted voice preferences:

- `workspace/ui_state/hud_layout.json` (`voice` section)

## Runtime Behavior

1. Microphone frames are captured in background threads.
2. Voice activity detection determines utterance boundaries.
3. STT transcribes utterance locally.
4. Transcript is sent through normal chat send path.
5. Assistant text is queued to local TTS.

If optional voice dependencies are missing (`ctranslate2`, `faster-whisper`, `sounddevice`), Nova keeps running in text/tools mode and only voice runtime is disabled with a clear UI status.

### Barge-in

If speech is detected while TTS is speaking, TTS is stopped immediately and listening/transcription is prioritized.

## UI Controls

### HUD

- full Voice Chat panel (enable, mute, stop, replay, device picker)
- palette actions:
  - `voice.toggle`
  - `voice.mute`
  - `voice.unmute`
  - `voice.stop_speaking`
  - `voice.replay_last`

### Desktop chat

- `Voice On/Off`
- `Mute/Unmute`
- `Stop Voice`
- `Replay`

### Quick Panel

- `Mic` toggles local voice loop
- speaker toggle controls mute/unmute behavior
- `Stop Voice` interrupts active TTS

## Troubleshooting

1. Mic start failure:
- verify Windows microphone privacy settings
- verify input device exists
- try setting `VOICE_DEVICE`

2. STT failure:
- install `requirements-voice.txt`
- start with `VOICE_STT_MODEL=small`

3. TTS failure:
- verify Piper binary is reachable
- verify `VOICE_TTS_VOICE` path exists
