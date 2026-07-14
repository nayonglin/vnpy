from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_c9_intraday_state import RETRY_OPEN_ACTION_ROLE
from qmt_roll_official_live_late_retry_fill import build_late_retry_fill_reconciliation
from qmt_roll_official_live_execution_ledger import (
    append_reconciled_execution_fill_once,
    read_execution_ledger,
)


class LateRetryFillReconciliationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(tz=ZoneInfo("Asia/Shanghai")).replace(microsecond=0)
        self.reclaim_at = self.now - timedelta(seconds=30)
        self.send_at = self.now - timedelta(seconds=25)
        self.evidence_at = self.now - timedelta(seconds=20)
        self.fill_at = self.now - timedelta(seconds=24)
        self.root = "c9root-jm-short"
        self.epoch = "c9epoch-original"
        self.cycle = f"{self.root}:cycle1"
        self.fingerprint = "fp-retry"
        self.orderid = "CTP.retry-unknown"
        self.target_date = self.now.date().isoformat()
        self.broker_trading_day = self.now.strftime("%Y%m%d")
        self.generation = "11111111-2222-4333-8444-555555555555"
        self.account_fingerprint = "a" * 64

    def iso(self, value: datetime) -> str:
        return value.isoformat()

    def state(self) -> dict:
        return {
            "phase": "retry_reclaim_latched",
            "target_date": self.target_date,
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "root_position_id": self.root,
            "position_epoch_id": self.epoch,
            "position_cycle_id": self.cycle,
            "retry_reclaim_latched_at": self.iso(self.reclaim_at),
        }

    def base(self, *, orderids: list[str] | None = None) -> dict:
        return {
            "position_source": "broker",
            "volume": 1.0,
            "broker_epoch_reconstruction_complete": 1,
            "broker_open_trade_volume": 1.0,
            "broker_fill_price": 1246.0,
            "broker_position_epoch_entry_at": self.iso(self.fill_at),
            "broker_position_epoch_order_ids": orderids or [self.orderid],
            "broker_position_epoch_order_identity_complete": 1,
            "broker_position_epoch_trade_identities": ["ctp:stable-late-retry-fill"],
            "broker_position_epoch_trade_identity_complete": 1,
            "broker_position_epoch_reported_date": self.fill_at.date().isoformat(),
            "broker_query_generation_uuid": self.generation,
            "broker_query_trading_day": self.broker_trading_day,
            "broker_trade_snapshot_rows": 1,
        }

    def summary(self) -> dict:
        generated_at = self.iso(self.now - timedelta(seconds=1))
        query = {
            "request_sent": True,
            "request_return_code": 0,
            "callback_count": 2,
            "data_callback_count": 1,
            "last_seen": True,
            "error_rows": 0,
            "complete": True,
        }
        queries = {
            "orders": {
                **query,
                "reqid": 101,
                "request_sent_at": self.iso(self.evidence_at + timedelta(seconds=1)),
                "completed_at": self.iso(self.evidence_at + timedelta(seconds=2)),
            },
            "trades": {
                **query,
                "reqid": 102,
                "request_sent_at": self.iso(self.evidence_at + timedelta(seconds=3)),
                "completed_at": self.iso(self.evidence_at + timedelta(seconds=4)),
            },
            "positions": {
                **query,
                "reqid": 103,
                "request_sent_at": self.iso(self.evidence_at + timedelta(seconds=5)),
                "completed_at": self.iso(self.evidence_at + timedelta(seconds=6)),
                "position_raw_row_count": 1,
                "position_normalized_row_count": 1,
                "position_invalid_row_count": 0,
                "position_normalization_complete": True,
            },
        }
        artifacts = {
            "orders": {"row_count": 1, "sha256": "1" * 64},
            "trades": {"row_count": 1, "sha256": "2" * 64},
            "positions": {"row_count": 1, "sha256": "3" * 64},
        }
        return {
            "status": "readonly_snapshots_received",
            "generated_at": generated_at,
            "query_generation_uuid": self.generation,
            "broker_trading_day": self.broker_trading_day,
            "broker_query_bundle": {
                "schema_version": 1,
                "generation_uuid": self.generation,
                "generated_at": generated_at,
                "broker_trading_day": self.broker_trading_day,
                "account": {
                    "account_fingerprint": self.account_fingerprint,
                    "login_account_match": True,
                    "response_account_match": True,
                },
                "queries": queries,
                "trade_order_join_complete": True,
                "trade_identity_complete": True,
                "complete": True,
                "artifacts": artifacts,
            },
            "broker_snapshot": {
                "position_snapshot_state": "positions_received",
                "position_query_last_seen": True,
                "position_query_error_rows": 0,
            },
        }

    def manifest(self, summary: dict | None = None) -> dict:
        effective_summary = summary or self.summary()
        bundle = effective_summary["broker_query_bundle"]
        return {
            "schema_version": 1,
            "generation_uuid": self.generation,
            "generated_at": effective_summary["generated_at"],
            "broker_trading_day": self.broker_trading_day,
            "account": dict(bundle["account"]),
            "queries": {
                "orders": dict(bundle["queries"]["orders"]),
                "trades": dict(bundle["queries"]["trades"]),
                "positions": dict(bundle["queries"]["positions"]),
            },
            "trade_order_join_complete": True,
            "trade_identity_complete": True,
            "complete": True,
            "artifacts": {
                name: dict(value) for name, value in bundle["artifacts"].items()
            },
            "summary_binding": {
                "generated_at": effective_summary["generated_at"],
                "status": effective_summary["status"],
            },
        }

    def evidence(self) -> dict:
        return {
            "artifacts": {
                "orders": {
                    "row_count": 1,
                    "sha256": "1" * 64,
                    "generation_uuids": [self.generation],
                    "account_fingerprints": [self.account_fingerprint],
                },
                "trades": {
                    "row_count": 1,
                    "sha256": "2" * 64,
                    "generation_uuids": [self.generation],
                    "account_fingerprints": [self.account_fingerprint],
                    "order_mapping_complete": True,
                    "stable_trade_identity_complete": True,
                },
                "positions": {
                    "row_count": 1,
                    "sha256": "3" * 64,
                    "generation_uuids": [self.generation],
                    "account_fingerprints": [self.account_fingerprint],
                },
            }
        }

    def ledger(self, *, second_send: bool = False) -> list[dict]:
        payload = {
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "offset": "open",
            "root_position_id": self.root,
            "position_epoch_id": self.epoch,
            "position_cycle_id": self.cycle,
            "position_cycle_no": 1,
            "intent_role": RETRY_OPEN_ACTION_ROLE,
        }
        rows = [
            {
                "event_type": "reserved",
                "target_date": self.target_date,
                "generated_at": self.iso(self.send_at - timedelta(seconds=1)),
                "intent_fingerprint": self.fingerprint,
                "intent_payload": payload,
            },
            {
                "event_type": "send_order_called",
                "target_date": self.target_date,
                "generated_at": self.iso(self.send_at),
                "intent_id": "STAGE905-C9RETRY-1",
                "intent_fingerprint": self.fingerprint,
                "vt_symbol": "JM609.DCE",
                "vt_orderid": self.orderid,
                "direction": "short",
                "offset": "open",
                "volume": 2.0,
                **{key: value for key, value in payload.items() if key not in {"vt_symbol", "direction", "offset"}},
            },
            {
                "event_type": "residual_order_unknown_after_cancel",
                "target_date": self.target_date,
                "generated_at": self.iso(self.evidence_at),
                "intent_fingerprint": self.fingerprint,
                "vt_orderid": self.orderid,
                "residual_volume": 2.0,
                **payload,
            },
        ]
        if second_send:
            rows.append(
                {
                    **rows[1],
                    "generated_at": self.iso(self.send_at + timedelta(seconds=1)),
                    "intent_fingerprint": "fp-second",
                    "vt_orderid": "CTP.second-retry",
                }
            )
        return rows

    def decide(
        self,
        *,
        base: dict | None = None,
        ledger: list[dict] | None = None,
        summary: dict | None = None,
        manifest: dict | None = None,
        evidence: dict | None = None,
    ) -> dict:
        effective_summary = summary or self.summary()
        return build_late_retry_fill_reconciliation(
            state=self.state(),
            base=base or self.base(),
            ledger_rows=ledger or self.ledger(),
            readonly_summary=effective_summary,
            bundle_manifest=(
                self.manifest(effective_summary) if manifest is None else manifest
            ),
            bundle_evidence=self.evidence() if evidence is None else evidence,
            now=self.now,
        )

    def test_unique_unknown_retry_fill_is_reconciled_into_original_cycle(self) -> None:
        result = self.decide()

        self.assertEqual("reconciled", result["status"])
        event = result["ledger_event"]
        self.assertEqual(self.epoch, event["position_epoch_id"])
        self.assertEqual(self.cycle, event["position_cycle_id"])
        self.assertEqual(RETRY_OPEN_ACTION_ROLE, event["intent_role"])
        self.assertEqual(1.0, event["trade_volume_delta"])
        self.assertEqual(1246.0, event["price"])
        self.assertEqual(self.orderid, event["vt_orderid"])
        self.assertEqual(1, event["broker_reconciled_late_retry_fill"])
        self.assertEqual(self.iso(self.send_at), event["generated_at"])
        self.assertEqual(self.iso(self.fill_at), event["broker_trade_at"])

    def test_manual_reopen_order_id_is_not_adopted(self) -> None:
        result = self.decide(base=self.base(orderids=["CTP.manual-reopen"]))

        self.assertEqual("blocked", result["status"])
        self.assertEqual(1, result["manual_intervention_required"])
        self.assertIn("match_not_unique", result["reason"])

    def test_multiple_retry_sends_are_ambiguous(self) -> None:
        result = self.decide(ledger=self.ledger(second_send=True))

        self.assertEqual("blocked", result["status"])
        self.assertIn("multiple_retry_open_orders", result["reason"])

    def test_mixed_broker_order_ids_are_ambiguous(self) -> None:
        result = self.decide(
            base=self.base(orderids=[self.orderid, "CTP.manual-open"])
        )

        self.assertEqual("blocked", result["status"])
        self.assertIn("order_id_ambiguous", result["reason"])

    def test_future_snapshot_is_not_fresh(self) -> None:
        summary = self.summary()
        summary["generated_at"] = self.iso(self.now + timedelta(minutes=1))
        summary["broker_query_bundle"]["generated_at"] = summary["generated_at"]

        result = self.decide(summary=summary)

        self.assertEqual("blocked", result["status"])
        self.assertIn("snapshot_age_invalid", result["reason"])

    def test_late_publish_cannot_hide_query_sent_before_unknown_evidence(self) -> None:
        summary = self.summary()
        for index, name in enumerate(("orders", "trades", "positions")):
            query = summary["broker_query_bundle"]["queries"][name]
            query["request_sent_at"] = self.iso(
                self.evidence_at - timedelta(seconds=6 - index * 2)
            )
            query["completed_at"] = self.iso(
                self.evidence_at - timedelta(seconds=5 - index * 2)
            )
        manifest = self.manifest(summary)

        result = self.decide(summary=summary, manifest=manifest)

        self.assertEqual("blocked", result["status"])
        self.assertIn(
            "query_request_precedes_unknown_order_evidence",
            result["reason"],
        )

    def test_legacy_top_level_row_counts_are_not_bundle_interface(self) -> None:
        summary = self.summary()
        self.assertNotIn("row_counts", summary)

        result = self.decide(summary=summary)

        self.assertEqual("reconciled", result["status"])

    def test_same_count_stale_trade_file_hash_is_blocked(self) -> None:
        evidence = self.evidence()
        evidence["artifacts"]["trades"]["sha256"] = "9" * 64

        result = self.decide(evidence=evidence)

        self.assertEqual("blocked", result["status"])
        self.assertIn("trades_count_or_hash_mismatch", result["reason"])

    def test_incomplete_trade_query_generation_is_blocked(self) -> None:
        summary = self.summary()
        summary["broker_query_bundle"]["queries"]["trades"]["last_seen"] = False
        summary["broker_query_bundle"]["queries"]["trades"]["complete"] = False
        manifest = self.manifest(summary)
        manifest["queries"]["trades"] = dict(
            summary["broker_query_bundle"]["queries"]["trades"]
        )
        manifest["complete"] = False

        result = self.decide(summary=summary, manifest=manifest)

        self.assertEqual("blocked", result["status"])
        self.assertIn("trades_query_generation_incomplete", result["reason"])

    def test_incomplete_position_query_generation_is_blocked(self) -> None:
        summary = self.summary()
        summary["broker_query_bundle"]["queries"]["positions"]["last_seen"] = False
        summary["broker_query_bundle"]["queries"]["positions"]["complete"] = False
        manifest = self.manifest(summary)
        manifest["queries"]["positions"] = dict(
            summary["broker_query_bundle"]["queries"]["positions"]
        )
        manifest["complete"] = False

        result = self.decide(summary=summary, manifest=manifest)

        self.assertEqual("blocked", result["status"])
        self.assertIn("positions_query_generation_incomplete", result["reason"])

    def test_position_row_from_another_generation_is_blocked(self) -> None:
        evidence = self.evidence()
        evidence["artifacts"]["positions"]["generation_uuids"] = [
            "99999999-2222-4333-8444-555555555555"
        ]

        result = self.decide(evidence=evidence)

        self.assertEqual("blocked", result["status"])
        self.assertIn("positions_row_generation_mismatch", result["reason"])

    def test_order_reported_unpriced_fill_can_be_priced_by_unique_broker_trade(self) -> None:
        ledger = self.ledger()
        ledger[-1] = {
            **ledger[-1],
            "event_type": "fill_reconciliation_pending",
            "order_traded_volume": 1.0,
            "trade_event_volume": 0.0,
            "unpriced_volume": 1.0,
            "residual_volume": 1.0,
        }

        result = self.decide(ledger=ledger)

        self.assertEqual("reconciled", result["status"])
        self.assertEqual(
            "fill_reconciliation_pending",
            result["ledger_event"]["unknown_order_evidence_type"],
        )

    def test_existing_priced_fill_is_left_to_normal_ledger_path(self) -> None:
        ledger = self.ledger()
        ledger.insert(
            -1,
            {
                **ledger[1],
                "event_type": "filled_or_part_filled",
                "generated_at": self.iso(self.fill_at),
                "trade_volume_delta": 1.0,
                "price": 1246.0,
                "fill_price_source": "event_trade_weighted_avg",
            },
        )

        result = self.decide(ledger=ledger)

        self.assertEqual("not_applicable", result["status"])
        self.assertIn("already_present", result["reason"])

    def test_priced_fill_after_unknown_evidence_is_not_backfilled_again(self) -> None:
        ledger = self.ledger()
        ledger.append(
            {
                **ledger[1],
                "event_type": "filled_or_part_filled",
                "generated_at": self.iso(self.evidence_at + timedelta(seconds=1)),
                "trade_volume_delta": 1.0,
                "price": 1246.0,
                "fill_price_source": "event_trade_weighted_avg",
            }
        )

        result = self.decide(ledger=ledger)

        self.assertEqual("not_applicable", result["status"])
        self.assertIn("already_present", result["reason"])

    def test_unstable_broker_row_trade_identity_is_blocked(self) -> None:
        base = self.base()
        base["broker_position_epoch_trade_identity_complete"] = 0
        base["broker_position_epoch_trade_identities"] = []

        result = self.decide(base=base)

        self.assertEqual("blocked", result["status"])
        self.assertIn("trade_identity_incomplete", result["reason"])

    def test_trade_without_order_sysid_mapping_is_blocked(self) -> None:
        evidence = self.evidence()
        evidence["artifacts"]["trades"]["order_mapping_complete"] = False

        result = self.decide(evidence=evidence)

        self.assertEqual("blocked", result["status"])
        self.assertIn("order_mapping_incomplete", result["reason"])

    def test_friday_target_accepts_monday_broker_trading_day(self) -> None:
        tz = ZoneInfo("Asia/Shanghai")
        self.now = datetime(2026, 7, 13, 9, 1, 0, tzinfo=tz)
        self.reclaim_at = self.now - timedelta(seconds=30)
        self.send_at = self.now - timedelta(seconds=25)
        self.fill_at = self.now - timedelta(seconds=24)
        self.evidence_at = self.now - timedelta(seconds=20)
        self.target_date = "2026-07-10"
        self.broker_trading_day = "20260713"

        result = self.decide()

        self.assertEqual("reconciled", result["status"])
        self.assertEqual("20260713", result["ledger_event"]["broker_trading_day"])

    def test_send_without_durable_reservation_is_rejected(self) -> None:
        ledger = self.ledger()[1:]

        result = self.decide(ledger=ledger)

        self.assertEqual("blocked", result["status"])
        self.assertIn("reservation_missing", result["reason"])

    def test_fill_cannot_exceed_unknown_residual(self) -> None:
        ledger = self.ledger()
        ledger[-1]["residual_volume"] = 0.5

        result = self.decide(ledger=ledger)

        self.assertEqual("blocked", result["status"])
        self.assertIn("exceeds_unknown_residual", result["reason"])

    def test_reconciled_fill_append_is_idempotent(self) -> None:
        event = self.decide()["ledger_event"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.ndjson"
            first = append_reconciled_execution_fill_once(event, path)
            second = append_reconciled_execution_fill_once(event, path)
            rows = read_execution_ledger(path)

        self.assertTrue(first["appended"])
        self.assertFalse(second["appended"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(1, len(rows))
        self.assertEqual(
            event["broker_reconciliation_key"],
            rows[0]["broker_reconciliation_key"],
        )

    def test_reconciled_fill_refuses_corrupt_ledger(self) -> None:
        event = self.decide()["ledger_event"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.ndjson"
            path.write_text(
                json.dumps({"event_type": "bad", "record_checksum": "wrong"})
                + "\n",
                encoding="utf-8",
            )
            result = append_reconciled_execution_fill_once(event, path)

        self.assertFalse(result["appended"])
        self.assertIn("ledger_integrity_error", result["blocker"])


if __name__ == "__main__":
    unittest.main()
