"""Fallback startup guard for portfolio backtesting scripts."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
EXPECTED_TEMP_DIR: Path = PROJECT_ROOT / ".vntrader"


def _inside_project(path: Path) -> bool:
    try:
        path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return False
    return True


def _preload_project_vnpy_utility() -> None:
    if os.environ.get("QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD") == "1":
        return
    if not EXPECTED_TEMP_DIR.exists():
        return

    original_cwd = Path.cwd()
    if not _inside_project(original_cwd):
        return

    try:
        os.chdir(PROJECT_ROOT)
        import vnpy.trader.utility  # noqa: F401
    finally:
        os.chdir(original_cwd)

    os.environ.setdefault("QMT_BACKTEST_ORIGINAL_CWD", str(original_cwd))
    os.environ["QMT_BACKTEST_PROJECT_ROOT_GUARD"] = "1"


_preload_project_vnpy_utility()
