from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))

import qmt_roll_official_live_broker_sizing as sizing
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931
import test_stage931_ctp_readiness as fixtures


NOW = 1788832800.0
GENERATED_AT = "2026-09-08T10:00:00+08:00"
FINGERPRINT = hashlib.sha256(b"fake-broker\0fake-user").hexdigest()


def sizing_row():
    inputs = {
        "intent": {
            "vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open",
            "planned_volume": 4, "limit_price": 1948.0,
            "strategy_initial_stop_price": 1933.0, "intent_role": "c9_initial_open",
        },
        "signal": {
            "risk_ratio": 0.018, "risk_multiplier": 1.0,
            "directional_30d_risk_boost_multiplier": 1.0, "margin_ratio": 0.12,
            "size": 30, "stop_price": 1933.0, "entry_price": 1948.0,
            "risk_cluster_cap_enabled": 1, "risk_cluster_cap_ratio": 0.25,
            "risk_cluster_name": "SH.CZCE",
        },
        "account": {
            "equity": 186670.0, "available": 140110.0, "margin": 46560.0,
            "frozen": 0.0, "product_margin": {"MA.CZCE": 46560.0},
            "generation_uuid": "sizing-generation", "account_fingerprint": FINGERPRINT,
            "generated_at": GENERATED_AT,
        },
        "policy": {
            "max_capital_usage_ratio": 0.9, "max_single_trade_capital_usage_ratio": 0.7,
            "min_risk_per_trade": 1000.0, "max_risk_per_trade": 50000000.0,
            "min_position_size": 1, "max_position_size": 50000,
            "max_concurrent_positions": 4, "sizing_equity_cap": 1000000.0,
        },
        "pricetick": 1.0,
    }
    audit = sizing.size_open_intent(**inputs)
    payload = {
        **inputs["intent"], "volume": audit["volume"], "price": 1948.0,
        "symbol": "SH611", "exchange": "CZCE", "execution_profile": "c9-15w",
        "broker_sizing": copy.deepcopy(audit), "broker_sizing_inputs": copy.deepcopy(inputs),
    }
    return {
        **payload, "planned_volume": audit["volume"],
        "order_request": copy.deepcopy(payload), "order_request_json": json.dumps(payload),
        "order_request_volume": audit["volume"],
    }


def raw_account(**changes):
    return {
        "BrokerID": "fake-broker", "AccountID": "fake-user", "CurrencyID": "CNY",
        "Balance": 186670.0, "Available": 140110.0, "CurrMargin": 46560.0,
        "FrozenMargin": 0.0, "FrozenCash": 0.0, "FrozenCommission": 0.0,
        **changes,
    }


def raw_position(**changes):
    return {
        "BrokerID": "fake-broker", "InvestorID": "fake-user",
        "InstrumentID": "MA609", "ExchangeID": "CZCE", "PosiDirection": "2",
        "Position": 2, "TodayPosition": 2, "YdPosition": 0,
        "ShortFrozen": 0, "LongFrozen": 0, "UseMargin": 46560.0,
        **changes,
    }


def request(volume=4, price=1948.0, **changes):
    return stage931.OrderRequest(**{
        "symbol": "SH611", "exchange": stage931.Exchange.CZCE,
        "direction": stage931.Direction.LONG, "type": stage931.OrderType.FAK,
        "volume": volume, "price": price, "offset": stage931.Offset.OPEN,
        "reference": "test-broker-sizing", **changes,
    })


def gate(monkeypatch, *, row=None, requests=None, account=None, positions=None,
         maximum=99, age=0, missing_position_epoch=False, event_during_query=False,
         contract_changes=None, missing_contract=False):
    assert "intent_row" in inspect.signature(stage931._final_open_funds_margin_gate).parameters
    monkeypatch.setattr(stage931.time, "time", lambda: NOW + age)
    clock = fixtures.FakeClock()
    rows = fixtures.Stage931CtpReadinessTests._funds_rows()
    if event_during_query:
        clock.hook = lambda: rows["_execution_event_ingress_counts"].update(trade=1)
    raw_positions = [raw_position()] if positions is None else positions
    rows["positions"] = [stage931._raw_ctp_position_row(
        item, reqid=99, vt_symbol_by_instrument={},
    ) for item in raw_positions]
    if not missing_position_epoch:
        rows["_position_query_epoch"] = {
            "active_reqid": None, "complete_reqid": 99, "strict_identity": True,
            "identity_blockers": [], "expected_broker_id": "fake-broker",
            "expected_investor_id": "fake-user", "authoritative_position_rows": len(raw_positions),
            "broker_sizing_raw_positions": copy.deepcopy(raw_positions),
        }
    td_api = fixtures.FakeFundsTdApi(
        clock, account_data=account or raw_account(), max_data={"MaxVolume": maximum},
    )
    td_api.contract = None if missing_contract else SimpleNamespace(**{
        "vt_symbol": "SH611.CZCE", "gateway_name": "CTP", "size": 30,
        **(contract_changes or {}),
    })
    td_api.main_engine = SimpleNamespace(get_contract=lambda _symbol: td_api.contract)
    intent_row = sizing_row() if row is None else row
    physical = [request()] if requests is None else requests
    before = copy.deepcopy((intent_row, physical))
    with stage931._instrument_ctp_readiness_callbacks(fixtures.FakeFundsTdApi, rows):
        result = stage931._final_open_funds_margin_gate(
            td_api, rows, physical, intent_row=intent_row, max_wait_seconds=5.0,
            monotonic=clock.monotonic, sleeper=clock.sleep,
            main_engine=td_api.main_engine,
        )
    assert before == (intent_row, physical)
    assert td_api.send_order_api_called_count == td_api.cancel_order_api_called_count == 0
    return result, td_api, rows, physical


def test_fresh_c9_sizing_passes_without_mutating_signed_request(monkeypatch):
    result, td_api, rows, physical = gate(monkeypatch)
    assert result["confirmed"], result["blockers"]
    assert result["broker_sizing_check"]["requested_volume"] == 4
    assert result["broker_sizing_check"]["actual_risk"] == 1800
    assert stage931._open_funds_gate_consistency_blockers(
        td_api, rows, physical, result, main_engine=td_api.main_engine,
    ) == []


@pytest.mark.parametrize("changes", [
    {"size": 60}, {"size": 15}, {"size": 0}, {"size": True},
    {"size": float("nan")}, {"size": float("inf")}, {"size": None},
    {"gateway_name": "OTHER"}, {"vt_symbol": "MA609.CZCE"},
])
def test_actual_contract_multiplier_and_identity_must_be_verified(monkeypatch, changes):
    result, *_ = gate(monkeypatch, contract_changes=changes)
    assert not result["confirmed"]
    assert any("contract" in blocker for blocker in result["blockers"])


