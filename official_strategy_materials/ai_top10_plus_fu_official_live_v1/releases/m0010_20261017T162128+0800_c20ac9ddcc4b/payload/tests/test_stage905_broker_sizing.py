from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from dataclasses import replace
from types import SimpleNamespace

import pandas as pd
import pytest


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))

import run_qmt_roll_stage905_official_live_executor_dry_run as stage905
from test_official_live_broker_sizing import account, intent, policy, signal
from test_stage905_c9_cycle_intents import _FakeClock


def risk_frame():
    return pd.DataFrame([{**signal(), "date": "2026-09-07", "contract_vt_symbol": "SH611.CZCE", "direction": "long"}])


def test_stage905_recalculates_before_payload_hash_and_keeps_shadow_volume():
    row = {**intent(), "intent_id": "pending-sh", "target_date": "2026-09-07",
           "source": "stage901_pending_order", "root_entry_volume": 4}
    original = row.copy()
    sized = stage905._size_c9_open_intent(
        row, entry_risk=risk_frame(), broker_account=account(equity=100000, available=100000, margin=0, product_margin={}),
        policy=policy(), pricetick=1,
    )
    assert row == original
    assert sized["planned_volume"] == 3
    assert sized["root_entry_volume"] == 3
    assert sized["shadow_planned_volume"] == 4
    assert sized["intent_id"] == "pending-sh"
    checked = stage905._validate_intent(
        sized, contracts=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "pricetick": 1, "min_volume": 1, "max_volume": 100}]),
        positions=pd.DataFrame(), orders=pd.DataFrame(),
        stage902_summary={"blocking_failure_count": 0, "allow_new_open": 1},
        stage260_summary={"executable_count": 1}, stage904_summary={}, mode="dry-run",
    )
    assert checked["executor_status"] == "dry_run_order_request_payload_ready"
    payload = json.loads(checked["order_request_json"])
    assert payload["volume"] == 3
    assert payload["broker_sizing"]["volume"] == 3
    assert json.loads(checked["spool_payload_json"])["planned_volume"] == 3
    assert hashlib.sha256(checked["spool_payload_json"].encode()).hexdigest() == checked["payload_sha256"]


@pytest.mark.parametrize("frame", [pd.DataFrame(), pd.concat([risk_frame(), risk_frame()]), risk_frame().assign(date="2026-09-04")])
def test_missing_ambiguous_or_other_day_risk_fails_closed(frame):
    with pytest.raises(ValueError, match="entry_risk"):
        stage905._size_c9_open_intent(
            {**intent(), "target_date": "2026-09-07"}, entry_risk=frame,
            broker_account=account(), policy=policy(), pricetick=1,
        )


def test_size_error_produces_no_order_payload():
    checked = stage905._validate_intent(
        {**intent(), "intent_id": "bad", "source": "stage901_pending_order", "broker_sizing_error": "broker_sizing_account_missing"},
        contracts=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "pricetick": 1}]),
        positions=pd.DataFrame(), orders=pd.DataFrame(),
        stage902_summary={"blocking_failure_count": 0, "allow_new_open": 1},
        stage260_summary={"executable_count": 1}, stage904_summary={}, mode="dry-run",
    )
    assert checked["executor_status"] == "blocked"
    assert json.loads(checked["order_request_json"]) == {}


def test_nan_risk_switch_is_not_deleted_into_disabled_default():
    with pytest.raises(ValueError, match="env_gate_enabled"):
        stage905._size_c9_open_intent(
            {**intent(), "target_date": "2026-09-07"},
            entry_risk=risk_frame().assign(env_gate_enabled=float("nan"), env_gate_weight=0),
            broker_account=account(), policy=policy(), pricetick=1,
        )


def test_retry_sizing_uses_final_protective_price_and_preserves_root_risk_cap():
    retry = {**intent(), "target_date": "2026-09-07", "direction": "short",
             "intent_role": "c9_retry_open_once", "source": "stage904_c9_intraday_retry_open",
             "limit_price": 1245.5, "root_entry_price": 1245.5, "root_initial_stop_price": 1257.5,
             "root_entry_volume": 2, "planned_volume": 2, "live_bid_price_1": 1243.5, "live_ask_price_1": 1244}
    frame = risk_frame().assign(direction="short", stop_price=1257.5, size=60)
    result = stage905._size_c9_open_intent(retry, entry_risk=frame, broker_account=account(), policy=policy(), pricetick=0.5)
    expected_price, _ = stage905._protective_close_price(retry, "short", 0.5, 1245.5)
    assert result["broker_sizing"]["entry_price"] == expected_price
    assert result["broker_sizing"]["actual_risk"] <= 1440


