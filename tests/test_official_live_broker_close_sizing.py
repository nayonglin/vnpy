from __future__ import annotations

import copy
from datetime import datetime
import importlib
import importlib.util
import os
from pathlib import Path
import sys

import pandas as pd
import pytest


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"))


def close_inputs():
    pending = {"vt_symbol": "SH611.CZCE", "direction": "short", "offset": "close",
               "volume": 4, "traded": 0, "price": 1948, "vt_orderid": "BACKTEST.1",
               "cohort_id": "c" * 64, "target_date": "2026-09-07"}
    return {
        "intent": {"vt_symbol": "SH611.CZCE", "direction": "short", "offset": "close", "planned_volume": 4},
        "pending_orders": pd.DataFrame([pending]),
        "current_positions": pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long",
                                            "date": "2026-09-07", "end_pos": 4}]),
        "official_summary": {"analysis_end": "2026-09-07", "cohort_id": "c" * 64,
                             "pending_orders": [pending.copy()], "live_stop_alignment": {}},
        "broker_positions": pd.DataFrame([{"vt_symbol": "SH611.CZCE", "direction": "long", "volume": 3, "frozen": 0}]),
        "broker_trade_rows": [],
        "execution_ledger_rows": [{
            "event_type": "filled_or_part_filled", "source": "stage901_pending_order", "intent_role": "c9_initial_open",
            "vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open", "trade_volume_delta": 3,
            "root_position_id": "root-1", "position_epoch_id": "epoch-1", "vt_tradeid": "CTP.open1",
            "fill_price_source": "event_trade_weighted_avg", "price": 1948,
        }],
    }


def size(**inputs):
    assert importlib.util.find_spec("qmt_roll_official_live_broker_close_sizing") is not None, "full-close helper missing"
    module = importlib.import_module("qmt_roll_official_live_broker_close_sizing")
    return module.size_full_close_intent(**inputs)


def test_shadow_four_full_close_uses_real_three_without_mutating_inputs():
    inputs = close_inputs()
    original = copy.deepcopy(inputs)
    decision = size(**inputs)
    assert decision["volume"] == 3
    assert decision["shadow_volume"] == decision["shadow_position_volume"] == 4
    assert decision["cohort_id"] == "c" * 64
    assert decision["mode"] == "full_close"
    for key in inputs:
        if isinstance(inputs[key], pd.DataFrame):
            pd.testing.assert_frame_equal(inputs[key], original[key])
        else:
            assert inputs[key] == original[key]


@pytest.mark.parametrize("pending,shadow", [(2, 4), (1, 3), (5, 4)])
def test_partial_and_oversized_shadow_close_are_never_inferred(pending, shadow):
    inputs = close_inputs()
    inputs["pending_orders"].loc[0, "volume"] = pending
    inputs["official_summary"]["pending_orders"][0]["volume"] = pending
    inputs["intent"]["planned_volume"] = pending
    inputs["current_positions"].loc[0, "end_pos"] = shadow
    with pytest.raises(ValueError, match="full_close"):
        size(**inputs)


def test_short_full_close_and_today_yesterday_slices_use_gross_quantity():
    inputs = close_inputs()
    inputs["intent"]["direction"] = "long"
    inputs["pending_orders"].loc[0, "direction"] = "long"
    inputs["official_summary"]["pending_orders"][0]["direction"] = "long"
    inputs["current_positions"].loc[0, ["direction", "end_pos"]] = ["short", -4]
    inputs["broker_positions"] = pd.DataFrame([
        {"vt_symbol": "SH611.CZCE", "direction": "short", "volume": 1, "frozen": 0},
        {"vt_symbol": "SH611.CZCE", "direction": "short", "volume": 2, "frozen": 0},
    ])
    inputs["execution_ledger_rows"][0]["direction"] = "short"
    assert size(**inputs)["volume"] == 3


@pytest.mark.parametrize("mutation", ["cohort", "date", "summary_pending", "duplicate_pending", "duplicate_position",
                                      "missing_position", "wrong_sign", "traded", "aligned", "quarantined"])
def test_ambiguous_or_mixed_signal_evidence_fails_closed(mutation):
    inputs = close_inputs()
    if mutation == "cohort":
        inputs["pending_orders"].loc[0, "cohort_id"] = "d" * 64
    elif mutation == "date":
        inputs["current_positions"].loc[0, "date"] = "2026-09-06"
    elif mutation == "summary_pending":
        inputs["official_summary"]["pending_orders"] = []
    elif mutation == "duplicate_pending":
        inputs["pending_orders"] = pd.concat([inputs["pending_orders"]] * 2)
    elif mutation == "duplicate_position":
        inputs["current_positions"] = pd.concat([inputs["current_positions"]] * 2)
    elif mutation == "missing_position":
        inputs["current_positions"] = pd.DataFrame()
    elif mutation == "wrong_sign":
        inputs["current_positions"].loc[0, "end_pos"] = -4
    elif mutation == "traded":
        inputs["pending_orders"].loc[0, "traded"] = 1
    elif mutation == "aligned":
        inputs["current_positions"].loc[0, "live_stop_alignment_delta_volume"] = -1
    else:
        inputs["official_summary"]["live_stop_alignment"] = {"position_adjustments": [
            {"vt_symbol": "SH611.CZCE", "direction": "long", "status": "quarantined", "blocker": "missing_root"}]}
    with pytest.raises(ValueError):
        size(**inputs)


