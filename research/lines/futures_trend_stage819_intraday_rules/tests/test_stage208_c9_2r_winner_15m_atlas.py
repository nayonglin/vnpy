from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "stage208_c9_2r_winner_15m_atlas.py"
)
SPEC = importlib.util.spec_from_file_location("stage208", MODULE_PATH)
assert SPEC and SPEC.loader
stage208 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage208)


def test_build_winner_events_aggregates_filters_and_sorts() -> None:
    frame = pd.DataFrame(
        [
            {"requested_start_month": "2020-01", "open_trade_id": "A", "lot_id": 1, "vt_symbol": "rb.SHFE", "direction": "long", "entry_date": "2021-01-04", "exit_date": "2021-01-08", "entry_price": 100.0, "realized_pnl": 120.0, "risk_amount": 40.0},
            {"requested_start_month": "2020-01", "open_trade_id": "A", "lot_id": 2, "vt_symbol": "rb.SHFE", "direction": "long", "entry_date": "2021-01-04", "exit_date": "2021-01-11", "entry_price": 100.0, "realized_pnl": 80.0, "risk_amount": 40.0},
            {"requested_start_month": "2020-01", "open_trade_id": "B", "lot_id": 3, "vt_symbol": "jm.DCE", "direction": "short", "entry_date": "2021-02-01", "exit_date": "2021-02-03", "entry_price": 200.0, "realized_pnl": 60.0, "risk_amount": 20.0},
            {"requested_start_month": "2020-01", "open_trade_id": "C", "lot_id": 4, "vt_symbol": "FG.CZCE", "direction": "long", "entry_date": "2021-03-01", "exit_date": "2021-03-02", "entry_price": 300.0, "realized_pnl": 19.0, "risk_amount": 10.0},
            {"requested_start_month": "2021-01", "open_trade_id": "D", "lot_id": 5, "vt_symbol": "au.SHFE", "direction": "long", "entry_date": "2021-04-01", "exit_date": "2021-04-02", "entry_price": 400.0, "realized_pnl": 1000.0, "risk_amount": 10.0},
        ]
    )

    result = stage208.build_winner_events(frame, enforce_expected_counts=False)

    assert result["open_trade_id"].tolist() == ["B", "A"]
    assert result["aggregate_r"].round(2).tolist() == [3.00, 2.50]
    assert result["realized_pnl"].tolist() == [60.0, 200.0]
    assert result["winner_rank"].tolist() == [1, 2]


def test_assign_trading_day_maps_night_to_next_available_day() -> None:
    calendar = pd.DatetimeIndex(
        pd.to_datetime(["2021-01-08", "2021-01-11", "2021-01-12"])
    )
    bars = pd.DataFrame(
        {
            "bar_datetime": pd.to_datetime(
                ["2021-01-08 21:01", "2021-01-11 00:01", "2021-01-11 09:01"]
            ),
            "vt_symbol": ["rb.SHFE"] * 3,
        }
    )

    result = stage208.assign_trading_day(bars, calendar)

    assert result["trading_day"].dt.strftime("%Y-%m-%d").tolist() == [
        "2021-01-11",
        "2021-01-11",
        "2021-01-11",
    ]


def test_select_window_days_returns_five_before_and_after() -> None:
    calendar = pd.bdate_range("2021-01-01", periods=20)

    result = stage208.select_window_days(calendar[10], calendar)

    assert result == list(calendar[5:16])


def test_resample_15m_uses_ohlcv_and_does_not_fill_empty_buckets() -> None:
    bars = pd.DataFrame(
        {
            "vt_symbol": ["rb.SHFE"] * 4,
            "trading_day": pd.to_datetime(["2021-01-11"] * 4),
            "bar_datetime": pd.to_datetime(
                [
                    "2021-01-08 21:01",
                    "2021-01-08 21:14",
                    "2021-01-08 21:16",
                    "2021-01-08 21:29",
                ]
            ),
            "open": [100, 102, 104, 103],
            "high": [103, 105, 106, 104],
            "low": [99, 101, 103, 100],
            "close": [102, 104, 103, 101],
            "volume": [1, 2, 3, 4],
            "open_oi": [10, 11, 12, 13],
            "close_oi": [11, 12, 13, 14],
        }
    )

    result = stage208.resample_15m(bars)

    assert len(result) == 2
    assert result.iloc[0][
        ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    ].tolist() == [100, 105, 99, 104, 3, 10, 12]
    assert result.iloc[1][
        ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    ].tolist() == [104, 106, 100, 101, 7, 12, 14]
