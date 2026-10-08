from __future__ import annotations

import copy
from dataclasses import asdict, replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

import pandas as pd
import pytest

os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))
import qmt_roll_official_live_broker_open_queue as queue
import qmt_roll_official_live_execution_ledger as ledger
import qmt_roll_official_live_intent_spool as spool
import run_qmt_roll_stage941_official_live_c9_detector as detector
import test_official_live_intent_spool as spool_fixtures
from test_official_live_broker_open_queue import inputs as queue_inputs
from test_stage905_broker_sizing import executor_inputs
from test_stage905_c9_cycle_intents import _FakeClock
import run_qmt_roll_stage905_official_live_executor_dry_run as stage905


@pytest.fixture
def scenario(request):
    factory = spool_fixtures.OfficialLiveIntentSpoolTest()
    factory.setUp()
    try:
        values = queue_inputs()
        sent_at = values["sent_intent"]["updated_epoch_ns"]
        raw = factory.intent("first", deadline_epoch_ns=sent_at + 20_000_000_000)
        payload = json.loads(raw["spool_payload_json"])
        payload.update(direction="long", root_position_id="root", position_cycle_id="root:0", intent_role="c9_initial_open",
                       broker_sizing=values["sent_intent"]["payload"]["broker_sizing"],
                       order_request={"symbol": "JM609", "exchange": "DCE", "offset": "open", "direction": "long", "volume": 1, "price": 1245.5})
        legacy_source = getattr(request, "param", "")
        if legacy_source:
            account_fingerprint = payload.pop("broker_sizing")["account_fingerprint"]
            if legacy_source == "payload":
                payload["account_fingerprint"] = account_fingerprint
            elif legacy_source == "order_request":
                payload["order_request"]["account_fingerprint"] = account_fingerprint
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        raw.update(spool_payload_json=encoded, payload_sha256=hashlib.sha256(encoded.encode()).hexdigest())
        factory.commit([raw], now_epoch_ns=sent_at - 3, now_monotonic_ns=sent_at - 3)
        lease = spool.lease_next(factory.connection, owner_id="executor", now_epoch_ns=sent_at - 2,
                                now_monotonic_ns=sent_at - 2, clock_domain_id="boot-a", lease_seconds=300)
        for before, after, stamp in [("leased", "sending", sent_at - 1), ("sending", "sent", sent_at)]:
            spool.transition_intent(factory.connection, intent_id="first", owner_id="executor", lease_token=lease.lease_token,
                                    expected_state=before, new_state=after, now_epoch_ns=stamp, now_monotonic_ns=stamp,
                                    clock_domain_id="boot-a", ledger_disposition=after)
        sent = asdict(spool._row_to_intent(factory.connection.execute("SELECT * FROM intents").fetchone()))
        fingerprint, normalized = ledger.intent_fingerprint(sent["target_date"], payload, payload["order_request"])
        for event in values["execution_ledger_rows"]:
            event.update(target_date=sent["target_date"], intent_fingerprint=fingerprint, intent_payload=normalized,
                         spool_lease_token=sent["lease_token"])
        if legacy_source == "ledger":
            values["execution_ledger_rows"][1]["account_fingerprint"] = account_fingerprint
        events = [ledger._with_record_checksum(event) for event in values["execution_ledger_rows"]]
        snapshot = values["broker_snapshot"]
        snapshot["orders"][0].update(vt_symbol="JM609.DCE", status="已撤销", volume="1", traded="0")
        snapshot.update(broker_sizing_sha256="a" * 64, artifacts={name: {"sha256": "b" * 64} for name in ("orders", "positions", "trades")})
        now_ns = int(values["now"].timestamp() * 1_000_000_000)
        yield {"connection": factory.connection, "path": factory.path, "sent_intent": sent,
               "broker_snapshot": snapshot, "execution_ledger_rows": events, "now": values["now"],
               "clock": _FakeClock(epoch_ns=now_ns, monotonic_ns=now_ns, domain="boot-a")}
    finally:
        factory.doCleanups()


def proof_for(values):
    return queue.build_sent_open_reconciliation_proof(**{key: values[key] for key in
        ("sent_intent", "broker_snapshot", "execution_ledger_rows", "now")})


def reconcile(values, proof=None):
    return spool.reconcile_sent_open(
        values["connection"], evidence=proof_for(values) if proof is None else proof,
        broker_snapshot=values["broker_snapshot"], execution_ledger_rows=values["execution_ledger_rows"],
        now_epoch_ns=values["clock"].epoch_ns(), now_monotonic_ns=values["clock"].monotonic_ns(), clock_domain_id="boot-a")


