from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
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


def test_daily_bars_to_frame_normalizes_timezone_and_ohlcv() -> None:
    bars = [
        SimpleNamespace(
            datetime=pd.Timestamp("2021-01-04 00:00", tz="Asia/Shanghai").to_pydatetime(),
            open_price=100.0,
            high_price=105.0,
            low_price=98.0,
            close_price=103.0,
            volume=1234.0,
        ),
        SimpleNamespace(
            datetime=pd.Timestamp("2021-01-05 00:00", tz="Asia/Shanghai").to_pydatetime(),
            open_price=103.0,
            high_price=106.0,
            low_price=101.0,
            close_price=102.0,
            volume=987.0,
        ),
    ]

    result = stage208.daily_bars_to_frame("rb2105.SHFE", bars)

    assert result["vt_symbol"].tolist() == ["rb2105.SHFE", "rb2105.SHFE"]
    assert result["trade_date"].tolist() == [
        pd.Timestamp("2021-01-04"),
        pd.Timestamp("2021-01-05"),
    ]
    assert result.iloc[0][["open", "high", "low", "close", "volume"]].tolist() == [
        100.0,
        105.0,
        98.0,
        103.0,
        1234.0,
    ]


def _daily_fixture(periods: int = 80) -> pd.DataFrame:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    values = pd.Series(range(periods), dtype=float)
    return pd.DataFrame(
        {
            "vt_symbol": "rb2105.SHFE",
            "trade_date": dates,
            "open": 100.0 + values,
            "high": 102.0 + values,
            "low": 99.0 + values,
            "close": 101.0 + values,
            "volume": 1000.0 + values,
        }
    )


def test_select_daily_window_returns_60_before_holding_and_5_after() -> None:
    daily = _daily_fixture()
    event = pd.Series(
        {
            "entry_date": daily.iloc[60]["trade_date"],
            "exit_date": daily.iloc[64]["trade_date"],
        }
    )

    window, facts = stage208.select_daily_window(event, daily)

    assert len(window) == 70
    assert window.iloc[0]["trade_date"] == daily.iloc[0]["trade_date"]
    assert window.iloc[-1]["trade_date"] == daily.iloc[69]["trade_date"]
    assert facts == {
        "daily_bar_count": 70,
        "daily_before_count": 60,
        "daily_holding_count": 5,
        "daily_after_count": 5,
        "daily_coverage_state": "complete",
        "daily_source": "vnpy_local_database_exact_contract_daily",
    }


def test_select_daily_window_marks_short_history_partial() -> None:
    daily = _daily_fixture(periods=20)
    event = pd.Series(
        {
            "entry_date": daily.iloc[10]["trade_date"],
            "exit_date": daily.iloc[12]["trade_date"],
        }
    )

    window, facts = stage208.select_daily_window(event, daily)

    assert len(window) == 18
    assert facts["daily_before_count"] == 10
    assert facts["daily_holding_count"] == 3
    assert facts["daily_after_count"] == 5
    assert facts["daily_coverage_state"] == "partial"