@pytest.mark.parametrize("field,value", [("volume", -1), ("volume", 1.5), ("volume", float("inf")),
                                        ("volume", True), ("frozen", 1), ("frozen", float("nan"))])
def test_invalid_or_frozen_broker_positions_are_not_resized(field, value):
    inputs = close_inputs()
    inputs["broker_positions"][field] = pd.Series([value], dtype=object)
    with pytest.raises(ValueError):
        size(**inputs)


def test_flat_broker_is_explicit_zero_not_shadow_quantity():
    inputs = close_inputs()
    inputs["broker_positions"] = pd.DataFrame()
    assert size(**inputs)["volume"] == 0


def test_stage260_uses_same_full_close_result_before_old_quantity_gate():
    import run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate as stage260
    from qmt_roll_official_execution_profile import C9_15W_PROFILE
    inputs = close_inputs()
    summary = {**inputs["official_summary"], "execution_profile": C9_15W_PROFILE.profile_key,
               "official_live_version": C9_15W_PROFILE.official_version, "capital": C9_15W_PROFILE.capital,
               "capital_label": C9_15W_PROFILE.capital_label,
               "risk_snapshot": {"risk_level": "normal", "allow_real_new_orders": 1}}
    from unittest.mock import patch
    with patch.object(stage260, "read_execution_ledger", return_value=inputs["execution_ledger_rows"], create=True):
        result = stage260.run_daily_execution_gate(
        C9_15W_PROFILE, official_summary=summary, pending_orders=inputs["pending_orders"],
        current_positions=inputs["current_positions"], signal_plan=pd.DataFrame(),
        readonly_summary={"status": "readonly_snapshots_received", "generated_at": "2026-09-08T09:00:00+08:00",
                          "broker_snapshot": {"position_snapshot_state": "positions_received"}},
        positions=inputs["broker_positions"], orders=pd.DataFrame(),
        broker_trade_rows=inputs["broker_trade_rows"],
        now=datetime.fromisoformat("2026-09-08T09:00:10+08:00"), write_outputs=False,
    )
    row = result.decisions.iloc[0]
    assert row["execution_action"] == "simnow_executable"
    assert row["planned_volume"] == 3
    assert row["broker_close_sizing"]["shadow_volume"] == 4


def test_resizing_requires_unique_owned_epoch_not_just_broker_gross():
    inputs = close_inputs()
    inputs["execution_ledger_rows"] = None
    with pytest.raises(ValueError, match="owned"):
        size(**inputs)


def test_equal_quantity_compatibility_still_requires_full_close_proof():
    inputs = close_inputs()
    inputs["execution_ledger_rows"] = None
    inputs["broker_positions"].loc[0, "volume"] = 4
    assert size(**inputs)["volume"] == 4
    inputs["pending_orders"].loc[0, "volume"] = 2
    inputs["official_summary"]["pending_orders"][0]["volume"] = 2
    with pytest.raises(ValueError):
        size(**inputs)


def test_larger_real_position_does_not_swallow_unowned_addition():
    inputs = close_inputs()
    inputs["broker_positions"].loc[0, "volume"] = 5
    with pytest.raises(ValueError, match="owned"):
        size(**inputs)
    inputs["execution_ledger_rows"][0]["trade_volume_delta"] = 5
    result = size(**inputs)
    assert result["volume"] == 5
    assert result["root_position_id"] == "root-1"
    assert result["position_epoch_id"] == "epoch-1"
    assert result["owned_net_volume"] == 5


@pytest.mark.parametrize("case", ["two_epochs", "partial_closed", "unknown_fill_identity", "unpriced", "duplicate_conflict"])
def test_owned_net_quantity_and_fill_identity_must_be_unambiguous(case):
    inputs = close_inputs()
    rows = inputs["execution_ledger_rows"]
    if case == "two_epochs":
        rows[0]["trade_volume_delta"] = 1
        rows.append({**rows[0], "position_epoch_id": "epoch-2", "vt_tradeid": "CTP.open2", "trade_volume_delta": 2})
    elif case == "partial_closed":
        rows.append({**rows[0], "direction": "short", "offset": "close", "vt_tradeid": "CTP.close1", "trade_volume_delta": 1})
    elif case == "unknown_fill_identity":
        rows[0].pop("vt_tradeid")
    elif case == "unpriced":
        rows[0]["fill_price_source"] = "order_traded_without_trade_price"
    else:
        rows.append({**rows[0], "trade_volume_delta": 1})
    with pytest.raises(ValueError, match="owned"):
        size(**inputs)


