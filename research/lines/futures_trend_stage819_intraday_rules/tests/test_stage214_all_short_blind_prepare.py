from __future__ import annotations

import hashlib
import importlib.util
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "stage214_all_short_blind_prepare.py"
)
SPEC = importlib.util.spec_from_file_location("stage214", MODULE_PATH)
assert SPEC and SPEC.loader
stage214 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage214)


def test_build_short_events_keeps_all_short_events_and_zero_risk() -> None:
    """A missing short-only filter, aggregation, or zero-risk handling is a bug."""
    closed_lots = pd.DataFrame(
        [
            {
                "requested_start_month": "2020-01",
                "open_trade_id": "short-a",
                "lot_id": 1,
                "vt_symbol": "rb2105.SHFE",
                "direction": "SHORT",
                "entry_date": "2021-01-11",
                "exit_date": "2021-01-13",
                "entry_price": 4200.0,
                "realized_pnl": 300.0,
                "risk_amount": 100.0,
            },
            {
                "requested_start_month": "2020-01",
                "open_trade_id": "short-a",
                "lot_id": 2,
                "vt_symbol": "rb2105.SHFE",
                "direction": "short",
                "entry_date": "2021-01-11",
                "exit_date": "2021-01-14",
                "entry_price": 4200.0,
                "realized_pnl": -100.0,
                "risk_amount": 100.0,
            },
            {
                "requested_start_month": "2020-01",
                "open_trade_id": "short-zero",
                "lot_id": 3,
                "vt_symbol": "jm2205.DCE",
                "direction": "short",
                "entry_date": "2021-02-01",
                "exit_date": "2021-02-02",
                "entry_price": 2100.0,
                "realized_pnl": 50.0,
                "risk_amount": 0.0,
            },
            {
                "requested_start_month": "2020-01",
                "open_trade_id": "long-ignore",
                "lot_id": 4,
                "vt_symbol": "FG2105.CZCE",
                "direction": "long",
                "entry_date": "2021-03-01",
                "exit_date": "2021-03-02",
                "entry_price": 3000.0,
                "realized_pnl": 999.0,
                "risk_amount": 10.0,
            },
            {
                "requested_start_month": "2021-01",
                "open_trade_id": "other-start-ignore",
                "lot_id": 5,
                "vt_symbol": "au2106.SHFE",
                "direction": "short",
                "entry_date": "2021-04-01",
                "exit_date": "2021-04-02",
                "entry_price": 400.0,
                "realized_pnl": 999.0,
                "risk_amount": 10.0,
            },
        ]
    )

    events = stage214.build_short_events(closed_lots, enforce_expected_counts=False)

    assert events["open_trade_id"].tolist() == ["short-a", "short-zero"]
    assert events["lot_count"].tolist() == [2, 1]
    assert events["realized_pnl"].tolist() == [200.0, 50.0]
    assert events["risk_amount"].tolist() == [200.0, 0.0]
    assert events.loc[0, "aggregate_r"] == 1.0
    assert np.isnan(events.loc[1, "aggregate_r"])
    assert events["outcome_ge_2r"].tolist() == [False, False]
    assert events["outcome_profitable"].tolist() == [True, True]
    assert events["entry_year"].tolist() == [2021, 2021]


def test_select_preentry_days_returns_only_the_five_days_before_entry() -> None:
    """Including the entry day or an extra day would leak chart context."""
    calendar = pd.bdate_range("2021-01-04", periods=8)

    result = stage214.select_preentry_days(calendar[6], calendar)

    assert result == list(calendar[1:6])
    assert calendar[6] not in result


