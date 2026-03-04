# Phase0 Inventory (Windows Stabilize & Unblock)

Date: 2026-02-22
Workspace: `D:\nouva hub\nova_hub_v1_release\nova_hub`

## 1) Runtime Entrypoints (confirmed)

- `run_hud_qml.py` -> dispatches to `main.py hud`
- `run_chat.py` -> dispatches to `main.py chat`
- `run_whatsapp.py` -> dispatches to `main.py whatsapp`
- `run_quick_panel.py` -> dispatches to `main.py whatsapp`
- `run_quick_panel_v2.py` -> dispatches to `main.py quick_panel_v2`
- `run_ui.py` -> dispatches to `main.py dashboard`
- `main.py` launchers:
  - `_launch_hud()` (`ui.hud_qml.app_qml`)
  - `_launch_chat()` (`ui.chat.app.ChatWindow`)
  - `_launch_whatsapp()` (`ui.quick_panel.app.QuickPanelWindow`)
  - `_launch_quick_panel_v2()` (`ui.quick_panel_v2.app.main`)

## 2) Current pytest temp strategy

Source: `tests/conftest.py`.

- Uses unique run tag: `run_<pid>_<timestamp>`.
- Candidate roots:
  - `NH_PYTEST_TMP` (if set)
  - `ROOT/tmp_pytest_work`
  - `ROOT/tmp_pytest`
  - `%TEMP%/nova_hub_pytest`
- Sets `config.option.basetemp` to created unique directory.
- Exports `TMP`, `TEMP`, `TMPDIR` to same base temp.

Result: Windows-friendly, workspace-local-first, unique per run.

## 3) Bytecode behavior during tests

- Python bytecode (`__pycache__`, `.pyc`) is currently written.
- Evidence: multiple files present under `nova_hub/tests/__pycache__` and `nova_hub/tests/release/__pycache__`.

## 4) Syntax/import blocker status (baseline)

- `py_compile` on core entrypoints and target UIs: PASS.
- Import smoke on `run_hud_qml`, `run_chat`, `run_whatsapp`, `ui.chat.app`, `ui.whatsapp.app`: PASS.
- Existing blockers are not syntax/import hard-blockers at entrypoint level.

## 5) Timeline/log readers loading full files

### Core
- `core/audit_spine.py`
  - `AuditSpine._read_events()` builds full `out` list.
  - `ProjectAuditSpine.read_events(limit=...)` reads full file then slices tail.

### HUD/QML
- `ui/hud_qml/controller.py`
  - module helper `_read_jsonl()` full-loads file.
- `ui/hud_qml/managers/chat_manager.py`
  - `_read_jsonl()` full-loads file.
  - `load_messages()` slices `items[-400:]` after full-load.

### Quick Panel
- `ui/quick_panel/app.py`
  - timeline refresh uses `ProjectAuditSpine.read_events(limit=200)` (currently full-read then slice).

## 6) Optional dependency guard gaps observed

No unified guard utility currently exists (`core/utils/optional_deps.py` missing).

Observed mixed handling:
- Some modules correctly catch `ImportError`/`ModuleNotFoundError`.
- Some optional import paths only catch broad runtime errors but not explicit import errors.

High-risk optional deps in runtime paths:
- Voice stack: `faster_whisper`, `ctranslate2`, `sounddevice`, `pyttsx3`.
- OCR/docs parsing: `Pillow`, `pytesseract`, `python-docx`, `PyMuPDF`, `openpyxl`.
- CAD: `cadquery`, `shapely`.

## 7) Safety semantics baseline

- No P0 requirement asks to modify approvals.
- Approval/safety semantics are preserved as-is (no bypass changes planned).
