# NEXT SPRINT — Nova HUD v1
## Objective
Replace the WhatsApp UI with a modern digital HUD that matches Nova’s capabilities.

## Deliverables
1) New entrypoint: `python run_hud.py`
2) New UI module: `ui/hud/app.py` + `ui/hud/theme.py` + `ui/hud/widgets/*`
3) Keep `run_whatsapp.py` as legacy.
4) Zero changes to approvals and tool execution semantics.

## UX spec (v1)
- Header: Project picker, Online AI toggle (session/project), status chips.
- Left rail: Projects list (search, last message, timestamp, status, awaiting-confirm icon).
- Main: Chat transcript + input; confirmation strip appears when action pending.
- Right dock: Tabs
  - Suggestions (execute/apply)
  - Docs (open folders + ingested list)
  - Engineering (preview + assumptions + report)
  - 3D (preview + assumptions + export)
  - Sketch (canvas + export)
  - Security (run audit + gate state)
  - Timeline (filter + refresh)
- Floating “Cards” (optional): show key warnings, job waiting state.

## Implementation notes
- Use QDockWidget / splitter layout.
- Theme: dark, accent color; avoid “WhatsApp” look.
- Keep performance: lazy refresh per tab.