def test_merge_minute_sources_prefers_stage861_and_unions_exact_contract_rows(
    tmp_path: Path,
) -> None:
    """A lower-priority duplicate or another contract must not enter a frozen window."""
    calendar = pd.bdate_range("2021-01-04", periods=8)
    events = pd.DataFrame(
        [
            {
                "open_trade_id": "short-a",
                "vt_symbol": "rb2105.SHFE",
                "entry_date": calendar[6],
            }
        ]
    )
    minute_columns = [
        "vt_symbol",
        "bar_datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
    ]
    stage861_path = tmp_path / "stage861.csv"
    cache_path = tmp_path / "SHFE" / "rb2105_minute_backtest.csv"
    cache_path.parent.mkdir()
    pd.DataFrame(
        [
            ["rb2105.SHFE", "2021-01-04 21:01", 100, 101, 99, 100.5, 10, 1000, 1001],
            ["jm2205.DCE", "2021-01-04 21:01", 200, 201, 199, 200.5, 10, 2000, 2001],
        ],
        columns=minute_columns,
    ).to_csv(stage861_path, index=False)
    pd.DataFrame(
        [
            ["rb2105.SHFE", "2021-01-04 21:01", 900, 901, 899, 900.5, 10, 1000, 1001],
            ["rb2105.SHFE", "2021-01-06 09:01", 102, 103, 101, 102.5, 11, 1002, 1003],
        ],
        columns=minute_columns,
    ).to_csv(cache_path, index=False)

    class FakeDatabase:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []

        def load_bar_data(self, symbol, exchange, interval, start, end):
            self.calls.append((symbol, exchange, interval, start, end))
            return [
                type(
                    "Bar",
                    (),
                    {
                        "datetime": pd.Timestamp("2021-01-07 09:01"),
                        "open_price": 103.0,
                        "high_price": 104.0,
                        "low_price": 102.0,
                        "close_price": 103.5,
                        "volume": 12.0,
                        "open_interest": 1004.0,
                    },
                )()
            ]

    database = FakeDatabase()
    minutes, sources = stage214.merge_minute_sources(
        events, calendar, stage861_path, [cache_path], database
    )

    assert minutes["vt_symbol"].tolist() == ["rb2105.SHFE"] * 3
    assert minutes["bar_datetime"].dt.strftime("%Y-%m-%d %H:%M").tolist() == [
        "2021-01-04 21:01",
        "2021-01-06 09:01",
        "2021-01-07 09:01",
    ]
    assert minutes["open"].tolist() == [100.0, 102.0, 103.0]
    assert minutes["minute_source_kind"].tolist() == [
        "stage861",
        "local_cache",
        "vnpy_database",
    ]
    assert minutes["source_priority"].tolist() == [3, 2, 1]
    assert sources["source"].tolist() == [
        "stage861",
        "local_cache",
        "vnpy_database",
    ]
    assert [(call[0], call[1].value, call[2].value) for call in database.calls] == [
        ("rb2105", "SHFE", "1m")
    ]


