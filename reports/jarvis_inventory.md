# Jarvis UX Unification Inventory (Checkpoint 0)

## Backend chat send boundary
- HUD QML send signal: `ui/hud_qml/qml/components/CommandBar.qml:10`, `ui/hud_qml/qml/components/CommandBar.qml:17`
- HUD QML -> controller boundary: `ui/hud_qml/qml/Main.qml:404`
- HUD backend boundary function: `ui/hud_qml/controller.py:2823` (`send_message`)
- HUD chat-mode reply pipeline: `ui/hud_qml/controller.py:1396` (`_reply_in_chat_mode`), `ui/hud_qml/controller.py:1371` (`_interactive_chat_reply`)

- Desktop Chat UI send hooks: `ui/chat/app.py:290`, `ui/chat/app.py:291`
- Desktop Chat boundary function: `ui/chat/app.py:498` (`_send_message`)
- Desktop Chat tool dispatch to conversation: `ui/chat/app.py:511`

- WhatsApp UI send hooks: `ui/whatsapp/app.py:701`, `ui/whatsapp/app.py:702`
- WhatsApp boundary function: `ui/whatsapp/app.py:1105` (`_send_message`)
- WhatsApp tool dispatch to conversation: `ui/whatsapp/app.py:1223`

## Registry / tool catalog entrypoint
- Plugin loading in HUD: `ui/hud_qml/controller.py:380`
- Plugin loading in Chat UI: `ui/chat/app.py:57`
- Plugin loading in WhatsApp UI: `ui/whatsapp/app.py:304`
- Loader integration manifest path resolution: `core/plugin_engine/loader.py:20`, `core/plugin_engine/loader.py:28`
- Tool registration primitive: `core/plugin_engine/registry.py:35`
- Conversation tool registration: `integrations/conversation/plugin.py:47`
- Existing advanced full-tool listing (chat UI): `ui/chat/app.py:90`, `ui/chat/app.py:190`

## Ingest entrypoints (chat/whatsapp)
- Ingest core class: `core/ingest/ingest_manager.py:21`
- Ingest function: `core/ingest/ingest_manager.py:28`
- Chat attach flow: `ui/chat/app.py:471` -> `ui/chat/app.py:479` -> `ui/chat/app.py:483`
- WhatsApp attach flow: `ui/whatsapp/app.py:2089` -> `ui/whatsapp/app.py:2097` -> `ui/whatsapp/app.py:2099`

## HUD input components and current panels
- Command bar component exists: `ui/hud_qml/qml/components/CommandBar.qml`
- Current HUD panel titles in `ui/hud_qml/qml/Main.qml`:
  - `:413` Diff Preview
  - `:458` Engineering
  - `:492` Voice Chat
  - `:506` 3D Mind
  - `:520` Sketch / DXF
  - `:533` DXF/Clip QA
  - `:544` Security Doctor
  - `:561` Timeline

## Currently supported file types
- Extension classification in `core/ingest/file_types.py`:
  - Text/code/config: `:5`
  - PDF: `:6`
  - DOCX: `:7`
  - XLSX: `:8`
  - Images: `:9`
  - ZIP: `:10`
- Classifier function: `core/ingest/file_types.py:13`
- Parsers:
  - `core/ingest/parsers/text_parser.py:5`
  - `core/ingest/parsers/pdf_parser.py:5`
  - `core/ingest/parsers/docx_parser.py:5`
  - `core/ingest/parsers/xlsx_parser.py:5`
  - `core/ingest/parsers/image_parser.py:5`
- ZIP safety/limits: `core/ingest/unzip.py:11`, `core/ingest/unzip.py:19`, `core/ingest/unzip.py:24`, `core/ingest/unzip.py:28`

## Blockers / integrity issues
- Hard blocker (resolved in Checkpoint 1): `ui/whatsapp/app.py` syntax issue around `sketch_apply` branch.
- Windows environment blocker affecting verification reliability:
  - `py_compile` intermittently fails writing `__pycache__` due ACL denied.
  - test temp dir ACL can fail under `tmp_pytest_work`.
- No hard import chain failure found for `run_hud_qml.py`, `run_chat.py`, `run_ui.py`, `run_whatsapp.py` by source-compile checks.
