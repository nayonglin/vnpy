from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from research.lines.futures_trend_l1_topbook_entry_quality.tools import (
    stage001_l1_tick_canary as stage,
)


def _ns(value: str) -> int:
    return int(pd.Timestamp(value, tz="Asia/Shanghai").tz_convert("UTC").value)


def _valid_tick(
    *,
    value: str = "2024-01-02 09:00:05",
    symbol: str = "DCE.lh2403",
    tick_id: int = 1,
    volume: int = 10,
) -> dict[str, object]:
    return {
        "id": tick_id,
        "datetime": _ns(value),
        "symbol": symbol,
        "last_price": 100.5,
        "ask_price1": 101.0,
        "ask_volume1": 3,
        "bid_price1": 100.0,
        "bid_volume1": 4,
        "volume": volume,
        "open_interest": 1000,
    }


def test_canary_selection_is_exchange_session_earliest_latest_deterministic() -> None:
    rows = [
        {
            "event_id": "czce-late",
            "entry_date": "2024-03-01",
            "product_vt_symbol": "AP.CZCE",
            "vt_symbol": "AP405.CZCE",
            "tqsdk_underlying": "CZCE.AP405",
        },
        {
            "event_id": "czce-early-z",
            "entry_date": "2024-01-02",
            "product_vt_symbol": "AP.CZCE",
            "vt_symbol": "AP405.CZCE",
            "tqsdk_underlying": "CZCE.AP405",
        },
        {
            "event_id": "czce-early-a",
            "entry_date": "2024-01-02",
            "product_vt_symbol": "AP.CZCE",
            "vt_symbol": "AP405.CZCE",
            "tqsdk_underlying": "CZCE.AP405",
        },
        {
            "event_id": "dce-night-early",
            "entry_date": "2024-01-03",
            "product_vt_symbol": "jm.DCE",
            "vt_symbol": "jm2405.DCE",
            "tqsdk_underlying": "DCE.jm2405",
        },
        {
            "event_id": "dce-night-late",
            "entry_date": "2024-04-01",
            "product_vt_symbol": "jm.DCE",
            "vt_symbol": "jm2405.DCE",
            "tqsdk_underlying": "DCE.jm2405",
        },
    ]
    events = pd.DataFrame(rows).sample(frac=1.0, random_state=7)

    selected = stage.select_canary_events(events)

    assert selected["event_id"].tolist() == [
        "czce-early-a",
        "czce-late",
        "dce-night-early",
        "dce-night-late",
    ]
    assert selected["boundary"].tolist() == ["earliest", "latest", "earliest", "latest"]
    assert selected["has_night_session"].tolist() == [False, False, True, True]


def test_night_session_uses_previous_global_trade_date_not_calendar_day() -> None:
    global_dates = pd.DatetimeIndex(
        pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-08"])
    )

    window = stage.compute_session_window(
        entry_date="2024-01-08",
        has_night_session=True,
        global_trade_dates=global_dates,
    )

    assert window["session_start"] == "2024-01-05 20:59:00"
    assert window["session_open"] == "2024-01-05 21:00:00"
    assert window["session_end"] == "2024-01-05 21:05:00"

    day = stage.compute_session_window(
        entry_date="2024-01-08",
        has_night_session=False,
        global_trade_dates=global_dates,
    )
    assert day["session_start"] == "2024-01-08 08:59:00"
    assert day["session_open"] == "2024-01-08 09:00:00"
    assert day["session_end"] == "2024-01-08 09:05:00"


def test_integer_nanoseconds_normalize_exactly_without_float_roundtrip() -> None:
    raw = pd.DataFrame([_valid_tick()])

    normalized, parse_audit = stage.normalize_tick_frame(
        raw,
        start="2024-01-02 08:59:00",
        end="2024-01-02 09:05:00",
    )

    assert parse_audit["float_datetime_count"] == 0
    assert parse_audit["malformed_datetime_count"] == 0
    assert int(normalized.loc[0, "datetime_ns"]) == _ns("2024-01-02 09:00:05")
    assert normalized.loc[0, "datetime_beijing"].isoformat() == "2024-01-02T09:00:05+08:00"
    assert bool(normalized.loc[0, "in_request_window"])

    float_raw = raw.copy()
    float_raw["datetime"] = float_raw["datetime"].astype(float)
    _, float_audit = stage.normalize_tick_frame(
        float_raw,
        start="2024-01-02 08:59:00",
        end="2024-01-02 09:05:00",
    )
    assert float_audit["float_datetime_count"] == 1
    assert float_audit["malformed_datetime_count"] == 1


