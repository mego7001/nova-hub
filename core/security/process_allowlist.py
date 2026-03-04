from __future__ import annotations
import os
from typing import List, Optional

_ALLOWED_EXEC = {"python", "chrome", "code", "explorer"}
_DENY_EXEC = {"cmd", "powershell", "pwsh"}


class CommandNotAllowed(ValueError):
    pass


def validate_command(cmd: List[str], allowed_entries: Optional[List[str]] = None) -> None:
    if not cmd or not cmd[0]:
        raise CommandNotAllowed("Empty command")
    exe = os.path.basename(cmd[0]).lower()
    if exe.endswith(".exe"):
        exe = exe[:-4]
    if exe in _DENY_EXEC:
        raise CommandNotAllowed("Executable is explicitly denied")
    if exe not in _ALLOWED_EXEC:
        raise CommandNotAllowed("Executable not allowlisted")

    if exe == "python":
        _validate_python_args(cmd[1:], allowed_entries or [])


def _validate_python_args(args: List[str], allowed_entries: List[str]) -> None:
    if not args:
        raise CommandNotAllowed("python requires arguments")
    if args[0] == "-c":
        raise CommandNotAllowed("python -c is not allowed")
    if args[0] == "-m":
        if len(args) < 2:
            raise CommandNotAllowed("python -m requires module")
        mod = args[1]
        if mod == "compileall":
            return
        if mod == "ruff":
            if len(args) >= 3 and args[2] == "check":
                return
            raise CommandNotAllowed("python -m ruff only allows 'check'")
        raise CommandNotAllowed("python -m module not allowed")

    if args[0].endswith(".py"):
        base = os.path.basename(args[0])
        if base in allowed_entries:
            return
        raise CommandNotAllowed("python entrypoint not allowlisted")

    raise CommandNotAllowed("python arguments not allowlisted")
