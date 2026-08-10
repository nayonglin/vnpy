from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = PROJECT_ROOT / "examples" / "portfolio_backtesting"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_qmt_roll_stage904_official_live_c9_intraday_monitor as stage904  # noqa: E402
import run_qmt_roll_stage905_official_live_executor_dry_run as stage905  # noqa: E402
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931  # noqa: E402
from qmt_roll_official_live_execution_ledger import (  # noqa: E402
    append_execution_ledger_event,
    read_execution_ledger,
)


TARGET_DATE = "2026-08-08"
VT_SYMBOL = "rb2610.SHFE"


def _ticks(*rows: tuple[pd.Timestamp, float, float | None, float | None]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vt_symbol": VT_SYMBOL,
                "datetime": dt,
                "last_price": last,
                "bid_price_1": last if bid is None else bid,
                "ask_price_1": last if ask is None else ask,
            }
            for dt, last, bid, ask in rows
        ]
    )


def _position_action(
    ticks: pd.DataFrame,
    *,
    progress_confirmed: bool | None = False,
    ledger_rows: list[dict] | None = None,
    direction: str = "long",
    trade_datetime: str | pd.Timestamp | None = None,
) -> dict:
    trade_datetime = trade_datetime or f"{TARGET_DATE} 09:01:00"
    return stage904._action_for_position(
        {
            "vt_symbol": VT_SYMBOL,
            "direction": direction,
            "end_pos": 1,
            "close_price": 100,
            "position_source": "shadow",
        },
        trades=pd.DataFrame(
            [
                {
                    "trade_id": "open-1",
                    "vt_symbol": VT_SYMBOL,
                    "direction": direction,
                    "offset": "open",
                    "date": TARGET_DATE,
                    "datetime": trade_datetime,
                    "price": 100,
                    "volume": 1,
                }
            ]
        ),
        broker_trades=pd.DataFrame(),
        execution_ledger_rows=ledger_rows or [],
        entry_risk=pd.DataFrame(
            [
                {
                    "contract_vt_symbol": VT_SYMBOL,
                    "direction": direction,
                    "date": TARGET_DATE,
                    "datetime": f"{TARGET_DATE} 09:01:00",
                    "stop_price": 90 if direction == "long" else 110,
                }
            ]
        ),
        ticks=ticks,
        target_date=TARGET_DATE,
        max_tick_age_seconds=60,
        require_broker_fill_price=False,
        initial_progress_confirmed=progress_confirmed,
    )


def test_progress_confirmation_survives_a_later_adverse_poll() -> None:
    now = pd.Timestamp.now()
    first = _position_action(_ticks((now, 105, None, None)))
    assert first["monitor_action"] == "watch_progress_hit_no_initial_stop"
    assert first["initial_progress_confirmed_now"] == 1

    later = _position_action(
        _ticks((now + pd.Timedelta(milliseconds=1), 95, None, None)),
        progress_confirmed=True,
    )
    assert later["monitor_action"] == "watch_progress_hit_no_initial_stop"
    assert later["monitor_reason"] == "stage847_progress_previously_confirmed_no_initial_stop"


def test_fresh_tick_batch_honours_progress_before_adverse_order() -> None:
    now = pd.Timestamp.now()
    action = _position_action(
        _ticks(
            (now - pd.Timedelta(seconds=2), 105, None, None),
            (now - pd.Timedelta(seconds=1), 95, None, None),
        )
    )
    assert action["first_threshold_event"] == "progress"
    assert action["monitor_action"] == "watch_progress_hit_no_initial_stop"


def test_fresh_tick_batch_honours_adverse_before_progress_order() -> None:
    now = pd.Timestamp.now()
    action = _position_action(
        _ticks(
            (now - pd.Timedelta(seconds=2), 95, None, None),
            (now - pd.Timedelta(seconds=1), 105, None, None),
        )
    )
    assert action["first_threshold_event"] == "adverse"
    assert action["monitor_action"] == "close_dry_run"


def test_short_batch_honours_progress_before_adverse_order() -> None:
    now = pd.Timestamp.now()
    action = _position_action(
        _ticks(
            (now - pd.Timedelta(seconds=2), 95, None, None),
            (now - pd.Timedelta(seconds=1), 105, None, None),
        ),
        direction="short",
    )
    assert action["first_threshold_event"] == "progress"
    assert action["monitor_action"] == "watch_progress_hit_no_initial_stop"