def test_missing_actual_contract_blocks_c9_only(monkeypatch):
    result, *_ = gate(monkeypatch, missing_contract=True)
    assert not result["confirmed"]
    legacy, *_ = gate(monkeypatch, missing_contract=True, row={"execution_profile": "legacy"})
    assert legacy["confirmed"], legacy["blockers"]


@pytest.mark.parametrize("cluster", ["sh.czce", "Sh.Czce", "SH.CZCE"])
def test_cluster_comparison_matches_core_case_normalization(monkeypatch, cluster):
    row = sizing_row()
    row["broker_sizing_inputs"]["signal"]["risk_cluster_name"] = cluster
    row["broker_sizing"] = sizing.size_open_intent(**row["broker_sizing_inputs"])
    row["order_request"].update({
        "broker_sizing": copy.deepcopy(row["broker_sizing"]),
        "broker_sizing_inputs": copy.deepcopy(row["broker_sizing_inputs"]),
    })
    row["order_request_json"] = json.dumps(row["order_request"])
    result, *_ = gate(monkeypatch, row=row)
    assert result["confirmed"], result["blockers"]


def test_contract_multiplier_change_after_funds_gate_blocks_native_boundary(monkeypatch):
    result, td_api, rows, physical = gate(monkeypatch)
    assert result["confirmed"], result["blockers"]
    td_api.contract.size = 60
    blockers = stage931._open_funds_gate_consistency_blockers(
        td_api, rows, physical, result, main_engine=td_api.main_engine,
    )
    assert any("contract" in blocker for blocker in blockers)


@pytest.mark.parametrize("field", ["broker_sizing", "broker_sizing_inputs"])
def test_c9_requires_both_signed_sizing_fields(monkeypatch, field):
    row = sizing_row()
    del row[field]
    result, *_ = gate(monkeypatch, row=row)
    assert not result["confirmed"]
    assert any("broker_sizing" in item for item in result["blockers"])


@pytest.mark.parametrize("field,value", [
    ("Balance", 0), ("Balance", None), ("Balance", True), ("Balance", float("inf")),
    ("FrozenMargin", -1), ("FrozenMargin", None), ("FrozenCash", float("nan")),
    ("FrozenCommission", True), ("Available", True), ("CurrMargin", True),
    ("CurrencyID", "USD"),
])
def test_c9_raw_money_requires_strict_finite_cny_fields(monkeypatch, field, value):
    result, *_ = gate(monkeypatch, account=raw_account(**{field: value}))
    assert not result["confirmed"]


@pytest.mark.parametrize("age", [301, -1])
def test_expired_or_future_sizing_is_blocked(monkeypatch, age):
    result, *_ = gate(monkeypatch, age=age)
    assert not result["confirmed"]


def test_fresh_funds_shrink_capacity_but_never_change_volume(monkeypatch):
    result, *_ = gate(monkeypatch, account=raw_account(Balance=100000, Available=53440))
    assert not result["confirmed"]
    assert any("volume_exceeds" in item for item in result["blockers"])


def test_fresh_frozen_money_reduces_capacity(monkeypatch):
    result, *_ = gate(monkeypatch, account=raw_account(Available=100110, FrozenMargin=40000))
    assert not result["confirmed"]


def test_reprice_cannot_spend_new_larger_account_budget(monkeypatch):
    result, *_ = gate(monkeypatch, requests=[request(price=1952)],
                     account=raw_account(Balance=300000, Available=253440))
    assert not result["confirmed"]
    assert any("risk_budget_exceeded" in item for item in result["blockers"])


def test_split_children_share_one_budget(monkeypatch):
    result, *_ = gate(monkeypatch, requests=[request(volume=2), request(volume=2)])
    assert result["confirmed"], result["blockers"]
    excess, *_ = gate(monkeypatch, requests=[request(volume=3), request(volume=3)])
    assert not excess["confirmed"]


def test_each_child_affordable_does_not_make_combined_batch_affordable(monkeypatch):
    row = sizing_row()
    row["broker_sizing_inputs"]["account"].update(equity=300000, available=253440)
    row["broker_sizing"] = sizing.size_open_intent(**row["broker_sizing_inputs"])
    volume = row["broker_sizing"]["volume"]
    assert volume > 4
    row["planned_volume"] = row["volume"] = row["order_request_volume"] = volume
    payload = {key: value for key, value in row.items() if key not in {"order_request", "order_request_json"}}
    row["order_request"] = copy.deepcopy(payload)
    row["order_request_json"] = json.dumps(payload)
    result, *_ = gate(monkeypatch, row=row, requests=[request(4), request(volume - 4)])
    assert not result["confirmed"]
    assert "final_broker_sizing_volume_exceeds_fresh_limit" in result["blockers"]


def test_valid_audit_for_different_broker_account_is_rejected(monkeypatch):
    row = sizing_row()
    row["broker_sizing_inputs"]["account"]["account_fingerprint"] = "a" * 64
    row["broker_sizing"] = sizing.size_open_intent(**row["broker_sizing_inputs"])
    for field in ("broker_sizing", "broker_sizing_inputs"):
        row["order_request"][field] = copy.deepcopy(row[field])
    row["order_request_json"] = json.dumps(row["order_request"])
    result, *_ = gate(monkeypatch, row=row)
    assert not result["confirmed"]
    assert any("account_fingerprint_mismatch" in item for item in result["blockers"])


def test_mixed_physical_prices_or_symbols_are_unverifiable(monkeypatch):
    for physical in ([request(2), request(2, 1949)],
                     [request(2), request(2, symbol="MA609")]):
        result, *_ = gate(monkeypatch, requests=physical)
        assert not result["confirmed"]


def test_original_audit_and_nested_payload_cannot_disagree(monkeypatch):
    row = sizing_row()
    row["broker_sizing"]["risk_budget"] *= 2
    result, *_ = gate(monkeypatch, row=row)
    assert not result["confirmed"]


def test_even_consistent_audit_tamper_must_replay_original_inputs(monkeypatch):
    row = sizing_row()
    row["broker_sizing"]["risk_budget"] *= 2
    row["order_request"]["broker_sizing"] = copy.deepcopy(row["broker_sizing"])
    row["order_request_json"] = json.dumps(row["order_request"])
    result, *_ = gate(monkeypatch, row=row)
    assert not result["confirmed"]


def test_fresh_product_margin_not_old_snapshot_controls_cluster_cap(monkeypatch):
    result, *_ = gate(monkeypatch, positions=[raw_position(InstrumentID="SH609", UseMargin=46560)])
    assert not result["confirmed"]


def test_missing_product_margin_or_position_epoch_is_blocked(monkeypatch):
    for options in ({"missing_position_epoch": True},
                    {"positions": [raw_position(UseMargin=None)]},
                    {"positions": [raw_position(InvestorID="other")]},
                    {"positions": [raw_position(InstrumentID="SH609C1000")]}):
        result, *_ = gate(monkeypatch, **options)
        assert not result["confirmed"]


