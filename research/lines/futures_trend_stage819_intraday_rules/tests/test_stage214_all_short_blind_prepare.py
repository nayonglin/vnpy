from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo


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
    assert str(events["outcome_ge_2r"].dtype) == "boolean"
    assert str(events["outcome_profitable"].dtype) == "boolean"
    assert events.loc[0, "outcome_ge_2r"] == False
    assert events.loc[0, "outcome_profitable"] == True
    assert events.loc[1, "outcome_ge_2r"] is pd.NA
    assert events.loc[1, "outcome_profitable"] is pd.NA
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


def test_merge_authorized_completed_cache_supersedes_degenerate_stage861(
    tmp_path: Path,
) -> None:
    """A reviewed completed-row repair must replace the known rolling Stage861 duplicate."""
    calendar = pd.bdate_range("2021-01-04", periods=8)
    events = pd.DataFrame(
        [{"open_trade_id": "short-a", "vt_symbol": "rb2105.SHFE", "entry_date": calendar[6]}]
    )
    columns = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    stage861_path = tmp_path / "stage861.csv"
    authorized_path = tmp_path / "authorized_tqsdk_raw" / "SHFE" / "rb2105_20210105_minute_backtest.csv"
    authorized_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [["rb2105.SHFE", "2021-01-05 09:01", 100, 100, 100, 100, 0, 1000, 1000]],
        columns=columns,
    ).to_csv(stage861_path, index=False)
    pd.DataFrame(
        [["rb2105.SHFE", "2021-01-05 09:01", 100, 102, 99, 101, 12, 1000, 1001]],
        columns=columns,
    ).to_csv(authorized_path, index=False)

    class EmptyDatabase:
        def load_bar_data(self, *args):
            return []

    minutes, sources = stage214.merge_minute_sources(
        events,
        calendar,
        stage861_path,
        [],
        EmptyDatabase(),
        authorized_cache_paths=[authorized_path],
    )

    assert minutes.loc[0, "close"] == 101.0
    assert minutes.loc[0, "volume"] == 12.0
    assert minutes.loc[0, "minute_source_kind"] == "authorized_tqsdk_completed"
    assert minutes.loc[0, "source_priority"] == 4
    assert "authorized_tqsdk_completed" in set(sources["source"])


def test_merge_authorized_completed_day_rejects_lower_priority_tail_rows(
    tmp_path: Path,
) -> None:
    """A qualified authorized day must not be patched with any lower-priority row."""
    calendar = pd.bdate_range("2021-01-04", periods=8)
    trading_day = calendar[1]
    events = pd.DataFrame(
        [{"open_trade_id": "short-a", "vt_symbol": "rb2105.SHFE", "entry_date": calendar[6]}]
    )
    stage861_path = tmp_path / "stage861.csv"
    authorized_path = (
        tmp_path
        / "authorized_tqsdk_raw"
        / "SHFE"
        / "rb2105_20210105_minute_backtest.csv"
    )
    authorized_path.parent.mkdir(parents=True)
    authorized = _quality_day("rb2105.SHFE", trading_day, include_night=False)
    authorized.drop(columns=["trading_day", "minute_source_kind", "minute_source_path"]).to_csv(
        authorized_path, index=False
    )
    stale_tail = authorized.tail(1).copy()
    stale_tail["bar_datetime"] = trading_day + pd.Timedelta(hours=10)
    stale_tail[["open", "high", "low", "close"]] = 999.0
    stale_tail["volume"] = 0.0
    stale_tail.drop(columns=["trading_day", "minute_source_kind", "minute_source_path"]).to_csv(
        stage861_path, index=False
    )

    class EmptyDatabase:
        def load_bar_data(self, *args):
            return []

    minutes, _ = stage214.merge_minute_sources(
        events,
        calendar,
        stage861_path,
        [],
        EmptyDatabase(),
        authorized_cache_paths=[authorized_path],
    )

    selected_day = minutes[
        minutes["vt_symbol"].eq("rb2105.SHFE")
        & minutes["trading_day"].eq(trading_day)
    ]
    assert len(selected_day) == 60
    assert selected_day["minute_source_kind"].eq("authorized_tqsdk_completed").all()
    assert pd.Timestamp("2021-01-05 10:00") not in set(selected_day["bar_datetime"])


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
    minutes = pd.concat(
        [
            *[
                _quality_day("rb2105.SHFE", day, include_night=False)
                for day in target_days
            ],
            *[
                _quality_day("jm2205.DCE", day, include_night=False)
                for day in target_days[:4]
            ],
        ],
        ignore_index=True,
    )
    minutes["minute_source_kind"] = "stage861"
    minutes["minute_source_path"] = "/frozen/stage861.csv"
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