def test_persistent_reconciliation_api_exists():
    assert callable(getattr(spool, "reconcile_sent_open", None))


def test_proof_and_terminal_state_survive_reopen(scenario):
    before = scenario["sent_intent"]
    proof = proof_for(scenario)
    result = reconcile(scenario, proof)
    assert result.state == "reconciled"
    assert result.payload_sha256 == before["payload_sha256"]
    assert not result.lease_token
    connection = spool.open_spool(scenario["path"])
    try:
        row = connection.execute("SELECT * FROM intents").fetchone()
        assert spool._row_to_intent(row).state == "reconciled"
        assert json.loads(row["recovery_evidence_json"])["proof"] == proof
        assert proof["vt_orderids"] == ["CTP.1_2_3"]
        assert proof["payload_sha256"] == before["payload_sha256"]
        assert proof["ledger_checksum_sha256"] == scenario["execution_ledger_rows"][-1]["record_checksum"]
        assert proof["snapshot_generation_uuid"] == scenario["broker_snapshot"]["generation_uuid"]
        assert detector._broker_snapshot_watermark(connection) == scenario["clock"].epoch_ns()
    finally:
        connection.close()


@pytest.mark.parametrize("field,value", [("payload_sha256", "c" * 64), ("lease_token", "wrong"),
    ("snapshot_generation_uuid", "old"), ("snapshot_sha256", "c" * 64), ("ledger_checksum_sha256", "c" * 64),
    ("vt_orderids", []), ("sent_state_revision", 999)])
def test_wrong_proof_never_changes_state(scenario, field, value):
    proof = proof_for(scenario)
    proof[field] = value
    with pytest.raises(spool.SpoolError):
        reconcile(scenario, proof)
    row = scenario["connection"].execute("SELECT * FROM intents").fetchone()
    assert row["state"] == "sent"
    assert row["recovery_evidence_json"] == ""
    assert row["state_revision"] == scenario["sent_intent"]["state_revision"]


def test_changed_snapshot_after_proof_is_rejected(scenario):
    proof = proof_for(scenario)
    scenario["broker_snapshot"]["orders"][0]["status"] = "未成交"
    with pytest.raises(spool.SpoolError):
        reconcile(scenario, proof)
    assert scenario["connection"].execute("SELECT state FROM intents").fetchone()[0] == "sent"


def test_concurrent_state_revision_change_rejects_stale_proof(scenario):
    proof = proof_for(scenario)
    scenario["connection"].execute("UPDATE intents SET state_revision=state_revision+1")
    with pytest.raises(spool.SpoolError):
        reconcile(scenario, proof)
    assert scenario["connection"].execute("SELECT state FROM intents").fetchone()[0] == "sent"


def test_transaction_failure_rolls_back_both_proof_and_terminal(scenario):
    scenario["connection"].execute("CREATE TEMP TRIGGER fail_reconcile AFTER UPDATE OF state ON intents WHEN NEW.state='reconciled' BEGIN SELECT RAISE(ABORT, 'injected_crash'); END")
    with pytest.raises(spool.SpoolStorageError):
        reconcile(scenario)
    row = scenario["connection"].execute("SELECT state,recovery_evidence_json FROM intents").fetchone()
    assert tuple(row) == ("sent", "")
    scenario["connection"].execute("DROP TRIGGER fail_reconcile")
    assert reconcile(scenario).state == "reconciled"


def test_corrupted_spool_payload_is_not_reconciled(scenario):
    proof = proof_for(scenario)
    scenario["connection"].execute("UPDATE intents SET payload_sha256=?", ("f" * 64,))
    with pytest.raises(spool.SpoolValidationError):
        reconcile(scenario, proof)


@pytest.mark.parametrize("scenario", ["", "ledger"], indirect=True)
def test_reconciled_yesterday_allows_new_open_with_empty_orders_today(scenario):
    reconcile(scenario)
    existing, blocker = detector._broker_open_queue_state(scenario["connection"], target_date="2026-09-09")
    assert not blocker and not existing
    base = executor_inputs()
    snapshot = {**base.broker_account, "generated_at": "2026-09-09T09:00:30+08:00", "query_started_at": "2026-09-09T09:00:10+08:00", "positions": [], "orders": [], "trades": []}
    inputs = replace(base, broker_account=snapshot, entry_risk=base.entry_risk.assign(date="2026-09-09"))
    result = stage905.run_executor_dry_run("2026-09-09", snapshots=inputs, stage904_actions=pd.DataFrame(),
        stage904_summary={"target_date": "2026-09-09", "action_count": 0, "close_dry_run_count": 0,
            "retry_open_dry_run_count": 0, "retry_watch_count": 0, "blocked_count": 0,
            "order_api_called_count": 0, "durable_batch_cursor": {}},
        existing_open_intent_ids=tuple(existing), open_sizing_blocker=blocker,
        broker_snapshot_not_before_epoch_ns=detector._broker_snapshot_watermark(scenario["connection"]),
        clock=_FakeClock(epoch_ns=int(datetime.fromisoformat("2026-09-09T09:01:00+08:00").timestamp()*1e9), monotonic_ns=1),
        write_compat_outputs=False)
    assert result.summary["ready_count"] == 1