def test_valid_l1_tick_passes_open_deadline_and_integrity() -> None:
    raw = pd.DataFrame(
        [
            _valid_tick(value="2024-01-02 08:59:59", tick_id=1, volume=9),
            _valid_tick(value="2024-01-02 09:00:05", tick_id=2, volume=10),
        ]
    )

    audit, normalized = stage.audit_tick_frame(
        raw,
        requested_symbol="DCE.lh2403",
        start="2024-01-02 08:59:00",
        end="2024-01-02 09:05:00",
        session_open="2024-01-02 09:00:00",
    )

    assert len(normalized) == 2
    assert audit["valid_l1_within_60s_count"] == 1
    assert audit["tick_integrity_pass"] is True


def test_tick_integrity_rejects_all_frozen_failure_modes() -> None:
    rows = [
        _valid_tick(value="2024-01-02 09:00:01", tick_id=1, volume=10),
        _valid_tick(value="2024-01-02 09:00:01", tick_id=1, volume=9),
        _valid_tick(value="2024-01-02 09:00:02", tick_id=2, volume=8),
        _valid_tick(value="2024-01-02 09:06:00", tick_id=3, volume=11),
    ]
    rows[0]["ask_price1"] = 99.0
    rows[1]["bid_volume1"] = -1
    rows[2]["ask_price1"] = np.inf
    rows[2]["symbol"] = "DCE.wrong2403"
    raw = pd.DataFrame(rows)

    audit, _ = stage.audit_tick_frame(
        raw,
        requested_symbol="DCE.lh2403",
        start="2024-01-02 08:59:00",
        end="2024-01-02 09:05:00",
        session_open="2024-01-02 09:00:00",
    )

    assert audit["outside_window_count"] == 1
    assert audit["symbol_mismatch_count"] == 1
    assert audit["duplicate_key_row_count"] == 2
    assert audit["crossed_spread_count"] == 1
    assert audit["negative_size_count"] == 1
    assert audit["infinite_numeric_count"] == 1
    assert audit["cumulative_volume_rollback_count"] >= 1
    assert audit["tick_integrity_pass"] is False


def test_redaction_removes_every_credential_literal() -> None:
    message = "login alice failed with password hunter2"
    redacted = stage.redact_message(message, ["alice", "hunter2"])
    assert "alice" not in redacted
    assert "hunter2" not in redacted
    assert redacted.count("<redacted>") == 2


def test_fake_fetch_failure_stays_in_denominator_and_never_marks_ready(tmp_path: Path) -> None:
    plan = pd.DataFrame(
        [
            {
                "event_id": f"event-{index:02d}",
                "exchange": "DCE",
                "has_night_session": False,
                "boundary": "earliest" if index % 2 == 0 else "latest",
                "entry_date": "2024-01-02",
                "product_vt_symbol": "lh.DCE",
                "vt_symbol": "lh2403.DCE",
                "tqsdk_underlying": "DCE.lh2403",
                "session_start": "2024-01-02 08:59:00",
                "session_open": "2024-01-02 09:00:00",
                "session_end": "2024-01-02 09:05:00",
            }
            for index in range(12)
        ]
    )

    def fake_fetch(_event: dict[str, object]) -> stage.FetchResult:
        return stage.FetchResult(
            terminal_status="query_failed",
            frame=pd.DataFrame(),
            message="synthetic failure",
            elapsed_seconds=0.01,
            network_called=False,
        )

    ledger = stage.execute_plan(
        plan,
        fetcher=fake_fetch,
        attempts_root=tmp_path / "attempts",
        secrets=[],
        run_id="unit-fake-fetch",
    )
    decision = stage.build_decision(plan, ledger)

    assert len(ledger) == 12
    assert set(ledger["terminal_status"]) == {"query_failed"}
    assert decision["denominator_event_count"] == 12
    assert decision["passed_event_count"] == 0
    assert decision["decision"] == "CLOSE_LINE_L1_TICK_COVERAGE_INELIGIBLE"
    assert decision["ready_for_feature"] is False
    assert decision["ready_for_backtest"] is False
    assert decision["ready_for_live"] is False
    assert len(list((tmp_path / "attempts").glob("*/attempt_0001"))) == 12


class Stage001L1TickCanaryTest(unittest.TestCase):
    def test_canary_selection(self) -> None:
        test_canary_selection_is_exchange_session_earliest_latest_deterministic()

    def test_session_window(self) -> None:
        test_night_session_uses_previous_global_trade_date_not_calendar_day()

    def test_integer_nanoseconds(self) -> None:
        test_integer_nanoseconds_normalize_exactly_without_float_roundtrip()

    def test_valid_l1_tick(self) -> None:
        test_valid_l1_tick_passes_open_deadline_and_integrity()

    def test_frozen_failure_modes(self) -> None:
        test_tick_integrity_rejects_all_frozen_failure_modes()

    def test_redaction(self) -> None:
        test_redaction_removes_every_credential_literal()

    def test_fake_fetch_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            test_fake_fetch_failure_stays_in_denominator_and_never_marks_ready(
                Path(directory)
            )


if __name__ == "__main__":
    unittest.main()