def _quality_day(
    vt_symbol: str,
    trading_day: pd.Timestamp,
    *,
    include_night: bool,
    degenerate: bool = False,
    one_row: bool = False,
) -> pd.DataFrame:
    """Build a hand-checked minute session without using production helpers."""
    day = pd.Timestamp(trading_day).normalize()
    timestamps: list[pd.Timestamp] = []
    if include_night:
        timestamps.extend(pd.date_range(day - pd.Timedelta(days=1) + pd.Timedelta(hours=21), periods=60, freq="min"))
    timestamps.extend(pd.date_range(day + pd.Timedelta(hours=9), periods=59, freq="min"))
    timestamps.append(day + pd.Timedelta(hours=14, minutes=59))
    if one_row:
        timestamps = timestamps[:1]
    sequence = np.arange(len(timestamps), dtype=float)
    if degenerate:
        open_price = np.full(len(timestamps), 100.0)
        close_price = open_price.copy()
        high_price = open_price.copy()
        low_price = open_price.copy()
        volume = np.zeros(len(timestamps))
    else:
        open_price = 100.0 + sequence * 0.01
        close_price = open_price + 0.05
        high_price = close_price + 0.02
        low_price = open_price - 0.02
        volume = np.ones(len(timestamps))
    return pd.DataFrame(
        {
            "vt_symbol": vt_symbol,
            "bar_datetime": timestamps,
            "trading_day": [day] * len(timestamps),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "open_oi": np.full(len(timestamps), 1000.0),
            "close_oi": np.full(len(timestamps), 1001.0),
            "minute_source_kind": ["fixture"] * len(timestamps),
            "minute_source_path": ["/fixture/completed.csv"] * len(timestamps),
        }
    )


def test_authorized_completed_day_requires_1459_session_close() -> None:
    """Stopping at 14:58 must fail while a completed 14:59 day passes."""
    trading_day = pd.Timestamp("2021-01-05")
    completed = _quality_day("rb2105.SHFE", trading_day, include_night=False)
    completed["minute_source_kind"] = "authorized_tqsdk_completed"
    truncated = completed.copy()
    truncated.loc[
        truncated["bar_datetime"].eq(pd.Timestamp("2021-01-05 14:59")),
        "bar_datetime",
    ] = pd.Timestamp("2021-01-05 14:58")

    completed_quality = stage214.build_minute_day_quality(completed).iloc[0]
    truncated_quality = stage214.build_minute_day_quality(truncated).iloc[0]

    assert bool(completed_quality["quality_passed"])
    assert bool(completed_quality["has_session_end_1459"])
    assert not bool(truncated_quality["quality_passed"])
    assert not bool(truncated_quality["has_session_end_1459"])
    assert "missing_session_end_1459" in truncated_quality["failure_reasons"]


