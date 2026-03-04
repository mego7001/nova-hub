from __future__ import annotations

import sys

from main import main as nova_main


def main() -> int:
    sys.argv = [sys.argv[0], "chat", *sys.argv[1:]]
    return int(nova_main())


if __name__ == "__main__":
    raise SystemExit(main())