def test_load_daily_context_queries_each_exact_contract_once_and_builds_manifest() -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []

        def load_bar_data(self, symbol, exchange, interval, start, end):
            self.calls.append((symbol, exchange, interval, start, end))
            base = pd.Timestamp("2021-01-04", tz="Asia/Shanghai")
            return [
                SimpleNamespace(
                    datetime=(base + pd.Timedelta(days=offset)).to_pydatetime(),
                    open_price=100.0 + offset,
                    high_price=102.0 + offset,
                    low_price=99.0 + offset,
                    close_price=101.0 + offset,
                    volume=1000.0 + offset,
                )
                for offset in range(2)
            ]

    winners = pd.DataFrame(
        {
            "vt_symbol": ["rb2105.SHFE", "jm2205.DCE", "rb2105.SHFE"],
        }
    )
    database = FakeDatabase()

    context = stage208.load_daily_context(winners, database=database)
    manifest = stage208.build_daily_source_manifest(context)

    assert sorted(context) == ["jm2205.DCE", "rb2105.SHFE"]
    assert [(call[0], call[1].value) for call in database.calls] == [
        ("jm2205", "DCE"),
        ("rb2105", "SHFE"),
    ]
    assert manifest["vt_symbol"].tolist() == ["jm2205.DCE", "rb2105.SHFE"]
    assert manifest["row_count"].tolist() == [2, 2]
    assert manifest["min_trade_date"].tolist() == ["2021-01-04", "2021-01-04"]
    assert manifest["max_trade_date"].tolist() == ["2021-01-05", "2021-01-05"]
    assert manifest["source"].unique().tolist() == [
        "vnpy_local_database_exact_contract_daily"
    ]
    assert manifest["canonical_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()


def _chart_event(daily: pd.DataFrame) -> pd.Series:
    return pd.Series(
        {
            "winner_rank": 1,
            "open_trade_id": "A",
            "vt_symbol": "rb2105.SHFE",
            "direction": "long",
            "entry_date": daily.iloc[60]["trade_date"],
            "exit_date": daily.iloc[64]["trade_date"],
            "entry_price": float(daily.iloc[60]["open"]),
            "realized_pnl": 300.0,
            "risk_amount": 100.0,
            "aggregate_r": 3.0,
            "entry_datetime": pd.Timestamp(daily.iloc[60]["trade_date"]) + pd.Timedelta(hours=9),
        }
    )


def _bars15_fixture(event: pd.Series) -> pd.DataFrame:
    entry_day = pd.Timestamp(event["entry_date"])
    return pd.DataFrame(
        {
            "vt_symbol": [event["vt_symbol"]] * 2,
            "trading_day": [entry_day] * 2,
            "bar_15m": [entry_day + pd.Timedelta(hours=9), entry_day + pd.Timedelta(hours=9, minutes=15)],
            "open": [160.0, 161.0],
            "high": [162.0, 163.0],
            "low": [159.0, 160.0],
            "close": [161.0, 162.0],
            "volume": [10.0, 12.0],
            "open_oi": [1000.0, 1001.0],
            "close_oi": [1001.0, 1002.0],
        }
    )


def test_create_winner_figure_has_three_axes_and_only_daily_volume_bars() -> None:
    daily = _daily_fixture()
    event = _chart_event(daily)
    daily_window, _ = stage208.select_daily_window(event, daily)
    daily_window.loc[0, "close"] = daily_window.loc[0, "open"] + 1.0
    daily_window.loc[1, "close"] = daily_window.loc[1, "open"] - 1.0
    bars15 = _bars15_fixture(event)

    figure = stage208.create_winner_figure(
        event,
        bars15,
        [pd.Timestamp(event["entry_date"])],
        daily_window,
    )

    assert [axis.get_ylabel() for axis in figure.axes] == [
        "15m Price",
        "Daily Price",
        "Daily Volume",
    ]
    assert len(figure.axes[0].containers) == 0
    assert len(figure.axes[1].containers) == 0
    assert len(figure.axes[2].containers) == 1
    volume_colors = [
        patch.get_facecolor()
        for patch in figure.axes[2].containers[0].patches[:2]
    ]
    assert np.allclose(volume_colors[0], stage208.matplotlib.colors.to_rgba("#d62728", 0.72))
    assert np.allclose(volume_colors[1], stage208.matplotlib.colors.to_rgba("#159447", 0.72))
    stage208.plt.close(figure)


def test_create_winner_figure_keeps_daily_chart_when_minutes_are_missing() -> None:
    daily = _daily_fixture()
    event = _chart_event(daily)
    daily_window, _ = stage208.select_daily_window(event, daily)

    figure = stage208.create_winner_figure(
        event,
        pd.DataFrame(),
        [pd.Timestamp(event["entry_date"])],
        daily_window,
    )

    assert any("unavailable" in text.get_text() for text in figure.axes[0].texts)
    assert len(figure.axes[1].patches) >= len(daily_window)
    assert len(figure.axes[2].containers) == 1
    stage208.plt.close(figure)


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
    calendar = pd.bdate_range("2021-01-01", periods=80)
    winners = pd.DataFrame(
        [
            {
                "winner_rank": 1,
                "open_trade_id": "A",
                "vt_symbol": "rb.SHFE",
                "direction": "long",
                "entry_date": calendar[60],
                "exit_date": calendar[62],
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
                "entry_date": calendar[60],
                "exit_date": calendar[63],
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
                    f"{calendar[60].date()} 09:01",
                    f"{calendar[60].date()} 09:16",
                    f"{calendar[60].date()} 09:01",
                    f"{calendar[60].date()} 09:16",
                ]
            ),
            "trading_day": [calendar[60]] * 4,
            "open": [100, 101, 200, 199],
            "high": [102, 103, 201, 200],
            "low": [99, 100, 198, 197],
            "close": [101, 102, 199, 198],
            "volume": [10, 12, 20, 22],
            "open_oi": [1000, 1001, 2000, 2001],
            "close_oi": [1001, 1002, 2001, 2002],
        }
    )
    daily_context = {}
    for symbol in ["rb.SHFE", "jm.DCE"]:
        daily = _daily_fixture()
        daily["vt_symbol"] = symbol
        daily_context[symbol] = daily
    output_dir = tmp_path / "atlas"

    stage208.write_outputs(
        winners,
        minutes,
        calendar,
        output_dir,
        event_count=2,
        input_hashes={"fixture": "abc"},
        daily_context=daily_context,
    )

    assert len(pd.read_csv(output_dir / "winner_manifest.csv")) == 2
    assert len(pd.read_csv(output_dir / "daily_source_manifest.csv")) == 2
    coverage = pd.read_csv(output_dir / "coverage_summary.csv")
    assert coverage["daily_coverage_state"].tolist() == ["complete", "complete"]
    assert coverage["daily_before_count"].tolist() == [60, 60]
    assert coverage["daily_after_count"].tolist() == [5, 5]
    assert len(list(output_dir.glob("winner_*.png"))) == 2
    assert len(list(output_dir.glob("atlas_page*.png"))) == 1
    chart_pixels = stage208.plt.imread(sorted(output_dir.glob("winner_*.png"))[0])
    atlas_pixels = stage208.plt.imread(output_dir / "atlas_page001.png")
    assert chart_pixels.shape[:2] == (1800, 2700)
    assert atlas_pixels.shape[:2] == (1600, 2400)
    decision = json.loads((output_dir / "decision.json").read_text())
    assert decision["layout"] == "15m_kline+daily_kline+daily_volume"
    assert decision["daily_complete_count"] == 2
    assert decision["daily_partial_count"] == 0
    assert decision["daily_missing_count"] == 0
    assert decision["daily_contract_count"] == 2
    assert decision["send_order_api_called_count"] == 0
    assert decision["cancel_order_api_called_count"] == 0
    assert decision["ctp_connected"] is False