def test_untraded_offer_or_bid_does_not_confirm_progress() -> None:
    now = pd.Timestamp.now()
    long_action = _position_action(_ticks((now, 104, 104, 105)))
    short_action = _position_action(
        _ticks((now, 96, 95, 96)),
        direction="short",
    )
    assert long_action["first_threshold_event"] == ""
    assert long_action["initial_progress_confirmed_now"] == 0
    assert short_action["first_threshold_event"] == ""
    assert short_action["initial_progress_confirmed_now"] == 0


def test_ticks_before_actual_open_fill_are_excluded() -> None:
    now = pd.Timestamp.now()
    entry_time = now - pd.Timedelta(seconds=10)
    action = _position_action(
        _ticks(
            (now - pd.Timedelta(seconds=20), 105, None, None),
            (now, 100, None, None),
        ),
        trade_datetime=entry_time,
    )
    assert action["first_threshold_event"] == ""
    assert action["initial_progress_confirmed_now"] == 0
    assert action["fresh_tick_batch_count"] == 1


def test_same_tick_progress_and_adverse_is_conservative() -> None:
    now = pd.Timestamp.now()
    action = _position_action(_ticks((now, 100, 95, 105)))
    assert action["first_threshold_event"] == "adverse"
    assert action["monitor_action"] == "close_dry_run"


def test_same_timestamp_rows_are_conservative_when_order_is_unknown() -> None:
    now = pd.Timestamp.now()
    action = _position_action(
        _ticks(
            (now, 105, None, None),
            (now, 95, None, None),
        )
    )
    assert action["first_threshold_event"] == "adverse"
    assert action["monitor_action"] == "close_dry_run"


def test_progress_confirmation_is_restored_from_append_only_ledger(tmp_path: Path) -> None:
    ledger_path = tmp_path / "execution-ledger.jsonl"
    append_execution_ledger_event(
        {
            "event_type": "c9_initial_progress_confirmed",
            "target_date": TARGET_DATE,
            "vt_symbol": VT_SYMBOL,
            "direction": "long",
            "entry_epoch": "shadow:open-1",
            "source": "stage904_c9_intraday_monitor",
        },
        path=ledger_path,
    )
    restarted_rows = read_execution_ledger(ledger_path)

    assert stage904._stage904_initial_progress_confirmed(
        restarted_rows, TARGET_DATE, VT_SYMBOL, "long", "shadow:open-1"
    )
    assert not stage904._stage904_initial_progress_confirmed(
        restarted_rows, "2026-08-09", VT_SYMBOL, "long", "shadow:open-1"
    )
    assert not stage904._stage904_initial_progress_confirmed(
        restarted_rows, TARGET_DATE, VT_SYMBOL, "long", "shadow:open-2"
    )
    restored_action = _position_action(
        _ticks((pd.Timestamp.now(), 95, None, None)),
        progress_confirmed=None,
        ledger_rows=restarted_rows,
    )
    assert restored_action["monitor_action"] == "watch_progress_hit_no_initial_stop"
    assert restored_action["initial_progress_confirmed_before"] == 1


def test_entry_epoch_stays_stable_and_uses_actual_fill_time() -> None:
    epoch, fill_at = stage904._entry_epoch_and_fill_at(
        {"trade_id": "open-1", "datetime": f"{TARGET_DATE} 09:01:00"},
        {
            "intent_id": "live-intent-1",
            "first_trade_at": f"{TARGET_DATE} 09:01:01",
            "generated_at": f"{TARGET_DATE} 09:01:03",
        },
        {"tradeid": "broker-trade-1", "datetime": f"{TARGET_DATE} 09:01:02"},
    )
    assert epoch == "shadow:open-1"
    assert fill_at == f"{TARGET_DATE} 09:01:01"


def test_broker_trade_time_beats_late_ledger_generated_time() -> None:
    _, fill_at = stage904._entry_epoch_and_fill_at(
        {"trade_id": "open-1", "datetime": f"{TARGET_DATE} 09:01:00"},
        {"intent_id": "live-intent-1", "generated_at": f"{TARGET_DATE} 09:01:08"},
        {"tradeid": "broker-trade-1", "datetime": f"{TARGET_DATE} 09:01:02"},
    )
    assert fill_at == f"{TARGET_DATE} 09:01:02"