@pytest.mark.parametrize("scenario", ["", "ledger"], indirect=True)
def test_detector_reconciles_even_without_heartbeat_or_new_open(scenario, monkeypatch):
    monkeypatch.setattr(detector, "load_broker_account_snapshot", lambda *args, **kwargs: scenario["broker_snapshot"])
    monkeypatch.setattr(detector, "read_execution_ledger", lambda: scenario["execution_ledger_rows"])
    monkeypatch.setattr(detector, "run_executor_dry_run", lambda *args, **kwargs: pytest.fail("no new open should be required"))
    config = detector.DetectorConfig(target_date="2026-09-07", spool_path=scenario["path"],
        tick_stream_heartbeat_path=scenario["path"].parent / "missing-heartbeat.json")
    result = detector.run_detector_once(config, clock=scenario["clock"])
    assert result.status == "detector_feed_unready"
    assert scenario["connection"].execute("SELECT state FROM intents").fetchone()[0] == "reconciled"


def test_legacy_sent_requires_explicit_migration(scenario):
    values = copy.deepcopy(scenario["sent_intent"])
    values["payload"].pop("broker_sizing")
    with pytest.raises(ValueError, match="legacy_audit_migration_required"):
        queue.build_sent_open_reconciliation_proof(sent_intent=values, broker_snapshot=scenario["broker_snapshot"],
            execution_ledger_rows=scenario["execution_ledger_rows"], now=scenario["now"])


@pytest.mark.parametrize("scenario", ["payload", "order_request", "ledger"], indirect=True)
def test_legacy_proof_uses_existing_account_binding_without_rewriting_payload(scenario):
    before = scenario["connection"].execute("SELECT payload_json,payload_sha256 FROM intents").fetchone()
    proof = proof_for(scenario)
    assert proof["kind"] == "legacy_sent_open_broker_reconciliation_v1"
    assert proof["migration"]["prior_broker_sizing_present"] is False
    assert proof["migration"]["account_binding_sources"]
    assert proof["migration"]["owned_order_ledger_checksums"]
    assert not queue.evaluate_sent_open_budget_release(**{key: scenario[key] for key in
        ("sent_intent", "broker_snapshot", "execution_ledger_rows", "now")})["budget_released"]
    assert reconcile(scenario, proof).state == "reconciled"
    connection = spool.open_spool(scenario["path"])
    try:
        row = connection.execute("SELECT * FROM intents").fetchone()
        assert (row["payload_json"], row["payload_sha256"]) == tuple(before)
        assert "broker_sizing" not in json.loads(row["payload_json"])
        assert json.loads(row["recovery_evidence_json"])["proof"] == proof
        assert not detector._broker_open_queue_state(connection, target_date="2026-09-09")[1]
    finally:
        connection.close()


@pytest.mark.parametrize("scenario", ["ledger"], indirect=True)
@pytest.mark.parametrize("problem", ["missing_orders", "active_order", "wrong_order_account", "old_query",
    "stale_query", "duplicate_order", "missing_checksum", "wrong_checksum", "wrong_account",
    "wrong_lease", "wrong_intent_id", "order_owned_by_other_lease", "missing_account",
    "account_only_on_unrelated_event", "unknown_second_order", "missing_reservation"])