def test_owned_net_uses_linked_payload_and_deduplicates_exact_fills():
    inputs = close_inputs()
    fill = inputs["execution_ledger_rows"][0]
    payload = {key: fill.pop(key) for key in ("source", "intent_role", "vt_symbol", "direction", "offset", "root_position_id", "position_epoch_id")}
    fill["intent_fingerprint"] = "fingerprint-1"
    inputs["execution_ledger_rows"] = [
        {"intent_fingerprint": "fingerprint-1", "intent_payload": payload}, fill, dict(fill),
    ]
    assert size(**inputs)["owned_net_volume"] == 3


def validate_owned(inputs):
    module = importlib.import_module("qmt_roll_official_live_broker_close_sizing")
    return module.validate_owned_full_close(
        execution_ledger_rows=inputs["execution_ledger_rows"], vt_symbol="SH611.CZCE",
        position_direction="long", broker_gross_volume=3, broker_trade_rows=inputs["broker_trade_rows"],
    )


def broker_trade(**changes):
    return {"symbol": "SH611", "exchange": "CZCE", "vt_tradeid": "CTP.open1", "tradeid": "open1",
            "direction": "long", "offset": "open", "volume": 3, "price": 1948, **changes}


def test_exported_owned_validator_covers_normalized_final_query_rows():
    inputs = close_inputs()
    inputs["broker_trade_rows"] = [broker_trade(), broker_trade()]
    result = validate_owned(inputs)
    assert result["position_epoch_id"] == "epoch-1"
    assert result["broker_trade_coverage_count"] == 1


@pytest.mark.parametrize("event_type", ["filled_or_part_filled", "broker_trade_callback_unbound", "broker_trade_callback_unidentified"])
def test_unowned_same_symbol_ledger_trade_is_never_skipped(event_type):
    inputs = close_inputs()
    inputs["execution_ledger_rows"].append({**inputs["execution_ledger_rows"][0], "event_type": event_type,
                                          "source": "manual", "direction": "short", "offset": "close",
                                          "vt_tradeid": "CTP.manual-close"})
    with pytest.raises(ValueError, match="owned"):
        size(**inputs)


def test_manual_close_then_equal_manual_reopen_cannot_pass_owned_net_equals_gross():
    inputs = close_inputs()
    inputs["broker_trade_rows"] = [broker_trade(tradeid="manual-close", vt_tradeid="CTP.manual-close",
                                               direction="short", offset="close"),
                                    broker_trade(tradeid="manual-reopen", vt_tradeid="CTP.manual-reopen")]
    with pytest.raises(ValueError, match="owned.*coverage"):
        size(**inputs)


@pytest.mark.parametrize("change", [{"price": 1949}, {"volume": 2}, {"direction": "short"},
                                    {"offset": "close"}, {"tradeid": "other"},
                                    {"tradeid": "", "vt_tradeid": ""}])
def test_query_trade_must_match_ledger_identity_and_economics(change):
    inputs = close_inputs()
    inputs["broker_trade_rows"] = [broker_trade(**change)]
    with pytest.raises(ValueError, match="owned"):
        size(**inputs)


def test_absent_trade_query_is_not_an_explicit_complete_empty_query():
    inputs = close_inputs()
    inputs["broker_trade_rows"] = None
    with pytest.raises(ValueError, match="owned.*trade"):
        size(**inputs)


def test_quarantined_symbol_without_position_adjustment_still_blocks_close():
    inputs = close_inputs()
    inputs["official_summary"]["live_stop_alignment"] = {"quarantined_symbols": ["sh611.czce"]}
    with pytest.raises(ValueError, match="quarantined"):
        size(**inputs)


def test_draft_can_explicitly_defer_query_coverage_but_audit_requires_final_guard():
    inputs = close_inputs()
    inputs["broker_trade_rows"] = None
    result = size(**inputs, require_broker_trade_coverage=False)
    assert result["volume"] == 3
    assert result["position_epoch_id"] == "epoch-1"
    assert result["final_broker_trade_coverage_required"] is True
    assert result["broker_trade_coverage_verified"] is False
    with pytest.raises(ValueError, match="owned.*trade"):
        validate_owned(inputs)


def test_draft_cannot_defer_owned_ledger_or_unbound_trade_checks():
    inputs = close_inputs()
    inputs["broker_trade_rows"] = None
    inputs["execution_ledger_rows"].append({**inputs["execution_ledger_rows"][0], "source": "manual",
                                          "vt_tradeid": "CTP.manual"})
    with pytest.raises(ValueError, match="owned"):
        size(**inputs, require_broker_trade_coverage=False)
    inputs["execution_ledger_rows"] = None
    with pytest.raises(ValueError, match="owned"):
        size(**inputs, require_broker_trade_coverage=False)