def test_gap_audit_rejects_one_row_missing_night_and_degenerate_days() -> None:
    """Presence-only coverage must not accept sparse, session-truncated, or rolling rows."""
    calendar = pd.bdate_range("2021-01-04", periods=6)
    target_days = list(calendar[:-1])
    events = pd.DataFrame(
        [
            {"open_trade_id": "one-row", "vt_symbol": "one2105.SHFE", "entry_date": calendar[-1], "risk_status": "resolved"},
            {"open_trade_id": "missing-night", "vt_symbol": "night2105.SHFE", "entry_date": calendar[-1], "risk_status": "resolved"},
            {"open_trade_id": "degenerate", "vt_symbol": "flat2105.SHFE", "entry_date": calendar[-1], "risk_status": "resolved"},
            {"open_trade_id": "qualified", "vt_symbol": "day2105.SHFE", "entry_date": calendar[-1], "risk_status": "resolved"},
        ]
    )
    minute_frames: list[pd.DataFrame] = []
    for day in target_days:
        minute_frames.append(_quality_day("day2105.SHFE", day, include_night=False))
        minute_frames.append(_quality_day("one2105.SHFE", day, include_night=False, one_row=day == target_days[-1]))
        minute_frames.append(_quality_day("night2105.SHFE", day, include_night=day != target_days[-1]))
        minute_frames.append(_quality_day("flat2105.SHFE", day, include_night=False, degenerate=day == target_days[-1]))
    minutes = pd.concat(minute_frames, ignore_index=True)

    audit = stage214.build_data_gap_audit(events, minutes, calendar).set_index("open_trade_id")

    assert audit.loc["qualified", "coverage_state"] == "complete"
    assert audit.loc["one-row", "coverage_state"] == "partial"
    assert "insufficient_bar_count" in audit.loc["one-row", "failure_reasons"]
    assert audit.loc["missing-night", "coverage_state"] == "partial"
    assert "missing_night_session" in audit.loc["missing-night", "failure_reasons"]
    assert audit.loc["degenerate", "coverage_state"] == "partial"
    assert "all_ohlc_flat_and_zero_volume" in audit.loc["degenerate", "failure_reasons"]


def test_gap_audit_accepts_completed_query_that_proves_holiday_night_absent() -> None:
    """A fully completed authorized query may prove a one-day night-session exception."""
    calendar = pd.bdate_range("2021-01-04", periods=6)
    target_days = list(calendar[:-1])
    frames = [
        _quality_day("FG999.CZCE", day, include_night=day != target_days[-1])
        for day in target_days
    ]
    frames[-1]["minute_source_kind"] = "authorized_tqsdk_completed"
    frames[-1]["minute_source_path"] = "/controller/authorized_tqsdk_raw/FG999.csv"
    minutes = pd.concat(frames, ignore_index=True)
    events = pd.DataFrame(
        [{"open_trade_id": "holiday", "vt_symbol": "FG999.CZCE", "entry_date": calendar[-1], "risk_status": "resolved"}]
    )

    audit = stage214.build_data_gap_audit(events, minutes, calendar)

    assert audit.loc[0, "coverage_state"] == "complete"
    assert audit.loc[0, "failure_reasons"] == ""


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


def test_blind_mapping_is_seeded_and_independent_of_input_order() -> None:
    """An input-order-dependent or unseeded case assignment breaks blind replication."""
    events = pd.DataFrame(
        {
            "open_trade_id": [f"BACKTESTING.{index:03d}" for index in range(64)],
            "vt_symbol": ["rb2105.SHFE"] * 64,
            "entry_date": ["2021-01-11"] * 64,
        }
    )

    first = stage214.build_blind_mapping(events, seed=21420260808)
    shuffled = stage214.build_blind_mapping(
        events.sample(frac=1.0, random_state=7), seed=21420260808
    )
    changed_seed = stage214.build_blind_mapping(events, seed=1)

    first_by_event = first.set_index("open_trade_id")["case_id"].to_dict()
    assert first_by_event == shuffled.set_index("open_trade_id")["case_id"].to_dict()
    assert sorted(first["case_id"].tolist()) == [f"CASE-{index:03d}" for index in range(1, 65)]
    assert first_by_event != changed_seed.set_index("open_trade_id")["case_id"].to_dict()


def test_normalize_preentry_bars_scales_all_ohlc_from_first_close() -> None:
    """Scaling only close or choosing another anchor would expose absolute-price clues."""
    bars = pd.DataFrame(
        {
            "open": [5.0, 4.0],
            "high": [6.0, 5.0],
            "low": [3.0, 2.0],
            "close": [4.0, 3.0],
        }
    )

    normalized = stage214.normalize_preentry_bars(bars)

    assert normalized.loc[0, ["open", "high", "low", "close"]].tolist() == [125.0, 150.0, 75.0, 100.0]
    assert normalized.loc[1, ["open", "high", "low", "close"]].tolist() == [100.0, 125.0, 50.0, 75.0]
    assert normalized["high"].ge(normalized[["open", "close", "low"]].max(axis=1)).all()
    assert normalized["low"].le(normalized[["open", "close", "high"]].min(axis=1)).all()


