from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
EXPECTED_TEMP_DIR: Path = PROJECT_ROOT / ".vntrader"
EXPECTED_DATABASE_PATH: Path = EXPECTED_TEMP_DIR / "database.db"


class QmtBacktestRuntimeError(RuntimeError):
    """Raised when a QMT backtest would run against the wrong runtime state."""


def assert_project_trader_dir() -> None:
    """Fail fast when vn.py selected a non-project ``TRADER_DIR``."""
    if os.environ.get("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR") == "1":
        return

    from vnpy.trader.utility import TEMP_DIR, TRADER_DIR

    actual_temp_dir = Path(TEMP_DIR).resolve()
    expected_temp_dir = EXPECTED_TEMP_DIR.resolve()
    if actual_temp_dir != expected_temp_dir:
        raise QmtBacktestRuntimeError(
            "QMT backtest runtime guard failed: vn.py is not using the project .vntrader directory.\n"
            f"  cwd={Path.cwd().resolve()}\n"
            f"  TRADER_DIR={Path(TRADER_DIR).resolve()}\n"
            f"  TEMP_DIR={actual_temp_dir}\n"
            f"  expected_TEMP_DIR={expected_temp_dir}\n"
            "Run from the repository root, or keep the repository sitecustomize.py startup guard enabled.\n"
            "Emergency override: QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1"
        )

    if not EXPECTED_DATABASE_PATH.exists():
        raise QmtBacktestRuntimeError(
            f"QMT backtest runtime guard failed: missing project database {EXPECTED_DATABASE_PATH}"
        )


def assert_stage196_database_sentinels() -> None:
    """Verify the repaired 2015 futures bars are visible in the selected database."""
    if os.environ.get("QMT_BACKTEST_SKIP_DATABASE_SENTINELS") == "1":
        return

    from vnpy.trader.constant import Exchange, Interval
    from vnpy.trader.database import get_database

    assert_project_trader_dir()
    database = get_database()
    sentinels = [
        ("rb1505", Exchange.SHFE, 1),
        ("jm1505", Exchange.DCE, 1),
        ("MA506", Exchange.CZCE, 1),
    ]

    missing: list[str] = []
    for symbol, exchange, minimum_count in sentinels:
        bars = database.load_bar_data(
            symbol,
            exchange,
            Interval.DAILY,
            datetime(2015, 1, 1),
            datetime(2015, 12, 31),
        )
        if len(bars) < minimum_count:
            missing.append(f"{symbol}.{exchange.value}={len(bars)}")

    if missing:
        raise QmtBacktestRuntimeError(
            "QMT backtest runtime guard failed: Stage196 repaired 2015 bars are not visible.\n"
            f"  database={EXPECTED_DATABASE_PATH.resolve()}\n"
            f"  missing_or_too_short={', '.join(missing)}\n"
            "This usually means the process is reading an old database or the repaired data was not imported."
        )
