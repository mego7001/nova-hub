# Verify Smoke Report

Timestamp: 2026-02-22T23:04:53.714186Z
Target Root: D:\nouva hub\nova_hub_v1_release\nova_hub

## Checks
- success: python -m compileall D:\nouva hub\nova_hub_v1_release\nova_hub
- failed: python main.py --list-tools
  - stderr: usage: main.py [-h]
               {hud,core,chat,dashboard,whatsapp,quick_panel_v2,cli,call} ...
main.py: error: unrecognized arguments: --list-tools

## Recommendation
- Fix failing checks and re-run verify.smoke.