def test_render_blind_chart_excludes_entry_day_and_returns_reviewer_safe_counts(
    tmp_path: Path,
) -> None:
    """Including D0 or returning an identity field would defeat the pre-entry blind."""
    target_days = list(pd.bdate_range("2021-01-04", periods=5))
    entry_day = pd.Timestamp("2021-01-11")
    bars = pd.DataFrame(
        {
            "bar_15m": pd.to_datetime(
                [f"{day.date()} 09:00" for day in [*target_days, entry_day]]
            ),
            "trading_day": [*target_days, entry_day],
            "open": [100.0, 101.0, 102.0, 103.0, 104.0, 999.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0, 1000.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0, 998.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5, 999.5],
            "volume": [10.0] * 6,
        }
    )
    output_path = tmp_path / "CASE-001.png"

    metadata = stage214.render_blind_chart("CASE-001", bars, target_days, output_path)

    assert output_path.is_file() and output_path.stat().st_size > 0
    assert metadata == {
        "case_id": "CASE-001",
        "chart_file": "CASE-001.png",
        "available_day_count": 5,
        "bar_count": 5,
    }


@pytest.mark.parametrize(
    ("leak_kind", "chart_name", "manifest", "png_text"),
    [
        (
            "contract filename",
            "CASE-001_rb2105.SHFE.png",
            pd.DataFrame(
                [{"case_id": "CASE-001", "chart_file": "CASE-001_rb2105.SHFE.png", "available_day_count": 5, "bar_count": 5}]
            ),
            {},
        ),
        (
            "winner manifest column",
            "CASE-001.png",
            pd.DataFrame(
                [{"case_id": "CASE-001", "chart_file": "CASE-001.png", "available_day_count": 5, "bar_count": 5, "winner": True}]
            ),
            {},
        ),
        (
            "outcome PNG metadata",
            "CASE-001.png",
            pd.DataFrame(
                [{"case_id": "CASE-001", "chart_file": "CASE-001.png", "available_day_count": 5, "bar_count": 5}]
            ),
            {"aggregate_r": "2.5"},
        ),
    ],
)
def test_audit_blind_artifacts_rejects_identity_or_outcome_leaks(
    tmp_path: Path,
    leak_kind: str,
    chart_name: str,
    manifest: pd.DataFrame,
    png_text: dict[str, str],
) -> None:
    """A contract, outcome field, or PNG text chunk must fail the reviewer boundary."""
    chart_dir = tmp_path / "blind_charts"
    chart_dir.mkdir()
    info = PngInfo()
    for key, value in png_text.items():
        info.add_text(key, value)
    Image.new("RGB", (4, 4), "white").save(chart_dir / chart_name, pnginfo=info)
    sealed_mapping = pd.DataFrame(
        [{"case_id": "CASE-001", "open_trade_id": "BACKTESTING.123", "vt_symbol": "rb2105.SHFE", "entry_date": "2021-01-11", "aggregate_r": 2.5}]
    )

    audit = stage214.audit_blind_artifacts(chart_dir, manifest, sealed_mapping)

    assert audit["ok"] is False, leak_kind
    assert audit["violations"]


def test_audit_blind_artifacts_accepts_only_the_sealed_reviewer_surface(
    tmp_path: Path,
) -> None:
    """A safe case filename and four-column manifest must pass the leakage gate."""
    chart_dir = tmp_path / "blind_charts"
    chart_dir.mkdir()
    Image.new("RGB", (4, 4), "white").save(chart_dir / "CASE-001.png")
    reviewer_manifest = pd.DataFrame(
        [{"case_id": "CASE-001", "chart_file": "CASE-001.png", "available_day_count": 5, "bar_count": 5}]
    )
    sealed_mapping = pd.DataFrame(
        [{"case_id": "CASE-001", "open_trade_id": "BACKTESTING.123", "vt_symbol": "rb2105.SHFE", "entry_date": "2021-01-11", "aggregate_r": 2.5}]
    )

    audit = stage214.audit_blind_artifacts(chart_dir, reviewer_manifest, sealed_mapping)

    assert audit == {"ok": True, "violations": []}


