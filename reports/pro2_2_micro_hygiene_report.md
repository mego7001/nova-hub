# Pro-2.2 Micro Hygiene Report

## Summary of Hygiene Fixes

Applied minimal hygiene-only cleanup in the requested scope:

- `core/ipc/service.py`
  - `dispatch()` now follows a strict single `if/elif` chain across all supported ops.
  - `dispatch()` keeps one `safe_payload` and one `dispatch_context`, with a single unknown-op raise and guaranteed context clear in `finally`.
  - `_chat_send()` now parses the wrapped message once and reuses it, removing duplicate wrapper parsing in the local branch.
  - `_chat_send()` retains one canonical success/error flow and one task-run finalization helper.

- `core/llm/router.py`
  - import normalized to a single line: `decide_online, OnlineDecision`.
  - route decision now typed once: `decision: OnlineDecision = decide_online(...)`.
  - no duplicate init/fallbacks/stray provider-return artifacts remain.

No telemetry schema changes, selector math changes, or feature behavior changes were introduced.

## Files Changed

- `core/ipc/service.py`
- `core/llm/router.py`

## Grep Proofs

### service.dispatch chain / unknown-op

- Command: `rg -n "elif name == .*projects\\.list" core/ipc/service.py`
- Output: `190:            elif name == "projects.list":`

- Command: `rg -n "Unknown op" core/ipc/service.py`
- Output: `210:                raise ValueError(f"Unknown op: {name}")`

### router merge-artifact hygiene

- Command: `rg -n "from core\\.llm\\.online_policy import decide_online" core/llm/router.py`
- Output: `6:from core.llm.online_policy import decide_online, OnlineDecision`

- Command: `rg -n "^\\s*def __init__\\(" core/llm/router.py`
- Output: `12:    def __init__(`

- Command: `rg -n "self\\.fallbacks\\s*=" core/llm/router.py`
- Output: `34:        self.fallbacks = ["deepseek", "gemini", "openai"]`

- Command: `rg -n "return self\\._call_provider\\(" core/llm/router.py`
- Output: `(no matches)`

- Command: `rg -n '"provider": provider,' core/llm/router.py`
- Output: `(no matches)`

## Verification Outputs

- `python -B -m py_compile core/ipc/service.py core/llm/router.py`
  - Result: PASS

- `pytest -q -p no:cacheprovider`
  - Result: `89 passed, 129 warnings`

- `python scripts/smoke_test.py`
  - Result: `smoke_status: PASS`
  - Result: `tools_loaded: 33`

- `NH_IPC_ENABLED=1 python run_ipc_cli.py --op doctor.report`
  - Result: PASS (valid JSON returned with `db`, `recent_errors`, `best_provider_by_mode`, `scoreboard`, `voice`, `ipc`, `remediation`)

## Final Status

**PRO-2 HYGIENE COMPLETE: YES**