def test_broker_max_volume_gate_is_still_required(monkeypatch):
    result, *_ = gate(monkeypatch, maximum=3)
    assert not result["confirmed"]
    assert any("max_volume_insufficient" in item for item in result["blockers"])


def test_other_profile_and_close_only_keep_previous_behavior(monkeypatch):
    result, *_ = gate(monkeypatch, row={"execution_profile": "stage372"}, account={
        "BrokerID": "fake-broker", "AccountID": "fake-user", "Available": 100000, "CurrMargin": 0,
    })
    assert result["confirmed"], result["blockers"]
    close, td_api, *_ = gate(monkeypatch, row={"execution_profile": "c9-15w"},
                            requests=[request(offset=stage931.Offset.CLOSE, type=stage931.OrderType.LIMIT)])
    assert close["confirmed"]
    assert td_api.calls == []


def test_sizing_expiry_and_product_evidence_rechecked_at_native_boundary(monkeypatch):
    result, td_api, rows, physical = gate(monkeypatch)
    assert result["confirmed"], result["blockers"]
    monkeypatch.setattr(stage931.time, "time", lambda: NOW + 301)
    assert stage931._open_funds_gate_consistency_blockers(
        td_api, rows, physical, result, main_engine=td_api.main_engine,
    )
    monkeypatch.setattr(stage931.time, "time", lambda: NOW)
    rows["_position_query_epoch"]["broker_sizing_raw_positions"][0]["UseMargin"] += 1
    assert stage931._open_funds_gate_consistency_blockers(
        td_api, rows, physical, result, main_engine=td_api.main_engine,
    )


def test_trade_during_funds_queries_cannot_be_absorbed_into_baseline(monkeypatch):
    result, *_ = gate(monkeypatch, event_during_query=True)
    assert not result["confirmed"]


def test_sizing_stop_is_bound_to_execution_stop_metadata(monkeypatch):
    row = sizing_row()
    row["strategy_initial_stop_price"] = 1900
    row["order_request"]["strategy_initial_stop_price"] = 1900
    row["order_request_json"] = json.dumps(row["order_request"])
    result, *_ = gate(monkeypatch, row=row)
    assert not result["confirmed"]


def test_non_tick_physical_price_is_unverifiable(monkeypatch):
    result, *_ = gate(monkeypatch, requests=[request(price=1948.5)])
    assert not result["confirmed"]


def test_raw_position_callback_preserves_fresh_use_margin(monkeypatch):
    rows = fixtures.Stage931CtpReadinessTests._funds_rows()
    rows["_position_query_epoch"] = {
        "active_reqid": 99, "complete_reqid": None, "pending_callbacks": [],
        "strict_identity": True, "expected_broker_id": "fake-broker",
        "expected_investor_id": "fake-user",
    }
    td_api = fixtures.FakeFundsTdApi(fixtures.FakeClock())
    with stage931._instrument_ctp_readiness_callbacks(fixtures.FakeFundsTdApi, rows):
        td_api.onRspQryInvestorPosition(raw_position(), {}, 99, False)
        assert "broker_sizing_raw_positions" not in rows["_position_query_epoch"]
        td_api.onRspQryInvestorPosition({}, {}, 99, True)
    products, _, reqid = stage931._broker_sizing_position_evidence(
        rows, broker_id="fake-broker", investor_id="fake-user",
    )
    assert products == {"MA.CZCE": 46560.0}
    assert reqid == 99


def test_stage905_payload_and_spool_materialize_into_final_gate(monkeypatch):
    import pandas as pd
    import run_qmt_roll_stage905_official_live_executor_dry_run as stage905
    from types import SimpleNamespace

    initial = sizing_row()["broker_sizing_inputs"]
    intent = {
        **initial["intent"], "intent_id": "pending-sh", "target_date": "2026-09-07",
        "source": "stage901_pending_order", "execution_profile": "c9-15w",
    }
    sized = stage905._size_c9_open_intent(
        intent, entry_risk=pd.DataFrame([{
            **initial["signal"], "date": "2026-09-07", "contract_vt_symbol": "SH611.CZCE",
            "direction": "long",
        }]), broker_account=initial["account"], policy=initial["policy"], pricetick=1,
    )
    validated = stage905._validate_intent(
        sized, contracts=pd.DataFrame([{"vt_symbol": "SH611.CZCE", "pricetick": 1}]),
        positions=pd.DataFrame(), orders=pd.DataFrame(),
        stage902_summary={"blocking_failure_count": 0, "allow_new_open": 1},
        stage260_summary={"executable_count": 1}, stage904_summary={}, mode="dry-run",
    )
    assert validated["executor_status"] == "dry_run_order_request_payload_ready"
    row, _ = stage931._stage179_spool_lease_row(SimpleNamespace(intent=SimpleNamespace(
        payload=json.loads(validated["spool_payload_json"]), intent_id="pending-sh",
    )))
    result, *_ = gate(monkeypatch, row=row)
    assert result["confirmed"], result["blockers"]


def test_retry_is_checked_without_rewriting_root_or_replenishing_lots(monkeypatch):
    row = sizing_row()
    row["broker_sizing_inputs"]["intent"].update({
        "intent_role": "c9_retry_open_once", "planned_volume": 2,
        "root_entry_volume": 2, "root_entry_price": 1948.0, "root_initial_stop_price": 1933.0,
    })
    row["broker_sizing"] = sizing.size_open_intent(**row["broker_sizing_inputs"])
    row.update(row["broker_sizing_inputs"]["intent"])
    row["volume"] = row["planned_volume"] = row["order_request_volume"] = 2
    payload = {key: value for key, value in row.items() if key not in {"order_request", "order_request_json"}}
    row["order_request"] = copy.deepcopy(payload)
    row["order_request_json"] = json.dumps(payload)
    result, *_ = gate(monkeypatch, row=row, requests=[request(volume=2)])
    assert result["confirmed"], result["blockers"]
    excess, *_ = gate(monkeypatch, row=row, requests=[request(volume=3)])
    assert not excess["confirmed"]