def test_snapshot_time_requires_fresh_timezone_aware_generation():
    now = datetime.fromisoformat("2026-09-08T09:01:00+08:00")
    stage905._check_broker_sizing_snapshot(account(), now=now)
    for generated_at in ["2026-09-08T08:00:00+08:00", "2026-09-08T09:02:00+08:00", "2026-09-08 09:00:00", ""]:
        with pytest.raises(ValueError):
            stage905._check_broker_sizing_snapshot(account(generated_at=generated_at), now=now)


def test_fresh_snapshot_must_also_start_after_previous_reconciliation():
    now = datetime.fromisoformat("2026-09-08T09:01:00+08:00")
    cutoff = int(datetime.fromisoformat("2026-09-08T09:00:10+08:00").timestamp() * 1e9)
    with pytest.raises(ValueError, match="precedes_reconciliation"):
        stage905._check_broker_sizing_snapshot(
            account(generated_at="2026-09-08T09:00:30+08:00", query_started_at="2026-09-08T09:00:00+08:00"),
            now=now, not_before_epoch_ns=cutoff,
        )
    stage905._check_broker_sizing_snapshot(
        account(generated_at="2026-09-08T09:00:30+08:00", query_started_at="2026-09-08T09:00:20+08:00"),
        now=now, not_before_epoch_ns=cutoff,
    )


def executor_inputs(*, funds=True, pending=None):
    return stage905.Stage905SnapshotInputs(
        pending_orders=pd.DataFrame(pending or [{"vt_symbol": "SH611.CZCE", "direction": "long",
                                              "offset": "open", "volume": 4, "price": 1948, "stop_price": 1933}]),
        contracts=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "size": 30, "pricetick": 1, "min_volume": 1, "max_volume": 100}]),
        positions=pd.DataFrame(), orders=pd.DataFrame(), execution_ledger_rows=[],
        stage902_summary={"blocking_failure_count": 0, "allow_new_open": 1, "allow_reduce_close": 1},
        stage260_summary={"executable_count": 1}, entry_risk=risk_frame(), sizing_policy=policy(),
        broker_account=account(equity=100000, available=100000, margin=0, product_margin={}) if funds else None,
    )


def execute(**kwargs):
    return stage905.run_executor_dry_run(
        target_date="2026-09-07", stage904_actions=pd.DataFrame(),
        stage904_summary={"target_date": "2026-09-07", "action_count": 0, "close_dry_run_count": 0,
                          "retry_open_dry_run_count": 0, "retry_watch_count": 0, "blocked_count": 0,
                          "order_api_called_count": 0, "durable_batch_cursor": {}},
        clock=_FakeClock(epoch_ns=int(datetime.fromisoformat("2026-09-08T09:01:00+08:00").timestamp() * 1e9), monotonic_ns=1),
        write_compat_outputs=False, **kwargs,
    )


def test_real_executor_sizes_and_missing_funds_cannot_fallback():
    result = execute(snapshots=executor_inputs())
    assert result.summary["ready_count"] == 1
    assert result.intents.iloc[0]["planned_volume"] == 3
    missing = execute(snapshots=executor_inputs(funds=False))
    assert missing.summary["ready_count"] == 0
    assert missing.summary["blocked_count"] == 1


@pytest.mark.parametrize("size", [None, 10, 0])
def test_executor_rejects_missing_or_mismatched_broker_contract_size(size):
    inputs = executor_inputs()
    result = execute(snapshots=replace(inputs, contracts=inputs.contracts.assign(size=size)))
    assert result.summary["ready_count"] == 0
    assert "broker_sizing_contract_size_mismatch" in result.intents.iloc[0]["broker_sizing_error"]


def test_existing_immutable_open_is_skipped_before_account_refresh():
    first = execute(snapshots=executor_inputs())
    second = execute(snapshots=executor_inputs(funds=False), existing_open_intent_ids=[first.intents.iloc[0]["intent_id"]])
    assert second.intents.empty


@pytest.mark.parametrize("released", [True, False])
def test_sent_open_requires_budget_release_proof_from_the_sizing_snapshot(monkeypatch, released):
    import qmt_roll_official_live_broker_open_queue as queue
    inputs = executor_inputs()
    funds = {**inputs.broker_account, "positions": [], "orders": [], "trades": []}
    calls = []
    def verify(**kwargs):
        calls.append(kwargs)
        return {"budget_released": released, "blocker": "test_unreconciled_sent"}
    monkeypatch.setattr(queue, "evaluate_sent_open_budget_release", verify)
    result = execute(snapshots=replace(inputs, broker_account=funds), sent_open_intents=[{"intent_id": "older"}])
    assert result.summary["ready_count"] == int(released)
    assert calls[0]["broker_snapshot"]["positions"] == []
    assert calls[0]["execution_ledger_rows"] == []


