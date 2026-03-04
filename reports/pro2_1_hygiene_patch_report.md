# Pro-2.1 Hygiene Patch Report

## Summary

Applied a minimal hygiene-only patch focused on dispatch and chat-flow cleanup in IPC core service.

- Removed ambiguity by enforcing a single explicit dispatch chain in `dispatch()`.
- Removed duplicated task-run completion branches in `_chat_send()` by centralizing finish logic.
- Verified `core/llm/router.py` merge-artifact indicators are clean (single `decide_online` import, single `self.fallbacks`, no broken `return self._call_provider(...)` loop pattern).

No telemetry schema, selector math, or feature behavior changes were introduced.

## Files Changed

- `core/ipc/service.py`
  - `dispatch` (single source-of-truth op routing; `if/elif` chain; safe payload normalization)
  - `_chat_send` (single task-run finisher helper; exactly one success/error finalization path)

No code edits were required in `core/llm/router.py` during this hygiene pass; it already matched the expected clean structure.

## Pre-Patch Baseline

Commands:

- `pytest -q -p no:cacheprovider`
- `python scripts/smoke_test.py`

Results:

- `89 passed, 129 warnings`
- `smoke_status: PASS`
- `tools_loaded: 33`

## Post-Patch Verification

Commands:

- `python -B -m py_compile core/ipc/service.py core/llm/router.py`
- `pytest -q -p no:cacheprovider`
- `python scripts/smoke_test.py`
- `NH_IPC_ENABLED=1 python run_ipc_cli.py --op doctor.report`

Results:

- `py_compile`: PASS
- `pytest`: `89 passed, 129 warnings`
- `smoke_status: PASS` / `tools_loaded: 33`
- `doctor.report`: PASS (valid JSON response returned)

## Grep Proofs

1) Unknown-op raise (single dispatch path)

Command:

- `rg -n 'raise ValueError\\(f\\\"Unknown op' core/ipc/service.py`

Output:

- `210:                raise ValueError(f"Unknown op: {name}")`

2) Broken loop artifact removed (`return self._call_provider(` should be absent)

Command:

- `rg -n 'return self\\._call_provider\\(' core/llm/router.py`

Output:

- no matches

3) `decide_online` import appears once

Command:

- `rg -n 'from core\\.llm\\.online_policy import decide_online' core/llm/router.py`

Output:

- `6:from core.llm.online_policy import decide_online`

4) `self.fallbacks =` appears once

Command:

- `rg -n 'self\\.fallbacks =' core/llm/router.py`

Output:

- `34:        self.fallbacks = ["deepseek", "gemini", "openai"]`