class FakeCloseTdApi(fixtures.FakeSnapshotTdApi):
    def __init__(self, clock, *, trades, orders, positions, details=None):
        super().__init__(clock, order_responses=[{"callbacks": orders}, {"callbacks": orders}],
                         position_responses=[{"callbacks": positions}])
        self.trade_callbacks = trades
        self.frontid = 1
        self.sessionid = 2
        self.native_calls = 0
        self.detail_callbacks = details or [fixtures._callback({})]

    def getTradingDay(self):
        return "20260908"

    def onRspQryInvestorPositionDetail(self, data, error, reqid, last):
        return None

    def reqQryInvestorPositionDetail(self, query, reqid):
        self.calls.append({"kind": "detail", "reqid": reqid})
        for callback in self.detail_callbacks:
            self.onRspQryInvestorPositionDetail(callback["data"], callback.get("error", {}),
                                                reqid + callback.get("reqid_delta", 0), callback.get("last", True))
        return 0

    def onRspQryTrade(self, data, error, reqid, last):
        return None

    def reqQryTrade(self, query, reqid):
        self.calls.append({"kind": "trade", "reqid": reqid})
        for callback in self.trade_callbacks:
            self.onRspQryTrade(callback["data"], callback.get("error", {}),
                               reqid + callback.get("reqid_delta", 0), callback.get("last", True))
        return 0

    def reqOrderInsert(self, data, reqid):
        self.native_calls += 1
        return 0


def close_case():
    audit = {
        "mode": "full_close", "volume": 4, "broker_gross_volume": 4,
        "shadow_volume": 7, "shadow_position_volume": 7,
        "vt_symbol": "SH611.CZCE", "position_direction": "long",
        "root_position_id": "root-1", "position_epoch_id": "epoch-1", "owned_net_volume": 4,
        "account_fingerprint": FINGERPRINT, "cohort_id": "a" * 64, "target_date": "2026-09-08",
    }
    payload = {
        "broker_close_sizing": audit, "vt_symbol": "SH611.CZCE", "direction": "short",
        "offset": "close", "volume": 4, "price": 1948,
    }
    row = {**payload, "target_date": "2026-09-08", "planned_volume": 4,
           "execution_profile": "c9-15w", "source": "stage901_pending_order",
           "order_request": copy.deepcopy(payload), "order_request_json": json.dumps(payload)}
    trade = {
        "BrokerID": "fake-broker", "InvestorID": "fake-user", "InstrumentID": "SH611",
        "ExchangeID": "CZCE", "OrderSysID": "O1", "TradeID": "T1", "Direction": "0",
        "OffsetFlag": "0", "Price": 1948, "Volume": 4,
        "TradeDate": "20260908", "TradeTime": "09:30:00", "TradingDay": "20260908",
    }
    order = {
        "BrokerID": "fake-broker", "InvestorID": "fake-user", "InstrumentID": "SH611",
        "ExchangeID": "CZCE", "OrderSysID": "O1", "OrderRef": "3", "FrontID": 1, "SessionID": 2,
        "OrderStatus": "0", "Direction": "0", "CombOffsetFlag": "0",
        "VolumeTotalOriginal": 4, "VolumeTraded": 4,
    }
    position = raw_position(InstrumentID="SH611", Position=4, TodayPosition=4, UseMargin=28051.2)
    fill = {
        "event_type": "filled_or_part_filled", "source": "stage901_pending_order",
        "target_date": "2026-09-08", "vt_symbol": "SH611.CZCE", "direction": "long", "offset": "open",
        "root_position_id": "root-1", "position_epoch_id": "epoch-1", "vt_orderid": "CTP.1_2_3",
        "vt_tradeid": "CTP.T1", "tradeid": "T1", "trade_fill_key": "ctp:CZCE:T1",
        "volume": 4, "trade_volume_delta": 4, "price": 1948,
        "fill_price_source": "event_trade_weighted_avg", "broker_trade_at": "2026-09-08T09:30:00+08:00",
        "broker_trading_day": "2026-09-08", "account_fingerprint": FINGERPRINT,
    }
    return row, trade, order, position, [fill]


