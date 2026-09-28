from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import MappingProxyType
from types import SimpleNamespace

import pandas as pd
import pytest


TOOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "stage230_current_live_recent_windows.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stage230_current_live_recent_windows", TOOL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {TOOL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_requested_windows_end_on_latest_completed_trading_day() -> None:
    module = _load_module()

    windows = module.build_requested_windows(pd.Timestamp("2026-09-18"))

    assert [(row.name, row.start.date().isoformat(), row.end.date().isoformat()) for row in windows] == [
        ("since_2025", "2025-01-01", "2026-09-18"),
        ("since_2026", "2026-01-01", "2026-09-18"),
    ]


def test_requested_windows_reject_incomplete_2026_range() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="latest_complete_date_before_2026_start"):
        module.build_requested_windows(pd.Timestamp("2025-12-31"))


def test_window_summary_uses_fresh_window_capital_and_costs() -> None:
    module = _load_module()
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
            "account_equity": [151_000.0, 149_000.0, 153_000.0],
            "net_pnl": [1_000.0, -2_000.0, 4_000.0],
            "slippage": [10.0, 20.0, 30.0],
            "trade_count": [1.0, 2.0, 1.0],
            "broker10_total_margin_exact": [15_000.0, 30_000.0, 0.0],
        }
    )

    result = module.summarize_window(
        daily,
        window_name="since_2026",
        initial_capital=150_000.0,
    )

    assert result["actual_start"] == "2026-01-02"
    assert result["actual_end"] == "2026-01-06"
    assert result["end_equity"] == pytest.approx(153_000.0)
    assert result["total_return_pct"] == pytest.approx(2.0)
    assert result["max_dd_pct"] == pytest.approx((149_000.0 / 151_000.0 - 1.0) * 100.0)
    assert result["total_slippage"] == pytest.approx(60.0)
    assert result["total_trade_count"] == pytest.approx(4.0)
    assert result["nonzero_daily_win_rate_pct"] == pytest.approx(200.0 / 3.0)
    assert result["max_broker10_margin_to_equity_pct"] == pytest.approx(30_000.0 / 149_000.0 * 100.0)


def test_json_safe_materializes_generic_mapping() -> None:
    module = _load_module()
    value = MappingProxyType({"strategy_overrides": MappingProxyType({"capital": 150_000.0})})

    result = module.json_safe(value)

    assert result == {"strategy_overrides": {"capital": 150_000.0}}


def test_open_day_minute_coverage_is_checked_by_contract_and_date() -> None:
    module = _load_module()
    trades = pd.DataFrame(
        {
            "vt_symbol": ["fu2609.SHFE", "SA701.CZCE", "fu2609.SHFE"],
            "date": ["2026-08-19", "2026-09-09", "2026-08-25"],
            "offset": ["开", "开", "平"],
        }
    )
    minute_bars = pd.DataFrame(
        {
            "vt_symbol": ["SA701.CZCE"] * 200,
            "bar_date": ["2026-09-09"] * 200,
        }
    )

    audit, missing = module.audit_open_day_minute_coverage(trades, minute_bars)

    assert audit == {
        "open_trade_count": 2,
        "covered_open_trade_count": 1,
        "missing_open_trade_count": 1,
        "open_day_coverage_pct": 50.0,
        "minimum_required_bars_per_open_day": 200,
        "minimum_observed_bars_per_covered_open_day": 200,
    }
    assert missing.to_dict("records") == [
        {
            "vt_symbol": "fu2609.SHFE",
            "required_date": "2026-08-19",
            "minute_bar_count": 0,
            "minimum_required_bars": 200,
        }
    ]


def test_open_day_minute_coverage_fails_closed() -> None:
    module = _load_module()

    with pytest.raises(RuntimeError, match="open_day_minute_coverage_incomplete:1"):
        module.require_complete_open_day_minute_coverage(
            {"missing_open_trade_count": 1, "open_day_coverage_pct": 50.0}
        )


def test_open_day_minute_coverage_requires_a_full_session() -> None:
    module = _load_module()
    trades = pd.DataFrame(
        {
            "vt_symbol": ["fu2609.SHFE", "SA701.CZCE"],
            "date": ["2026-08-19", "2026-09-09"],
            "offset": ["开", "开"],
        }
    )
    minute_bars = pd.concat(
        [
            pd.DataFrame(
                {
                    "vt_symbol": ["fu2609.SHFE"] * 199,
                    "bar_date": ["2026-08-19"] * 199,
                }
            ),
            pd.DataFrame(
                {
                    "vt_symbol": ["SA701.CZCE"] * 200,
                    "bar_date": ["2026-09-09"] * 200,
                }
            ),
        ],
        ignore_index=True,
    )

    audit, missing = module.audit_open_day_minute_coverage(trades, minute_bars)

    assert audit["minimum_required_bars_per_open_day"] == 200
    assert audit["minimum_observed_bars_per_covered_open_day"] == 200
    assert audit["covered_open_trade_count"] == 1
    assert audit["missing_open_trade_count"] == 1
    assert missing.to_dict("records") == [
        {
            "vt_symbol": "fu2609.SHFE",
            "required_date": "2026-08-19",
            "minute_bar_count": 199,
            "minimum_required_bars": 200,
        }
    ]


def test_latest_complete_date_uses_daily_overviews_only() -> None:
    module = _load_module()
    rows = [
        SimpleNamespace(interval=SimpleNamespace(value="1m"), end=pd.Timestamp("2026-09-21 14:00")),
        SimpleNamespace(interval=SimpleNamespace(value="d"), end=pd.Timestamp("2026-09-18")),
        SimpleNamespace(interval=SimpleNamespace(value="d"), end=pd.Timestamp("2026-09-17")),
    ]

    assert module.latest_complete_daily_date(rows) == pd.Timestamp("2026-09-18")
