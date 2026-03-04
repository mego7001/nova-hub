# Repo Scan Summary (Nova Hub)

## 1) Entry points
- `main.py` (interactive CLI):
  - Setup: `python -m venv .venv` then activate and `pip install -r requirements.txt`
  - Run: `python main.py`
  - Optional env: `NH_PROFILE` (defaults to `engineering`)
  - Optional secrets: copy `.env.example` to `.env` for API keys

## 2) Current architecture (plugin_engine -> permission_guard -> runner)
- `main.py` loads `.env`, builds:
  - `ToolPolicy` from `configs/tool_policy.yaml`
  - `ApprovalFlow` from `configs/approvals.yaml`
  - `Runner` with an approval callback (interactive prompt)
- `PluginLoader` reads `configs/plugins_enabled.yaml`:
  - Loads each `integrations/<plugin>/novahub.plugin.json`
  - Validates plugin config via `core/plugin_engine/schema.py`
  - Imports plugin `entrypoint` and calls `init_plugin(cfg, registry, manifest)`
- `PluginRegistry` holds:
  - `PluginRegistration` entries
  - `ToolRegistration` entries
- Execution path:
  1. User selects a tool in `main.py`
  2. `Runner.execute_registered_tool()` builds `ToolRequest`
  3. `ApprovalFlow.check()` runs:
     - `ToolPolicy.evaluate_group()` (profile allow/deny)
     - `RiskScorer.score()` (base risk + bumps)
     - `Approvals` rules (auto_allow/require/deny)
  4. If approval required, `approval_callback` prompts
  5. Tool handler executes with provided args

## 3) Tooling inventory summary (by tool_group)
- `fs_write`
  - `fs.write_text`: write text file (default `outputs/hello.txt`)
  - `nesting.solve_rectangles`: pack rectangles + DXF export
  - `conical.generate_helix`: conical helix DXF export
  - `halftone.generate_pattern`: halftone DXF export
- `git`
  - `git.status`: `git status --porcelain -b`
  - `git.diff`: `git diff`
  - `git.commit`: guarded commit (disabled unless config allows)
- `telegram`
  - `telegram.send`: send message via Telegram Bot API
- `gemini`
  - `gemini.prompt`: Google Gemini generateContent
- `deepseek`
  - `deepseek.chat`: DeepSeek chat.completions

## 4) Gaps for "project analyzer + fixer" goal
- No filesystem read tools (cannot scan repo contents safely via tools)
- No repository index or inventory (file tree, metadata, language stats)
- No code search or semantic analysis tools
- No patch planning or patch application tool
- No verification tools (tests, lint, build) via guarded execution
- No structured report outputs or persistence beyond ad-hoc outputs
- No non-interactive CLI workflow (current CLI is tool picker only)

## 5) Minimal incremental roadmap to v1 analyzer (each step runnable)
1. Add `fs_read` tools: list tree, read file, read multiple files (guarded).
2. Add `repo.scan` tool: build file index + metadata summary into `outputs/`.
3. Add `repo.search` tool: regex search with limits, outputs report to `outputs/`.
4. Add `analysis.basic_audit` tool: run rule checks on index (dead files, large files, TODOs) and write report.
5. Add `patch.plan` tool: propose unified diff without applying.
6. Add `patch.apply` tool: apply unified diff to repo with approvals.
7. Add `verify.run` tool: run tests/lints via `process_exec` with approvals.
8. Add a scripted CLI mode in `main.py` (e.g., `NH_MODE=analyze`) that calls the analyzer pipeline end-to-end.