def test_account_budget_is_not_reused_for_two_ready_opens():
    pending = [{"vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open",
                "volume": 4, "price": 1948, "stop_price": 1933, "orderid": order_id}
               for order_id in ("first", "second")]
    pending[1]["vt_symbol"] = "SA609.CZCE"
    result = execute(snapshots=executor_inputs(pending=pending))
    assert result.summary["ready_count"] == 1
    assert result.summary["blocked_count"] == 1
    assert "broker_sizing_wait_prior_open" in result.intents.iloc[1]["broker_sizing_error"]


def test_production_path_validates_positions_from_same_account_generation(monkeypatch):
    inputs = executor_inputs()
    snapshot = SimpleNamespace(pending_orders=inputs.pending_orders, entry_risk=inputs.entry_risk,
                               current_positions=pd.DataFrame(), official_summary={})
    monkeypatch.setattr(stage905, "load_validated_artifact_snapshot", lambda profile: object())
    monkeypatch.setattr(stage905, "materialize_validated_artifact_snapshot", lambda profile, snapshot_arg: snapshot)
    monkeypatch.setattr(stage905, "_read_csv_maybe", lambda path: inputs.contracts if path == stage905.READONLY_CONTRACTS_PATH else pd.DataFrame())
    monkeypatch.setattr(stage905, "_read_json", lambda path: {"broker_query_bundle": None}
                        if path == stage905.READONLY_SUMMARY_PATH else {**inputs.stage902_summary, **inputs.stage260_summary})
    monkeypatch.setattr(stage905, "read_execution_ledger", lambda: [])
    monkeypatch.setattr(stage905, "official_sizing_policy", policy)
    import qmt_roll_official_live_broker_account_snapshot as loader
    fresh = {**inputs.broker_account, "positions": [{"vt_symbol": "SH611.CZCE", "direction": "long", "volume": 3}],
             "orders": [], "trades": []}
    monkeypatch.setattr(loader, "load_broker_account_snapshot", lambda *args, **kwargs: fresh.copy())
    result = execute()
    assert result.summary["ready_count"] == 0
    assert result.summary["skipped_count"] == 1
    assert result.intents.iloc[0]["executor_status"] == "skipped_existing_broker_position"


def test_daily_full_close_uses_real_quantity_without_requiring_account_funds(monkeypatch):
    import qmt_roll_official_live_broker_close_sizing as close_sizing
    from test_official_live_broker_close_sizing import close_inputs
    inputs = close_inputs()
    snapshots = executor_inputs(funds=False)
    snapshots = replace(
        snapshots, pending_orders=inputs["pending_orders"], positions=inputs["broker_positions"],
        current_positions=inputs["current_positions"], official_summary=inputs["official_summary"],
        broker_account_fingerprint="a" * 64,
    )
    decision = {
        "mode": "full_close",
        "volume": 3,
        "shadow_volume": 4,
        "cohort_id": "c" * 64,
        "root_position_id": "root-1",
        "position_cycle_id": "root-1:cycle0",
        "position_cycle_no": 0,
        "position_epoch_id": "epoch-1",
        "state_generation": "epoch-1:0",
    }
    calls = []
    def verified_close(**kwargs):
        calls.append(kwargs)
        return decision
    monkeypatch.setattr(close_sizing, "size_full_close_intent", verified_close)
    result = execute(snapshots=snapshots)
    assert result.summary["ready_count"] == 1
    assert result.intents.iloc[0]["planned_volume"] == 3
    assert result.intents.iloc[0]["intent_role"] == "c9_full_position_close"
    assert result.intents.iloc[0]["root_position_id"] == "root-1"
    assert json.loads(result.intents.iloc[0]["order_request_json"])["broker_close_sizing"] == decision
    assert len(calls) == 1


@pytest.mark.parametrize("owned", [True, False])
def test_full_close_real_helper_preserves_owned_epoch_or_blocks(owned):
    from test_official_live_broker_close_sizing import close_inputs
    inputs = close_inputs()
    snapshots = replace(
        executor_inputs(funds=False), pending_orders=inputs["pending_orders"], positions=inputs["broker_positions"],
        current_positions=inputs["current_positions"], official_summary=inputs["official_summary"],
        broker_account_fingerprint="a" * 64,
        execution_ledger_rows=inputs["execution_ledger_rows"] if owned else [],
    )
    result = execute(snapshots=snapshots)
    assert result.summary["ready_count"] == int(owned), result.intents.iloc[0]["executor_reason"]
    if owned:
        audit = json.loads(result.intents.iloc[0]["order_request_json"])["broker_close_sizing"]
        assert audit["volume"] == 3
        assert audit["position_epoch_id"] == "epoch-1"
        assert audit["account_fingerprint"] == "a" * 64
