# Jarvis Core QA

Generated at: 2026-02-06T06:03:12.980615Z
Summary: 5 passed / 0 failed

## Tests
- [PASS] Disagreement: Disagreement + single question + no execution
- [PASS] Graduated Warnings: Level 2 differs, no question spam, level 3 logged
- [PASS] Confirmation Gating: No execution without explicit confirm
- [PASS] Recovery Mode: Plan first, reminder once after success
- [PASS] Persistence: Warning level persists across sessions

## Limitations
- Simulator mirrors Jarvis Core flow; it does not drive the Qt UI.
- Tool execution gating is simulated; UI button flows are not exercised.
