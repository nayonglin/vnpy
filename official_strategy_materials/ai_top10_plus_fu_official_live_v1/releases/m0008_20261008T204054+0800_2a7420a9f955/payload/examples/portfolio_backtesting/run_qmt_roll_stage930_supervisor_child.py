from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        raise SystemExit("usage: supervisor_child.py EXECUTABLE [ARG ...]")
    executable = arguments[0]
    os.setsid()
    os.execv(executable, arguments)


if __name__ == "__main__":
    main()
