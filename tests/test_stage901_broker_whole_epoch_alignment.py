from __future__ import annotations

import os
from pathlib import Path
import sys

import pandas as pd
import pytest


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"))
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as stage901


def ledger():
    identity = {"target_date": "2026-09-07", "vt_symbol": "SH611.CZCE", "root_position_id": "root-1",
                "position_epoch_id": "epoch-1", "position_cycle_id": "cycle-0", "position_cycle_no": 0,
                "root_entry_volume": 3, "fill_price_source": "event_trade_weighted_avg", "price": 1900,
                "event_type": "filled_or_part_filled"}
    return [
        {**identity, "generated_at": "2026-09-07 09:00:00", "direction": "long", "offset": "open",
         "intent_role": "c9_initial_open", "trade_volume_delta": 3, "vt_tradeid": "CTP.open1",
         "source": "stage901_pending_order"},
        {**identity, "generated_at": "2026-09-07 09:30:00", "direction": "short", "offset": "close",
         "intent_role": "c9_initial_stop_close", "trade_volume_delta": 3, "vt_tradeid": "CTP.close1",
         "source": "stage904_c9_intraday_close"},
    ]


def aligned(monkeypatch, rows):
    monkeypatch.setattr(stage901, "read_execution_ledger", lambda: rows)
    return stage901._align_shadow_with_live_stop_fills(
        current_positions=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "end_pos": 4,
                                         "margin_exact": 28000, "date": "2026-09-07"}]),
        signal_plan=pd.DataFrame(), pending_orders=pd.DataFrame(),
        trades=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open", "date": "2026-09-07"}]),
        analysis_start=pd.Timestamp("2026-09-07"), analysis_end=pd.Timestamp("2026-09-07"),
    )


def test_full_actual_root_stop_removes_whole_shadow_epoch(monkeypatch):
    positions, _, _, _, audit = aligned(monkeypatch, ledger())
    assert positions.empty
    adjustment = audit["position_adjustments"][0]
    assert adjustment["original_volume"] == 4
    assert adjustment["new_volume"] == 0
    assert adjustment["root_actual_volume"] == 3
    assert adjustment["status"] == "whole_epoch_flat"


@pytest.mark.parametrize("case", ["no_root", "no_open_fill", "partial_stop", "wrong_epoch", "root_volume_mismatch", "unpriced", "infinite_price"])
def test_missing_or_partial_root_evidence_is_quarantined_not_subtracted(monkeypatch, case):
    rows = ledger()
    if case == "no_root":
        rows[-1].pop("root_position_id")
    elif case == "no_open_fill":
        rows = rows[-1:]
    elif case == "partial_stop":
        rows[-1]["trade_volume_delta"] = 1
    elif case == "wrong_epoch":
        rows[-1]["position_epoch_id"] = "other"
    elif case == "root_volume_mismatch":
        rows[-1]["root_entry_volume"] = 4
    elif case == "infinite_price":
        rows[-1]["price"] = float("inf")
    else:
        rows[-1]["fill_price_source"] = "order_traded_without_trade_price"
    positions, _, _, _, audit = aligned(monkeypatch, rows)
    assert positions.empty
    assert audit["position_adjustments"][0]["status"] == "quarantined"
    assert audit["position_adjustments"][0]["blocker"]


def test_split_stop_fills_are_aggregated_and_duplicate_trade_is_not_recounted(monkeypatch):
    rows = ledger()
    rows[-1]["trade_volume_delta"] = 1
    rows.append({**rows[-1], "trade_volume_delta": 2, "vt_tradeid": "CTP.close2"})
    rows.append(dict(rows[-1]))
    positions, _, _, _, audit = aligned(monkeypatch, rows)
    assert positions.empty
    assert audit["position_adjustments"][0]["status"] == "whole_epoch_flat"


def test_conflicting_duplicate_trade_is_quarantined(monkeypatch):
    rows = ledger()
    rows.append({**rows[-1], "trade_volume_delta": 1})
    positions, _, _, _, audit = aligned(monkeypatch, rows)
    assert positions.empty
    assert audit["position_adjustments"][0]["status"] == "quarantined"


@pytest.mark.parametrize("has_shadow_position", [True, False])
def test_quarantine_blocks_all_symbol_orders_without_claiming_flat(monkeypatch, has_shadow_position):
    rows = ledger()
    rows[-1].pop("root_position_id")
    original = [dict(row) for row in rows]
    monkeypatch.setattr(stage901, "read_execution_ledger", lambda: rows)
    candidates = pd.DataFrame([
        {"vt_symbol": symbol, "direction": direction, "offset": offset, "volume": 4}
        for symbol in ("SH611.CZCE", "sh611.czce", "MA609.CZCE")
        for direction in ("long", "short") for offset in ("open", "close")
    ])
    positions, signals, pending, _, audit = stage901._align_shadow_with_live_stop_fills(
        current_positions=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "end_pos": 4}])
        if has_shadow_position else pd.DataFrame(), signal_plan=candidates, pending_orders=candidates,
        trades=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open", "date": "2026-09-07"}]),
        analysis_start=pd.Timestamp("2026-09-07"), analysis_end=pd.Timestamp("2026-09-07"),
    )
    assert positions.empty
    assert set(signals.vt_symbol) == set(pending.vt_symbol) == {"MA609.CZCE"}
    assert audit["quarantined_symbols"] == ["SH611.CZCE"]
    assert audit["blockers"]
    assert audit["signal_plan_suppressed_count"] == audit["pending_order_suppressed_count"] == 8
    assert all(row["suppress_reason"] == "stage901_root_epoch_quarantined_blocks_all_symbol_signals"
               for row in audit["suppressed_rows"])
    assert not has_shadow_position or audit["position_adjustments"][0]["new_volume"] is None
    assert rows == original


@pytest.mark.parametrize("second_stop", [False, True])
def test_retry_epoch_keeps_whole_shadow_until_complete_actual_retry_stop(monkeypatch, second_stop):
    rows = ledger()
    rows.append({**rows[0], "source": "stage904_c9_intraday_retry_open", "intent_role": "c9_retry_open",
                 "trade_volume_delta": 2, "position_cycle_id": "cycle-1", "position_cycle_no": 1,
                 "vt_tradeid": "CTP.retry1", "generated_at": "2026-09-07 10:00:00"})
    if second_stop:
        rows.append({**rows[1], "trade_volume_delta": 2, "position_cycle_id": "cycle-1", "position_cycle_no": 1,
                     "vt_tradeid": "CTP.retry-close1", "generated_at": "2026-09-07 10:30:00"})
    positions, _, _, _, audit = aligned(monkeypatch, rows)
    if second_stop:
        assert positions.empty
        assert audit["position_adjustments"][0]["status"] == "whole_epoch_flat"
    else:
        assert positions.iloc[0]["end_pos"] == 4
        assert audit["position_adjustments"] == []