def test_source_manifest_gap_coverage_and_zero_risk_resolution(tmp_path: Path) -> None:
    """A mutable file hash, false complete coverage, or inferred zero risk is a bug."""
    calendar = pd.bdate_range("2021-01-04", periods=8)
    entry_day = calendar[6]
    events = pd.DataFrame(
        [
            {
                "open_trade_id": "complete",
                "vt_symbol": "rb2105.SHFE",
                "entry_date": entry_day,
                "realized_pnl": 200.0,
                "risk_amount": 100.0,
                "aggregate_r": 2.0,
            },
            {
                "open_trade_id": "partial",
                "vt_symbol": "jm2205.DCE",
                "entry_date": entry_day,
                "realized_pnl": 50.0,
                "risk_amount": 0.0,
                "aggregate_r": np.nan,
            },
            {
                "open_trade_id": "missing",
                "vt_symbol": "FG2105.CZCE",
                "entry_date": entry_day,
                "realized_pnl": -10.0,
                "risk_amount": 0.0,
                "aggregate_r": np.nan,
            },
        ]
    )
    closed_lots = events.copy()
    resolved, risk_audit = stage214.resolve_risk_zero_events(events, closed_lots)

    assert resolved["risk_status"].tolist() == ["resolved", "unresolved", "unresolved"]
    assert np.isnan(resolved.loc[1, "aggregate_r"])
    assert risk_audit["risk_status"].tolist() == ["unresolved", "unresolved"]

    target_days = list(calendar[1:6])
    minutes = pd.DataFrame(
        {
            "vt_symbol": ["rb2105.SHFE"] * 5 + ["jm2205.DCE"] * 4,
            "bar_datetime": pd.to_datetime(
                [f"{day.date()} 09:01" for day in target_days]
                + [f"{day.date()} 09:01" for day in target_days[:4]]
            ),
            "trading_day": target_days + target_days[:4],
            "minute_source_kind": ["stage861"] * 9,
            "minute_source_path": ["/frozen/stage861.csv"] * 9,
        }
    )
    gap_audit = stage214.build_data_gap_audit(resolved, minutes, calendar)

    assert gap_audit["coverage_state"].tolist() == ["complete", "partial", "missing"]
    assert gap_audit["missing_days"].tolist() == ["", target_days[-1].date().isoformat(), "|".join(day.date().isoformat() for day in target_days)]
    assert gap_audit["attempted_sources"].tolist() == ["stage861", "stage861", ""]
    assert gap_audit["risk_status"].tolist() == ["resolved", "unresolved", "unresolved"]

    source_path = tmp_path / "stage861.csv"
    pd.DataFrame(
        {
            "vt_symbol": ["rb2105.SHFE"],
            "bar_datetime": ["2021-01-04 21:01"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [10.0],
            "open_oi": [1000.0],
            "close_oi": [1001.0],
        }
    ).to_csv(source_path, index=False)

    class EmptyDatabase:
        def load_bar_data(self, *args):
            return []

    _, sources = stage214.merge_minute_sources(
        events.iloc[:1], calendar, source_path, [], EmptyDatabase()
    )

    assert sources.columns.tolist()[:7] == [
        "vt_symbol",
        "source",
        "path",
        "row_count",
        "min_datetime",
        "max_datetime",
        "sha256",
    ]
    assert sources.loc[0, "source"] == "stage861"
    assert sources.loc[0, "path"] == str(source_path)
    assert sources.loc[0, "row_count"] == 1
    assert sources["sha256"].str.fullmatch(r"[0-9a-f]{64}").all()


def test_enforced_short_events_lock_the_three_predeclared_zero_risk_ids() -> None:
    """Changing any frozen zero-risk identity must reject the 309/64 production input."""
    zero_ids = {"BACKTESTING.166", "BACKTESTING.265", "BACKTESTING.589"}
    rows = []
    for index in range(64):
        open_trade_id = (
            sorted(zero_ids)[index]
            if index < len(zero_ids)
            else f"short-{index:03d}"
        )
        rows.append(
            {
                "requested_start_month": "2020-01",
                "open_trade_id": open_trade_id,
                "lot_id": index,
                "vt_symbol": "rb2105.SHFE",
                "direction": "short",
                "entry_date": "2021-01-11",
                "exit_date": "2021-01-12",
                "entry_price": 4200.0,
                "realized_pnl": 10.0,
                "risk_amount": 0.0 if open_trade_id in zero_ids else 5.0,
            }
        )
    for index in range(245):
        rows.append(
            {
                "requested_start_month": "2020-01",
                "open_trade_id": f"long-{index:03d}",
                "lot_id": 1000 + index,
                "vt_symbol": "rb2105.SHFE",
                "direction": "long",
                "entry_date": "2021-01-11",
                "exit_date": "2021-01-12",
                "entry_price": 4200.0,
                "realized_pnl": 10.0,
                "risk_amount": 5.0,
            }
        )
    closed_lots = pd.DataFrame(rows)

    events = stage214.build_short_events(closed_lots)

    assert stage214.EXPECTED_ZERO_RISK_OPEN_TRADE_IDS == frozenset(zero_ids)
    assert set(events.loc[events["risk_amount"].eq(0.0), "open_trade_id"]) == zero_ids

    invalid = closed_lots.copy()
    invalid.loc[invalid["open_trade_id"].eq("BACKTESTING.589"), "open_trade_id"] = (
        "BACKTESTING.invalid"
    )
    with pytest.raises(RuntimeError, match="zero-risk"):
        stage214.build_short_events(invalid)


def test_merge_starts_monday_window_at_previous_official_night_session(
    tmp_path: Path,
) -> None:
    """Using the prior natural day loses Friday night before a Monday D-5 window."""
    calendar = pd.DatetimeIndex(
        pd.to_datetime(
            [
                "2020-12-28",
                "2020-12-29",
                "2020-12-30",
                "2020-12-31",
                "2021-01-04",
                "2021-01-05",
                "2021-01-06",
                "2021-01-07",
                "2021-01-08",
                "2021-01-11",
            ]
        )
    )
    events = pd.DataFrame(
        [{"open_trade_id": "short-a", "vt_symbol": "rb2105.SHFE", "entry_date": calendar[-1]}]
    )

    class EmptyDatabase:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []

        def load_bar_data(self, *args):
            self.calls.append(args)
            return []

    database = EmptyDatabase()
    stage214.merge_minute_sources(
        events, calendar, tmp_path / "missing-stage861.csv", [], database
    )

    assert database.calls[0][3] == datetime(2020, 12, 31, 20, 0)
    assert database.calls[0][4] == datetime(2021, 1, 11, 0, 0)


def test_empty_source_attempts_are_manifested_and_audited(tmp_path: Path) -> None:
    """A source with no target rows must remain visible and reproducible in the audit."""
    calendar = pd.bdate_range("2021-01-04", periods=8)
    events = pd.DataFrame(
        [{"open_trade_id": "missing", "vt_symbol": "rb2105.SHFE", "entry_date": calendar[6]}]
    )
    stage861_path = tmp_path / "stage861.csv"
    cache_path = tmp_path / "SHFE" / "rb2105_minute_backtest.csv"
    cache_path.parent.mkdir()
    source_rows = pd.DataFrame(
        {
            "vt_symbol": ["jm2205.DCE"],
            "bar_datetime": ["2021-01-04 21:01"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [10.0],
            "open_oi": [1000.0],
            "close_oi": [1001.0],
        }
    )
    source_rows.to_csv(stage861_path, index=False)
    source_rows.to_csv(cache_path, index=False)

    class EmptyDatabase:
        def load_bar_data(self, *args):
            return []

    minutes, sources = stage214.merge_minute_sources(
        events, calendar, stage861_path, [cache_path], EmptyDatabase()
    )
    audit = stage214.build_data_gap_audit(events, minutes, calendar)

    assert minutes.empty
    assert sources["source"].tolist() == ["stage861", "local_cache", "vnpy_database"]
    assert sources["row_count"].tolist() == [0, 0, 0]
    assert sources["result_status"].tolist() == [
        "attempted_no_target_rows",
        "attempted_no_target_rows",
        "attempted_no_target_rows",
    ]
    assert sources.loc[0, "sha256"] == hashlib.sha256(stage861_path.read_bytes()).hexdigest()
    assert sources.loc[1, "sha256"] == hashlib.sha256(cache_path.read_bytes()).hexdigest()
    assert sources.loc[2, "query_start"] == "2021-01-04T20:00:00"
    assert sources.loc[2, "query_end"] == "2021-01-12T00:00:00"
    assert audit.loc[0, "attempted_sources"] == "stage861|local_cache|vnpy_database"


def test_preentry_15m_output_uses_stage208_without_filling_empty_buckets() -> None:
    """The blind plotting input must remain sparse and bounded to D-5 through D-1."""
    calendar = pd.bdate_range("2021-01-04", periods=8)
    minutes = pd.DataFrame(
        {
            "vt_symbol": ["rb2105.SHFE"] * 3,
            "bar_datetime": pd.to_datetime(
                ["2021-01-05 09:01", "2021-01-05 09:14", "2021-01-06 09:01"]
            ),
            "trading_day": [calendar[1], calendar[1], calendar[2]],
            "open": [100.0, 102.0, 104.0],
            "high": [103.0, 105.0, 106.0],
            "low": [99.0, 101.0, 103.0],
            "close": [102.0, 104.0, 105.0],
            "volume": [1.0, 2.0, 3.0],
            "open_oi": [10.0, 11.0, 12.0],
            "close_oi": [11.0, 12.0, 13.0],
        }
    )
    events = pd.DataFrame(
        [{"open_trade_id": "short-a", "vt_symbol": "rb2105.SHFE", "entry_date": calendar[6]}]
    )

    bars_15m = stage214.build_preentry_15m(minutes, events, calendar)

    assert len(bars_15m) == 2
    assert bars_15m["bar_15m"].dt.strftime("%Y-%m-%d %H:%M").tolist() == [
        "2021-01-05 09:00",
        "2021-01-06 09:00",
    ]
    assert bars_15m.iloc[0][["open", "high", "low", "close", "volume"]].tolist() == [
        100.0,
        105.0,
        99.0,
        104.0,
        3.0,
    ]


def test_source_hashes_detect_content_changes_but_normalize_database_row_order(
    tmp_path: Path,
) -> None:
    """File bytes are immutable evidence; database rows are order-independent evidence."""
    calendar = pd.bdate_range("2021-01-04", periods=8)
    events = pd.DataFrame(
        [{"open_trade_id": "short-a", "vt_symbol": "rb2105.SHFE", "entry_date": calendar[6]}]
    )
    stage861_path = tmp_path / "stage861.csv"
    source = pd.DataFrame(
        {
            "vt_symbol": ["rb2105.SHFE"],
            "bar_datetime": ["2021-01-04 21:01"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [10.0],
            "open_oi": [1000.0],
            "close_oi": [1001.0],
        }
    )
    source.to_csv(stage861_path, index=False)

    def bar(timestamp: str, close: float):
        return type(
            "Bar",
            (),
            {
                "datetime": pd.Timestamp(timestamp),
                "open_price": close - 0.5,
                "high_price": close + 0.5,
                "low_price": close - 1.0,
                "close_price": close,
                "volume": 12.0,
                "open_interest": 1004.0,
            },
        )()

    class Database:
        def __init__(self, bars):
            self.bars = bars

        def load_bar_data(self, *args):
            return self.bars

    first_bars = [bar("2021-01-05 09:01", 103.5), bar("2021-01-06 09:01", 104.5)]
    _, first_sources = stage214.merge_minute_sources(
        events, calendar, stage861_path, [], Database(first_bars)
    )
    first_file_hash = first_sources.loc[first_sources["source"].eq("stage861"), "sha256"].iloc[0]
    first_database_hash = first_sources.loc[
        first_sources["source"].eq("vnpy_database"), "sha256"
    ].iloc[0]

    source.loc[0, "close"] = 101.5
    source.to_csv(stage861_path, index=False)
    _, reordered_sources = stage214.merge_minute_sources(
        events, calendar, stage861_path, [], Database(list(reversed(first_bars)))
    )
    reordered_file_hash = reordered_sources.loc[
        reordered_sources["source"].eq("stage861"), "sha256"
    ].iloc[0]
    reordered_database_hash = reordered_sources.loc[
        reordered_sources["source"].eq("vnpy_database"), "sha256"
    ].iloc[0]
    _, changed_sources = stage214.merge_minute_sources(
        events, calendar, stage861_path, [], Database([bar("2021-01-05 09:01", 103.6), first_bars[1]])
    )
    changed_database_hash = changed_sources.loc[
        changed_sources["source"].eq("vnpy_database"), "sha256"
    ].iloc[0]

    assert reordered_file_hash != first_file_hash
    assert reordered_database_hash == first_database_hash
    assert changed_database_hash != first_database_hash
