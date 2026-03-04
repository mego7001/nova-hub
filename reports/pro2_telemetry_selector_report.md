# Pro-2 Telemetry + Selector Report

## Scope Delivered

Implemented IPC-native telemetry and provider selection in the core service with additive behavior:

- Persistent SQLite telemetry store
- Provider scoreboard/stat queries
- Deterministic weighted provider selector
- `doctor.report` diagnostics op
- Minimal HUD + Quick Panel health/stats surfaces

Legacy behavior remains unchanged when `NH_IPC_ENABLED=0`.

## Telemetry DB

- Location: `workspace/runtime/telemetry/nova_telemetry.sqlite3`
- Engine: stdlib `sqlite3`
- Journal mode: WAL enabled
- Schema version: `1` (`schema_meta`)

### Tables

1. `schema_meta(schema_version, created_at)`
2. `llm_calls(...)`
3. `tool_calls(...)`
4. `task_runs(...)`

### Migration approach

- `core/telemetry/db.py` initializes DB, enforces WAL, creates tables/indexes via `CREATE TABLE IF NOT EXISTS`.
- `schema_meta` stores integer version and creation timestamp.

## Selector Policy

Implemented in:

- `core/llm/selection_policy.py`
- `core/llm/selector.py`

Formula:

`score = Wq*quality - Wc*cost - Wl*latency - We*error_rate`

Where:

- `quality`: recent success rate
- `cost`: avg `cost_usd`, fallback to token proxy when unknown
- `latency`: avg latency ms
- `error_rate`: recent error ratio

Recency/data window:

- 7-day window
- max 200 recent calls per `(provider, mode, request_kind)`
- sparse-data threshold: `<20` calls triggers deterministic fallback boost

Guardrails:

- `build_software`: minimum success rate guard (`0.85`) with strong penalty if alternatives exceed threshold
- cooldown penalty for recent `rate_limit` / `auth` errors
- deterministic tie-breaker by fallback order and provider id

## IPC Ops Added

Added to `core/ipc/service.py` dispatcher:

- `telemetry.scoreboard.get`
- `telemetry.provider.stats`
- `doctor.report`
- `selector.pick_provider` (internal/debug)

Also integrated:

- Tool-call telemetry wrapping around core runner execution (centralized in service)
- LLM call telemetry in `core/llm/router.py` for each provider attempt (success + failures)
- `task_runs` start/finish hooks for `build_software` mode in IPC chat path

## UI Surface (Minimal)

### HUD QML

- New panel: `Health / Stats`
- New QML panel component: `ui/hud_qml/qml/panels/HealthStatsPanel.qml`
- New controller model/summary + refresh slot:
  - `healthStatsModel`
  - `healthStatsSummary`
  - `refreshHealthStats()`
- Data source: IPC call to `telemetry.scoreboard.get`

### Quick Panel

- Added `Health` button near input controls
- Added `Health/Stats` tab with refresh action and provider list
- Data source: IPC call to `telemetry.scoreboard.get`

## Verification Commands + Results

### Compile

```powershell
$files = Get-ChildItem core/telemetry -Filter *.py | ForEach-Object { $_.FullName }; $files += @((Resolve-Path core/llm/selector.py).Path,(Resolve-Path core/llm/selection_policy.py).Path,(Resolve-Path core/ipc/service.py).Path,(Resolve-Path run_core_service.py).Path,(Resolve-Path run_ipc_cli.py).Path); python -B -m py_compile $files
```

Result: pass

### Mandatory new tests

```powershell
pytest -q tests/test_telemetry_db_migrations.py tests/test_telemetry_record_and_query.py tests/test_selector_weighted_deterministic.py tests/test_doctor_report.py -p no:cacheprovider
```

Result: `4 passed`

### Full suite

```powershell
pytest -q -p no:cacheprovider
```

Result: `89 passed, 129 warnings`

### Smoke

```powershell
python scripts/smoke_test.py
```

Result: `smoke_status: PASS`, `tools_loaded: 33`

### IPC smoke

```powershell
$env:QT_QPA_PLATFORM='offscreen'; $env:NH_HUD_AUTOCLOSE_MS='200'; $env:NH_IPC_ENABLED='1'; python run_hud_qml.py
$env:NH_IPC_ENABLED='1'; python run_ipc_cli.py --op doctor.report
```

Result: HUD offscreen exit `0`; `doctor.report` returned valid JSON with required sections.

## Known Limitations

- Cost extraction from provider responses is nullable in v1 (currently no provider-specific USD parser wired).
- Selector currently deterministic/rule-based only; no online learning.
- `task_runs` enrichment (QA/tests counts) is basic and can be expanded deeper into orchestrator lifecycle.
- Event streaming remains optional; request/response path is primary for this phase.

## Bandit-Ready Hooks (Prepared)

- Central telemetry schema and recorder APIs (`llm_calls`, `tool_calls`, `task_runs`) support future reward/outcome signals.
- Selector already consumes per-provider historical aggregates; adding exploration policy can extend `pick_provider` without schema break.
- `selector.pick_provider` IPC op enables debug/inspection for future adaptive policy rollout.
