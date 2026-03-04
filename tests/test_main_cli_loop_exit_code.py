from __future__ import annotations

import main as cli_main


def test_run_cli_loop_returns_zero_when_all_tool_runs_succeed(monkeypatch) -> None:
    inputs = iter(["1", "q"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(cli_main, "_execute_tool_choice", lambda _runner, _tool: {"ok": True})

    code = cli_main._run_cli_loop(runner=object(), tools=[object()])

    assert code == 0


def test_run_cli_loop_returns_one_when_any_tool_run_fails(monkeypatch) -> None:
    inputs = iter(["1", "q"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    def _raise_error(_runner, _tool):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_main, "_execute_tool_choice", _raise_error)

    code = cli_main._run_cli_loop(runner=object(), tools=[object()])

    assert code == 1
