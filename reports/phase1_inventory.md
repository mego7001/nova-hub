# Phase 1 Inventory (Attach Parity + PPTX + ZIP Safety)

## Supported extensions (before patch)
- `text`: `.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.yml`, `.ini`, `.cfg`
- `pdf`: `.pdf`
- `docx`: `.docx`
- `xlsx`: `.xlsx`
- `image`: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tiff`
- `zip`: `.zip`
- Missing at baseline: `.pptx`

## Existing parsers
- `core/ingest/parsers/text_parser.py`
- `core/ingest/parsers/pdf_parser.py`
- `core/ingest/parsers/docx_parser.py`
- `core/ingest/parsers/xlsx_parser.py`
- `core/ingest/parsers/image_parser.py`

## Attach locations
- Chat UI: `ui/chat/app.py` (`_attach_files`, `_ingest_paths`)
- Quick Panel / WhatsApp: `ui/quick_panel/app.py` (`_attach_files`, `_ingest_paths`), `ui/whatsapp/app.py` alias
- HUD: `ui/hud_qml/controller.py` (`attachFiles`) + QML triggers in:
  - `ui/hud_qml/qml/Main.qml`
  - `ui/hud_qml_v2/MainV2.qml`

## ZIP baseline rules (before hardening)
- Path traversal (`zip-slip`) blocked.
- `max_files` limit enforced.
- `max_total_bytes` limit enforced.
- Missing baseline behaviors:
  - Deterministic `reason_code` payload.
  - Extension whitelist for extracted members.
  - Nested-zip policy.
  - Per-member size policy.
