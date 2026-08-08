from __future__ import annotations

import importlib.util
import json
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


def test_load_target_minutes_filters_symbols_and_window(tmp_path: Path) -> None:
    source = tmp_path / "minutes.csv"
    pd.DataFrame(
        {
            "vt_symbol": ["rb.SHFE", "rb.SHFE", "jm.DCE"],
            "bar_datetime": [
                "2021-01-08 21:01",
                "2021-02-01 09:01",
                "2021-01-08 21:01",
            ],
            "open": [100, 110, 200],
            "high": [101, 111, 201],
            "low": [99, 109, 199],
            "close": [100, 110, 200],
            "volume": [1, 1, 1],
            "open_oi": [10, 10, 20],
            "close_oi": [10, 10, 20],
        }
    ).to_csv(source, index=False)
    winners = pd.DataFrame(
        [{"vt_symbol": "rb.SHFE", "entry_date": pd.Timestamp("2021-01-11")}]
    )
    calendar = pd.DatetimeIndex(
        pd.to_datetime(["2021-01-08", "2021-01-11", "2021-01-12"])
    )

    result = stage208.load_target_minutes(source, winners, calendar, chunksize=2)

    assert result["vt_symbol"].unique().tolist() == ["rb.SHFE"]
    assert result["bar_datetime"].dt.strftime("%Y-%m-%d %H:%M").tolist() == [
        "2021-01-08 21:01"
    ]


def test_load_target_minutes_supplements_cache_but_keeps_primary_duplicates(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "primary.csv"
    fallback = tmp_path / "rb2105_minute_backtest.csv"
    columns = {
        "vt_symbol": ["rb2105.SHFE"],
        "bar_datetime": ["2021-01-08 21:01"],
        "open": [100.0],
        "high": [101.0],
        "low": [99.0],
        "close": [100.5],
        "volume": [10.0],
        "open_oi": [1000.0],
        "close_oi": [1001.0],
    }
    pd.DataFrame(columns).to_csv(primary, index=False)
    fallback_frame = pd.DataFrame(columns)
    fallback_frame.loc[0, "open"] = 999.0
    fallback_frame.loc[1] = {
        "vt_symbol": "rb2105.SHFE",
        "bar_datetime": "2021-01-11 09:01",
        "open": 102.0,
        "high": 103.0,
        "low": 101.0,
        "close": 102.5,
        "volume": 12.0,
        "open_oi": 1002.0,
        "close_oi": 1003.0,
    }
    fallback_frame.to_csv(fallback, index=False)
    winners = pd.DataFrame(
        [{"vt_symbol": "rb2105.SHFE", "entry_date": pd.Timestamp("2021-01-11")}]
    )
    calendar = pd.DatetimeIndex(
        pd.to_datetime(["2021-01-08", "2021-01-11", "2021-01-12"])
    )

    result = stage208.load_target_minutes(
        primary,
        winners,
        calendar,
        fallback_paths=[fallback],
        chunksize=2,
    )

    assert len(result) == 2
    duplicate = result[result["bar_datetime"].eq(pd.Timestamp("2021-01-08 21:01"))]
    assert duplicate["open"].tolist() == [100.0]
    assert set(result["minute_source_kind"]) == {"primary", "local_contract_cache"}


def test_discover_contract_cache_paths_requires_exact_contract_and_exchange(
    tmp_path: Path,
) -> None:
    exact = tmp_path / "batch" / "SHFE" / "rb2105_minute_backtest.csv"
    wrong_contract = tmp_path / "batch" / "SHFE" / "rb21050_minute_backtest.csv"
    wrong_exchange = tmp_path / "batch" / "DCE" / "rb2105_minute_backtest.csv"
    for path in [exact, wrong_contract, wrong_exchange]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    winners = pd.DataFrame([{"vt_symbol": "rb2105.SHFE"}])

    result = stage208.discover_contract_cache_paths(tmp_path, winners)

    assert result == [exact]


def test_write_placeholder_creates_nonempty_png(tmp_path: Path) -> None:
    output = tmp_path / "missing.png"
    event = pd.Series(
        {
            "winner_rank": 71,
            "vt_symbol": "jm2609.DCE",
            "direction": "long",
            "entry_date": pd.Timestamp("2026-06-03"),
            "aggregate_r": 4.6667,
        }
    )

    stage208.write_placeholder(event, output, "no local minute bars")

    assert output.exists()
    assert output.stat().st_size > 1000


def test_write_outputs_creates_manifest_charts_atlas_and_safe_decision(
    tmp_path: Path,
) -> None:
    calendar = pd.bdate_range("2021-01-01", periods=15)
    winners = pd.DataFrame(
        [
            {
                "winner_rank": 1,
                "open_trade_id": "A",
                "vt_symbol": "rb.SHFE",
                "direction": "long",
                "entry_date": calendar[7],
                "exit_date": calendar[9],
                "entry_price": 100.0,
                "realized_pnl": 300.0,
                "risk_amount": 100.0,
                "lot_count": 1,
                "aggregate_r": 3.0,
            },
            {
                "winner_rank": 2,
                "open_trade_id": "B",
                "vt_symbol": "jm.DCE",
                "direction": "short",
                "entry_date": calendar[7],
                "exit_date": calendar[10],
                "entry_price": 200.0,
                "realized_pnl": 200.0,
                "risk_amount": 100.0,
                "lot_count": 1,
                "aggregate_r": 2.0,
            },
        ]
    )
    minutes = pd.DataFrame(
        {
            "vt_symbol": ["rb.SHFE", "rb.SHFE", "jm.DCE", "jm.DCE"],
            "bar_datetime": pd.to_datetime(
                [
                    f"{calendar[7].date()} 09:01",
                    f"{calendar[7].date()} 09:16",
                    f"{calendar[7].date()} 09:01",
                    f"{calendar[7].date()} 09:16",
                ]
            ),
            "trading_day": [calendar[7]] * 4,
            "open": [100, 101, 200, 199],
            "high": [102, 103, 201, 200],
            "low": [99, 100, 198, 197],
            "close": [101, 102, 199, 198],
            "volume": [10, 12, 20, 22],
            "open_oi": [1000, 1001, 2000, 2001],
            "close_oi": [1001, 1002, 2001, 2002],
        }
    )
    output_dir = tmp_path / "atlas"

    stage208.write_outputs(
        winners,
        minutes,
        calendar,
        output_dir,
        event_count=2,
        input_hashes={"fixture": "abc"},
    )

    assert len(pd.read_csv(output_dir / "winner_manifest.csv")) == 2
    assert len(list(output_dir.glob("winner_*.png"))) == 2
    assert len(list(output_dir.glob("atlas_page*.png"))) == 1
    decision = json.loads((output_dir / "decision.json").read_text())
    assert decision["send_order_api_called_count"] == 0
    assert decision["cancel_order_api_called_count"] == 0
    assert decision["ctp_connected"] is False