def test_legacy_incomplete_or_conflicting_evidence_never_reconciles(scenario, problem):
    snapshot = scenario["broker_snapshot"]
    events = scenario["execution_ledger_rows"]
    native = events[1]
    if problem == "missing_orders":
        snapshot["orders"] = []
    elif problem == "active_order":
        snapshot["orders"][0]["status"] = "未成交"
    elif problem == "wrong_order_account":
        snapshot["orders"][0]["account_id"] = "different"
    elif problem == "old_query":
        snapshot["query_started_at"] = "2026-09-08T10:00:00+08:00"
    elif problem == "stale_query":
        scenario["now"] = datetime.fromisoformat("2026-09-08T10:10:00+08:00")
    elif problem == "duplicate_order":
        snapshot["orders"].append(dict(snapshot["orders"][0]))
    elif problem == "missing_checksum":
        native.pop("record_checksum")
    elif problem == "wrong_checksum":
        native["record_checksum"] = "f" * 64
    elif problem == "wrong_account":
        native["account_fingerprint"] = "f" * 64
    elif problem == "wrong_lease":
        native["spool_lease_token"] = "another-lease"
    elif problem == "wrong_intent_id":
        native["intent_id"] = "another-intent"
    elif problem == "order_owned_by_other_lease":
        events.append(ledger._with_record_checksum({**native, "spool_lease_token": "another-lease"}))
    elif problem == "missing_account":
        native.pop("account_fingerprint")
    elif problem == "account_only_on_unrelated_event":
        events.append(ledger._with_record_checksum({**native, "vt_orderid": "CTP.unrelated", "spool_lease_token": "another-lease"}))
        native.pop("account_fingerprint")
    elif problem == "unknown_second_order":
        events.append(ledger._with_record_checksum({**native, "vt_orderid": "CTP.missing"}))
    elif problem == "missing_reservation":
        events.pop(0)
    if problem not in {"missing_checksum", "wrong_checksum"}:
        scenario["execution_ledger_rows"] = [ledger._with_record_checksum(event) for event in events]
    with pytest.raises(ValueError):
        proof_for(scenario)
    row = scenario["connection"].execute("SELECT state,recovery_evidence_json FROM intents").fetchone()
    assert tuple(row) == ("sent", "")


@pytest.mark.parametrize("scenario", ["ledger"], indirect=True)
def test_legacy_proof_migration_metadata_cannot_be_tampered(scenario):
    proof = proof_for(scenario)
    proof["migration"]["account_binding_sources"] = ["operator_adopt"]
    with pytest.raises(spool.SpoolTransitionError, match="proof_mismatch"):
        reconcile(scenario, proof)
    assert tuple(scenario["connection"].execute("SELECT state,recovery_evidence_json FROM intents").fetchone()) == ("sent", "")


@pytest.mark.parametrize("scenario", ["ledger"], indirect=True)
def test_legacy_migration_rolls_back_proof_and_state_together(scenario):
    scenario["connection"].execute("CREATE TEMP TRIGGER fail_legacy AFTER UPDATE OF state ON intents WHEN NEW.state='reconciled' BEGIN SELECT RAISE(ABORT, 'injected_crash'); END")
    with pytest.raises(spool.SpoolStorageError):
        reconcile(scenario)
    assert tuple(scenario["connection"].execute("SELECT state,recovery_evidence_json FROM intents").fetchone()) == ("sent", "")


@pytest.mark.parametrize("scenario", ["ledger"], indirect=True)
def test_legacy_atomic_reconcile_rechecks_ledger_account_after_proof(scenario):
    proof = proof_for(scenario)
    scenario["execution_ledger_rows"][1]["account_fingerprint"] = "f" * 64
    scenario["execution_ledger_rows"] = [ledger._with_record_checksum(event) for event in scenario["execution_ledger_rows"]]
    with pytest.raises(spool.SpoolValidationError, match="account_binding_mismatch"):
        reconcile(scenario, proof)
    assert tuple(scenario["connection"].execute("SELECT state,recovery_evidence_json FROM intents").fetchone()) == ("sent", "")


@pytest.mark.parametrize("scenario", ["payload"], indirect=True)
def test_legacy_conflicting_ledger_account_cannot_override_immutable_binding(scenario):
    scenario["execution_ledger_rows"][1]["account_fingerprint"] = "f" * 64
    scenario["execution_ledger_rows"] = [ledger._with_record_checksum(event) for event in scenario["execution_ledger_rows"]]
    with pytest.raises(ValueError, match="account_binding_mismatch"):
        proof_for(scenario)


@pytest.mark.parametrize("scenario", ["ledger"], indirect=True)
@pytest.mark.parametrize("status,traded", [("已撤销", "0"), ("cancelled", "1"), ("ALL_TRADED", "2")])
def test_legacy_partial_or_full_fill_terminal_preserves_real_snapshot(scenario, status, traded):
    snapshot = scenario["broker_snapshot"]
    snapshot["orders"][0].update(volume="2", traded=traded, status=status)
    before = copy.deepcopy(snapshot)
    assert reconcile(scenario).state == "reconciled"
    assert snapshot == before


@pytest.mark.parametrize("scenario", ["ledger"], indirect=True)
def test_legacy_multiple_reservations_do_not_hide_earlier_owned_orders(scenario):
    scenario["execution_ledger_rows"].extend(copy.deepcopy(scenario["execution_ledger_rows"]))
    with pytest.raises(ValueError, match="legacy_reservation_ambiguous"):
        proof_for(scenario)