def test_prepare_writes_only_consistent_reviewer_artifacts_for_64_complete_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing a required artifact or mismatching its chart set must block blind handoff."""
    input_path = tmp_path / "input.csv"
    pd.DataFrame({"placeholder": [1]}).to_csv(input_path, index=False)
    calendar = pd.bdate_range("2021-01-04", periods=6)
    events = pd.DataFrame(
        {
            "open_trade_id": [f"event-{index:03d}" for index in range(64)],
            "vt_symbol": ["rb2105.SHFE"] * 64,
            "entry_date": [calendar[-1]] * 64,
            "aggregate_r": [float(index) for index in range(64)],
        }
    )
    bars15 = pd.DataFrame(
        {
            "vt_symbol": ["rb2105.SHFE"] * 5,
            "trading_day": list(calendar[:-1]),
            "bar_15m": pd.to_datetime([f"{day.date()} 09:00" for day in calendar[:-1]]),
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
        }
    )
    gap_audit = pd.DataFrame(
        {"open_trade_id": events["open_trade_id"], "coverage_state": ["complete"] * 64}
    )
    monkeypatch.setattr(stage214, "CLOSED_LOTS_PATH", input_path)
    monkeypatch.setattr(stage214, "CURVES_PATH", input_path)
    monkeypatch.setattr(stage214, "MINUTE_PATH", input_path)
    monkeypatch.setattr(stage214, "build_short_events", lambda _: events.copy())
    monkeypatch.setattr(stage214, "resolve_risk_zero_events", lambda frame, _: (frame, pd.DataFrame()))
    monkeypatch.setattr(stage214, "build_trading_calendar", lambda _: calendar)
    monkeypatch.setattr(stage214, "discover_contract_cache_paths", lambda *_: [])
    monkeypatch.setattr(
        stage214,
        "merge_minute_sources",
        lambda *_, **__: (pd.DataFrame(), pd.DataFrame({"source": ["fixture"]})),
    )
    monkeypatch.setattr(stage214, "build_data_gap_audit", lambda *_: gap_audit.copy())
    monkeypatch.setattr(stage214, "build_preentry_15m", lambda *_: bars15.copy())

    decision = stage214.prepare(tmp_path / "prepared", database=object())

    output_dir = tmp_path / "prepared"
    assert decision["status"] == "ready"
    assert decision["event_count"] == 64
    assert decision["chartable_event_count"] == 64
    assert decision["result_analyzable_event_count"] == 64
    assert decision["chart_count"] == 64
    assert decision["chart_set_matches_reviewer_manifest"] is True
    assert {path.name for path in output_dir.iterdir()} >= {
        "short_event_manifest.csv",
        "minute_source_manifest.csv",
        "data_gap_audit.csv",
        "blind_mapping.csv",
        "reviewer_manifest.csv",
        "blind_charts",
        "prepare_decision.json",
    }
    reviewer_manifest = pd.read_csv(output_dir / "reviewer_manifest.csv")
    assert reviewer_manifest.columns.tolist() == stage214.REVIEWER_MANIFEST_COLUMNS
    assert len(list((output_dir / "blind_charts").glob("*.png"))) == 64


@pytest.mark.parametrize(
    "target_days",
    [
        list(pd.bdate_range("2021-01-04", periods=4)),
        list(pd.bdate_range("2021-01-04", periods=6)),
        [
            pd.Timestamp("2021-01-04"),
            pd.Timestamp("2021-01-05"),
            pd.Timestamp("2021-01-06"),
            pd.Timestamp("2021-01-07"),
            pd.Timestamp("2021-01-07"),
        ],
        [
            pd.Timestamp("2021-01-05"),
            pd.Timestamp("2021-01-04"),
            pd.Timestamp("2021-01-06"),
            pd.Timestamp("2021-01-07"),
            pd.Timestamp("2021-01-08"),
        ],
    ],
)
def test_render_blind_chart_rejects_noncanonical_target_day_sets(
    tmp_path: Path,
    target_days: list[pd.Timestamp],
) -> None:
    """A short, extended, duplicate, or unordered D-5..D-1 window is not blind-safe."""
    all_days = pd.bdate_range("2021-01-04", periods=6)
    bars = pd.DataFrame(
        {
            "bar_15m": pd.to_datetime([f"{day.date()} 09:00" for day in all_days]),
            "trading_day": all_days,
            "open": [100.0] * 6,
            "high": [101.0] * 6,
            "low": [99.0] * 6,
            "close": [100.5] * 6,
        }
    )

    with pytest.raises(ValueError, match="target_days"):
        stage214.render_blind_chart("CASE-001", bars, target_days, tmp_path / "CASE-001.png")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("pnl", "123.4"),
        ("R", "2.0"),
        ("exit", "2021-01-11"),
        ("rank", "1"),
        ("absolute_price", "4200"),
    ],
)
def test_audit_blind_artifacts_rejects_unapproved_png_text_chunks(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    """Every non-allowlisted PNG text chunk is a potential identity or outcome leak."""
    chart_dir = tmp_path / "blind_charts"
    chart_dir.mkdir()
    info = PngInfo()
    info.add_text(key, value)
    Image.new("RGB", (4, 4), "white").save(chart_dir / "CASE-001.png", pnginfo=info)
    reviewer_manifest = pd.DataFrame(
        [{"case_id": "CASE-001", "chart_file": "CASE-001.png", "available_day_count": 5, "bar_count": 5}]
    )
    sealed_mapping = pd.DataFrame(
        [{"case_id": "CASE-001", "open_trade_id": "event-001", "vt_symbol": "rb2105.SHFE", "entry_date": "2021-01-11"}]
    )

    audit = stage214.audit_blind_artifacts(chart_dir, reviewer_manifest, sealed_mapping)

    assert audit["ok"] is False
    assert audit["violations"]


@pytest.mark.parametrize("extra_kind", ["txt", "hidden", "extra_png", "directory", "symlink"])
def test_audit_blind_artifacts_rejects_every_unlisted_chart_directory_entry(
    tmp_path: Path,
    extra_kind: str,
) -> None:
    """Only manifest-addressed ordinary CASE PNG files may live in blind_charts."""
    chart_dir = tmp_path / "blind_charts"
    chart_dir.mkdir()
    Image.new("RGB", (4, 4), "white").save(chart_dir / "CASE-001.png")
    if extra_kind == "txt":
        (chart_dir / "notes.txt").write_text("not a chart", encoding="utf-8")
    elif extra_kind == "hidden":
        (chart_dir / ".hidden").write_text("not a chart", encoding="utf-8")
    elif extra_kind == "extra_png":
        Image.new("RGB", (4, 4), "white").save(chart_dir / "CASE-002.png")
    elif extra_kind == "directory":
        (chart_dir / "nested").mkdir()
    else:
        (chart_dir / "CASE-002.png").symlink_to(chart_dir / "CASE-001.png")
    reviewer_manifest = pd.DataFrame(
        [{"case_id": "CASE-001", "chart_file": "CASE-001.png", "available_day_count": 5, "bar_count": 5}]
    )
    sealed_mapping = pd.DataFrame(
        [{"case_id": "CASE-001", "open_trade_id": "event-001", "vt_symbol": "rb2105.SHFE", "entry_date": "2021-01-11"}]
    )

    audit = stage214.audit_blind_artifacts(chart_dir, reviewer_manifest, sealed_mapping)

    assert audit["ok"] is False
    assert audit["violations"]


def _patch_prepare_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    event_count: int = 64,
    complete_count: int = 64,
    unresolved_count: int = 0,
) -> None:
    input_path = tmp_path / "input.csv"
    pd.DataFrame({"placeholder": [1]}).to_csv(input_path, index=False)
    calendar = pd.bdate_range("2021-01-04", periods=6)
    events = pd.DataFrame(
        {
            "open_trade_id": [f"event-{index:03d}" for index in range(event_count)],
            "vt_symbol": ["rb2105.SHFE"] * event_count,
            "entry_date": [calendar[-1]] * event_count,
            "aggregate_r": [np.nan] * unresolved_count + [1.0] * (event_count - unresolved_count),
            "risk_status": ["unresolved"] * unresolved_count + ["resolved"] * (event_count - unresolved_count),
        }
    )
    bars15 = pd.DataFrame(
        {
            "vt_symbol": ["rb2105.SHFE"] * 5,
            "trading_day": list(calendar[:-1]),
            "bar_15m": pd.to_datetime([f"{day.date()} 09:00" for day in calendar[:-1]]),
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
        }
    )
    gap_audit = pd.DataFrame(
        {
            "open_trade_id": events["open_trade_id"],
            "coverage_state": ["complete"] * complete_count + ["missing"] * (event_count - complete_count),
        }
    )
    monkeypatch.setattr(stage214, "CLOSED_LOTS_PATH", input_path)
    monkeypatch.setattr(stage214, "CURVES_PATH", input_path)
    monkeypatch.setattr(stage214, "MINUTE_PATH", input_path)
    monkeypatch.setattr(stage214, "build_short_events", lambda _: events.copy())
    monkeypatch.setattr(stage214, "resolve_risk_zero_events", lambda frame, _: (frame, pd.DataFrame()))
    monkeypatch.setattr(stage214, "build_trading_calendar", lambda _: calendar)
    monkeypatch.setattr(stage214, "discover_contract_cache_paths", lambda *_: [])
    monkeypatch.setattr(
        stage214,
        "merge_minute_sources",
        lambda *_, **__: (pd.DataFrame(), pd.DataFrame({"source": ["fixture"]})),
    )
    monkeypatch.setattr(stage214, "build_data_gap_audit", lambda *_: gap_audit.copy())
    monkeypatch.setattr(stage214, "build_preentry_15m", lambda *_: bars15.copy())


@pytest.mark.parametrize(
    ("event_count", "complete_count", "reason"),
    [(63, 63, "event_count_not_64"), (64, 59, "result_analyzable_event_count_below_60")],
)
def test_prepare_writes_blocked_decision_before_count_gate_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_count: int,
    complete_count: int,
    reason: str,
) -> None:
    """Count gates must never leave a ready decision behind when prepare raises."""
    _patch_prepare_fixture(
        monkeypatch, tmp_path, event_count=event_count, complete_count=complete_count
    )
    output_dir = tmp_path / "prepared"

    with pytest.raises(RuntimeError):
        stage214.prepare(output_dir, database=object())

    decision = json.loads((output_dir / "prepare_decision.json").read_text(encoding="utf-8"))
    assert decision["status"] == "blocked"
    assert reason in decision["blocking_reasons"]


def test_prepare_distinguishes_64_chartable_from_61_result_analyzable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unresolved R stays chartable but is excluded from the result-analysis count."""
    _patch_prepare_fixture(monkeypatch, tmp_path, unresolved_count=3)

    decision = stage214.prepare(tmp_path / "prepared", database=object())

    assert decision["status"] == "ready"
    assert decision["chartable_event_count"] == 64
    assert decision["result_analyzable_event_count"] == 61