def test_stage931_extracts_earliest_real_trade_time() -> None:
    rows = [
        {
            "vt_orderid": "CTP.order-1",
            "datetime": f"{TARGET_DATE} 09:01:03",
            "received_at": f"{TARGET_DATE} 09:01:04",
        },
        {
            "vt_orderid": "CTP.order-1",
            "datetime": f"{TARGET_DATE} 09:01:01",
            "received_at": f"{TARGET_DATE} 09:01:02",
        },
    ]
    assert stage931._trade_delta_first_fill_at(rows, 0, "CTP.order-1") == f"{TARGET_DATE} 09:01:01"


def test_corrupt_ledger_is_rejected_in_strict_monitor_mode(tmp_path: Path) -> None:
    ledger_path = tmp_path / "execution-ledger.jsonl"
    ledger_path.write_text('{"event_type":"c9_initial_progress_confirmed"', encoding="utf-8")
    with pytest.raises(RuntimeError, match="execution ledger contains invalid JSON"):
        read_execution_ledger(ledger_path)


def test_new_progress_is_persisted_and_persistence_failure_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    progress_action = _position_action(_ticks((pd.Timestamp.now(), 105, None, None)))
    ledger_path = tmp_path / "execution-ledger.jsonl"
    monkeypatch.setattr(
        stage904,
        "append_execution_ledger_event",
        lambda event: append_execution_ledger_event(event, path=ledger_path),
    )
    ledger_rows: list[dict] = []
    persisted = stage904._persist_new_initial_progress_events(
        pd.DataFrame([progress_action]), ledger_rows
    )
    assert persisted.iloc[0]["monitor_action"] == "watch_progress_hit_no_initial_stop"
    assert len(ledger_rows) == 1
    assert read_execution_ledger(ledger_path)[0]["event_type"] == "c9_initial_progress_confirmed"

    def _fail_to_persist(_: dict) -> dict:
        raise OSError("disk unavailable")

    monkeypatch.setattr(stage904, "append_execution_ledger_event", _fail_to_persist)
    blocked = stage904._persist_new_initial_progress_events(
        pd.DataFrame([progress_action]), []
    )
    assert blocked.iloc[0]["monitor_action"] == "block"
    assert "initial_progress_persistence_failed:OSError" in blocked.iloc[0]["monitor_reason"]


def _validate_large_intent(volume: float, *, contract_max_volume: float = 1000) -> dict:
    return stage905._validate_intent(
        {
            "intent_id": f"large-{int(volume)}",
            "vt_symbol": VT_SYMBOL,
            "direction": "long",
            "offset": "open",
            "limit_price": 3500,
            "planned_volume": volume,
            "source": "stage901_pending_order",
        },
        contracts=pd.DataFrame(
            [
                {
                    "vt_symbol": VT_SYMBOL,
                    "pricetick": 1,
                    "min_volume": 1,
                    "max_volume": contract_max_volume,
                    "gateway_name": "CTP",
                }
            ]
        ),
        positions=pd.DataFrame(),
        orders=pd.DataFrame(),
        stage902_summary={
            "blocking_failure_count": 0,
            "blocking_failure_count_for_reduce_close": 0,
            "allow_new_open": 1,
            "allow_reduce_close": 1,
        },
        stage260_summary={"executable_count": 1},
        mode="dry-run",
    )


@pytest.mark.parametrize("volume", [500.0, 503.0])
def test_large_intent_is_not_blocked_by_removed_twenty_lot_limit(volume: float) -> None:
    result = _validate_large_intent(volume)

    assert result["executor_status"] == "dry_run_order_request_payload_ready"
    assert json.loads(result["order_request_json"])["volume"] == volume
    assert "volume_above_phase_d_limit" not in result["executor_reason"]


def test_removed_local_limit_does_not_remove_contract_maximum() -> None:
    result = _validate_large_intent(503, contract_max_volume=500)
    assert stage905.build_phase_d_config().hard_limits.max_single_order_volume == 0
    assert result["executor_status"] == "blocked"
    assert "volume_above_contract_max" in result["executor_reason"]
