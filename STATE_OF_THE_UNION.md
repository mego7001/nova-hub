# State of the Union — Nova Hub (Snapshot)
## What works
- Conversational guardrails + explicit confirmation gating.
- Workspace-only enforcement; preview vs working separation.
- Suggestions with evidence; apply loop fixed; verify after apply.
- Jobs persistence with “Awaiting Confirm” state.
- Security Doctor audit + project-level online gating.
- Sketch: preview/apply/export DXF.
- Geometry3D: preview/apply/export STL (where present).
- Engineering Brain: materials/loads/tolerances rules + risk scoring + report persistence.
- Timeline (audit spine) for actions/events.

## Known limits
- Voice features depend on local engines; safe degradation required.
- UI currently WhatsApp-style; target is Nova HUD.
- Some QA is headless-limited; interactive click-through should be validated by user.

## Next milestone
- Replace WhatsApp UI with Nova HUD while reusing the same underlying orchestrator/runner layers.