def run_close_gate(monkeypatch, *, change=None, deadline=110.0, lock=None, details=None, position_rows=None):
    assert hasattr(stage931, "_requires_resized_broker_close")
    row, trade, order, position, ledger = close_case()
    if change:
        change(row, trade, order, position, ledger)
    clock = fixtures.FakeClock()
    clock.now = 100.0
    monkeypatch.setattr(stage931.time, "time", lambda: NOW)
    monkeypatch.setattr(stage931.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(stage931.time, "sleep", clock.sleep)
    from qmt_roll_official_live_execution_ledger import _record_checksum

    def read_ledger(*_args):
        checked = copy.deepcopy(ledger)
        for item in checked:
            item.setdefault("record_checksum", _record_checksum(item))
        return checked

    monkeypatch.setattr(stage931, "read_execution_ledger", read_ledger)
    monkeypatch.setattr(stage931, "_final_ctp_transport_blockers", lambda *_args: [])
    monkeypatch.setattr(stage931, "_post_snapshot_final_reprice", lambda *_args, **_kwargs: {"final_reprice_status": "applied"})
    rows = fixtures.Stage931CtpReadinessTests._funds_rows()
    rows["_execution_event_ingress_lock"] = threading.RLock()
    positions = position_rows or [position]
    rows["positions"] = [stage931._raw_ctp_position_row(item, reqid=49, vt_symbol_by_instrument={}) for item in positions]
    initial = {
        "canonical_positions": stage931._canonical_position_snapshot(rows["positions"]),
        "event_watermark_before_q2": stage931._execution_event_watermark(rows),
        "event_watermark_after_q2": stage931._execution_event_watermark(rows),
    }
    td_api = FakeCloseTdApi(clock, trades=[fixtures._callback(trade)],
                           orders=[fixtures._callback(order)], positions=[fixtures._callback(item, last=index == len(positions) - 1)
                                                                        for index, item in enumerate(positions)],
                           details=[fixtures._callback(detail, last=index == len(details or [position_detail()]) - 1)
                                    for index, detail in enumerate(details or [position_detail()])])
    physical = [request(direction=stage931.Direction.SHORT, offset=stage931.Offset.CLOSE, type=stage931.OrderType.LIMIT)]
    physical[0].symbol, exchange = row["vt_symbol"].rsplit(".", 1)
    physical[0].exchange = stage931.Exchange(exchange)
    physical[0].__post_init__()
    before = copy.deepcopy((row, physical))
    with stage931._instrument_ctp_readiness_callbacks(FakeCloseTdApi, rows):
        result = stage931._post_reprice_final_state_gate(
            None, td_api, rows, row, physical[0], initial_snapshot=initial,
            initial_reprice_result={"final_reprice_status": "applied"}, max_tick_age_seconds=30,
            max_wait_seconds=10.0, readiness_state=stage931.CtpReadinessState(account_required=False),
            hard_deadline_monotonic=deadline, query_lock=lock or threading.RLock(),
            ledger_path=Path("/fake/ledger.jsonl"),
        )
        funds = stage931._final_open_funds_margin_gate(td_api, rows, physical, max_wait_seconds=0, intent_row=row)
    assert before == (row, physical)
    assert td_api.native_calls == 0
    return result, funds, td_api, rows, physical, ledger


def test_resized_full_close_owned_today_epoch_passes_trade_then_final_q2(monkeypatch):
    result, funds, td_api, rows, physical, _ = run_close_gate(monkeypatch)
    assert result["confirmed"], result["blockers"]
    assert funds["confirmed"], funds["blockers"]
    assert [call["kind"] for call in td_api.calls] == ["detail", "trade", "order", "position", "order"]
    assert stage931._open_funds_gate_consistency_blockers(td_api, rows, physical, funds) == []


@pytest.mark.parametrize("fault", ["epoch", "account", "manual", "unbound", "overnight", "foreign_query", "missing_trade", "trade_volume", "order_identity", "payload", "ledger_decode", "checksum"])
def test_resized_close_rejects_unproven_ownership(monkeypatch, fault):
    def change(row, trade, order, position, ledger):
        if fault == "epoch":
            ledger[0]["position_epoch_id"] = "epoch-new-same-quantity"
        elif fault == "account":
            row["broker_close_sizing"]["account_fingerprint"] = "b" * 64
            row["order_request"]["broker_close_sizing"] = copy.deepcopy(row["broker_close_sizing"])
            row["order_request_json"] = json.dumps(row["order_request"])
        elif fault == "manual":
            ledger[0]["source"] = "manual"
        elif fault == "unbound":
            ledger.append({"event_type": "broker_trade_callback_unbound", "vt_symbol": "SH611.CZCE", "tradeid": "MANUAL"})
        elif fault == "overnight":
            position.update(TodayPosition=0, YdPosition=4)
        elif fault == "foreign_query":
            trade["InvestorID"] = "other-user"
        elif fault == "missing_trade":
            trade.clear()
        elif fault == "trade_volume":
            trade["Volume"] = 3
        elif fault == "order_identity":
            order["OrderRef"] = "manual-ref"
        elif fault == "payload":
            row["order_request"]["broker_close_sizing"]["position_epoch_id"] = "new"
        elif fault == "ledger_decode":
            ledger.append({"event_type": "ledger_decode_error", "ledger_line_number": 2})
        elif fault == "checksum":
            ledger[0]["record_checksum"] = "changed"
    result, funds, *_ = run_close_gate(monkeypatch, change=change)
    assert not result["confirmed"]
    assert not funds["confirmed"]


def test_resized_close_deadline_exhaustion_makes_no_query(monkeypatch):
    result, funds, td_api, *_ = run_close_gate(monkeypatch, deadline=100.0)
    assert not result["confirmed"] and not funds["confirmed"]
    assert td_api.calls == []


def test_resized_close_busy_query_lock_is_bounded_and_zero_query(monkeypatch):
    class BusyLock:
        def acquire(self, *, timeout):
            assert 0 < timeout <= 10
            return False

        def release(self):
            pytest.fail("unowned lock must not be released")

    result, funds, td_api, *_ = run_close_gate(monkeypatch, lock=BusyLock())
    assert not result["confirmed"] and not funds["confirmed"]
    assert td_api.calls == []


def test_resized_close_reconnect_during_query_cannot_be_absorbed(monkeypatch):
    original = FakeCloseTdApi.reqQryTrade

    def reconnect(self, query, reqid):
        result = original(self, query, reqid)
        self.sessionid += 1
        return result

    monkeypatch.setattr(FakeCloseTdApi, "reqQryTrade", reconnect)
    result, funds, *_ = run_close_gate(monkeypatch)
    assert not result["confirmed"] and not funds["confirmed"]


@pytest.mark.parametrize("drift", [False, True])
def test_resized_close_actual_native_wrapper_rechecks_without_io(monkeypatch, drift):
    result, funds, td_api, rows, physical, _ = run_close_gate(monkeypatch)
    assert result["confirmed"] and funds["confirmed"]
    monkeypatch.setattr(stage931, "read_execution_ledger", lambda *_args: pytest.fail("native ledger I/O"))
    rows["_before_native_order_insert"] = lambda *_args: None
    td_api.reqid += 1
    if drift:
        rows["_execution_event_ingress_counts"]["trade"] += 1
    native = {
        "BrokerID": "fake-broker", "InvestorID": "fake-user", "UserID": "fake-user",
        "InstrumentID": "SH611", "ExchangeID": "CZCE", "Direction": "1",
        "CombOffsetFlag": "1", "CombHedgeFlag": "1", "OrderPriceType": "2",
        "TimeCondition": "3", "VolumeCondition": "1", "LimitPrice": 1948.0, "VolumeTotalOriginal": 4,
        "OrderRef": "4",
    }
    with stage931._instrument_ctp_readiness_callbacks(FakeCloseTdApi, rows):
        if drift:
            with pytest.raises(RuntimeError, match="resized_close_native_gate_blocked"):
                td_api.reqOrderInsert(native, td_api.reqid)
        else:
            assert td_api.reqOrderInsert(native, td_api.reqid) == 0
    assert td_api.native_calls == int(not drift)


def test_resized_close_physical_split_is_not_new_partial_support(monkeypatch):
    result, funds, td_api, rows, physical, _ = run_close_gate(monkeypatch)
    assert result["confirmed"] and funds["confirmed"]
    children = [copy.deepcopy(physical[0]), copy.deepcopy(physical[0])]
    for child in children:
        child.volume = 2
    blocked = stage931._final_open_funds_margin_gate(td_api, rows, children, max_wait_seconds=0, intent_row=close_case()[0])
    assert not blocked["confirmed"]
    assert "resized_close_converted_bundle_mismatch" in blocked["blockers"]


def test_cold_and_warm_final_gate_call_sites_supply_owned_query_lock_and_ledger():
    import ast

    tree = ast.parse(Path(stage931.__file__).read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "_post_reprice_final_state_gate"]
    assert len(calls) == 2
    for call in calls:
        assert {"query_lock", "ledger_path"} <= {keyword.arg for keyword in call.keywords}


@pytest.mark.parametrize("change", ["reqid", "trade_callback", "event", "connection", "bundle", "expiry"])
def test_resized_close_native_zero_io_watermark_rejects_drift(monkeypatch, change):
    result, funds, td_api, rows, physical, _ = run_close_gate(monkeypatch)
    assert result["confirmed"] and funds["confirmed"]
    query_count = len(td_api.calls)
    monkeypatch.setattr(stage931, "read_execution_ledger", lambda *_args: pytest.fail("native must not read ledger"))
    if change == "reqid":
        td_api.reqid += 1
    elif change == "trade_callback":
        rows["trade_query_callbacks"].append({"reqid": 999})
    elif change == "event":
        rows["_execution_event_ingress_counts"]["trade"] += 1
    elif change == "connection":
        td_api.sessionid += 1
    elif change == "bundle":
        physical[0].volume = 3
    elif change == "expiry":
        monkeypatch.setattr(stage931.time, "monotonic", lambda: 111.0)
    assert stage931._open_funds_gate_consistency_blockers(td_api, rows, physical, funds)
    assert len(td_api.calls) == query_count


def position_detail(**changes):
    return {
        "BrokerID": "fake-broker", "InvestorID": "fake-user", "InstrumentID": "SH611",
        "ExchangeID": "CZCE", "TradeID": "T1", "Direction": "0", "Volume": 4,
        "OpenDate": "20260908", "TradingDay": "20260908", "OpenPrice": 1948,
        "HedgeFlag": "1", "TradeType": "0", "CloseVolume": 0, **changes,
    }


@pytest.mark.parametrize("fault", [None, "foreign_reqid", "error", "missing_last", "account", "empty_data", "late_duplicate"])
def test_position_detail_query_requires_complete_owned_epoch(fault):
    clock = fixtures.FakeClock()
    clock.now = 100.0
    callback = fixtures._callback(position_detail())
    if fault == "foreign_reqid":
        callback["reqid_delta"] = 1
    elif fault == "error":
        callback["error"] = {"ErrorID": 1}
    elif fault == "missing_last":
        callback["last"] = False
    elif fault == "account":
        callback["data"]["InvestorID"] = "foreign"
    elif fault == "empty_data":
        callback["data"] = "invalid"
    callbacks = [callback, copy.deepcopy(callback)] if fault == "late_duplicate" else [callback]
    td_api = FakeCloseTdApi(clock, trades=[], orders=[], positions=[], details=callbacks)
    rows = fixtures.Stage931CtpReadinessTests._funds_rows()
    with stage931._instrument_ctp_readiness_callbacks(FakeCloseTdApi, rows):
        result = stage931._final_position_detail_query_epoch(
            td_api, rows, max_wait_seconds=2, monotonic=clock.monotonic, sleeper=clock.sleep,
        )
    assert result["confirmed"] is (fault is None), result
    assert td_api.native_calls == 0
    if fault is None:
        assert result["position_details"] == [position_detail()]
        assert result["trading_day"] == "2026-09-08"


def test_owned_overnight_detail_survives_empty_current_trade_query(monkeypatch):
    def change(row, trade, order, position, ledger):
        trade.clear()
        order.clear()
        position.update(TodayPosition=0, YdPosition=4)
        ledger[0].update(target_date="2026-09-07", broker_trade_at="2026-09-07T09:30:00+08:00",
                         broker_trading_day="2026-09-07", account_fingerprint=FINGERPRINT)

    result, funds, *_ = run_close_gate(monkeypatch, change=change, details=[position_detail(OpenDate="20260907")])
    assert result["confirmed"], result["blockers"]
    assert funds["confirmed"], funds["blockers"]


def test_overnight_detail_same_quantity_manual_reopen_is_not_owned(monkeypatch):
    def change(row, trade, order, position, ledger):
        trade.clear()
        order.clear()
        position.update(TodayPosition=0, YdPosition=4)
        ledger[0].update(target_date="2026-09-07", broker_trade_at="2026-09-07T09:30:00+08:00",
                         broker_trading_day="2026-09-07", account_fingerprint=FINGERPRINT)

    result, funds, *_ = run_close_gate(monkeypatch, change=change,
                                     details=[position_detail(OpenDate="20260907", TradeID="manual-same-qty")])
    assert not result["confirmed"] and not funds["confirmed"]


@pytest.mark.parametrize("fault", [None, "offset", "volume", "price", "symbol", "duplicate", "fractional"])
def test_resized_close_split_exact_today_yesterday_bundle(fault):
    logical = request(direction=stage931.Direction.SHORT, offset=stage931.Offset.CLOSE,
                      type=stage931.OrderType.LIMIT)
    logical.symbol = "rb2610"
    logical.exchange = stage931.Exchange.SHFE
    proof = {"logical_bundle": stage931._physical_request_bundle([logical]), "today_volume": 2, "yesterday_volume": 2}
    children = [copy.deepcopy(logical), copy.deepcopy(logical)]
    children[0].offset = stage931.Offset.CLOSETODAY
    children[1].offset = stage931.Offset.CLOSEYESTERDAY
    for child in children:
        child.volume = 2
    if fault == "offset":
        children[1].offset = stage931.Offset.CLOSE
    elif fault == "volume":
        children[1].volume = 1
    elif fault == "price":
        children[1].price += 1
    elif fault == "symbol":
        children[1].symbol = "rb2701"
    elif fault == "duplicate":
        children[1].offset = stage931.Offset.CLOSETODAY
    elif fault == "fractional":
        children[0].volume = 1.5
        children[1].volume = 2.5
    blockers = stage931._resized_close_converted_bundle_blockers(proof, children)
    assert bool(blockers) is (fault is not None)


@pytest.mark.parametrize("wrong_child", [False, True])
def test_resized_close_native_children_require_exact_owned_prefix(monkeypatch, wrong_child):
    clock = fixtures.FakeClock()
    clock.now = 100
    td_api = FakeCloseTdApi(clock, trades=[], orders=[], positions=[])
    rows = fixtures.Stage931CtpReadinessTests._funds_rows()
    rows["_execution_event_ingress_lock"] = threading.RLock()
    rows["_ctp_last_query_monotonic"] = 100
    monkeypatch.setattr(stage931.time, "monotonic", clock.monotonic)
    logical = request(direction=stage931.Direction.SHORT, offset=stage931.Offset.CLOSE, type=stage931.OrderType.LIMIT)
    logical.symbol = "rb2610"
    logical.exchange = stage931.Exchange.SHFE
    children = [copy.deepcopy(logical), copy.deepcopy(logical)]
    children[0].offset = stage931.Offset.CLOSETODAY
    children[1].offset = stage931.Offset.CLOSEYESTERDAY
    for child in children:
        child.volume = 2
    proof = {
        "confirmed": True, "expires_monotonic": 110, "front_id": "1", "session_id": "2",
        "trading_day": "2026-09-08", "query_watermark": stage931._physical_batch_query_watermark(td_api, rows),
        "event_watermark": stage931._execution_event_watermark(rows),
        "positions_sha256": stage931._canonical_evidence_sha256(rows.get("positions", [])),
        "callbacks_sha256": stage931._canonical_evidence_sha256({name: [] for name in (
            "trade_query_callbacks", "order_query_callbacks", "position_query_callbacks", "position_detail_query_callbacks")}),
    }
    bound = {"confirmed": True, "broker_close_sizing_gate": proof,
             "broker_close_sizing_gate_sha256": stage931._canonical_evidence_sha256(proof),
             "request_bundle_sha256": stage931._canonical_evidence_sha256(stage931._physical_request_bundle(children))}
    rows.update(_resized_close_bound_gate=bound, _resized_close_requests=children, _resized_close_native_count=0,
                _before_native_order_insert=lambda *_args: None)
    with stage931._instrument_ctp_readiness_callbacks(FakeCloseTdApi, rows):
        for index, child in enumerate(children):
            td_api.reqid += 1
            native = {
                "BrokerID": "fake-broker", "InvestorID": "fake-user", "UserID": "fake-user",
                "InstrumentID": "rb2610", "ExchangeID": "SHFE", "Direction": "1",
                "CombOffsetFlag": "3" if index == 0 or wrong_child else "4", "CombHedgeFlag": "1",
                "OrderPriceType": "2", "TimeCondition": "3", "VolumeCondition": "1",
                "LimitPrice": child.price, "VolumeTotalOriginal": 2, "OrderRef": str(index + 10),
            }
            if index == 1 and wrong_child:
                with pytest.raises(RuntimeError, match="resized_close_native_gate_blocked"):
                    td_api.reqOrderInsert(native, td_api.reqid)
            else:
                assert td_api.reqOrderInsert(native, td_api.reqid) == 0
    assert td_api.native_calls == (1 if wrong_child else 2)


@pytest.mark.parametrize("fault", [None, "price", "account", "date", "missing_day"])
def test_raw_trade_ownership_evidence_preserves_night_trading_day(fault):
    _, trade, _, _, ledger = close_case()
    trade.update(TradeDate="20260907", TradeTime="21:05:00", TradingDay="20260908", HedgeFlag="1")
    event = {**ledger[0], "datetime": "2026-09-07T21:05:00+08:00", "exchange": "CZCE", "symbol": "SH611"}
    event.pop("broker_trade_at")
    event.pop("broker_trading_day")
    event.pop("account_fingerprint")
    if fault == "price":
        trade["Price"] += 1
    elif fault == "account":
        trade["InvestorID"] = "foreign"
    elif fault == "date":
        trade["TradeDate"] = "20260908"
    elif fault == "missing_day":
        trade.pop("TradingDay")
    td_api = SimpleNamespace(brokerid="fake-broker", userid="fake-user")
    evidence = stage931._raw_trade_ownership_evidence(td_api, trade)
    rows = {"_raw_trade_ownership_evidence": {("CZCE", "T1", "2026-09-07"): evidence}}
    bound = stage931._bind_trade_ownership_evidence(rows, event)
    if fault is None:
        assert bound["broker_trading_day"] == "2026-09-08"
        assert bound["broker_trade_date"] == "2026-09-07"
        assert bound["account_fingerprint"] == FINGERPRINT
        assert bound["broker_trade_metadata_source"] == "ctp_on_rtn_trade"
    else:
        assert "broker_trade_metadata_source" not in bound


def test_night_fill_uses_broker_trading_day_not_calendar_day(monkeypatch):
    def change(row, trade, order, position, ledger):
        trade.update(TradeDate="20260907", TradeTime="21:05:00")
        ledger[0].update(broker_trade_at="2026-09-07T21:05:00+08:00", broker_trade_date="2026-09-07",
                         broker_trading_day="2026-09-08", target_date="2026-09-07")

    result, funds, *_ = run_close_gate(monkeypatch, change=change, details=[position_detail(OpenDate="20260907")])
    assert result["confirmed"], result["blockers"]
    assert funds["confirmed"], funds["blockers"]


def test_native_raw_trade_metadata_reaches_durable_fill(monkeypatch, tmp_path):
    _, raw, _, _, _ = close_case()
    raw.update(TradeDate="20260907", TradeTime="21:05:00", TradingDay="20260908", HedgeFlag="1")
    rows = fixtures.Stage931CtpReadinessTests._funds_rows()

    class NativeTradeApi(FakeCloseTdApi):
        def onRtnTrade(self, data):
            normalized, blockers = stage931._raw_ctp_trade_row(data, reqid=0, row_index=0)
            assert not blockers
            event = {**normalized, "datetime": normalized["broker_trade_at"], "vt_symbol": "SH611.CZCE", "vt_orderid": "CTP.1_2_3"}
            rows["received_trade"] = stage931._bind_trade_ownership_evidence(rows, event)

    td_api = NativeTradeApi(fixtures.FakeClock(), trades=[], orders=[], positions=[])
    events = []
    monkeypatch.setattr(stage931, "append_broker_callback_event_once", lambda event, *_args: events.append(event) or {})
    with stage931._instrument_ctp_readiness_callbacks(NativeTradeApi, rows):
        td_api.onRtnTrade(raw)
    context = {"target_date": "2026-09-08", "intent_id": "root-1", "fingerprint": "a" * 64,
               "row": {"vt_symbol": "SH611.CZCE", "source": "stage901_pending_order", "direction": "long", "offset": "open"}}
    stage931._persist_stage179_warm_broker_callback(kind="trade", callback=rows["received_trade"], context=context,
                                                   target_date="2026-09-08", ledger_path=tmp_path / "ledger.jsonl")
    assert events[0]["event_type"] == "filled_or_part_filled"
    assert "broker_trading_day" not in events[0]
    assert events[1]["event_type"] == "broker_trade_ownership_metadata"
    assert events[1]["broker_trading_day"] == "2026-09-08"
    assert events[1]["broker_trade_date"] == "2026-09-07"
    assert events[1]["account_fingerprint"] == FINGERPRINT
    assert events[1]["broker_trade_metadata_source"] == "ctp_on_rtn_trade"


def test_mixed_shfe_owned_lots_bind_complete_split_close(monkeypatch):
    def change(row, trade, order, position, ledger):
        row["vt_symbol"] = "rb2610.SHFE"
        row["broker_close_sizing"]["vt_symbol"] = row["vt_symbol"]
        row["order_request"]["vt_symbol"] = row["vt_symbol"]
        row["order_request"]["broker_close_sizing"] = copy.deepcopy(row["broker_close_sizing"])
        row["order_request_json"] = json.dumps(row["order_request"])
        trade.update(InstrumentID="rb2610", ExchangeID="SHFE", Volume=2, TradeID="T2")
        order.update(InstrumentID="rb2610", ExchangeID="SHFE", VolumeTotalOriginal=2, VolumeTraded=2)
        ledger[0].update(vt_symbol="rb2610.SHFE", volume=2, trade_volume_delta=2, trade_fill_key="ctp:SHFE:T1",
                         broker_trade_at="2026-09-07T09:30:00+08:00", broker_trading_day="2026-09-07", target_date="2026-09-07",
                         vt_orderid="CTP.old_1_1")
        ledger.append({**ledger[0], "tradeid": "T2", "vt_tradeid": "CTP.T2", "trade_fill_key": "ctp:SHFE:T2",
                       "broker_trade_at": "2026-09-08T09:30:00+08:00", "broker_trading_day": "2026-09-08",
                       "target_date": "2026-09-08", "vt_orderid": "CTP.1_2_3"})

    details = [position_detail(InstrumentID="rb2610", ExchangeID="SHFE", OpenDate="20260907", Volume=2),
               position_detail(InstrumentID="rb2610", ExchangeID="SHFE", TradeID="T2", Volume=2)]
    positions = [raw_position(InstrumentID="rb2610", ExchangeID="SHFE", PositionDate="1", Position=2, TodayPosition=2),
                 raw_position(InstrumentID="rb2610", ExchangeID="SHFE", PositionDate="2", Position=2, TodayPosition=0, YdPosition=2)]
    result, _, td_api, rows, physical, _ = run_close_gate(monkeypatch, change=change, details=details, position_rows=positions)
    assert result["confirmed"], result["blockers"]
    children = [copy.deepcopy(physical[0]), copy.deepcopy(physical[0])]
    children[0].offset = stage931.Offset.CLOSETODAY
    children[1].offset = stage931.Offset.CLOSEYESTERDAY
    for child in children:
        child.volume = 2
    row, *rest = close_case()
    change(row, *rest)
    funds = stage931._final_open_funds_margin_gate(td_api, rows, children, max_wait_seconds=0, intent_row=row)
    assert funds["confirmed"], funds["blockers"]


@pytest.mark.parametrize("kind", ["detail", "trade", "position"])
def test_late_query_callback_before_proof_is_not_absorbed(monkeypatch, kind):
    original = FakeCloseTdApi.reqQryTrade if kind == "detail" else FakeCloseTdApi.reqQryOrder

    def late(self, query, reqid):
        if kind == "detail":
            self.onRspQryInvestorPositionDetail(position_detail(), {}, reqid - 1, True)
        elif kind == "trade" and self.calls[-1]["kind"] == "trade":
            self.onRspQryTrade(close_case()[1], {}, reqid - 1, True)
        elif kind == "position" and self.calls[-1]["kind"] == "position":
            self.onRspQryInvestorPosition(close_case()[3], {}, reqid - 1, True)
        return original(self, query, reqid)

    monkeypatch.setattr(FakeCloseTdApi, "reqQryTrade" if kind == "detail" else "reqQryOrder", late)
    result, funds, *_ = run_close_gate(monkeypatch)
    assert not result["confirmed"] and not funds["confirmed"]


@pytest.mark.parametrize("raw_first", [False, True])
def test_durable_metadata_sidecar_preserves_fill_replay_and_overnight_ownership(tmp_path, raw_first):
    from qmt_roll_official_live_broker_position_ownership import validate_position_detail_ownership

    _, raw, _, _, ledger = close_case()
    raw.update(TradeDate="20260907", TradeTime="21:05:00", TradingDay="20260908", HedgeFlag="1")
    queried, blockers = stage931._raw_ctp_trade_row(raw, reqid=7, row_index=0)
    assert not blockers
    queried.update(vt_symbol="SH611.CZCE", vt_orderid="CTP.1_2_3")
    evidence = stage931._raw_trade_ownership_evidence(SimpleNamespace(brokerid="fake-broker", userid="fake-user"), raw)
    bound = stage931._bind_trade_ownership_evidence({"_raw_trade_ownership_evidence": {("CZCE", "T1", "2026-09-07"): evidence}}, queried)
    context = {"target_date": "2026-09-08", "intent_id": "root-1", "fingerprint": "a" * 64,
               "row": {"vt_symbol": "SH611.CZCE", "source": "stage901_pending_order", "direction": "long", "offset": "open",
                       "root_position_id": "root-1", "position_epoch_id": "epoch-1"}}
    path = tmp_path / "ledger.jsonl"
    callbacks = [bound, queried] if raw_first else [queried, bound]
    for index, callback in enumerate(callbacks):
        result = stage931._persist_stage179_warm_broker_callback(kind="trade", callback=callback, context=context,
                                                                target_date="2026-09-08", ledger_path=path)
        assert all(not item.get("blocker") for item in result), result
        assert result[0]["idempotent_replay"] is bool(index)
    persisted = stage931.read_execution_ledger(path)
    assert len(persisted) == 2
    proof = validate_position_detail_ownership(
        execution_ledger_rows=persisted, position_detail_rows=[position_detail(OpenDate="20260907", TradingDay="20260909")],
        vt_symbol="SH611.CZCE", position_direction="long", broker_gross_volume=4,
        account_fingerprint=FINGERPRINT, trading_day="2026-09-09",
    )
    assert proof["confirmed"] and proof["yesterday_volume"] == 4


def test_callback_after_seal_validation_cannot_replace_proof_baseline(monkeypatch):
    import qmt_roll_official_live_broker_position_ownership as ownership

    captured = {}
    original_query = FakeCloseTdApi.reqQryInvestorPositionDetail
    original_validate = ownership.validate_position_detail_ownership

    def capture(self, query, reqid):
        captured.update(api=self, reqid=reqid)
        return original_query(self, query, reqid)

    def late(**kwargs):
        proof = original_validate(**kwargs)
        captured["api"].onRspQryInvestorPositionDetail({}, {"ErrorID": 999}, captured["reqid"], True)
        return proof

    monkeypatch.setattr(FakeCloseTdApi, "reqQryInvestorPositionDetail", capture)
    monkeypatch.setattr(ownership, "validate_position_detail_ownership", late)
    result, funds, *_ = run_close_gate(monkeypatch)
    assert not result["confirmed"] and not funds["confirmed"]


@pytest.mark.parametrize("valid_first", [False, True])
def test_invalid_raw_duplicate_revokes_cached_trade_metadata(valid_first):
    _, raw, _, _, _ = close_case()
    raw["HedgeFlag"] = "1"
    rows = fixtures.Stage931CtpReadinessTests._funds_rows()

    class NativeTradeApi(FakeCloseTdApi):
        def onRtnTrade(self, data):
            normalized, blockers = stage931._raw_ctp_trade_row(data, reqid=0, row_index=0)
            assert not blockers
            normalized.update(vt_symbol="SH611.CZCE", vt_orderid="CTP.1_2_3")
            rows["received_trade"] = stage931._bind_trade_ownership_evidence(rows, normalized)

    td_api = NativeTradeApi(fixtures.FakeClock(), trades=[], orders=[], positions=[])
    with stage931._instrument_ctp_readiness_callbacks(NativeTradeApi, rows):
        if valid_first:
            td_api.onRtnTrade(raw)
            assert rows["received_trade"]["broker_trade_metadata_source"] == "ctp_on_rtn_trade"
        td_api.onRtnTrade({**raw, "HedgeFlag": "2"})
        td_api.onRtnTrade(raw)
    assert "broker_trade_metadata_source" not in rows["received_trade"]
    assert rows["received_trade"]["broker_trade_metadata_conflict"] is True
