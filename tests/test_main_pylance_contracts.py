from __future__ import annotations

import inspect

import main as cli_main


def test_default_bool_value_narrows_to_bool_or_none() -> None:
    assert cli_main._default_bool_value(True) is True
    assert cli_main._default_bool_value(False) is False
    assert cli_main._default_bool_value(inspect._empty) is None
    assert cli_main._default_bool_value("x") is None


def test_prompt_for_params_bool_default_uses_bool_or_none(monkeypatch) -> None:
    seen: list[bool | None] = []

    def _fake_prompt_bool(_label: str, default: bool | None) -> bool | None:
        seen.append(default)
        return True

    monkeypatch.setattr(cli_main, "_prompt_bool", _fake_prompt_bool)

    def handler(flag: bool = False):
        return flag

    values = cli_main._prompt_for_params(handler)

    assert values["flag"] is True
    assert seen == [False]
