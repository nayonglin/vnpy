from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import copy
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage904_official_live_c9_intraday_monitor as stage904
import run_ctp_stage608_readonly_tick_snapshot_probe as stage608
from qmt_roll_official_live_c9_intraday_state import (
    INITIAL_STOP_ACTION_ROLE,
    RETRY_OPEN_ACTION_ROLE,
    RETRY_STOP_ACTION_ROLE,
)


class Stage904DurableStateIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now().replace(microsecond=0)
        self.entry_at = self.now - timedelta(seconds=20)
        self.feed_started_at = self.entry_at - timedelta(seconds=5)
        self.target_date = self.now.date().isoformat()

    def iso(self, value: datetime) -> str:
        return value.isoformat()

    def heartbeat(self) -> dict:
        return {
            "stream_ready": True,
            "generated_at": self.iso(self.now),
            "feed_session_id": "feed-a",
            "feed_started_at": self.iso(self.feed_started_at),
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 100,
                }
            },
        }

    def readonly_flat(self, generated_at: datetime) -> dict:
        return {
            "status": "readonly_snapshots_received",
            "generated_at": self.iso(generated_at),
            "broker_snapshot": {
                "position_snapshot_state": "confirmed_flat",
                "position_rows": 0,
                "nonzero_position_rows": 0,
                "position_query_callback_rows": 1,
                "position_query_last_seen": True,
                "position_query_error_rows": 0,
            },
        }

    def readonly_position(self, volume: float) -> tuple[dict, pd.DataFrame]:
        frame = pd.DataFrame(
            [
                {
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "volume": volume,
                    "frozen": 0.0,
                }
            ]
        )
        summary = {
            "status": "readonly_snapshots_received",
            "generated_at": self.iso(self.now),
            "broker_snapshot": {
                "position_snapshot_state": "positions_received",
                "position_rows": 1,
                "nonzero_position_rows": 1,
                "position_query_callback_rows": 2,
                "position_query_last_seen": True,
                "position_query_error_rows": 0,
            },
        }
        return summary, frame

    def complete_query_bundle(
        self,
        *,
        trade_count: int,
        order_count: int | None = None,
        position_count: int = 1,
        generation: str = "11111111-2222-4333-8444-555555555555",
        broker_trading_day: str | None = None,
        query_completed_at: datetime | None = None,
    ) -> tuple[dict, dict, dict]:
        effective_order_count = trade_count if order_count is None else order_count
        trading_day = broker_trading_day or self.now.strftime("%Y%m%d")
        account_fingerprint = "a" * 64
        completion = query_completed_at or (self.now - timedelta(seconds=1))
        query_clock = completion - timedelta(seconds=5)
        base_query = {
            "request_sent": True,
            "request_return_code": 0,
            "last_seen": True,
            "error_rows": 0,
            "complete": True,
        }
        queries = {
            "orders": {
                **base_query,
                "reqid": 101,
                "request_sent_at": self.iso(query_clock),
                "completed_at": self.iso(query_clock + timedelta(seconds=1)),
                "callback_count": max(1, effective_order_count + 1),
                "data_callback_count": effective_order_count,
            },
            "trades": {
                **base_query,
                "reqid": 102,
                "request_sent_at": self.iso(query_clock + timedelta(seconds=2)),
                "completed_at": self.iso(query_clock + timedelta(seconds=3)),
                "callback_count": max(1, trade_count + 1),
                "data_callback_count": trade_count,
            },
            "positions": {
                **base_query,
                "reqid": 103,
                "request_sent_at": self.iso(query_clock + timedelta(seconds=4)),
                "completed_at": self.iso(query_clock + timedelta(seconds=5)),
                "callback_count": max(1, position_count + 1),
                "data_callback_count": position_count,
                "position_raw_row_count": position_count,
                "position_normalized_row_count": position_count,
                "position_invalid_row_count": 0,
                "position_normalization_complete": True,
            },
        }
        artifacts = {
            "orders": {
                "row_count": effective_order_count,
                "sha256": "1" * 64,
            },
            "trades": {"row_count": trade_count, "sha256": "2" * 64},
            "positions": {"row_count": position_count, "sha256": "3" * 64},
        }
        account = {
            "account_fingerprint": account_fingerprint,
            "login_account_match": True,
            "response_account_match": True,
        }
        generated_at = self.iso(completion + timedelta(milliseconds=100))
        bundle = {
            "schema_version": 1,
            "generation_uuid": generation,
            "generated_at": generated_at,
            "broker_trading_day": trading_day,
            "account": account,
            "queries": queries,
            "trade_order_join_complete": True,
            "trade_identity_complete": True,
            "complete": True,
            "artifacts": artifacts,
        }
        summary = {
            "status": "readonly_snapshots_received",
            "generated_at": generated_at,
            "query_generation_uuid": generation,
            "broker_trading_day": trading_day,
            "broker_query_bundle": copy.deepcopy(bundle),
        }
        manifest = {
            **copy.deepcopy(bundle),
            "summary_binding": {
                "generated_at": generated_at,
                "status": summary["status"],
            },
        }
        evidence = {
            "artifacts": {
                "orders": {
                    **artifacts["orders"],
                    "generation_uuids": [generation] if effective_order_count else [],
                    "account_fingerprints": (
                        [account_fingerprint] if effective_order_count else []
                    ),
                },
                "trades": {
                    **artifacts["trades"],
                    "generation_uuids": [generation] if trade_count else [],
                    "account_fingerprints": [account_fingerprint] if trade_count else [],
                    "order_mapping_complete": True,
                    "stable_trade_identity_complete": True,
                },
                "positions": {
                    **artifacts["positions"],
                    "generation_uuids": [generation] if position_count else [],
                    "account_fingerprints": [account_fingerprint] if position_count else [],
                },
            }
        }
        return summary, manifest, evidence

    def bind_position_query_bundle(
        self,
        summary: dict,
        broker_positions: pd.DataFrame,
    ) -> tuple[dict, dict, dict]:
        completed_at = datetime.fromisoformat(summary["generated_at"])
        bound_summary, manifest, evidence = self.complete_query_bundle(
            trade_count=0,
            position_count=len(broker_positions.drop_duplicates()),
            query_completed_at=completed_at,
        )
        bound_summary["status"] = summary["status"]
        bound_summary["broker_snapshot"] = copy.deepcopy(summary["broker_snapshot"])
        manifest["summary_binding"]["status"] = summary["status"]
        return bound_summary, manifest, evidence

    def advance_flat_states(
        self,
        *,
        readonly_summary: dict,
        broker_positions: pd.DataFrame,
        **kwargs: object,
    ) -> list[dict]:
        bound_summary, manifest, evidence = self.bind_position_query_bundle(
            readonly_summary,
            broker_positions,
        )
        return stage904._advance_flat_states(
            readonly_summary=bound_summary,
            broker_positions=broker_positions,
            readonly_bundle_manifest=manifest,
            readonly_bundle_evidence=evidence,
            **kwargs,
        )

    def late_close_bundle(
        self,
        *,
        order_count: int = 1,
        completion: datetime | None = None,
    ) -> tuple[dict, dict, dict]:
        completed_at = completion or (self.now - timedelta(seconds=1))
        summary, manifest, evidence = self.complete_query_bundle(
            trade_count=0,
            order_count=order_count,
            position_count=0,
            query_completed_at=completed_at,
        )
        summary["broker_snapshot"] = copy.deepcopy(
            self.readonly_flat(completed_at)["broker_snapshot"]
        )
        return summary, manifest, evidence

    def late_close_identity(
        self,
        state: dict,
        *,
        intent_role: str = INITIAL_STOP_ACTION_ROLE,
    ) -> dict:
        return {
            "vt_symbol": state["vt_symbol"],
            "direction": "long",
            "offset": "close",
            "root_position_id": state["root_position_id"],
            "position_epoch_id": state["position_epoch_id"],
            "position_cycle_id": state["position_cycle_id"],
            "position_cycle_no": state["position_cycle_no"],
            "intent_role": intent_role,
        }

    def late_close_ledger_events(
        self,
        state: dict,
        *,
        fingerprint: str = "fp-late-initial-stop",
        vt_orderid: str = "CTP.9_99_904",
        volume: float = 2.0,
        traded: float | None = None,
        residual: float = 0.0,
        intent_role: str = INITIAL_STOP_ACTION_ROLE,
        include_reservation: bool = True,
        include_evidence: bool = True,
    ) -> list[dict]:
        send_at = self.now - timedelta(seconds=9)
        evidence_at = self.now - timedelta(seconds=7)
        identity = self.late_close_identity(state, intent_role=intent_role)
        rows: list[dict] = []
        if include_reservation:
            rows.append(
                {
                    "event_type": "reserved",
                    "target_date": self.target_date,
                    "generated_at": self.iso(send_at - timedelta(seconds=1)),
                    "intent_fingerprint": fingerprint,
                    "intent_payload": identity,
                }
            )
        rows.append(
            {
                "event_type": "send_order_called",
                "target_date": self.target_date,
                "generated_at": self.iso(send_at),
                "intent_id": "STAGE905-C9MON-late-close",
                "intent_fingerprint": fingerprint,
                "vt_orderid": vt_orderid,
                "volume": volume,
                **identity,
            }
        )
        if include_evidence:
            effective_traded = volume if traded is None else traded
            rows.append(
                {
                    "event_type": "fill_reconciliation_pending",
                    "target_date": self.target_date,
                    "generated_at": self.iso(evidence_at),
                    "intent_fingerprint": fingerprint,
                    "vt_orderid": vt_orderid,
                    "order_traded_volume": effective_traded,
                    "trade_event_volume": 0.0,
                    "trade_event_priced_volume": 0.0,
                    "trade_event_total_volume": 0.0,
                    "unpriced_volume": effective_traded,
                    "residual_volume": residual,
                    **identity,
                }
            )
        return rows

    def late_close_broker_order(
        self,
        *,
        vt_orderid: str = "CTP.9_99_904",
        volume: float = 2.0,
        traded: float | None = None,
        status: str = "all traded",
        generation: str = "11111111-2222-4333-8444-555555555555",
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "query_generation_uuid": generation,
                    "broker_id": "9999",
                    "account_id": "stage904-test",
                    "vt_symbol": "JM609.DCE",
                    "direction": "long",
                    "offset": "close",
                    "volume": volume,
                    "traded": volume if traded is None else traded,
                    "status": status,
                    "vt_orderid": vt_orderid,
                    "stable_order_identity_complete": 1,
                }
            ]
        )

    def write_ledger(self, path: Path, rows: list[dict]) -> list[dict]:
        for row in rows:
            stage904.append_execution_ledger_event(row, path)
        return stage904.read_execution_ledger(path)

    def initial_stop_store(self) -> tuple[dict, dict, dict]:
        store = stage904._new_state_store(self.target_date)
        action = self.apply(store, self.ticks([(1, 1252.0)]))
        state = store["states"][action["root_position_id"]]
        self.assertEqual("initial_stop_latched", state["phase"])
        return store, state, action

    def run_late_close_advance(
        self,
        *,
        store: dict,
        ledger_rows: list[dict],
        ledger_path: Path,
        broker_orders: pd.DataFrame,
        summary: dict,
        manifest: dict,
        evidence: dict,
        journal_path: Path,
    ) -> list[dict]:
        return stage904._advance_flat_states(
            store=store,
            execution_ledger_rows=ledger_rows,
            broker_positions=pd.DataFrame(),
            broker_orders=broker_orders,
            readonly_summary=summary,
            readonly_bundle_manifest=manifest,
            readonly_bundle_evidence=evidence,
            ticks=self.ticks([(1, 1252.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=journal_path,
            max_tick_age_seconds=30,
            execution_ledger_path=ledger_path,
        )

    def base(self, *, fill_price: float = 1245.5, cycle_no: int = 0) -> dict:
        return {
            "target_date": self.target_date,
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "position_source": "broker",
            "volume": 2.0,
            "entry_day_active": 1,
            "entry_filled_at": self.iso(self.entry_at),
            "fill_price": fill_price,
            "initial_stop_price": 1258.0,
            "stage847_stop_price": 1251.75,
            "stage847_progress_price": 1239.25,
            "open_trade_id": "manual-jm-open",
            "ledger_open_intent_id": "",
            "entry_risk_date": self.target_date,
            "root_position_id": stage904.generate_root_position_id(
                target_date=self.target_date,
                vt_symbol="JM609.DCE",
                direction="short",
            ),
            "position_cycle_no": cycle_no,
            "live_price": fill_price,
            "monitor_action": "watch",
            "monitor_reason": "legacy_placeholder",
            "order_api_called": 0,
        }

    def ticks(self, values: list[tuple[int, float]]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": seq,
                    "received_at": self.iso(self.entry_at + timedelta(seconds=offset)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": price,
                    "bid_price_1": price,
                    "ask_price_1": price,
                }
                for seq, (offset, price) in enumerate(values, start=1)
            ]
        )

    def apply(
        self,
        store: dict,
        ticks: pd.DataFrame,
        ledger: list[dict] | None = None,
        base: dict | None = None,
        heartbeat: dict | None = None,
    ) -> dict:
        effective_base = base or self.base()
        readonly_summary, broker_positions = self.readonly_position(
            float(effective_base.get("volume", 0.0))
        )
        with tempfile.TemporaryDirectory() as tmp:
            return stage904._apply_state_to_position_action(
                effective_base,
                store=store,
                execution_ledger_rows=ledger or [],
                ticks=ticks,
                heartbeat=heartbeat or self.heartbeat(),
                journal_path=Path(tmp) / "journal.ndjson",
                readonly_summary=readonly_summary,
                broker_positions=broker_positions,
            )

    def test_progress_first_disarms_stop_in_same_batch_and_next_cycle(self) -> None:
        store = stage904._new_state_store(self.target_date)
        row = self.apply(store, self.ticks([(1, 1239.0), (2, 1252.0)]))
        self.assertEqual(row["monitor_action"], "watch_progress_hit_no_initial_stop")
        self.assertEqual(row["stage847_stop_price"], 1251.75)

        row = self.apply(store, self.ticks([(1, 1239.0), (2, 1252.0), (3, 1255.0)]))
        self.assertEqual(row["monitor_action"], "watch_progress_hit_no_initial_stop")
        self.assertEqual(row["state_phase"], "initial_progress_latched")

    def test_stop_action_latches_with_v2_identity_and_survives_recovery(self) -> None:
        store = stage904._new_state_store(self.target_date)
        row = self.apply(store, self.ticks([(1, 1252.0)]))
        self.assertEqual(row["monitor_action"], "close_dry_run")
        self.assertEqual(row["intent_role"], INITIAL_STOP_ACTION_ROLE)
        self.assertTrue(row["position_cycle_id"].endswith(":cycle0"))
        action_id = row["action_id"]

        row = self.apply(store, self.ticks([(1, 1252.0), (2, 1248.0)]))
        self.assertEqual(row["monitor_action"], "close_dry_run")
        self.assertEqual(row["action_id"], action_id)

    def test_flat_reclaim_retry_and_second_stop_keep_original_threshold(self) -> None:
        store = stage904._new_state_store(self.target_date)
        initial = self.apply(store, self.ticks([(1, 1252.0)]))
        root = initial["root_position_id"]
        epoch = initial["position_epoch_id"]
        cycle0 = initial["position_cycle_id"]
        close_at = self.entry_at + timedelta(seconds=2)
        flat_at = self.entry_at + timedelta(seconds=3)
        reclaim_at = self.entry_at + timedelta(seconds=4)
        ledger = [
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(close_at),
                "root_position_id": root,
                "position_epoch_id": epoch,
                "position_cycle_id": cycle0,
                "position_cycle_no": 0,
                "intent_role": INITIAL_STOP_ACTION_ROLE,
                "trade_volume_delta": 2.0,
                "price": 1252.0,
                "vt_tradeid": "CTP.close-1",
            }
        ]
        readonly = self.readonly_flat(flat_at)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(stage904, "_age_seconds", return_value=0.0),
        ):
            rows = self.advance_flat_states(
                store=store,
                execution_ledger_rows=ledger,
                broker_positions=pd.DataFrame(),
                readonly_summary=readonly,
                ticks=self.ticks([(1, 1252.0), (4, 1245.0)]),
                heartbeat=self.heartbeat(),
                represented_roots=set(),
                journal_path=Path(tmp) / "state.ndjson",
                max_tick_age_seconds=30,
            )
        retry = [row for row in rows if row["monitor_action"] == "retry_open_dry_run"]
        self.assertEqual(len(retry), 1)
        self.assertEqual(retry[0]["intent_role"], RETRY_OPEN_ACTION_ROLE)
        self.assertTrue(retry[0]["position_cycle_id"].endswith(":cycle1"))

        cycle1 = retry[0]["position_cycle_id"]
        retry_fill_at = reclaim_at + timedelta(seconds=1)
        ledger.append(
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(retry_fill_at),
                "root_position_id": root,
                "position_epoch_id": epoch,
                "position_cycle_id": cycle1,
                "position_cycle_no": 1,
                "intent_role": RETRY_OPEN_ACTION_ROLE,
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "offset": "open",
                "trade_volume_delta": 2.0,
                "volume": 2.0,
                "price": 1246.0,
                "fill_price_source": "event_trade_weighted_avg",
                "vt_tradeid": "CTP.retry-open-1",
            }
        )
        row = self.apply(
            store,
            self.ticks([(1, 1252.0), (4, 1245.0), (6, 1252.0)]),
            ledger=ledger,
            base=self.base(fill_price=1246.0, cycle_no=1),
        )
        self.assertEqual(row["monitor_action"], "close_dry_run")
        self.assertEqual(row["intent_role"], RETRY_STOP_ACTION_ROLE)
        self.assertTrue(row["position_cycle_id"].endswith(":cycle1"))
        self.assertEqual(row["stage847_stop_price"], 1251.75)
        self.assertEqual(row["volume"], 2.0)

    def test_late_unpriced_initial_stop_close_advances_from_exact_order_and_flat_once(self) -> None:
        store, stopped_state, _ = self.initial_stop_store()
        stopped_snapshot = copy.deepcopy(stopped_state)
        summary, manifest, evidence = self.late_close_bundle()
        broker_orders = self.late_close_broker_order()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_path = root / "execution.ndjson"
            ledger_rows = self.write_ledger(
                ledger_path, self.late_close_ledger_events(stopped_state)
            )
            self.run_late_close_advance(
                store=store,
                ledger_rows=ledger_rows,
                ledger_path=ledger_path,
                broker_orders=broker_orders,
                summary=summary,
                manifest=manifest,
                evidence=evidence,
                journal_path=root / "state.ndjson",
            )

            state = store["states"][stopped_state["root_position_id"]]
            self.assertEqual("retry_wait", state["phase"])
            self.assertEqual(1, state["close_fill_price_reconciliation_pending"])
            durable = stage904.read_execution_ledger(ledger_path)
            reconciled = [
                row
                for row in durable
                if row.get("event_type") == stage904.CLOSE_VOLUME_RECONCILED_EVENT
            ]
            self.assertEqual(1, len(reconciled))
            self.assertEqual(2.0, reconciled[0]["reconciled_close_volume"])
            self.assertEqual(1, reconciled[0]["fill_price_reconciliation_pending"])
            self.assertNotIn("trade_volume_delta", reconciled[0])
            self.assertNotIn("price", reconciled[0])

            replay = stage904._reconcile_late_stop_close_volume(
                state=stopped_snapshot,
                intent_role=INITIAL_STOP_ACTION_ROLE,
                target_volume=2.0,
                execution_ledger_rows=durable,
                broker_orders=broker_orders,
                broker_positions=pd.DataFrame(),
                readonly_summary=summary,
                readonly_bundle_manifest=manifest,
                readonly_bundle_evidence=evidence,
                execution_ledger_path=ledger_path,
            )
            self.assertEqual("reconciled", replay["status"])
            self.assertEqual(
                1,
                sum(
                    row.get("event_type")
                    == stage904.CLOSE_VOLUME_RECONCILED_EVENT
                    for row in stage904.read_execution_ledger(ledger_path)
                ),
            )

    def test_close_volume_reconciliation_and_later_priced_fills_take_max_per_order(self) -> None:
        _, state, _ = self.initial_stop_store()
        identity = self.late_close_identity(state)
        common = {
            "target_date": self.target_date,
            "intent_fingerprint": "fp-volume-max",
            "vt_orderid": "CTP.9_99_max",
            **identity,
        }
        reconciled = {
            "event_type": stage904.CLOSE_VOLUME_RECONCILED_EVENT,
            "generated_at": self.iso(self.now - timedelta(seconds=2)),
            "close_volume_reconciliation_key": "late-close-max",
            "reconciled_close_volume": 2.0,
            **common,
        }
        priced_one = {
            "event_type": "filled_or_part_filled",
            "generated_at": self.iso(self.now - timedelta(seconds=1)),
            "trade_volume_delta": 1.0,
            "price": 1252.0,
            "vt_tradeid": "CTP.priced-max-1",
            **common,
        }
        priced_two = {
            **priced_one,
            "generated_at": self.iso(self.now),
            "vt_tradeid": "CTP.priced-max-2",
        }
        matched = stage904._fill_events_for_identity(
            [reconciled, priced_one, priced_two],
            target_date=self.target_date,
            root_position_id=state["root_position_id"],
            position_epoch_id=state["position_epoch_id"],
            position_cycle_id=state["position_cycle_id"],
            intent_role=INITIAL_STOP_ACTION_ROLE,
        )
        self.assertEqual(2.0, stage904._filled_volume(matched))

    def test_late_close_reconciliation_rejects_partial_and_residual_unknown_states(self) -> None:
        blocker_types = [
            "residual_order_active_after_cancel",
            "residual_order_unknown_after_cancel",
            "unknown_order_status_after_send",
            "adapter_exception_after_reserve",
        ]
        scenarios: list[tuple[str, list[dict], pd.DataFrame]] = []
        _, seed, _ = self.initial_stop_store()
        scenarios.append(
            (
                "partial_volume",
                self.late_close_ledger_events(
                    seed, traded=1.0, residual=1.0
                ),
                self.late_close_broker_order(
                    traded=1.0, status="part traded"
                ),
            )
        )
        for blocker_type in blocker_types:
            events = self.late_close_ledger_events(seed)
            events.append(
                {
                    "event_type": blocker_type,
                    "target_date": self.target_date,
                    "generated_at": self.iso(self.now - timedelta(seconds=6)),
                    "intent_fingerprint": "fp-late-initial-stop",
                    "vt_orderid": "CTP.9_99_904",
                    "residual_volume": 1.0,
                    **self.late_close_identity(seed),
                }
            )
            scenarios.append((blocker_type, events, self.late_close_broker_order()))

        for name, events, broker_orders in scenarios:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                store, stopped_state, _ = self.initial_stop_store()
                root = Path(tmp)
                ledger_path = root / "execution.ndjson"
                ledger_rows = self.write_ledger(ledger_path, events)
                summary, manifest, evidence = self.late_close_bundle()
                self.run_late_close_advance(
                    store=store,
                    ledger_rows=ledger_rows,
                    ledger_path=ledger_path,
                    broker_orders=broker_orders,
                    summary=summary,
                    manifest=manifest,
                    evidence=evidence,
                    journal_path=root / "state.ndjson",
                )
                self.assertEqual("initial_stop_latched", store["states"][stopped_state["root_position_id"]]["phase"])
                self.assertFalse(
                    any(
                        row.get("event_type")
                        == stage904.CLOSE_VOLUME_RECONCILED_EVENT
                        for row in stage904.read_execution_ledger(ledger_path)
                    )
                )

    def test_late_close_reconciliation_requires_reservation_and_not_position_only(self) -> None:
        scenarios = {
            "reservation_missing": {"include_reservation": False},
            "unpriced_evidence_missing": {"include_evidence": False},
        }
        for name, options in scenarios.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                store, stopped_state, _ = self.initial_stop_store()
                root = Path(tmp)
                ledger_path = root / "execution.ndjson"
                ledger_rows = self.write_ledger(
                    ledger_path,
                    self.late_close_ledger_events(stopped_state, **options),
                )
                summary, manifest, evidence = self.late_close_bundle()
                self.run_late_close_advance(
                    store=store,
                    ledger_rows=ledger_rows,
                    ledger_path=ledger_path,
                    broker_orders=self.late_close_broker_order(),
                    summary=summary,
                    manifest=manifest,
                    evidence=evidence,
                    journal_path=root / "state.ndjson",
                )
                self.assertEqual(
                    "initial_stop_latched",
                    store["states"][stopped_state["root_position_id"]]["phase"],
                )
                self.assertFalse(
                    any(
                        row.get("event_type")
                        == stage904.CLOSE_VOLUME_RECONCILED_EVENT
                        for row in stage904.read_execution_ledger(ledger_path)
                    )
                )

    def test_late_close_reconciliation_rejects_stale_hash_and_wrong_exact_identity(self) -> None:
        for name in ("stale_hash", "wrong_fingerprint", "wrong_vt_orderid"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                store, stopped_state, _ = self.initial_stop_store()
                events = self.late_close_ledger_events(stopped_state)
                if name == "wrong_fingerprint":
                    events[-1]["intent_fingerprint"] = "fp-other"
                if name == "wrong_vt_orderid":
                    events[-1]["vt_orderid"] = "CTP.other-order"
                root = Path(tmp)
                ledger_path = root / "execution.ndjson"
                ledger_rows = self.write_ledger(ledger_path, events)
                summary, manifest, evidence = self.late_close_bundle()
                if name == "stale_hash":
                    manifest["artifacts"]["orders"]["sha256"] = "f" * 64
                self.run_late_close_advance(
                    store=store,
                    ledger_rows=ledger_rows,
                    ledger_path=ledger_path,
                    broker_orders=self.late_close_broker_order(),
                    summary=summary,
                    manifest=manifest,
                    evidence=evidence,
                    journal_path=root / "state.ndjson",
                )
                self.assertEqual(
                    "initial_stop_latched",
                    store["states"][stopped_state["root_position_id"]]["phase"],
                )
                self.assertFalse(
                    any(
                        row.get("event_type")
                        == stage904.CLOSE_VOLUME_RECONCILED_EVENT
                        for row in stage904.read_execution_ledger(ledger_path)
                    )
                )

    def test_late_unpriced_retry_stop_close_can_mark_position_done(self) -> None:
        store, stopped_state, initial = self.initial_stop_store()
        root_position_id = stopped_state["root_position_id"]
        ledger = [
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(self.entry_at + timedelta(seconds=2)),
                "root_position_id": root_position_id,
                "position_epoch_id": stopped_state["position_epoch_id"],
                "position_cycle_id": stopped_state["position_cycle_id"],
                "intent_role": INITIAL_STOP_ACTION_ROLE,
                "trade_volume_delta": 2.0,
                "price": 1252.0,
                "vt_tradeid": "CTP.initial-close-before-retry-late-close",
            }
        ]
        retry_rows = self.advance_flat_states(
            store=store,
            execution_ledger_rows=ledger,
            broker_positions=pd.DataFrame(),
            readonly_summary=self.readonly_flat(
                self.entry_at + timedelta(seconds=3)
            ),
            ticks=self.ticks([(1, 1252.0), (4, 1245.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-retry-late-close-arm.ndjson",
            max_tick_age_seconds=30,
        )
        retry = next(row for row in retry_rows if row["monitor_action"] == "retry_open_dry_run")
        ledger.append(
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(self.entry_at + timedelta(seconds=5)),
                "root_position_id": root_position_id,
                "position_epoch_id": stopped_state["position_epoch_id"],
                "position_cycle_id": retry["position_cycle_id"],
                "position_cycle_no": 1,
                "intent_role": RETRY_OPEN_ACTION_ROLE,
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "offset": "open",
                "trade_volume_delta": 2.0,
                "volume": 2.0,
                "price": 1246.0,
                "fill_price_source": "event_trade_weighted_avg",
                "vt_tradeid": "CTP.retry-open-before-late-close",
            }
        )
        self.apply(
            store,
            self.ticks([(1, 1252.0), (4, 1245.0), (6, 1252.0)]),
            ledger=ledger,
            base=self.base(fill_price=1246.0, cycle_no=1),
        )
        retry_stopped = store["states"][root_position_id]
        self.assertEqual("retry_stop_latched", retry_stopped["phase"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_path = root / "execution.ndjson"
            durable = self.write_ledger(
                ledger_path,
                self.late_close_ledger_events(
                    retry_stopped,
                    fingerprint="fp-late-retry-stop",
                    vt_orderid="CTP.9_99_retry_stop",
                    intent_role=RETRY_STOP_ACTION_ROLE,
                ),
            )
            summary, manifest, evidence = self.late_close_bundle()
            self.run_late_close_advance(
                store=store,
                ledger_rows=durable,
                ledger_path=ledger_path,
                broker_orders=self.late_close_broker_order(
                    vt_orderid="CTP.9_99_retry_stop"
                ),
                summary=summary,
                manifest=manifest,
                evidence=evidence,
                journal_path=root / "state.ndjson",
            )
            self.assertEqual("done", store["states"][root_position_id]["phase"])
            reconciled = [
                row
                for row in stage904.read_execution_ledger(ledger_path)
                if row.get("event_type")
                == stage904.CLOSE_VOLUME_RECONCILED_EVENT
            ]
            self.assertEqual(1, len(reconciled))
            self.assertEqual(RETRY_STOP_ACTION_ROLE, reconciled[0]["intent_role"])
            self.assertEqual(
                retry_stopped["position_cycle_id"],
                reconciled[0]["position_cycle_id"],
            )

    def test_close_volume_reconciliation_cannot_be_used_for_retry_open(self) -> None:
        _, stopped_state, _ = self.initial_stop_store()
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "execution.ndjson"
            ledger_path.touch()
            decision = stage904._reconcile_late_stop_close_volume(
                state=stopped_state,
                intent_role=RETRY_OPEN_ACTION_ROLE,
                target_volume=2.0,
                execution_ledger_rows=[],
                broker_orders=self.late_close_broker_order(),
                broker_positions=pd.DataFrame(),
                readonly_summary={},
                readonly_bundle_manifest={},
                readonly_bundle_evidence={},
                execution_ledger_path=ledger_path,
            )
            self.assertEqual("not_applicable", decision["status"])
            self.assertEqual([], stage904.read_execution_ledger(ledger_path))

    def test_late_close_blocks_other_active_order_only_on_target_symbol(self) -> None:
        for other_symbol, expected_phase in (
            ("JM609.DCE", "initial_stop_latched"),
            ("RB610.SHFE", "retry_wait"),
        ):
            with self.subTest(other_symbol=other_symbol), tempfile.TemporaryDirectory() as tmp:
                store, stopped_state, _ = self.initial_stop_store()
                exact = self.late_close_broker_order()
                other = pd.DataFrame(
                    [
                        {
                            "query_generation_uuid": "11111111-2222-4333-8444-555555555555",
                            "broker_id": "9999",
                            "account_id": "stage904-test",
                            "vt_symbol": other_symbol,
                            "direction": "long",
                            "offset": "close",
                            "volume": 1.0,
                            "traded": 0.0,
                            "status": "not traded",
                            "vt_orderid": "CTP.9_99_other-active",
                            "stable_order_identity_complete": 1,
                        }
                    ]
                )
                broker_orders = pd.concat([exact, other], ignore_index=True)
                root = Path(tmp)
                ledger_path = root / "execution.ndjson"
                ledger_rows = self.write_ledger(
                    ledger_path,
                    self.late_close_ledger_events(stopped_state),
                )
                summary, manifest, evidence = self.late_close_bundle(order_count=2)
                self.run_late_close_advance(
                    store=store,
                    ledger_rows=ledger_rows,
                    ledger_path=ledger_path,
                    broker_orders=broker_orders,
                    summary=summary,
                    manifest=manifest,
                    evidence=evidence,
                    journal_path=root / "state.ndjson",
                )
                self.assertEqual(
                    expected_phase,
                    store["states"][stopped_state["root_position_id"]]["phase"],
                )

    def test_partial_retry_fill_is_immediately_protected_at_broker_residual_volume(self) -> None:
        store = stage904._new_state_store(self.target_date)
        initial = self.apply(store, self.ticks([(1, 1252.0)]))
        root = initial["root_position_id"]
        epoch = initial["position_epoch_id"]
        cycle0 = initial["position_cycle_id"]
        close_at = self.entry_at + timedelta(seconds=2)
        flat_at = self.entry_at + timedelta(seconds=3)
        ledger = [
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(close_at),
                "root_position_id": root,
                "position_epoch_id": epoch,
                "position_cycle_id": cycle0,
                "position_cycle_no": 0,
                "intent_role": INITIAL_STOP_ACTION_ROLE,
                "trade_volume_delta": 2.0,
                "price": 1252.0,
                "vt_tradeid": "CTP.close-partial-case",
            }
        ]
        rows = self.advance_flat_states(
            store=store,
            execution_ledger_rows=ledger,
            broker_positions=pd.DataFrame(),
            readonly_summary=self.readonly_flat(flat_at),
            ticks=self.ticks([(1, 1252.0), (4, 1245.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-partial-retry.ndjson",
            max_tick_age_seconds=30,
        )
        retry = next(row for row in rows if row["monitor_action"] == "retry_open_dry_run")
        retry_fill_at = self.entry_at + timedelta(seconds=5)
        ledger.append(
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(retry_fill_at - timedelta(seconds=1)),
                "root_position_id": root,
                "position_epoch_id": "old-same-day-epoch",
                "position_cycle_id": retry["position_cycle_id"],
                "position_cycle_no": 1,
                "intent_role": RETRY_OPEN_ACTION_ROLE,
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "offset": "open",
                "trade_volume_delta": 2.0,
                "volume": 2.0,
                "price": 1300.0,
                "fill_price_source": "event_trade_weighted_avg",
                "vt_tradeid": "CTP.old-epoch-retry-fill",
            }
        )
        ledger.append(
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(retry_fill_at),
                "root_position_id": root,
                "position_epoch_id": epoch,
                "position_cycle_id": retry["position_cycle_id"],
                "position_cycle_no": 1,
                "intent_role": RETRY_OPEN_ACTION_ROLE,
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "offset": "open",
                "trade_volume_delta": 1.0,
                "volume": 1.0,
                "price": 1246.0,
                "fill_price_source": "event_trade_weighted_avg",
                "vt_tradeid": "CTP.retry-open-partial-1",
            }
        )
        missing_broker_rows = self.advance_flat_states(
            store=store,
            execution_ledger_rows=ledger,
            broker_positions=pd.DataFrame(),
            readonly_summary=self.readonly_flat(flat_at),
            ticks=self.ticks([(1, 1252.0), (4, 1245.0), (6, 1252.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-partial-retry-no-broker.ndjson",
            max_tick_age_seconds=30,
        )
        self.assertEqual("close_dry_run", missing_broker_rows[0]["monitor_action"])
        self.assertEqual(1.0, missing_broker_rows[0]["volume"])
        self.assertEqual("retry_stop_latched", store["states"][root]["phase"])
        self.assertEqual("retry_failed_at_c9_stop", missing_broker_rows[0]["monitor_reason"])

        broker_retry = self.base(fill_price=1246.0, cycle_no=1)
        broker_retry["volume"] = 1.0
        row = self.apply(
            store,
            self.ticks([(1, 1252.0), (4, 1245.0), (6, 1252.0)]),
            ledger=ledger,
            base=broker_retry,
        )
        self.assertEqual(row["monitor_action"], "close_dry_run")
        self.assertEqual(row["intent_role"], RETRY_STOP_ACTION_ROLE)
        self.assertEqual(row["volume"], 1.0)
        self.assertEqual(store["states"][root]["retry_filled_volume"], 1)
        self.assertEqual(store["states"][root]["current_position_volume"], 1)

    def test_order_reported_retry_fill_without_trade_detail_is_still_protected(self) -> None:
        store = stage904._new_state_store(self.target_date)
        initial = self.apply(store, self.ticks([(1, 1252.0)]))
        root = initial["root_position_id"]
        epoch = initial["position_epoch_id"]
        ledger = [
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(self.entry_at + timedelta(seconds=2)),
                "root_position_id": root,
                "position_epoch_id": epoch,
                "position_cycle_id": initial["position_cycle_id"],
                "intent_role": INITIAL_STOP_ACTION_ROLE,
                "trade_volume_delta": 2.0,
                "vt_tradeid": "CTP.close-before-unpriced-retry",
            }
        ]
        retry_rows = self.advance_flat_states(
            store=store,
            execution_ledger_rows=ledger,
            broker_positions=pd.DataFrame(),
            readonly_summary=self.readonly_flat(self.entry_at + timedelta(seconds=3)),
            ticks=self.ticks([(1, 1252.0), (4, 1245.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-unpriced-retry.ndjson",
            max_tick_age_seconds=30,
        )
        retry = next(row for row in retry_rows if row["monitor_action"] == "retry_open_dry_run")
        ledger.append(
            {
                "event_type": "fill_reconciliation_pending",
                "target_date": self.target_date,
                "generated_at": self.iso(self.entry_at + timedelta(seconds=5)),
                "root_position_id": root,
                "position_epoch_id": epoch,
                "position_cycle_id": retry["position_cycle_id"],
                "position_cycle_no": 1,
                "intent_role": RETRY_OPEN_ACTION_ROLE,
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "offset": "open",
                "order_traded_volume": 1.0,
                "trade_event_volume": 0.0,
                "unpriced_volume": 1.0,
                "vt_orderid": "CTP.retry-unpriced",
            }
        )

        protected_rows = self.advance_flat_states(
            store=store,
            execution_ledger_rows=ledger,
            broker_positions=pd.DataFrame(),
            readonly_summary=self.readonly_flat(self.entry_at + timedelta(seconds=5)),
            ticks=self.ticks([(1, 1252.0), (4, 1245.0), (6, 1252.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-unpriced-retry.ndjson",
            max_tick_age_seconds=30,
        )

        close = next(row for row in protected_rows if row["monitor_action"] == "close_dry_run")
        self.assertEqual(close["volume"], 1.0)
        self.assertEqual(store["states"][root]["phase"], "retry_stop_latched")
        self.assertEqual(
            store["states"][root]["retry_fill_price_source"],
            "order_callback_traded_volume_price_pending_original_threshold_only",
        )
        self.assertEqual(store["states"][root]["retry_fill_reconciliation_pending"], 1)

    def test_error_or_incomplete_position_query_cannot_prove_flat(self) -> None:
        store = stage904._new_state_store(self.target_date)
        initial = self.apply(store, self.ticks([(1, 1252.0)]))
        ledger = [
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(self.entry_at + timedelta(seconds=2)),
                "root_position_id": initial["root_position_id"],
                "position_epoch_id": initial["position_epoch_id"],
                "position_cycle_id": initial["position_cycle_id"],
                "intent_role": INITIAL_STOP_ACTION_ROLE,
                "trade_volume_delta": 2.0,
                "vt_tradeid": "CTP.close-error-proof",
            }
        ]
        invalid = self.readonly_flat(self.entry_at + timedelta(seconds=3))
        invalid["status"] = "connect_exception"
        invalid["broker_snapshot"]["position_snapshot_state"] = "position_query_error"
        invalid["broker_snapshot"]["position_query_error_rows"] = 1
        rows = self.advance_flat_states(
            store=store,
            execution_ledger_rows=ledger,
            broker_positions=pd.DataFrame(),
            readonly_summary=invalid,
            ticks=self.ticks([(1, 1252.0), (4, 1245.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-invalid-flat.ndjson",
            max_tick_age_seconds=30,
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("retry_block", rows[0]["monitor_action"])
        self.assertEqual(
            "initial_stop_latched",
            store["states"][initial["root_position_id"]]["phase"],
        )

    def test_opposite_direction_position_cannot_prove_symbol_flat_for_retry(self) -> None:
        readonly_summary, _ = self.readonly_position(2.0)
        opposite_position = pd.DataFrame(
            [
                {
                    "vt_symbol": "JM609.DCE",
                    "direction": "long",
                    "volume": 2.0,
                    "frozen": 0.0,
                }
            ]
        )
        readonly_summary, manifest, evidence = self.bind_position_query_bundle(
            readonly_summary,
            opposite_position,
        )

        flat, reason, _ = stage904._confirmed_broker_flat_evidence(
            readonly_summary=readonly_summary,
            broker_positions=opposite_position,
            vt_symbol="JM609.DCE",
            direction="short",
            readonly_bundle_manifest=manifest,
            readonly_bundle_evidence=evidence,
        )

        self.assertFalse(flat)
        self.assertIn("target_symbol_gross_position_present", reason)

    def test_flat_snapshot_must_be_causal_after_close_fill(self) -> None:
        close_fill_at = self.entry_at + timedelta(seconds=5)
        before = self.readonly_flat(self.entry_at + timedelta(seconds=4))
        after = self.readonly_flat(self.entry_at + timedelta(seconds=6))
        before, before_manifest, before_evidence = self.bind_position_query_bundle(
            before,
            pd.DataFrame(),
        )
        after, after_manifest, after_evidence = self.bind_position_query_bundle(
            after,
            pd.DataFrame(),
        )

        pre_flat, pre_reason, _ = stage904._confirmed_broker_flat_evidence(
            readonly_summary=before,
            broker_positions=pd.DataFrame(),
            vt_symbol="JM609.DCE",
            direction="short",
            not_before=self.iso(close_fill_at),
            readonly_bundle_manifest=before_manifest,
            readonly_bundle_evidence=before_evidence,
        )
        post_flat, post_reason, _ = stage904._confirmed_broker_flat_evidence(
            readonly_summary=after,
            broker_positions=pd.DataFrame(),
            vt_symbol="JM609.DCE",
            direction="short",
            not_before=self.iso(close_fill_at),
            readonly_bundle_manifest=after_manifest,
            readonly_bundle_evidence=after_evidence,
        )

        self.assertFalse(pre_flat)
        self.assertIn("precedes_close_fill", pre_reason)
        self.assertTrue(post_flat, post_reason)

    def test_flat_transition_rejects_stale_position_file_hash(self) -> None:
        summary = self.readonly_flat(self.entry_at + timedelta(seconds=6))
        summary, manifest, evidence = self.bind_position_query_bundle(
            summary,
            pd.DataFrame(),
        )
        evidence["artifacts"]["positions"]["sha256"] = "9" * 64

        flat, reason, _ = stage904._confirmed_broker_flat_evidence(
            readonly_summary=summary,
            broker_positions=pd.DataFrame(),
            vt_symbol="JM609.DCE",
            direction="short",
            readonly_bundle_manifest=manifest,
            readonly_bundle_evidence=evidence,
        )

        self.assertFalse(flat)
        self.assertIn("positions_count_or_hash_mismatch", reason)

    def test_done_epoch_rolls_forward_but_nonterminal_mismatch_blocks(self) -> None:
        store = stage904._new_state_store(self.target_date)
        first = self.apply(store, self.ticks([(1, 1252.0)]))
        root = first["root_position_id"]
        first_epoch = first["position_epoch_id"]
        changed = self.base(fill_price=1247.0)
        changed["open_trade_id"] = "manual-jm-open-2"
        changed["entry_filled_at"] = self.iso(self.entry_at + timedelta(seconds=5))

        blocked = self.apply(store, self.ticks([(6, 1247.0)]), base=changed)
        self.assertEqual("block", blocked["monitor_action"])
        self.assertIn("position_epoch_mismatch_with_nonterminal_state", blocked["monitor_reason"])

        store["states"][root] = stage904.mark_position_flat(
            store["states"][root], flat_at=self.entry_at + timedelta(seconds=4)
        )
        rolled = self.apply(store, self.ticks([(6, 1247.0)]), base=changed)
        self.assertNotEqual("block", rolled["monitor_action"])
        self.assertNotEqual(first_epoch, rolled["position_epoch_id"])
        self.assertEqual(rolled["position_epoch_id"], store["states"][root]["position_epoch_id"])

    def test_broker_fifo_reconstruction_discards_a_flattened_old_epoch(self) -> None:
        broker_trades = pd.DataFrame(
            [
                {
                    "gateway_name": "CTP",
                    "vt_symbol": "JM609.DCE",
                    "tradeid": "old-open",
                    "direction": "short",
                    "offset": "open",
                    "price": 1300.0,
                    "volume": 2.0,
                    "datetime": self.iso(self.entry_at - timedelta(seconds=10)),
                },
                {
                    "gateway_name": "CTP",
                    "vt_symbol": "JM609.DCE",
                    "tradeid": "old-close",
                    "direction": "long",
                    "offset": "close",
                    "price": 1290.0,
                    "volume": 2.0,
                    "datetime": self.iso(self.entry_at - timedelta(seconds=5)),
                },
                {
                    "gateway_name": "CTP",
                    "vt_symbol": "JM609.DCE",
                    "tradeid": "manual-reopen",
                    "direction": "short",
                    "offset": "open",
                    "price": 1246.0,
                    "volume": 2.0,
                    "datetime": self.iso(self.entry_at),
                },
            ]
        )
        current = stage904._weighted_broker_open_trade(
            broker_trades,
            "JM609.DCE",
            "short",
            self.target_date,
        )

        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current["price"], 1246.0)
        self.assertEqual(current["volume"], 2.0)
        self.assertEqual(current["position_epoch_fill_identity"], "trade:CTP:manual-reopen")
        self.assertEqual(current["position_epoch_trade_identities"], ["trade:CTP:manual-reopen"])

    def test_broker_fifo_uses_bound_monday_trading_day_for_friday_target(self) -> None:
        generation = "11111111-2222-4333-8444-555555555555"
        monday_fill = datetime(2026, 7, 13, 9, 0, 1)
        broker_trades = pd.DataFrame(
            [
                {
                    "gateway_name": "CTP",
                    "query_generation_uuid": generation,
                    "vt_symbol": "JM609.DCE",
                    "vt_orderid": "CTP.1_2_3",
                    "order_mapping_complete": 1,
                    "broker_trade_identity": "ctp:9999:test:DCE:20260713:T1",
                    "stable_trade_identity_complete": 1,
                    "direction": "short",
                    "offset": "open",
                    "price": 1246.0,
                    "volume": 1.0,
                    "datetime": self.iso(monday_fill),
                }
            ]
        )

        without_bound_day = stage904._weighted_broker_open_trade(
            broker_trades,
            "JM609.DCE",
            "short",
            "2026-07-10",
            query_generation_uuid=generation,
        )
        current = stage904._weighted_broker_open_trade(
            broker_trades,
            "JM609.DCE",
            "short",
            "2026-07-10",
            broker_trading_day="20260713",
            query_generation_uuid=generation,
        )

        self.assertIsNone(without_bound_day)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(1.0, current["volume"])
        self.assertEqual("2026-07-13", current["broker_reported_date"])
        self.assertEqual(generation, current["broker_query_generation_uuid"])

    def test_original_open_fallback_uses_bound_monday_not_calendar_plus_one(self) -> None:
        generation = "11111111-2222-4333-8444-555555555555"
        trades = pd.DataFrame(
            [
                {
                    "query_generation_uuid": generation,
                    "vt_symbol": "JM609.DCE",
                    "vt_orderid": "CTP.1_2_3",
                    "order_mapping_complete": 1,
                    "broker_trade_identity": "ctp:9999:test:DCE:20260713:SYS-1:T-1",
                    "stable_trade_identity_complete": 1,
                    "direction": "short",
                    "offset": "open",
                    "price": 1246.0,
                    "volume": 1.0,
                    "datetime": "2026-07-13T09:00:01",
                },
                {
                    "query_generation_uuid": generation,
                    "vt_symbol": "JM609.DCE",
                    "vt_orderid": "CTP.1_2_4",
                    "order_mapping_complete": 1,
                    "broker_trade_identity": "ctp:9999:test:DCE:20260713:SYS-2:T-2",
                    "stable_trade_identity_complete": 1,
                    "direction": "long",
                    "offset": "close",
                    "price": 1252.0,
                    "volume": 1.0,
                    "datetime": "2026-07-13T09:05:01",
                },
            ]
        )
        close_fill = {"price": 1252.0, "trade_volume_delta": 1.0}

        wrong_day = stage904._broker_original_open_trade_before_stage904_close(
            trades,
            "JM609.DCE",
            "short",
            "2026-07-10",
            close_fill,
            broker_trading_day="20260711",
            query_generation_uuid=generation,
        )
        bound_monday = stage904._broker_original_open_trade_before_stage904_close(
            trades,
            "JM609.DCE",
            "short",
            "2026-07-10",
            close_fill,
            broker_trading_day="20260713",
            query_generation_uuid=generation,
        )

        self.assertIsNone(wrong_day)
        self.assertIsNotNone(bound_monday)
        assert bound_monday is not None
        self.assertEqual(1246.0, bound_monday["price"])
        self.assertEqual(generation, bound_monday["broker_query_generation_uuid"])
        self.assertEqual("20260713", bound_monday["broker_query_trading_day"])

    def test_broker_epoch_reconstruction_blocks_stale_hash_bundle(self) -> None:
        generation = "11111111-2222-4333-8444-555555555555"
        summary, manifest, evidence = self.complete_query_bundle(
            trade_count=1,
            generation=generation,
        )
        evidence["artifacts"]["trades"]["sha256"] = "9" * 64
        broker_trades = pd.DataFrame(
            [
                {
                    "query_generation_uuid": generation,
                    "vt_symbol": "JM609.DCE",
                    "vt_orderid": "CTP.1_2_3",
                    "order_mapping_complete": 1,
                    "broker_trade_identity": "ctp:9999:test:DCE:20260713:SYS-1:T-1",
                    "stable_trade_identity_complete": 1,
                    "direction": "short",
                    "offset": "open",
                    "price": 1246.0,
                    "volume": 1.0,
                    "datetime": self.iso(self.entry_at),
                }
            ]
        )
        base = stage904._action_for_position(
            {
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "volume": 1.0,
                "position_source": "broker",
                "broker_fill_price": 1246.0,
            },
            trades=pd.DataFrame(),
            broker_trades=broker_trades,
            execution_ledger_rows=[],
            entry_risk=pd.DataFrame(
                [{"date": self.target_date, "contract_vt_symbol": "JM609.DCE", "direction": "short", "stop_price": 1258.0}]
            ),
            ticks=self.ticks([(1, 1252.0)]),
            target_date=self.target_date,
            max_tick_age_seconds=30,
            require_broker_fill_price=True,
            readonly_summary=summary,
            readonly_bundle_manifest=manifest,
            readonly_bundle_evidence=evidence,
        )

        self.assertEqual("block", base["monitor_action"])
        self.assertEqual(0, base["broker_epoch_reconstruction_complete"])
        self.assertIn("trades_count_or_hash_mismatch", base["monitor_reason"])

    def test_broker_epoch_reconstruction_blocks_incomplete_query_bundle(self) -> None:
        summary, manifest, evidence = self.complete_query_bundle(trade_count=1)
        for bundle in (summary["broker_query_bundle"], manifest):
            bundle["queries"]["trades"]["last_seen"] = False
            bundle["queries"]["trades"]["complete"] = False
            bundle["complete"] = False

        base = stage904._action_for_position(
            {
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "volume": 1.0,
                "position_source": "broker",
                "broker_fill_price": 1246.0,
            },
            trades=pd.DataFrame(),
            broker_trades=pd.DataFrame(),
            execution_ledger_rows=[],
            entry_risk=pd.DataFrame(
                [{"date": self.target_date, "contract_vt_symbol": "JM609.DCE", "direction": "short", "stop_price": 1258.0}]
            ),
            ticks=self.ticks([(1, 1252.0)]),
            target_date=self.target_date,
            max_tick_age_seconds=30,
            require_broker_fill_price=True,
            readonly_summary=summary,
            readonly_bundle_manifest=manifest,
            readonly_bundle_evidence=evidence,
        )

        self.assertEqual("block", base["monitor_action"])
        self.assertEqual(0, base["broker_query_bundle_valid"])
        self.assertIn("trades_query_generation_incomplete", base["monitor_reason"])

    def test_manual_reopen_uses_new_broker_epoch_instead_of_old_ledger_cycle(self) -> None:
        root = stage904.generate_root_position_id(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
        )
        old_entry_at = self.entry_at - timedelta(seconds=10)
        old_epoch = stage904.generate_position_epoch_id(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            entry_filled_at=self.iso(old_entry_at),
            fill_identity="vt:CTP.old-open",
        )
        old_ledger = [
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(old_entry_at),
                "root_position_id": root,
                "position_epoch_id": old_epoch,
                "position_cycle_id": f"{root}:cycle1",
                "position_cycle_no": 1,
                "intent_role": RETRY_OPEN_ACTION_ROLE,
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "offset": "open",
                "trade_volume_delta": 2.0,
                "volume": 2.0,
                "price": 1300.0,
                "fill_price_source": "event_trade_weighted_avg",
                "vt_tradeid": "CTP.old-open",
            }
        ]
        broker_trades = pd.DataFrame(
            [
                {
                    "gateway_name": "CTP",
                    "vt_symbol": "JM609.DCE",
                    "vt_tradeid": "CTP.old-open",
                    "direction": "short",
                    "offset": "open",
                    "price": 1300.0,
                    "volume": 2.0,
                    "datetime": self.iso(old_entry_at),
                },
                {
                    "gateway_name": "CTP",
                    "vt_symbol": "JM609.DCE",
                    "vt_tradeid": "CTP.old-close",
                    "direction": "long",
                    "offset": "close",
                    "price": 1290.0,
                    "volume": 2.0,
                    "datetime": self.iso(self.entry_at - timedelta(seconds=5)),
                },
                {
                    "gateway_name": "CTP",
                    "vt_symbol": "JM609.DCE",
                    "vt_tradeid": "CTP.manual-reopen",
                    "direction": "short",
                    "offset": "open",
                    "price": 1246.0,
                    "volume": 2.0,
                    "datetime": self.iso(self.entry_at),
                },
            ]
        )
        generation = "11111111-2222-4333-8444-555555555555"
        broker_trades["query_generation_uuid"] = generation
        broker_trades["vt_orderid"] = [
            "CTP.1_1_1",
            "CTP.1_1_2",
            "CTP.1_1_3",
        ]
        broker_trades["order_mapping_complete"] = 1
        broker_trades["broker_trade_identity"] = [
            f"ctp:9999:test:DCE:{self.now.strftime('%Y%m%d')}:SYS-{index}:T-{index}"
            for index in range(3)
        ]
        broker_trades["stable_trade_identity_complete"] = 1
        readonly_summary, bundle_manifest, bundle_evidence = (
            self.complete_query_bundle(trade_count=3, generation=generation)
        )
        entry_risk = pd.DataFrame(
            [
                {
                    "date": self.target_date,
                    "contract_vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "stop_price": 1258.0,
                }
            ]
        )
        position = {
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "volume": 2.0,
            "position_source": "broker",
            "broker_fill_price": 1246.0,
            "broker_fill_price_source": "readonly_position_price",
        }

        base = stage904._action_for_position(
            position,
            trades=pd.DataFrame(),
            broker_trades=broker_trades,
            execution_ledger_rows=old_ledger,
            entry_risk=entry_risk,
            ticks=self.ticks([(1, 1246.0)]),
            target_date=self.target_date,
            max_tick_age_seconds=30,
            require_broker_fill_price=True,
            readonly_summary=readonly_summary,
            readonly_bundle_manifest=bundle_manifest,
            readonly_bundle_evidence=bundle_evidence,
        )

        self.assertEqual(base["fill_price"], 1246.0)
        self.assertEqual(base["position_cycle_no"], 0)
        self.assertNotEqual(base["position_epoch_id"], old_epoch)
        self.assertEqual(base["position_epoch_source"], "readonly_broker_current_epoch_fifo")
        self.assertEqual(base["broker_epoch_reconstruction_complete"], 1)
        self.assertEqual(base["broker_epoch_ledger_identity_match"], 0)

        old_state = stage904.new_state(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            position_epoch_id=old_epoch,
            entry_filled_at=self.iso(old_entry_at),
            entry_price=1300.0,
            original_stop_price=1312.0,
            volume=2,
        )
        old_state = stage904.mark_position_flat(
            old_state,
            flat_at=self.entry_at - timedelta(seconds=5),
        )
        store = stage904._new_state_store(self.target_date)
        store["states"][root] = old_state
        rolled = self.apply(store, self.ticks([(1, 1246.0)]), ledger=old_ledger, base=base)
        self.assertNotEqual(rolled["monitor_action"], "block")
        self.assertEqual(store["states"][root]["position_epoch_id"], base["position_epoch_id"])
        self.assertEqual(store["states"][root]["entry_price"], 1246.0)

    def test_unique_callbackless_late_retry_fill_is_adopted_and_second_stop_latched(self) -> None:
        store = stage904._new_state_store(self.target_date)
        initial = self.apply(store, self.ticks([(1, 1252.0)]))
        root = initial["root_position_id"]
        epoch = initial["position_epoch_id"]
        close_at = self.entry_at + timedelta(seconds=2)
        flat_at = self.entry_at + timedelta(seconds=3)
        ledger = [
            {
                "event_type": "filled_or_part_filled",
                "target_date": self.target_date,
                "generated_at": self.iso(close_at),
                "root_position_id": root,
                "position_epoch_id": epoch,
                "position_cycle_id": initial["position_cycle_id"],
                "position_cycle_no": 0,
                "intent_role": INITIAL_STOP_ACTION_ROLE,
                "trade_volume_delta": 2.0,
                "price": 1252.0,
                "vt_tradeid": "CTP.close-before-late-retry",
            }
        ]
        retry_rows = self.advance_flat_states(
            store=store,
            execution_ledger_rows=ledger,
            broker_positions=pd.DataFrame(),
            readonly_summary=self.readonly_flat(flat_at),
            ticks=self.ticks([(1, 1252.0), (4, 1245.0)]),
            heartbeat=self.heartbeat(),
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-late-retry-arm.ndjson",
            max_tick_age_seconds=30,
        )
        retry = next(row for row in retry_rows if row["monitor_action"] == "retry_open_dry_run")
        cycle1 = retry["position_cycle_id"]
        reclaim_at = self.entry_at + timedelta(seconds=4)
        send_at = self.entry_at + timedelta(seconds=5)
        fill_at = self.entry_at + timedelta(seconds=6)
        unknown_at = self.entry_at + timedelta(seconds=7)
        fingerprint = "fp-callbackless-retry"
        vt_orderid = "CTP.retry-unknown"
        query_generation = "11111111-2222-4333-8444-555555555555"
        broker_trading_day = self.now.strftime("%Y%m%d")
        account_fingerprint = "a" * 64
        retry_payload = {
            "vt_symbol": "JM609.DCE",
            "direction": "short",
            "offset": "open",
            "root_position_id": root,
            "position_epoch_id": epoch,
            "position_cycle_id": cycle1,
            "position_cycle_no": 1,
            "intent_role": RETRY_OPEN_ACTION_ROLE,
        }
        ledger.extend(
            [
                {
                    "event_type": "reserved",
                    "target_date": self.target_date,
                    "generated_at": self.iso(reclaim_at + timedelta(milliseconds=100)),
                    "intent_fingerprint": fingerprint,
                    "intent_payload": retry_payload,
                },
                {
                    "event_type": "send_order_called",
                    "target_date": self.target_date,
                    "generated_at": self.iso(send_at),
                    "intent_id": "STAGE905-C9RETRY-late",
                    "intent_fingerprint": fingerprint,
                    "vt_orderid": vt_orderid,
                    "volume": 2.0,
                    **retry_payload,
                },
                {
                    "event_type": "residual_order_unknown_after_cancel",
                    "target_date": self.target_date,
                    "generated_at": self.iso(unknown_at),
                    "intent_fingerprint": fingerprint,
                    "vt_orderid": vt_orderid,
                    "residual_volume": 2.0,
                    **retry_payload,
                },
            ]
        )
        broker_trades = pd.DataFrame(
            [
                {
                    "gateway_name": "CTP",
                    "query_generation_uuid": query_generation,
                    "broker_id": "9999",
                    "account_id": "stage904-test",
                    "vt_symbol": "JM609.DCE",
                    "vt_orderid": vt_orderid,
                    "vt_tradeid": "CTP.retry-late-fill",
                    "broker_trade_identity": "ctp:stable-retry-late-fill",
                    "stable_trade_identity_complete": 1,
                    "order_mapping_complete": 1,
                    "direction": "short",
                    "offset": "open",
                    "price": 1246.0,
                    "volume": 1.0,
                    "datetime": self.iso(fill_at),
                }
            ]
        )
        entry_risk = pd.DataFrame(
            [
                {
                    "date": self.target_date,
                    "contract_vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "stop_price": 1258.0,
                }
            ]
        )
        query = {
            "request_sent": True,
            "request_return_code": 0,
            "callback_count": 2,
            "data_callback_count": 1,
            "last_seen": True,
            "error_rows": 0,
            "complete": True,
        }
        query_clock = self.now - timedelta(seconds=6)
        queries = {
            "orders": {
                **query,
                "reqid": 101,
                "request_sent_at": self.iso(query_clock),
                "completed_at": self.iso(query_clock + timedelta(seconds=1)),
            },
            "trades": {
                **query,
                "reqid": 102,
                "request_sent_at": self.iso(query_clock + timedelta(seconds=2)),
                "completed_at": self.iso(query_clock + timedelta(seconds=3)),
            },
            "positions": {
                **query,
                "reqid": 103,
                "request_sent_at": self.iso(query_clock + timedelta(seconds=4)),
                "completed_at": self.iso(query_clock + timedelta(seconds=5)),
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
        bundle_manifest = {
            "schema_version": 1,
            "generation_uuid": query_generation,
            "generated_at": self.iso(self.now),
            "broker_trading_day": broker_trading_day,
            "account": {
                "account_fingerprint": account_fingerprint,
                "login_account_match": True,
                "response_account_match": True,
            },
            "queries": {name: dict(value) for name, value in queries.items()},
            "trade_order_join_complete": True,
            "trade_identity_complete": True,
            "complete": True,
            "artifacts": artifacts,
            "summary_binding": {
                "generated_at": self.iso(self.now),
                "status": "readonly_snapshots_received",
            },
        }
        action_readonly_summary = {
            "status": "readonly_snapshots_received",
            "generated_at": self.iso(self.now),
            "query_generation_uuid": query_generation,
            "broker_trading_day": broker_trading_day,
            "broker_query_bundle": {
                key: copy.deepcopy(value)
                for key, value in bundle_manifest.items()
                if key != "summary_binding"
            },
        }
        action_bundle_evidence = {
            "artifacts": {
                "orders": {
                    "row_count": 1,
                    "sha256": "1" * 64,
                    "generation_uuids": [query_generation],
                    "account_fingerprints": [account_fingerprint],
                },
                "trades": {
                    "row_count": 1,
                    "sha256": "2" * 64,
                    "generation_uuids": [query_generation],
                    "account_fingerprints": [account_fingerprint],
                    "order_mapping_complete": True,
                    "stable_trade_identity_complete": True,
                },
                "positions": {
                    "row_count": 1,
                    "sha256": "3" * 64,
                    "generation_uuids": [query_generation],
                    "account_fingerprints": [account_fingerprint],
                },
            }
        }
        ticks = self.ticks([(1, 1252.0), (4, 1245.0), (8, 1252.0)])
        base = stage904._action_for_position(
            {
                "vt_symbol": "JM609.DCE",
                "direction": "short",
                "volume": 1.0,
                "position_source": "broker",
                "broker_fill_price": 1246.0,
                "broker_fill_price_source": "readonly_position_price",
            },
            trades=pd.DataFrame(),
            broker_trades=broker_trades,
            execution_ledger_rows=ledger,
            entry_risk=entry_risk,
            ticks=ticks,
            target_date=self.target_date,
            max_tick_age_seconds=30,
            require_broker_fill_price=True,
            readonly_summary=action_readonly_summary,
            readonly_bundle_manifest=bundle_manifest,
            readonly_bundle_evidence=action_bundle_evidence,
        )
        self.assertEqual([vt_orderid], base["broker_position_epoch_order_ids"])
        self.assertNotEqual(epoch, base["position_epoch_id"])
        readonly_summary, broker_positions = self.readonly_position(1.0)
        readonly_summary.update(
            {
                "query_generation_uuid": query_generation,
                "broker_trading_day": broker_trading_day,
                "broker_query_bundle": {
                    "schema_version": 1,
                    "generation_uuid": query_generation,
                    "generated_at": self.iso(self.now),
                    "broker_trading_day": broker_trading_day,
                    "account": dict(bundle_manifest["account"]),
                    "queries": {
                        name: dict(value) for name, value in queries.items()
                    },
                    "trade_order_join_complete": True,
                    "trade_identity_complete": True,
                    "complete": True,
                    "artifacts": {
                        name: dict(value) for name, value in artifacts.items()
                    },
                },
            }
        )
        bundle_evidence = {
            "artifacts": {
                "orders": {
                    "row_count": 1,
                    "sha256": "1" * 64,
                    "generation_uuids": [query_generation],
                    "account_fingerprints": [account_fingerprint],
                },
                "trades": {
                    "row_count": 1,
                    "sha256": "2" * 64,
                    "generation_uuids": [query_generation],
                    "account_fingerprints": [account_fingerprint],
                    "order_mapping_complete": True,
                    "stable_trade_identity_complete": True,
                },
                "positions": {
                    "row_count": 1,
                    "sha256": "3" * 64,
                    "generation_uuids": [query_generation],
                    "account_fingerprints": [account_fingerprint],
                },
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.ndjson"
            row = stage904._apply_state_to_position_action(
                base,
                store=store,
                execution_ledger_rows=ledger,
                ticks=ticks,
                heartbeat=self.heartbeat(),
                journal_path=Path(tmp) / "state.ndjson",
                readonly_summary=readonly_summary,
                readonly_bundle_manifest=bundle_manifest,
                readonly_bundle_evidence=bundle_evidence,
                broker_positions=broker_positions,
                max_tick_age_seconds=30,
                execution_ledger_path=ledger_path,
            )
            durable_rows = stage904.read_execution_ledger(ledger_path)

        self.assertEqual("close_dry_run", row["monitor_action"])
        self.assertEqual("retry_stop_latched", row["state_phase"])
        self.assertEqual(RETRY_STOP_ACTION_ROLE, row["intent_role"])
        self.assertEqual(epoch, row["position_epoch_id"])
        self.assertEqual(cycle1, row["position_cycle_id"])
        self.assertEqual(1.0, row["volume"])
        self.assertEqual(1, row["late_retry_fill_reconciled"])
        self.assertEqual(1, len(durable_rows))
        self.assertEqual(1, durable_rows[0]["broker_reconciled_late_retry_fill"])

    def test_first_observation_after_ring_overrun_blocks_favorable_latch(self) -> None:
        store = stage904._new_state_store(self.target_date)
        retained = pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 101,
                    "received_at": self.iso(self.entry_at + timedelta(seconds=15)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1239.0,
                    "bid_price_1": 1239.0,
                    "ask_price_1": 1239.0,
                }
            ]
        )
        heartbeat = {
            **self.heartbeat(),
            "journal_tick_count": 150,
            "stream_sequence": 150,
            "buffered_tick_count": 50,
        }
        with tempfile.TemporaryDirectory() as tmp:
            row = stage904._apply_state_to_position_action(
                self.base(),
                store=store,
                execution_ledger_rows=[],
                ticks=retained,
                heartbeat=heartbeat,
                journal_path=Path(tmp) / "journal.ndjson",
            )
        self.assertEqual("watch", row["monitor_action"])
        self.assertEqual("initial_armed", row["state_phase"])
        self.assertEqual(1, row["feed_gap_latched"])
        self.assertIn("tick_buffer_overrun_before_first_observation", row["feed_gap_reason"])

    def test_tick_snapshot_interleaving_retries_to_one_stable_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_path = root / "ticks.csv"
            heartbeat_path = root / "heartbeat.json"
            old_rows = [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 1,
                    "symbol_stream_sequence": 1,
                    "received_at": self.iso(self.now - timedelta(seconds=1)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1245.0,
                }
            ]
            new_rows = [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 2,
                    "received_at": self.iso(self.now),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1239.0,
                }
            ]

            def heartbeat(sequence: int) -> dict:
                return {
                    **self.heartbeat(),
                    "transport_ready": True,
                    "stream_sequence": sequence,
                    "buffered_tick_count": 1,
                }

            first_heartbeat_read = threading.Event()
            writer_done = threading.Event()
            writer_errors: list[BaseException] = []
            stage608._publish_tick_snapshot_commit(
                tick_path=tick_path,
                heartbeat_path=heartbeat_path,
                tick_rows=old_rows,
                heartbeat=heartbeat(1),
            )

            def writer() -> None:
                try:
                    if not first_heartbeat_read.wait(timeout=2):
                        raise TimeoutError("reader_did_not_reach_first_heartbeat")
                    stage608._publish_tick_snapshot_commit(
                        tick_path=tick_path,
                        heartbeat_path=heartbeat_path,
                        tick_rows=new_rows,
                        heartbeat=heartbeat(2),
                    )
                except BaseException as exc:  # surfaced in the test thread
                    writer_errors.append(exc)
                finally:
                    writer_done.set()

            worker = threading.Thread(target=writer)
            worker.start()
            read_json = stage904._read_json
            heartbeat_reads = 0

            def interleaved_read(path: Path) -> dict:
                nonlocal heartbeat_reads
                payload = read_json(path)
                if Path(path) == heartbeat_path:
                    heartbeat_reads += 1
                    if heartbeat_reads == 1:
                        first_heartbeat_read.set()
                        if not writer_done.wait(timeout=2):
                            raise TimeoutError("publisher_did_not_finish")
                return payload

            with patch.object(
                stage904, "_read_json", side_effect=interleaved_read
            ):
                frame, committed_heartbeat, error = (
                    stage904._read_committed_tick_snapshot(
                        tick_path,
                        heartbeat_path,
                        attempts=3,
                        retry_seconds=0,
                    )
                )
            worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(writer_errors, [])
        self.assertEqual(error, "")
        self.assertGreaterEqual(heartbeat_reads, 4)
        self.assertEqual(frame["stream_sequence"].tolist(), [2])
        self.assertEqual(frame["last_price"].tolist(), [1239.0])
        self.assertEqual(committed_heartbeat["stream_sequence"], 2)

    def test_heartbeat_metadata_change_with_reused_commit_blocks_current_cycle(self) -> None:
        """H1/H2 equality covers readiness fields, not only commit identity."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_path = root / "ticks.csv"
            heartbeat_path = root / "heartbeat.json"
            stage608._publish_tick_snapshot_commit(
                tick_path=tick_path,
                heartbeat_path=heartbeat_path,
                tick_rows=[
                    {
                        "feed_session_id": "feed-a",
                        "stream_sequence": 1,
                        "symbol_stream_sequence": 1,
                        "received_at": self.iso(self.now),
                        "vt_symbol": "JM609.DCE",
                        "last_price": 1245.0,
                    }
                ],
                heartbeat={
                    **self.heartbeat(),
                    "transport_ready": True,
                    "stream_sequence": 1,
                    "buffered_tick_count": 1,
                },
            )
            before = stage904._read_json(heartbeat_path)
            after = {
                **copy.deepcopy(before),
                # Simulate an alternate writer mutating readiness while
                # incorrectly retaining the old generation and hash.
                "stream_ready": False,
                "status": "alternate_writer_revoked",
            }
            heartbeat_reads = iter((before, after))
            with patch.object(
                stage904,
                "_read_json",
                side_effect=lambda _path: next(heartbeat_reads),
            ):
                frame, observed, error = stage904._read_committed_tick_snapshot(
                    tick_path,
                    heartbeat_path,
                    attempts=1,
                    retry_seconds=0,
                )

        self.assertTrue(frame.empty)
        self.assertEqual(observed["status"], "alternate_writer_revoked")
        self.assertIn("tick_snapshot_heartbeat_changed_during_read", error)

    def test_persistent_tick_commit_mismatch_blocks_without_latching_feed_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_path = root / "ticks.csv"
            heartbeat_path = root / "heartbeat.json"
            rows = [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 1,
                    "symbol_stream_sequence": 1,
                    "received_at": self.iso(self.now),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1245.0,
                }
            ]
            stage608._publish_tick_snapshot_commit(
                tick_path=tick_path,
                heartbeat_path=heartbeat_path,
                tick_rows=rows,
                heartbeat={
                    **self.heartbeat(),
                    "transport_ready": True,
                    "stream_sequence": 1,
                    "buffered_tick_count": 1,
                },
            )
            read_json = stage904._read_json
            heartbeat_reads = 0

            def corrupt_between_reads(path: Path) -> dict:
                nonlocal heartbeat_reads
                payload = read_json(path)
                if Path(path) == heartbeat_path:
                    heartbeat_reads += 1
                    if heartbeat_reads % 2 == 1:
                        changed_rows = [
                            {
                                **rows[0],
                                "last_price": 1250.0 + heartbeat_reads,
                            }
                        ]
                        stage608._atomic_write_bytes(
                            tick_path,
                            stage608._dataframe_csv_bytes(changed_rows),
                        )
                return payload

            with patch.object(
                stage904, "_read_json", side_effect=corrupt_between_reads
            ):
                frame, _, error = stage904._read_committed_tick_snapshot(
                    tick_path,
                    heartbeat_path,
                    attempts=2,
                    retry_seconds=0,
                )

        store = {
            "states": {
                "root-a": {
                    "root_position_id": "root-a",
                    "feed_gap_latched": False,
                    "feed_gap_reason": "",
                    "revision": 7,
                }
            }
        }
        before = copy.deepcopy(store)
        blocked, state_count = stage904._fail_closed_uncommitted_feed_cycle(
            store=store,
            base_rows=[{"vt_symbol": "JM609.DCE"}],
            commit_error=error,
        )

        self.assertTrue(frame.empty)
        self.assertIn("tick_snapshot_commit_unstable_after_2_attempts", error)
        self.assertIn("tick_snapshot_sha256_mismatch", error)
        self.assertEqual(store, before)
        self.assertFalse(store["states"]["root-a"]["feed_gap_latched"])
        self.assertEqual(state_count, 1)
        self.assertEqual(blocked[0]["monitor_action"], "block")
        self.assertIn("tick_snapshot_commit_transient_fail_closed", blocked[0]["monitor_reason"])

    def test_legacy_heartbeat_without_commit_blocks_cycle_without_state_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_path = root / "ticks.csv"
            heartbeat_path = root / "heartbeat.json"
            stage608._atomic_write_bytes(
                tick_path,
                stage608._dataframe_csv_bytes(
                    [{"stream_sequence": 1, "vt_symbol": "JM609.DCE"}]
                ),
            )
            stage608._atomic_write_json(
                heartbeat_path,
                {
                    "feed_session_id": "legacy-feed",
                    "stream_sequence": 1,
                    "buffered_tick_count": 1,
                },
            )
            frame, _, error = stage904._read_committed_tick_snapshot(
                tick_path,
                heartbeat_path,
                attempts=1,
                retry_seconds=0,
            )

        store = {"states": {"root-a": {"feed_gap_latched": False}}}
        before = copy.deepcopy(store)
        blocked, _ = stage904._fail_closed_uncommitted_feed_cycle(
            store=store,
            base_rows=[{"vt_symbol": "JM609.DCE"}],
            commit_error=error,
        )
        self.assertTrue(frame.empty)
        self.assertIn("tick_snapshot_commit_missing", error)
        self.assertEqual(store, before)
        self.assertEqual(blocked[0]["monitor_action"], "block")

    def test_symbol_silent_stall_blocks_favorable_progress_but_not_adverse_close(self) -> None:
        stale_at = self.now - timedelta(seconds=40)
        older_base = self.base()
        older_base["entry_filled_at"] = self.iso(self.now - timedelta(seconds=60))
        stale_heartbeat = {
            **self.heartbeat(),
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(stale_at),
                    "stream_sequence": 1,
                }
            },
        }

        favorable_store = stage904._new_state_store(self.target_date)
        favorable = self.apply(
            favorable_store,
            pd.DataFrame(
                [
                    {
                        "feed_session_id": "feed-a",
                        "stream_sequence": 1,
                        "received_at": self.iso(stale_at),
                        "vt_symbol": "JM609.DCE",
                        "last_price": 1239.0,
                        "bid_price_1": 1239.0,
                        "ask_price_1": 1239.0,
                    }
                ]
            ),
            base=older_base,
            heartbeat=stale_heartbeat,
        )
        self.assertEqual("watch", favorable["monitor_action"])
        self.assertEqual("initial_armed", favorable["state_phase"])
        self.assertIn("symbol_silent_stall", favorable["feed_gap_reason"])

        adverse_store = stage904._new_state_store(self.target_date)
        adverse = self.apply(
            adverse_store,
            pd.DataFrame(
                [
                    {
                        "feed_session_id": "feed-a",
                        "stream_sequence": 1,
                        "received_at": self.iso(stale_at),
                        "vt_symbol": "JM609.DCE",
                        "last_price": 1252.0,
                        "bid_price_1": 1252.0,
                        "ask_price_1": 1252.0,
                    }
                ]
            ),
            base=older_base,
            heartbeat=stale_heartbeat,
        )
        self.assertEqual("close_dry_run", adverse["monitor_action"])
        self.assertEqual(INITIAL_STOP_ACTION_ROLE, adverse["intent_role"])
        self.assertIn("symbol_silent_stall", adverse["feed_gap_reason"])

    def test_future_symbol_tick_cannot_latch_progress_or_retry_open(self) -> None:
        future_at = self.now + timedelta(seconds=5)
        future_heartbeat = {
            **self.heartbeat(),
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(future_at),
                    "stream_sequence": 2,
                }
            },
        }
        future_favorable = pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 2,
                    "received_at": self.iso(future_at),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1239.0,
                    "bid_price_1": 1239.0,
                    "ask_price_1": 1239.0,
                }
            ]
        )

        progress_store = stage904._new_state_store(self.target_date)
        progress = self.apply(
            progress_store,
            future_favorable,
            heartbeat=future_heartbeat,
        )
        self.assertEqual("initial_armed", progress["state_phase"])
        self.assertNotEqual("watch_progress_hit_no_initial_stop", progress["monitor_action"])
        self.assertIn("symbol_tick_from_future", progress["feed_gap_reason"])

        retry_store = stage904._new_state_store(self.target_date)
        stopped = self.apply(retry_store, self.ticks([(1, 1252.0)]))
        root = stopped["root_position_id"]
        retry_store["states"][root] = stage904.arm_retry_after_close(
            retry_store["states"][root],
            close_fill_at=self.iso(self.entry_at + timedelta(seconds=2)),
            broker_flat_at=self.iso(self.entry_at + timedelta(seconds=3)),
        )
        retry_rows = self.advance_flat_states(
            store=retry_store,
            execution_ledger_rows=[],
            broker_positions=pd.DataFrame(),
            readonly_summary=self.readonly_flat(self.now),
            ticks=future_favorable,
            heartbeat=future_heartbeat,
            represented_roots=set(),
            journal_path=Path(tempfile.gettempdir()) / "stage904-future-retry.ndjson",
            max_tick_age_seconds=30,
        )
        retry_row = next(row for row in retry_rows if row["root_position_id"] == root)
        self.assertEqual("retry_block", retry_row["monitor_action"])
        self.assertNotEqual(RETRY_OPEN_ACTION_ROLE, retry_row.get("intent_role"))
        self.assertIn("feed_gap", retry_row["monitor_reason"])

    def test_future_then_normal_buffer_latches_gap_before_favorable_progress(self) -> None:
        future_at = self.now + timedelta(seconds=5)
        ticks = pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 1,
                    "received_at": self.iso(future_at),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1239.0,
                    "bid_price_1": 1239.0,
                    "ask_price_1": 1239.0,
                },
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 2,
                    "received_at": self.iso(self.now),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1239.0,
                    "bid_price_1": 1239.0,
                    "ask_price_1": 1239.0,
                },
            ]
        )
        heartbeat = {
            **self.heartbeat(),
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 2,
                }
            },
        }

        row = self.apply(
            stage904._new_state_store(self.target_date),
            ticks,
            heartbeat=heartbeat,
        )

        self.assertEqual("initial_armed", row["state_phase"])
        self.assertEqual("watch", row["monitor_action"])
        self.assertEqual(1, row["feed_gap_latched"])
        self.assertIn("tick_from_future_before_consume", row["feed_gap_reason"])

    def test_target_symbol_evicted_from_global_ring_latches_feed_gap_even_when_target_frame_empty(
        self,
    ) -> None:
        retained_other_symbol = pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 1,
                    "received_at": self.iso(self.now),
                    "vt_symbol": "RB610.SHFE",
                    "last_price": 3500.0,
                    "bid_price_1": 3499.0,
                    "ask_price_1": 3500.0,
                }
            ]
        )
        heartbeat = {
            **self.heartbeat(),
            "stream_sequence": 2,
            "journal_tick_count": 2,
            "buffered_tick_count": 1,
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 1,
                    "symbol_stream_sequence": 1,
                    "durable_symbol_sequence": 1,
                    "first_buffered_symbol_sequence": 0,
                    "evicted_through_symbol_sequence": 1,
                },
                "RB610.SHFE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 1,
                    "durable_symbol_sequence": 1,
                    "first_buffered_symbol_sequence": 1,
                    "evicted_through_symbol_sequence": 0,
                },
            },
        }

        row = self.apply(
            stage904._new_state_store(self.target_date),
            retained_other_symbol,
            heartbeat=heartbeat,
        )

        self.assertEqual("initial_armed", row["state_phase"])
        self.assertEqual(1, row["feed_gap_latched"])
        self.assertEqual(
            "tick_target_symbol_evicted_before_consume:JM609.DCE;"
            "feed=feed-a;last_consumed=0;evicted_through=1",
            row["feed_gap_reason"],
        )

    def test_target_symbol_eviction_at_last_consumed_boundary_does_not_false_gap(
        self,
    ) -> None:
        store = stage904._new_state_store(self.target_date)
        first_heartbeat = {
            **self.heartbeat(),
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 1,
                    "symbol_stream_sequence": 1,
                    "durable_symbol_sequence": 1,
                    "first_buffered_symbol_sequence": 1,
                    "evicted_through_symbol_sequence": 0,
                }
            },
        }
        first = self.apply(
            store,
            self.ticks([(1, 1245.0)]),
            heartbeat=first_heartbeat,
        )
        self.assertEqual(0, first["feed_gap_latched"])

        retained_next_tick = pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 2,
                    "received_at": self.iso(self.entry_at + timedelta(seconds=2)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1245.0,
                    "bid_price_1": 1245.0,
                    "ask_price_1": 1245.0,
                }
            ]
        )
        second_heartbeat = {
            **self.heartbeat(),
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 2,
                    "durable_symbol_sequence": 2,
                    "first_buffered_symbol_sequence": 2,
                    "evicted_through_symbol_sequence": 1,
                }
            },
        }
        second = self.apply(
            store,
            retained_next_tick,
            heartbeat=second_heartbeat,
        )

        self.assertEqual(0, second["feed_gap_latched"])
        self.assertEqual("", second["feed_gap_reason"])
        self.assertEqual(
            2,
            store["states"][second["root_position_id"]]["last_seq_by_feed"]["feed-a"],
        )

    def test_interleaved_symbols_use_per_symbol_sequence_without_false_gap(self) -> None:
        ticks = pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 1,
                    "symbol_stream_sequence": 1,
                    "received_at": self.iso(self.now - timedelta(seconds=2)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1245.0,
                    "bid_price_1": 1245.0,
                    "ask_price_1": 1245.0,
                },
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 1,
                    "received_at": self.iso(self.now - timedelta(seconds=1)),
                    "vt_symbol": "RB610.SHFE",
                    "last_price": 3500.0,
                    "bid_price_1": 3499.0,
                    "ask_price_1": 3500.0,
                },
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 3,
                    "symbol_stream_sequence": 2,
                    "received_at": self.iso(self.now),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1239.0,
                    "bid_price_1": 1239.0,
                    "ask_price_1": 1239.0,
                },
            ]
        )
        heartbeat = {
            **self.heartbeat(),
            "stream_sequence": 3,
            "journal_tick_count": 3,
            "buffered_tick_count": 3,
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 3,
                    "symbol_stream_sequence": 2,
                    "durable_symbol_sequence": 2,
                    "first_buffered_symbol_sequence": 1,
                    "evicted_through_symbol_sequence": 0,
                },
                "RB610.SHFE": {
                    "received_at": self.iso(self.now - timedelta(seconds=1)),
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 1,
                    "durable_symbol_sequence": 1,
                    "first_buffered_symbol_sequence": 1,
                    "evicted_through_symbol_sequence": 0,
                },
            },
        }

        row = self.apply(
            stage904._new_state_store(self.target_date),
            ticks,
            heartbeat=heartbeat,
        )

        self.assertEqual("initial_progress_latched", row["state_phase"])
        self.assertEqual(0, row["feed_gap_latched"])
        self.assertEqual("", row["feed_gap_reason"])

    def test_true_per_symbol_sequence_gap_still_latches(self) -> None:
        ticks = pd.DataFrame(
            [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 1,
                    "symbol_stream_sequence": 1,
                    "received_at": self.iso(self.now - timedelta(seconds=1)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1245.0,
                },
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 2,
                    "symbol_stream_sequence": 1,
                    "received_at": self.iso(self.now - timedelta(seconds=1)),
                    "vt_symbol": "RB610.SHFE",
                    "last_price": 3500.0,
                },
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 3,
                    "symbol_stream_sequence": 3,
                    "received_at": self.iso(self.now),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1239.0,
                },
            ]
        )
        heartbeat = {
            **self.heartbeat(),
            "stream_sequence": 3,
            "journal_tick_count": 3,
            "buffered_tick_count": 3,
            "symbol_tick_watermarks": {
                "JM609.DCE": {
                    "received_at": self.iso(self.now),
                    "stream_sequence": 3,
                    "symbol_stream_sequence": 3,
                }
            },
        }

        row = self.apply(
            stage904._new_state_store(self.target_date),
            ticks,
            heartbeat=heartbeat,
        )

        self.assertEqual("initial_armed", row["state_phase"])
        self.assertEqual(1, row["feed_gap_latched"])
        self.assertTrue(
            "tick_sequence_gap_before_consume" in row["feed_gap_reason"]
            or "tick_buffer_overrun_before_first_observation"
            in row["feed_gap_reason"]
        )

    def test_fsynced_journal_recovers_close_intent_before_state_snapshot_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            journal_path = Path(tmp) / "state.ndjson"
            pre_transition = stage904._new_state_store(self.target_date)
            stage904._save_state_store(state_path, pre_transition)
            working = stage904._load_state_store(state_path, self.target_date)
            row = stage904._apply_state_to_position_action(
                self.base(),
                store=working,
                execution_ledger_rows=[],
                ticks=self.ticks([(1, 1252.0)]),
                heartbeat=self.heartbeat(),
                journal_path=journal_path,
            )
            self.assertEqual("close_dry_run", row["monitor_action"])
            expected_action_id = row["action_id"]

            # Simulate SIGKILL after journal fsync but before _save_state_store.
            recovered = stage904._load_state_store(
                state_path,
                self.target_date,
                journal_path=journal_path,
            )
            recovered_state = recovered["states"][row["root_position_id"]]
            recovered_action = stage904.get_pending_action(recovered_state)
            self.assertIsNotNone(recovered_action)
            self.assertEqual(expected_action_id, recovered_action["action_id"])
            self.assertEqual("close", recovered_action["action"])

            journal_record = json.loads(
                journal_path.read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertEqual(recovered_state, journal_record["state"])
            self.assertTrue(journal_record["checksum"])

            stage904._save_state_store(state_path, recovered)
            replayed_again = stage904._load_state_store(
                state_path,
                self.target_date,
                journal_path=journal_path,
            )
            self.assertEqual(
                expected_action_id,
                stage904.get_pending_action(
                    replayed_again["states"][row["root_position_id"]]
                )["action_id"],
            )

    def test_journal_corruption_checksum_and_revision_gap_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "state.json"
            journal_path = root / "state.ndjson"
            snapshot = stage904._new_state_store(self.target_date)
            stage904._save_state_store(state_path, snapshot)
            working = stage904._load_state_store(state_path, self.target_date)
            row = stage904._apply_state_to_position_action(
                self.base(),
                store=working,
                execution_ledger_rows=[],
                ticks=self.ticks([(1, 1252.0)]),
                heartbeat=self.heartbeat(),
                journal_path=journal_path,
            )
            first_text = journal_path.read_text(encoding="utf-8")

            with self.subTest("truncated_json"):
                journal_path.write_text(first_text.rstrip("\n")[:-5], encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "truncated_tail"):
                    stage904._load_state_store(
                        state_path, self.target_date, journal_path=journal_path
                    )

            with self.subTest("checksum_mismatch"):
                record = json.loads(first_text)
                record["state"]["phase"] = "tampered"
                journal_path.write_text(
                    stage904._canonical_json(record) + "\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "checksum_mismatch"):
                    stage904._load_state_store(
                        state_path, self.target_date, journal_path=journal_path
                    )

            with self.subTest("revision_chain_gap"):
                journal_path.write_text(first_text, encoding="utf-8")
                state = working["states"][row["root_position_id"]]
                second = stage904.consume_ticks(
                    state,
                    [
                        {
                            "feed_session_id": "feed-a",
                            "seq": 2,
                            "received_at": self.iso(self.now),
                            "vt_symbol": "JM609.DCE",
                            "last_price": 1253.0,
                            "bid_price_1": 1253.0,
                            "ask_price_1": 1253.0,
                        }
                    ],
                )
                stage904._append_state_journal(
                    journal_path,
                    previous_revision=int(state["revision"]),
                    state=second,
                )
                records = [
                    json.loads(line)
                    for line in journal_path.read_text(encoding="utf-8").splitlines()
                ]
                records[1]["previous_revision"] = 0
                unsigned = {
                    key: value
                    for key, value in records[1].items()
                    if key != "checksum"
                }
                records[1]["checksum"] = stage904._journal_record_checksum(unsigned)
                journal_path.write_text(
                    "".join(stage904._canonical_json(item) + "\n" for item in records),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "revision_chain_gap"):
                    stage904._load_state_store(
                        state_path, self.target_date, journal_path=journal_path
                    )

    def test_durable_checkpoint_bounds_long_session_wal_and_replay_latency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "state.json"
            journal_path = root / "state.ndjson"
            seed = stage904.new_state(
                target_date=self.target_date,
                vt_symbol="JM609.DCE",
                direction="short",
                position_epoch_id=stage904.generate_position_epoch_id(
                    target_date=self.target_date,
                    vt_symbol="JM609.DCE",
                    direction="short",
                    entry_filled_at=self.iso(self.entry_at),
                    fill_identity="trade:CTP:long-session",
                ),
                entry_filled_at=self.iso(self.entry_at),
                entry_price=1245.5,
                original_stop_price=1258.0,
                volume=2,
            )
            stage904._save_state_store(
                state_path, stage904._new_state_store(self.target_date)
            )
            lines: list[str] = []
            record_count = 5_000
            for revision in range(1, record_count + 1):
                state = copy.deepcopy(seed)
                state["revision"] = revision
                state["last_seq_by_feed"] = {"feed-a": revision}
                state["last_tick_order_key"] = [
                    self.iso(self.now),
                    "feed-a",
                    revision,
                ]
                state["last_tick_at"] = self.iso(self.now)
                payload = {
                    "journal_schema_version": stage904.STATE_JOURNAL_SCHEMA_VERSION,
                    "recorded_at": self.iso(self.now),
                    "target_date": self.target_date,
                    "root_position_id": state["root_position_id"],
                    "position_epoch_id": state["position_epoch_id"],
                    "previous_revision": revision - 1,
                    "revision": revision,
                    "state": state,
                }
                payload["checksum"] = stage904._journal_record_checksum(payload)
                lines.append(stage904._canonical_json(payload) + "\n")
            journal_path.write_text("".join(lines), encoding="utf-8")

            recovered = stage904._load_state_store(
                state_path,
                self.target_date,
                journal_path=journal_path,
            )
            self.assertGreater(journal_path.stat().st_size, 1_000_000)
            stage904._commit_state_store_and_checkpoint(
                state_path,
                journal_path,
                recovered,
            )

            self.assertEqual(0, journal_path.stat().st_size)
            started = time.perf_counter()
            replayed = stage904._load_state_store(
                state_path,
                self.target_date,
                journal_path=journal_path,
            )
            elapsed = time.perf_counter() - started
            root_position_id = seed["root_position_id"]
            self.assertEqual(
                record_count,
                replayed["states"][root_position_id]["revision"],
            )
            self.assertLess(elapsed, 1.0)

    def test_wal_terminal_epoch_rollover_recovers_latest_from_old_new_or_missing_snapshot(self) -> None:
        old_entry_at = self.entry_at - timedelta(seconds=10)
        new_entry_at = self.entry_at
        old_epoch = stage904.generate_position_epoch_id(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            entry_filled_at=self.iso(old_entry_at),
            fill_identity="trade:CTP:old-epoch",
        )
        new_epoch = stage904.generate_position_epoch_id(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            entry_filled_at=self.iso(new_entry_at),
            fill_identity="trade:CTP:new-epoch",
        )
        old_state = stage904.new_state(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            position_epoch_id=old_epoch,
            entry_filled_at=self.iso(old_entry_at),
            entry_price=1245.5,
            original_stop_price=1258.0,
            volume=2,
        )
        old_state = stage904.mark_position_flat(
            old_state, flat_at=self.iso(old_entry_at + timedelta(seconds=5))
        )
        new_state = stage904.new_state(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            position_epoch_id=new_epoch,
            entry_filled_at=self.iso(new_entry_at),
            entry_price=1245.5,
            original_stop_price=1258.0,
            volume=2,
        )
        new_state = stage904.consume_ticks(
            new_state,
            [
                {
                    "feed_session_id": "feed-a",
                    "seq": 1,
                    "received_at": self.iso(new_entry_at + timedelta(seconds=1)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1252.0,
                    "bid_price_1": 1252.0,
                    "ask_price_1": 1252.0,
                }
            ],
        )
        root_position_id = old_state["root_position_id"]
        expected_action_id = stage904.get_pending_action(new_state)["action_id"]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal_path = root / "state.ndjson"
            stage904._append_state_journal(
                journal_path, previous_revision=0, state=old_state
            )
            stage904._append_state_journal(
                journal_path, previous_revision=0, state=new_state
            )

            snapshots = {
                "old": old_state,
                "new": new_state,
                "missing": None,
            }
            for name, snapshot_state in snapshots.items():
                with self.subTest(snapshot=name):
                    state_path = root / f"state-{name}.json"
                    snapshot_store = stage904._new_state_store(self.target_date)
                    if snapshot_state is not None:
                        snapshot_store["states"][root_position_id] = snapshot_state
                    stage904._save_state_store(state_path, snapshot_store)
                    recovered = stage904._load_state_store(
                        state_path,
                        self.target_date,
                        journal_path=journal_path,
                    )
                    recovered_state = recovered["states"][root_position_id]
                    self.assertEqual(new_epoch, recovered_state["position_epoch_id"])
                    self.assertEqual(
                        expected_action_id,
                        stage904.get_pending_action(recovered_state)["action_id"],
                    )

    def test_wal_rejects_nonterminal_cross_epoch_rollover(self) -> None:
        old_entry_at = self.entry_at - timedelta(seconds=10)
        old_state = stage904.new_state(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            position_epoch_id=stage904.generate_position_epoch_id(
                target_date=self.target_date,
                vt_symbol="JM609.DCE",
                direction="short",
                entry_filled_at=self.iso(old_entry_at),
                fill_identity="trade:CTP:nonterminal-old",
            ),
            entry_filled_at=self.iso(old_entry_at),
            entry_price=1245.5,
            original_stop_price=1258.0,
            volume=2,
        )
        old_state = stage904.consume_ticks(
            old_state,
            [
                {
                    "feed_session_id": "feed-a",
                    "seq": 1,
                    "received_at": self.iso(old_entry_at + timedelta(seconds=1)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1245.5,
                    "bid_price_1": 1245.5,
                    "ask_price_1": 1245.5,
                }
            ],
        )
        new_state = stage904.new_state(
            target_date=self.target_date,
            vt_symbol="JM609.DCE",
            direction="short",
            position_epoch_id=stage904.generate_position_epoch_id(
                target_date=self.target_date,
                vt_symbol="JM609.DCE",
                direction="short",
                entry_filled_at=self.iso(self.entry_at),
                fill_identity="trade:CTP:forbidden-new",
            ),
            entry_filled_at=self.iso(self.entry_at),
            entry_price=1245.5,
            original_stop_price=1258.0,
            volume=2,
        )
        new_state = stage904.consume_ticks(
            new_state,
            [
                {
                    "feed_session_id": "feed-a",
                    "seq": 1,
                    "received_at": self.iso(self.entry_at + timedelta(seconds=1)),
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1252.0,
                    "bid_price_1": 1252.0,
                    "ask_price_1": 1252.0,
                }
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "state.json"
            journal_path = root / "state.ndjson"
            snapshot = stage904._new_state_store(self.target_date)
            snapshot["states"][old_state["root_position_id"]] = old_state
            stage904._save_state_store(state_path, snapshot)
            stage904._append_state_journal(
                journal_path, previous_revision=0, state=old_state
            )
            stage904._append_state_journal(
                journal_path, previous_revision=0, state=new_state
            )

            with self.assertRaisesRegex(ValueError, "nonterminal_epoch_rollover"):
                stage904._load_state_store(
                    state_path,
                    self.target_date,
                    journal_path=journal_path,
                )

    def test_partial_initial_close_reissues_only_fresh_broker_residual(self) -> None:
        store = stage904._new_state_store(self.target_date)
        original = self.base()
        original["volume"] = 15.0
        first = self.apply(store, self.ticks([(1, 1252.0)]), base=original)
        self.assertEqual(15.0, first["volume"])

        residual = dict(original)
        residual["volume"] = 10.0
        second = self.apply(
            store,
            self.ticks([(1, 1252.0), (2, 1253.0)]),
            base=residual,
        )
        self.assertEqual("close_dry_run", second["monitor_action"])
        self.assertEqual(10.0, second["volume"])

    def test_corrupt_store_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({"schema_version": 1, "target_date": self.target_date, "states": {"bad": {}}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                stage904._load_state_store(path, self.target_date)


if __name__ == "__main__":
    unittest.main()