def test_prepare_blocks_any_extra_chart_directory_entry_before_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An old or non-chart file in blind_charts must fail prepare rather than be ignored."""
    _patch_prepare_fixture(monkeypatch, tmp_path)
    original_render = stage214.render_blind_chart

    def render_with_extra_file(*args, **kwargs):
        metadata = original_render(*args, **kwargs)
        Path(args[3]).parent.joinpath("stale.txt").write_text("stale", encoding="utf-8")
        return metadata

    monkeypatch.setattr(stage214, "render_blind_chart", render_with_extra_file)
    output_dir = tmp_path / "prepared"

    with pytest.raises(RuntimeError):
        stage214.prepare(output_dir, database=object())

    decision = json.loads((output_dir / "prepare_decision.json").read_text(encoding="utf-8"))
    assert decision["status"] == "blocked"
    assert "blind_artifact_audit_failed" in decision["blocking_reasons"]


def test_prepare_marks_chart_manifest_mismatch_blocked_before_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reviewer manifest pointing at a non-existent chart must never be marked ready."""
    _patch_prepare_fixture(monkeypatch, tmp_path)
    original_render = stage214.render_blind_chart

    def render_with_wrong_manifest_file(*args, **kwargs):
        metadata = original_render(*args, **kwargs)
        if metadata["case_id"] == "CASE-001":
            metadata["chart_file"] = "CASE-999.png"
        return metadata

    monkeypatch.setattr(stage214, "render_blind_chart", render_with_wrong_manifest_file)
    output_dir = tmp_path / "prepared"

    with pytest.raises(RuntimeError):
        stage214.prepare(output_dir, database=object())

    decision = json.loads((output_dir / "prepare_decision.json").read_text(encoding="utf-8"))
    assert decision["status"] == "blocked"
    assert "chart_set_mismatch" in decision["blocking_reasons"]
