from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace
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

from qmt_roll_official_live_tick_types import DurableTickBatch, DurableTickCursor, TickStreamFault, TickStreamGap
from qmt_roll_official_live_time import utc_iso_from_epoch_ns
from qmt_roll_official_live_trace import ClockStamp, LatencyTrace
import qmt_roll_official_live_intent_spool as spool
import run_qmt_roll_stage941_official_live_c9_detector as detector


class _Clock:
    def __init__(self, epoch_ns: int = 200, monotonic_ns: int = 200) -> None:
        self._epoch_ns = epoch_ns
        self._monotonic_ns = monotonic_ns

    def epoch_ns(self) -> int:
        return self._epoch_ns

    def monotonic_ns(self) -> int:
        return self._monotonic_ns

    def clock_domain_id(self) -> str:
        return "boot-a"


class OfficialLiveC9DetectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.journal_path = root / "ticks.ndjson"
        self.heartbeat_path = root / "tick-heartbeat.json"
        self.spool_path = root / "intents.sqlite3"
        self.detector_heartbeat_path = root / "detector-heartbeat.json"
        self.config = detector.DetectorConfig(
            target_date="2026-07-16",
            tick_stream_heartbeat_path=self.heartbeat_path,
            spool_path=self.spool_path,
            detector_heartbeat_path=self.detector_heartbeat_path,
            max_batch_size=16,
            publish_compat_outputs=False,
        )
        self.write_tick_heartbeat()

    def cursor(self, sequence: int = 1, offset: int = 100) -> DurableTickCursor:
        return DurableTickCursor(
            feed_session_id="feed-a",
            ingress_sequence=sequence,
            journal_byte_offset=offset,
        )

    def write_tick_heartbeat(self, **overrides: object) -> None:
        payload = {
            "journal_authority_committed": True,
            "journal_session_state": "running",
            "stream_ready": True,
            "transport_ready": True,
            "writer_alive": True,
            "accepting": True,
            "stopped": False,
            "gap_latched": False,
            "writer_fault": None,
            "dropped_tick_count": 0,
            "feed_session_id": "feed-a",
            "durable_ingress_sequence": 1,
            "durable_journal_byte_offset": 100,
            "journal_schema": "stage179_framed_v1",
            "journal_segment_path": str(self.journal_path),
            "heartbeat_revision_uuid": "heartbeat-a",
        }
        payload.update(overrides)
        self.heartbeat_path.write_text(json.dumps(payload), encoding="utf-8")

    def tick_record(
        self,
        *,
        feed_session_id: str = "feed-a",
        ingress_sequence: int = 1,
        symbol_sequence: int = 1,
        vt_symbol: str = "JM609.DCE",
        ingress_epoch_ns: int = 100,
        ingress_monotonic_ns: int = 100,
    ) -> dict[str, object]:
        return {
            "feed_session_id": feed_session_id,
            "ingress_sequence": ingress_sequence,
            "symbol_sequence": symbol_sequence,
            "received_at_utc": utc_iso_from_epoch_ns(ingress_epoch_ns),
            "ingress_epoch_ns": ingress_epoch_ns,
            "ingress_monotonic_ns": ingress_monotonic_ns,
            "clock_domain_id": "boot-a",
            "trace_id": (
                f"stage179-tick/{feed_session_id}/{ingress_sequence}"
            ),
            "vt_symbol": vt_symbol,
            "last_price": 1245.5,
        }

    def batch(self, *, gap: TickStreamGap | None = None) -> DurableTickBatch:
        cursor = self.cursor()
        return DurableTickBatch(
            records=(self.tick_record(),),
            next_cursor=cursor,
            durable_through=cursor,
            caught_up=gap is None,
            gap=gap,
        )

    def valid_spool_intent(self, label: str = "close-1") -> dict[str, object]:
        trace = LatencyTrace.from_ingress_row(self.tick_record(), clock=_Clock(100, 100))
        trace = trace.record_stamp(
            "stage904_detected",
            ClockStamp(
                epoch_ns=101,
                monotonic_ns=101,
                clock_domain_id="boot-a",
                utc_iso=utc_iso_from_epoch_ns(101),
            ),
        ).record_stamp(
            "stage905_intent_ready",
            ClockStamp(
                epoch_ns=102,
                monotonic_ns=102,
                clock_domain_id="boot-a",
                utc_iso=utc_iso_from_epoch_ns(102),
            ),
        )
        business = {
            "intent_id": label,
            "action_id": f"business-{label}",
            "business_action_id": f"business-{label}",
            "trace_id": trace.trace_id,
            "target_date": "2026-07-16",
            "source": "stage904_c9_intraday_close",
            "offset": "close",
            "executor_status": "dry_run_order_request_payload_ready",
            "deadline_epoch_ns": trace.deadline_epoch_ns,
            "deadline_monotonic_ns": trace.deadline_monotonic_ns,
            "state_generation": "epoch-close-1:1",
            "position_epoch_id": "epoch-close-1",
            "vt_symbol": "JM609.DCE",
            "planned_volume": 1,
            "limit_price": 1245.5,
            "source_feed_session_id": trace.feed_session_id,
            "source_ingress_sequence": trace.ingress_sequence,
            "source_symbol_sequence": trace.symbol_sequence,
            "durable_cursor_feed_session_id": "feed-a",
            "durable_cursor_ingress_sequence": 1,
            "durable_cursor_journal_byte_offset": 100,
            "durable_cursor_journal_schema": "stage179_framed_v1",
        }
        canonical = json.dumps(
            business,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return {
            **business,
            "trace_json": trace.to_json(),
            "spool_payload_json": canonical,
            "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }

    def stage904_result(self, events: list[str]) -> SimpleNamespace:
        events.append("stage904_wal_fsync")
        return SimpleNamespace(
            target_date="2026-07-16",
            monitor_run_id="stage904-test",
            actions=pd.DataFrame(),
            summary={"target_date": "2026-07-16", "monitor_run_id": "stage904-test"},
            paths={},
        )

    def spool_intent_with_business_overrides(
        self,
        label: str,
        **overrides: object,
    ) -> dict[str, object]:
        intent = self.valid_spool_intent(label)
        business = json.loads(str(intent["spool_payload_json"]))
        business.update(overrides)
        canonical = json.dumps(
            business,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return {
            **intent,
            **overrides,
            "spool_payload_json": canonical,
            "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }

    def stage905_result(self, intents: list[dict[str, object]]) -> SimpleNamespace:
        return SimpleNamespace(
            intents=pd.DataFrame(intents),
            summary={"ready_count": len(intents), "send_order_api_called_count": 0, "cancel_order_api_called_count": 0},
            paths={},
        )

    def test_state_commit_happens_before_spool_commit(self) -> None:
        events: list[str] = []
        real_commit = spool.commit_detector_batch

        def commit_with_events(*args: object, **kwargs: object) -> object:
            events.append("spool_begin")
            result = real_commit(*args, **kwargs)
            events.append("spool_commit")
            return result

        with (
            patch.object(detector, "_read_durable_batch", return_value=self.batch()),
            patch.object(detector, "run_intraday_monitor", side_effect=lambda **_: self.stage904_result(events)) as monitor,
            patch.object(detector, "run_executor_dry_run", return_value=self.stage905_result([])),
            patch.object(detector, "commit_detector_batch", side_effect=commit_with_events),
        ):
            result = detector.run_detector_once(self.config, clock=_Clock())

        self.assertEqual("detector_cycle_committed", result.status)
        self.assertLess(events.index("stage904_wal_fsync"), events.index("spool_begin"))
        self.assertLess(events.index("spool_begin"), events.index("spool_commit"))
        self.assertTrue(monitor.call_args.kwargs["allow_partial_durable_batch"])

    def test_pending_provenance_uses_latest_exact_symbol_and_batch_cursor(self) -> None:
        open_epoch_ns = 1_784_206_800_000_000_000
        cursor = self.cursor(3, 300)
        batch = DurableTickBatch(
            records=(
                self.tick_record(ingress_sequence=1, symbol_sequence=1, ingress_epoch_ns=open_epoch_ns),
                self.tick_record(
                    ingress_sequence=2,
                    symbol_sequence=1,
                    vt_symbol="RB610.SHFE",
                    ingress_epoch_ns=open_epoch_ns,
                ),
                self.tick_record(ingress_sequence=3, symbol_sequence=2, ingress_epoch_ns=open_epoch_ns),
            ),
            next_cursor=cursor,
            durable_through=cursor,
            caught_up=True,
            gap=None,
        )

        provenance = detector._pending_initial_open_provenance(
            batch,
            clock=_Clock(),
        )

        self.assertEqual(3, provenance["JM609.DCE"]["source_ingress_sequence"])
        self.assertEqual(2, provenance["RB610.SHFE"]["source_ingress_sequence"])
        self.assertEqual(3, provenance["JM609.DCE"]["durable_cursor_ingress_sequence"])
        trace = LatencyTrace.from_json(provenance["JM609.DCE"]["trace_json"])
        self.assertEqual({"gateway_ingress", "stage904_detected"}, set(trace.stamps))

    def test_latched_close_gets_new_delivery_identity_from_each_fresh_symbol_tick(
        self,
    ) -> None:
        original_tick = self.tick_record()
        original_trace = LatencyTrace.from_ingress_row(
            original_tick,
            clock=_Clock(100, 100),
        )
        action_id = "business-close-action"
        action = {
            "target_date": "2026-07-16",
            "monitor_run_id": "stage904-close",
            "monitor_action": "close_dry_run",
            "monitor_reason": "initial_stop_triggered",
            "vt_symbol": "JM609.DCE",
            "direction": "long",
            "volume": 1,
            "stage847_stop_price": 1245.0,
            "live_price": 1244.5,
            "action_id": action_id,
            "logical_close_root_id": "logical-close-root",
            "position_epoch_id": "position-epoch-1",
            "state_generation": "position-epoch-1:2",
            "trace_json": original_trace.to_json(),
            "trace_id": original_trace.trace_id,
            "source_feed_session_id": original_trace.feed_session_id,
            "source_ingress_sequence": original_trace.ingress_sequence,
            "source_symbol_sequence": original_trace.symbol_sequence,
            "ingress_epoch_ns": 100,
            "ingress_monotonic_ns": 100,
            "deadline_epoch_ns": original_trace.deadline_epoch_ns,
            "deadline_monotonic_ns": original_trace.deadline_monotonic_ns,
            "durable_cursor_feed_session_id": "feed-a",
            "durable_cursor_ingress_sequence": 1,
            "durable_cursor_journal_byte_offset": 100,
            "durable_cursor_journal_schema": "stage179_framed_v1",
            "order_api_called": 0,
        }
        stage904_result = SimpleNamespace(
            target_date="2026-07-16",
            monitor_run_id="stage904-close",
            actions=pd.DataFrame([action]),
            summary={
                "target_date": "2026-07-16",
                "monitor_run_id": "stage904-close",
                "monitor_status": "intraday_monitor_close_dry_run",
                "action_count": 1,
                "close_dry_run_count": 1,
                "retry_open_dry_run_count": 0,
                "retry_watch_count": 0,
                "blocked_count": 0,
                "order_api_called_count": 0,
            },
            paths={},
        )

        def authorize(sequence: int, ingress_ns: int) -> object:
            cursor = self.cursor(sequence, sequence * 100)
            batch = DurableTickBatch(
                records=(
                    self.tick_record(
                        ingress_sequence=sequence,
                        symbol_sequence=sequence,
                        ingress_epoch_ns=ingress_ns,
                        ingress_monotonic_ns=ingress_ns,
                    ),
                ),
                next_cursor=cursor,
                durable_through=cursor,
                caught_up=True,
                gap=None,
            )
            return detector._refresh_close_delivery_provenance(
                stage904_result,
                batch,
                clock=_Clock(ingress_ns + 1, ingress_ns + 1),
            )

        second = authorize(2, 200)
        third = authorize(3, 300)
        second_intent = detector.stage905._stage904_intents(second.actions)[0]
        third_intent = detector.stage905._stage904_intents(third.actions)[0]

        self.assertEqual(action_id, second_intent["action_id"])
        self.assertEqual(action_id, second_intent["business_action_id"])
        self.assertNotEqual(second_intent["intent_id"], third_intent["intent_id"])
        self.assertTrue(second_intent["intent_id"].startswith("c9-close-delivery:"))
        self.assertEqual(2, second_intent["source_ingress_sequence"])
        self.assertEqual(3, third_intent["source_ingress_sequence"])
        self.assertEqual(
            original_trace.trace_id,
            second_intent["business_trigger_trace_id"],
        )
        refreshed_trace = LatencyTrace.from_json(second_intent["trace_json"])
        self.assertEqual(
            {"gateway_ingress", "stage904_detected"},
            set(refreshed_trace.stamps),
        )

    def test_latched_close_without_current_symbol_tick_creates_no_delivery(self) -> None:
        action = {
            "target_date": "2026-07-16",
            "monitor_run_id": "stage904-close",
            "monitor_action": "close_dry_run",
            "monitor_reason": "initial_stop_triggered",
            "vt_symbol": "JM609.DCE",
            "action_id": "business-close-action",
            "trace_id": "old-trace",
            "order_api_called": 0,
        }
        stage904_result = SimpleNamespace(
            target_date="2026-07-16",
            monitor_run_id="stage904-close",
            actions=pd.DataFrame([action]),
            summary={
                "target_date": "2026-07-16",
                "monitor_run_id": "stage904-close",
                "monitor_status": "intraday_monitor_close_dry_run",
                "action_count": 1,
                "close_dry_run_count": 1,
                "retry_open_dry_run_count": 0,
                "retry_watch_count": 0,
                "blocked_count": 0,
                "order_api_called_count": 0,
            },
            paths={},
        )
        cursor = self.cursor(2, 200)
        batch = DurableTickBatch(
            records=(
                self.tick_record(
                    ingress_sequence=2,
                    symbol_sequence=1,
                    vt_symbol="RB610.SHFE",
                ),
            ),
            next_cursor=cursor,
            durable_through=cursor,
            caught_up=True,
            gap=None,
        )

        refreshed = detector._refresh_close_delivery_provenance(
            stage904_result,
            batch,
            clock=_Clock(),
        )

        self.assertEqual("block", refreshed.actions.iloc[0]["monitor_action"])
        self.assertEqual("intraday_monitor_blocked", refreshed.summary["monitor_status"])
        self.assertEqual(1, refreshed.summary["blocked_count"])
        self.assertEqual([], detector.stage905._stage904_intents(refreshed.actions))

    def test_pending_initial_open_is_not_materialized_at_2059_but_is_at_2100(self) -> None:
        before = self.tick_record(
            ingress_epoch_ns=1_784_206_740_000_000_000
        )
        opening = self.tick_record(
            ingress_sequence=2,
            symbol_sequence=2,
            ingress_epoch_ns=1_784_206_800_000_000_000,
        )
        before_batch = DurableTickBatch(
            records=(before,), next_cursor=self.cursor(1, 100),
            durable_through=self.cursor(1, 100), caught_up=True, gap=None,
        )
        opening_batch = DurableTickBatch(
            records=(opening,), next_cursor=self.cursor(2, 200),
            durable_through=self.cursor(2, 200), caught_up=True, gap=None,
        )

        self.assertEqual(
            {}, detector._pending_initial_open_provenance(before_batch, clock=_Clock())
        )
        provenance = detector._pending_initial_open_provenance(
            opening_batch, clock=_Clock()
        )

        self.assertIn("JM609.DCE", provenance)
        self.assertEqual("night_open", provenance["JM609.DCE"]["initial_open_ingress_window"])
        self.assertEqual(
            1_784_207_100_000_000_000,
            provenance["JM609.DCE"]["initial_open_window_expiry_epoch_ns"],
        )

    def test_initial_open_filter_allows_recheck_skips_replay_and_keeps_close_first(self) -> None:
        blocked = {
            "intent_id": "STAGE905-PENDING-stable",
            "source": "stage901_pending_order",
            "offset": "open",
            "executor_status": "blocked",
        }
        ready = {
            **blocked,
            "executor_status": "dry_run_order_request_payload_ready",
        }
        close = {
            "intent_id": "close-action",
            "source": "stage904_c9_intraday_close",
            "offset": "close",
            "executor_status": "dry_run_order_request_payload_ready",
        }

        self.assertEqual(
            [],
            detector._intents_for_detector_commit(
                [blocked],
                existing_stage901_pending_ids=set(),
            ),
        )
        retried = detector._intents_for_detector_commit(
            [ready, close],
            existing_stage901_pending_ids=set(),
        )
        self.assertEqual(["close-action", "STAGE905-PENDING-stable"], [row["intent_id"] for row in retried])
        self.assertEqual(
            [close],
            detector._intents_for_detector_commit(
                [ready, close],
                existing_stage901_pending_ids={"STAGE905-PENDING-stable"},
            ),
        )

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        ready_open = self.spool_intent_with_business_overrides(
            "STAGE905-PENDING-stable",
            source="stage901_pending_order",
            offset="open",
            executor_status="dry_run_order_request_payload_ready",
        )
        ready_close = self.valid_spool_intent("close-action")
        committed = spool.commit_detector_batch(
            connection,
            consumer_id="stage941",
            expected_cursor=None,
            next_cursor=self.cursor(),
            intents=[ready_close, ready_open],
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
        )
        self.assertEqual(2, committed.inserted_count)
        self.assertEqual(
            ["close-action", "STAGE905-PENDING-stable"],
            [
                row[0]
                for row in connection.execute(
                    "SELECT intent_id FROM intents ORDER BY spool_sequence"
                )
            ],
        )
        existing = detector._existing_stage901_pending_intent_ids(
            connection,
            target_date="2026-07-16",
        )
        self.assertEqual({"STAGE905-PENDING-stable"}, existing)
        self.assertEqual(
            [],
            detector._intents_for_detector_commit(
                [ready],
                existing_stage901_pending_ids=existing,
            ),
        )
        self.assertEqual(2, spool.spool_counts(connection)["total"])

    def test_crash_after_state_commit_before_spool_replays_once(self) -> None:
        events: list[str] = []
        intent = self.valid_spool_intent()
        real_commit = spool.commit_detector_batch
        attempts = 0

        def crash_once(*args: object, **kwargs: object) -> object:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("injected_before_spool_commit")
            return real_commit(*args, **kwargs)

        with (
            patch.object(detector, "_read_durable_batch", return_value=self.batch()),
            patch.object(detector, "run_intraday_monitor", side_effect=lambda **_: self.stage904_result(events)),
            patch.object(detector, "run_executor_dry_run", return_value=self.stage905_result([intent])),
            patch.object(detector, "commit_detector_batch", side_effect=crash_once),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_before_spool_commit"):
                detector.run_detector_once(self.config, clock=_Clock())
            result = detector.run_detector_once(self.config, clock=_Clock())

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        self.assertEqual("detector_cycle_committed", result.status)
        self.assertEqual(1, spool.spool_counts(connection)["ready"])
        self.assertEqual(self.cursor(), spool.read_detector_cursor(connection, consumer_id="stage941"))

    def test_crash_after_spool_commit_repairs_missing_commit_stamp(self) -> None:
        intent = self.valid_spool_intent()
        real_record = spool.record_trace_observation
        failed = False

        def crash_after_commit(*args: object, **kwargs: object) -> object:
            nonlocal failed
            if not failed and kwargs.get("stage") == "spool_committed":
                failed = True
                raise RuntimeError("injected_after_spool_commit")
            return real_record(*args, **kwargs)

        with (
            patch.object(detector, "_read_durable_batch", return_value=self.batch()),
            patch.object(detector, "run_intraday_monitor", return_value=self.stage904_result([])),
            patch.object(detector, "run_executor_dry_run", return_value=self.stage905_result([intent])),
            patch.object(detector, "record_trace_observation", side_effect=crash_after_commit),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_after_spool_commit"):
                detector.run_detector_once(self.config, clock=_Clock())

        caught_up = DurableTickBatch(
            records=(),
            next_cursor=self.cursor(),
            durable_through=self.cursor(),
            caught_up=True,
            gap=None,
        )
        with patch.object(detector, "_read_durable_batch", return_value=caught_up):
            result = detector.run_detector_once(self.config, clock=_Clock(300, 300))

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        observations = spool.read_trace_observations(connection, intent_id="close-1")
        self.assertEqual("detector_idle_caught_up", result.status)
        self.assertEqual(300, observations["spool_committed"].epoch_ns)

    def test_crash_after_spool_commit_repairs_compat_publication_outbox(self) -> None:
        root = Path(self.tempdir.name)
        outbox = root / "compat-publication.json"
        config = detector.DetectorConfig(
            target_date="2026-07-16",
            tick_stream_heartbeat_path=self.heartbeat_path,
            spool_path=self.spool_path,
            detector_heartbeat_path=self.detector_heartbeat_path,
            publication_outbox_path=outbox,
            publish_compat_outputs=True,
        )
        stage904_result = SimpleNamespace(
            target_date="2026-07-16",
            monitor_run_id="stage904-test",
            actions=pd.DataFrame([{"monitor_action": "close_dry_run"}]),
            summary={"target_date": "2026-07-16", "monitor_run_id": "stage904-test"},
            paths={
                "actions_csv": root / "stage904-actions.csv",
                "summary_json": root / "stage904-summary.json",
                "report_md": root / "stage904-report.md",
            },
        )
        stage905_result = SimpleNamespace(
            intents=pd.DataFrame([self.valid_spool_intent()]),
            summary={"ready_count": 1, "send_order_api_called_count": 0, "cancel_order_api_called_count": 0},
            paths={
                "intents_csv": root / "stage905-intents.csv",
                "summary_json": root / "stage905-summary.json",
                "report_md": root / "stage905-report.md",
            },
        )
        real_publish = detector._publish_compat_publication
        failed = False

        def crash_before_publication(payload: dict[str, object]) -> None:
            nonlocal failed
            if not failed:
                failed = True
                raise RuntimeError("injected_before_compat_publication")
            real_publish(payload)

        with (
            patch.object(detector, "_read_durable_batch", return_value=self.batch()),
            patch.object(detector, "run_intraday_monitor", return_value=stage904_result),
            patch.object(detector, "run_executor_dry_run", return_value=stage905_result),
            patch.object(detector, "_publish_compat_publication", side_effect=crash_before_publication),
            patch.object(detector.stage904, "_build_report", return_value="stage904 report"),
            patch.object(detector.stage905, "_build_report", return_value="stage905 report"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "injected_before_compat_publication",
            ):
                detector.run_detector_once(config, clock=_Clock())

        caught_up = DurableTickBatch(
            records=(),
            next_cursor=self.cursor(),
            durable_through=self.cursor(),
            caught_up=True,
            gap=None,
        )
        with patch.object(detector, "_read_durable_batch", return_value=caught_up):
            result = detector.run_detector_once(config, clock=_Clock(300, 300))

        self.assertEqual("detector_idle_caught_up", result.status)
        self.assertTrue((root / "stage904-actions.csv").exists())
        self.assertTrue((root / "stage905-intents.csv").exists())
        self.assertFalse(outbox.exists())

    def test_gap_or_writer_fault_never_advances_cursor_or_ready_open(self) -> None:
        cases = (
            (self.batch(gap=TickStreamGap("feed-a", 1, 1, "injected_gap")), {}),
            (self.batch(), {"writer_fault": {"kind": "journal_write_error"}}),
        )
        for batch, heartbeat_override in cases:
            with self.subTest(heartbeat_override=heartbeat_override, gap=batch.gap):
                self.spool_path.unlink(missing_ok=True)
                self.write_tick_heartbeat(**heartbeat_override)
                with patch.object(detector, "_read_durable_batch", return_value=batch):
                    result = detector.run_detector_once(self.config, clock=_Clock())
                connection = spool.open_spool(self.spool_path)
                try:
                    self.assertEqual("detector_feed_unready", result.status)
                    self.assertIsNone(spool.read_detector_cursor(connection, consumer_id="stage941"))
                    self.assertEqual(0, spool.spool_counts(connection)["total"])
                finally:
                    connection.close()

    def test_heartbeat_revocation_during_stage904_never_commits_spool(self) -> None:
        def revoke_during_stage904(**_: object) -> SimpleNamespace:
            self.write_tick_heartbeat(
                stream_ready=False,
                writer_alive=False,
                accepting=False,
                writer_fault={"kind": "journal_write_error"},
            )
            return self.stage904_result([])

        with (
            patch.object(detector, "_read_durable_batch", return_value=self.batch()),
            patch.object(detector, "run_intraday_monitor", side_effect=revoke_during_stage904),
            patch.object(detector, "run_executor_dry_run") as stage905_run,
        ):
            result = detector.run_detector_once(self.config, clock=_Clock())

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        self.assertEqual("detector_feed_unready", result.status)
        self.assertIsNone(
            spool.read_detector_cursor(connection, consumer_id="stage941")
        )
        self.assertEqual(0, spool.spool_counts(connection)["total"])
        stage905_run.assert_not_called()

    def test_heartbeat_revocation_during_stage905_never_commits_spool(self) -> None:
        def revoke_during_stage905(*_args: object, **_kwargs: object) -> SimpleNamespace:
            self.write_tick_heartbeat(
                stream_ready=False,
                writer_alive=False,
                accepting=False,
                writer_fault={"kind": "journal_write_error"},
            )
            return self.stage905_result([self.valid_spool_intent()])

        with (
            patch.object(detector, "_read_durable_batch", return_value=self.batch()),
            patch.object(
                detector,
                "run_intraday_monitor",
                return_value=self.stage904_result([]),
            ),
            patch.object(
                detector,
                "run_executor_dry_run",
                side_effect=revoke_during_stage905,
            ),
        ):
            result = detector.run_detector_once(self.config, clock=_Clock())

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        self.assertEqual("detector_feed_unready", result.status)
        self.assertIsNone(
            spool.read_detector_cursor(connection, consumer_id="stage941")
        )
        self.assertEqual(0, spool.spool_counts(connection)["total"])

    def test_heartbeat_revocation_after_outbox_fsync_never_commits_spool(self) -> None:
        root = Path(self.tempdir.name)
        outbox = root / "compat-publication.json"
        config = detector.DetectorConfig(
            target_date="2026-07-16",
            tick_stream_heartbeat_path=self.heartbeat_path,
            spool_path=self.spool_path,
            detector_heartbeat_path=self.detector_heartbeat_path,
            publication_outbox_path=outbox,
            publish_compat_outputs=True,
        )
        stage904_result = SimpleNamespace(
            target_date="2026-07-16",
            monitor_run_id="stage904-test",
            actions=pd.DataFrame(),
            summary={"target_date": "2026-07-16", "monitor_run_id": "stage904-test"},
            paths={
                "actions_csv": root / "stage904-actions.csv",
                "summary_json": root / "stage904-summary.json",
                "report_md": root / "stage904-report.md",
            },
        )
        stage905_result = SimpleNamespace(
            intents=pd.DataFrame([self.valid_spool_intent()]),
            summary={"ready_count": 1, "send_order_api_called_count": 0, "cancel_order_api_called_count": 0},
            paths={
                "intents_csv": root / "stage905-intents.csv",
                "summary_json": root / "stage905-summary.json",
                "report_md": root / "stage905-report.md",
            },
        )
        real_atomic_write = detector._atomic_write_json

        def revoke_after_fsync(path: Path, payload: object) -> None:
            real_atomic_write(path, payload)
            if Path(path) == outbox:
                self.write_tick_heartbeat(
                    stream_ready=False,
                    writer_alive=False,
                    accepting=False,
                    writer_fault={"kind": "journal_write_error"},
                )

        with (
            patch.object(detector, "_read_durable_batch", return_value=self.batch()),
            patch.object(detector, "run_intraday_monitor", return_value=stage904_result),
            patch.object(detector, "run_executor_dry_run", return_value=stage905_result),
            patch.object(detector, "_atomic_write_json", side_effect=revoke_after_fsync),
            patch.object(detector.stage904, "_build_report", return_value="stage904 report"),
            patch.object(detector.stage905, "_build_report", return_value="stage905 report"),
        ):
            result = detector.run_detector_once(config, clock=_Clock())

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        self.assertEqual("detector_feed_unready", result.status)
        self.assertIsNone(
            spool.read_detector_cursor(connection, consumer_id="stage941")
        )
        self.assertEqual(0, spool.spool_counts(connection)["total"])
        self.assertTrue(outbox.exists())

    def test_idle_cycle_reports_persisted_spool_counts(self) -> None:
        intent = self.valid_spool_intent()
        caught_up = DurableTickBatch(
            records=(),
            next_cursor=self.cursor(),
            durable_through=self.cursor(),
            caught_up=True,
            gap=None,
        )
        with (
            patch.object(
                detector,
                "_read_durable_batch",
                side_effect=(self.batch(), caught_up),
            ),
            patch.object(
                detector,
                "run_intraday_monitor",
                return_value=self.stage904_result([]),
            ),
            patch.object(
                detector,
                "run_executor_dry_run",
                return_value=self.stage905_result([intent]),
            ),
        ):
            committed = detector.run_detector_once(self.config, clock=_Clock())
            idle = detector.run_detector_once(self.config, clock=_Clock(300, 300))

        self.assertEqual(1, committed.ready_count)
        self.assertEqual("detector_idle_caught_up", idle.status)
        self.assertEqual(1, idle.ready_count)

    def test_clean_feed_rollover_uses_lineage_and_commits_new_cursor(self) -> None:
        old_cursor = self.cursor()
        connection = spool.open_spool(self.spool_path)
        spool.commit_detector_batch(
            connection,
            consumer_id="stage941",
            expected_cursor=None,
            next_cursor=old_cursor,
            intents=[],
            now_epoch_ns=150,
            now_monotonic_ns=150,
            clock_domain_id="boot-a",
        )
        connection.close()
        self.write_tick_heartbeat(
            feed_session_id="feed-b",
            durable_ingress_sequence=1,
            durable_journal_byte_offset=120,
            journal_segment_path=str(Path(self.tempdir.name) / "feed-b.ndjson"),
            heartbeat_revision_uuid="heartbeat-b-running",
            prior_authoritative_feed_session_id="feed-a",
            prior_authoritative_journal_segment_path=str(self.journal_path),
            prior_authoritative_heartbeat_revision_uuid="heartbeat-a-terminal",
            prior_authoritative_journal_session_state="clean_stopped",
            prior_authoritative_clean_shutdown=True,
            recovery_previous_durable_cursor={
                "feed_session_id": "feed-a",
                "ingress_sequence": 1,
                "journal_byte_offset": 100,
                "journal_schema": "stage179_framed_v1",
            },
            prior_uncommitted_gaps=[],
        )
        new_cursor = DurableTickCursor("feed-b", 1, 120)
        new_batch = DurableTickBatch(
            records=(self.tick_record(feed_session_id="feed-b"),),
            next_cursor=new_cursor,
            durable_through=new_cursor,
            caught_up=True,
            gap=None,
        )
        observed_cursors: list[DurableTickCursor | None] = []

        class Reader:
            def __init__(self, _path: Path) -> None:
                pass

            def read_after(
                self,
                cursor: DurableTickCursor | None,
                *,
                durable_through: DurableTickCursor,
                limit: int,
            ) -> DurableTickBatch:
                observed_cursors.append(cursor)
                return new_batch

        with (
            patch.object(detector, "TickStreamJournalReader", Reader),
            patch.object(detector, "run_intraday_monitor", return_value=self.stage904_result([])),
            patch.object(detector, "run_executor_dry_run", return_value=self.stage905_result([])),
        ):
            result = detector.run_detector_once(self.config, clock=_Clock())

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        self.assertEqual("detector_cycle_committed", result.status)
        self.assertEqual([None], observed_cursors)
        self.assertEqual(
            new_cursor,
            spool.read_detector_cursor(connection, consumer_id="stage941"),
        )
        self.assertEqual(
            1,
            connection.execute(
                "SELECT COUNT(*) FROM detector_feed_rollovers"
            ).fetchone()[0],
        )

    def test_unclean_or_uncaught_up_feed_rollover_stays_on_old_cursor(self) -> None:
        invalid_overrides = (
            {"prior_authoritative_clean_shutdown": False},
            {"prior_uncommitted_gaps": [{"reason": "shutdown_gap"}]},
            {
                "recovery_previous_durable_cursor": {
                    "feed_session_id": "feed-a",
                    "ingress_sequence": 2,
                    "journal_byte_offset": 200,
                    "journal_schema": "stage179_framed_v1",
                }
            },
        )
        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                self.spool_path.unlink(missing_ok=True)
                connection = spool.open_spool(self.spool_path)
                spool.commit_detector_batch(
                    connection,
                    consumer_id="stage941",
                    expected_cursor=None,
                    next_cursor=self.cursor(),
                    intents=[],
                    now_epoch_ns=150,
                    now_monotonic_ns=150,
                    clock_domain_id="boot-a",
                )
                connection.close()
                lineage = {
                    "feed_session_id": "feed-b",
                    "durable_ingress_sequence": 1,
                    "durable_journal_byte_offset": 120,
                    "journal_segment_path": str(Path(self.tempdir.name) / "feed-b.ndjson"),
                    "heartbeat_revision_uuid": "heartbeat-b-running",
                    "prior_authoritative_feed_session_id": "feed-a",
                    "prior_authoritative_journal_segment_path": str(self.journal_path),
                    "prior_authoritative_heartbeat_revision_uuid": "heartbeat-a-terminal",
                    "prior_authoritative_journal_session_state": "clean_stopped",
                    "prior_authoritative_clean_shutdown": True,
                    "recovery_previous_durable_cursor": {
                        "feed_session_id": "feed-a",
                        "ingress_sequence": 1,
                        "journal_byte_offset": 100,
                        "journal_schema": "stage179_framed_v1",
                    },
                    "prior_uncommitted_gaps": [],
                    **overrides,
                }
                self.write_tick_heartbeat(**lineage)

                result = detector.run_detector_once(self.config, clock=_Clock())

                connection = spool.open_spool(self.spool_path)
                try:
                    self.assertEqual("detector_feed_unready", result.status)
                    self.assertEqual(
                        self.cursor(),
                        spool.read_detector_cursor(
                            connection,
                            consumer_id="stage941",
                        ),
                    )
                finally:
                    connection.close()

    def test_clean_terminal_feed_can_drain_to_final_watermark(self) -> None:
        connection = spool.open_spool(self.spool_path)
        spool.commit_detector_batch(
            connection,
            consumer_id="stage941",
            expected_cursor=None,
            next_cursor=self.cursor(),
            intents=[],
            now_epoch_ns=150,
            now_monotonic_ns=150,
            clock_domain_id="boot-a",
        )
        connection.close()
        self.write_tick_heartbeat(
            journal_session_state="clean_stopped",
            clean_shutdown=True,
            stopped=True,
            stream_ready=False,
            transport_ready=False,
            writer_alive=False,
            accepting=False,
            queue_depth=0,
            last_ingress_sequence=2,
            durable_ingress_sequence=2,
            durable_journal_byte_offset=200,
        )
        final_cursor = self.cursor(2, 200)
        final_batch = DurableTickBatch(
            records=(self.tick_record(ingress_sequence=2),),
            next_cursor=final_cursor,
            durable_through=final_cursor,
            caught_up=True,
            gap=None,
        )
        with (
            patch.object(detector, "_read_durable_batch", return_value=final_batch),
            patch.object(detector, "run_intraday_monitor", return_value=self.stage904_result([])),
            patch.object(detector, "run_executor_dry_run", return_value=self.stage905_result([])),
        ):
            result = detector.run_detector_once(self.config, clock=_Clock())

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        self.assertEqual("detector_cycle_committed", result.status)
        self.assertEqual(
            final_cursor,
            spool.read_detector_cursor(connection, consumer_id="stage941"),
        )

    def test_clean_empty_feed_lineage_can_bridge_to_next_nonempty_feed(self) -> None:
        old_cursor = self.cursor()
        connection = spool.open_spool(self.spool_path)
        spool.commit_detector_batch(
            connection,
            consumer_id="stage941",
            expected_cursor=None,
            next_cursor=old_cursor,
            intents=[],
            now_epoch_ns=150,
            now_monotonic_ns=150,
            clock_domain_id="boot-a",
        )
        connection.close()
        empty_path = Path(self.tempdir.name) / "feed-b.ndjson"
        empty_path.write_text("", encoding="utf-8")
        self.write_tick_heartbeat(
            feed_session_id="feed-b",
            durable_ingress_sequence=0,
            durable_journal_byte_offset=0,
            last_ingress_sequence=0,
            journal_segment_path=str(empty_path),
            heartbeat_revision_uuid="heartbeat-b-terminal",
            journal_session_state="clean_stopped",
            clean_shutdown=True,
            stopped=True,
            stream_ready=False,
            transport_ready=False,
            writer_alive=False,
            accepting=False,
            queue_depth=0,
            prior_authoritative_feed_session_id="feed-a",
            prior_authoritative_journal_segment_path=str(self.journal_path),
            prior_authoritative_heartbeat_revision_uuid="heartbeat-a-terminal",
            prior_authoritative_journal_session_state="clean_stopped",
            prior_authoritative_clean_shutdown=True,
            recovery_previous_durable_cursor={
                "feed_session_id": "feed-a",
                "ingress_sequence": 1,
                "journal_byte_offset": 100,
                "journal_schema": "stage179_framed_v1",
            },
            prior_uncommitted_gaps=[],
            prior_authoritative_empty_feed_sessions=[],
        )
        empty_result = detector.run_detector_once(self.config, clock=_Clock())
        self.assertEqual("detector_idle_caught_up", empty_result.status)
        self.assertEqual(old_cursor, empty_result.cursor_after)

        new_path = Path(self.tempdir.name) / "feed-c.ndjson"
        self.write_tick_heartbeat(
            feed_session_id="feed-c",
            durable_ingress_sequence=1,
            durable_journal_byte_offset=120,
            last_ingress_sequence=1,
            journal_segment_path=str(new_path),
            heartbeat_revision_uuid="heartbeat-c-running",
            journal_session_state="running",
            clean_shutdown=False,
            stopped=False,
            stream_ready=True,
            transport_ready=True,
            writer_alive=True,
            accepting=True,
            prior_authoritative_feed_session_id="feed-a",
            prior_authoritative_journal_segment_path=str(self.journal_path),
            prior_authoritative_heartbeat_revision_uuid="heartbeat-a-terminal",
            prior_authoritative_journal_session_state="clean_stopped",
            prior_authoritative_clean_shutdown=True,
            recovery_previous_durable_cursor={
                "feed_session_id": "feed-a",
                "ingress_sequence": 1,
                "journal_byte_offset": 100,
                "journal_schema": "stage179_framed_v1",
            },
            prior_uncommitted_gaps=[],
            prior_authoritative_empty_feed_sessions=[
                {
                    "feed_session_id": "feed-b",
                    "journal_segment_path": str(empty_path),
                    "heartbeat_revision_uuid": "heartbeat-b-terminal",
                    "journal_session_state": "clean_stopped",
                    "clean_shutdown": True,
                    "durable_ingress_sequence": 0,
                    "durable_journal_byte_offset": 0,
                }
            ],
        )
        new_cursor = DurableTickCursor("feed-c", 1, 120)
        new_batch = DurableTickBatch(
            records=(self.tick_record(feed_session_id="feed-c"),),
            next_cursor=new_cursor,
            durable_through=new_cursor,
            caught_up=True,
            gap=None,
        )
        with (
            patch.object(detector, "_read_durable_batch", return_value=new_batch),
            patch.object(detector, "run_intraday_monitor", return_value=self.stage904_result([])),
            patch.object(detector, "run_executor_dry_run", return_value=self.stage905_result([])),
        ):
            result = detector.run_detector_once(self.config, clock=_Clock(300, 300))

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        evidence = json.loads(
            connection.execute(
                "SELECT evidence_json FROM detector_feed_rollovers "
                "WHERE consumer_id='stage941' AND new_feed_session_id='feed-c'"
            ).fetchone()[0]
        )
        self.assertEqual("detector_cycle_committed", result.status)
        self.assertEqual(new_cursor, result.cursor_after)
        self.assertEqual(["feed-b"], evidence["bridged_empty_feed_sessions"])

    def test_backlog_larger_than_batch_limit_advances_across_partial_batches(self) -> None:
        self.write_tick_heartbeat(
            durable_ingress_sequence=2,
            durable_journal_byte_offset=200,
        )
        first_cursor = self.cursor(1, 100)
        final_cursor = self.cursor(2, 200)
        batches = (
            DurableTickBatch(
                records=(self.tick_record(ingress_sequence=1),),
                next_cursor=first_cursor,
                durable_through=final_cursor,
                caught_up=False,
                gap=None,
            ),
            DurableTickBatch(
                records=(self.tick_record(ingress_sequence=2),),
                next_cursor=final_cursor,
                durable_through=final_cursor,
                caught_up=True,
                gap=None,
            ),
        )
        with (
            patch.object(detector, "_read_durable_batch", side_effect=batches),
            patch.object(
                detector,
                "run_intraday_monitor",
                return_value=self.stage904_result([]),
            ),
            patch.object(
                detector,
                "run_executor_dry_run",
                return_value=self.stage905_result([]),
            ),
        ):
            first = detector.run_detector_once(self.config, clock=_Clock())
            second = detector.run_detector_once(self.config, clock=_Clock(300, 300))

        connection = spool.open_spool(self.spool_path)
        self.addCleanup(connection.close)
        self.assertEqual("detector_cycle_committed", first.status)
        self.assertEqual(first_cursor, first.cursor_after)
        self.assertFalse(first.cursor_after == first.durable_through)
        self.assertEqual("detector_cycle_committed", second.status)
        self.assertEqual(
            final_cursor,
            spool.read_detector_cursor(connection, consumer_id="stage941"),
        )

    def test_serve_stop_finishes_cycle_and_publishes_terminal_unready(self) -> None:
        stop_event = threading.Event()
        result = detector._result(
            status="detector_idle_caught_up",
            cursor_before=None,
            cursor_after=None,
            durable_through=None,
        )

        def finish_cycle(*_args: object, **_kwargs: object) -> object:
            stop_event.set()
            return result

        with patch.object(detector, "run_detector_once", side_effect=finish_cycle):
            exit_code = detector.serve_detector(
                self.config,
                clock=_Clock(),
                stop_event=stop_event,
            )

        heartbeat = json.loads(
            self.detector_heartbeat_path.read_text(encoding="utf-8")
        )
        self.assertEqual(0, exit_code)
        self.assertEqual("detector_stopped_unready", heartbeat["status"])
        self.assertFalse(heartbeat["ready"])
        self.assertTrue(heartbeat["stopped"])
        self.assertEqual(0, heartbeat["send_order_api_called_count"])
        self.assertEqual(0, heartbeat["cancel_order_api_called_count"])

    def test_real_sigterm_waits_for_current_cycle_then_publishes_terminal_unready(self) -> None:
        root = Path(self.tempdir.name)
        marker = root / "cycle-started"
        finished = root / "cycle-finished"
        code = "\n".join(
            [
                "import sys, time",
                f"sys.path.insert(0, {str(PORTFOLIO_DIR)!r})",
                "import run_qmt_roll_stage941_official_live_c9_detector as detector",
                "from pathlib import Path",
                f"marker = Path({str(marker)!r})",
                f"finished = Path({str(finished)!r})",
                "config = detector.DetectorConfig(",
                "    target_date='2026-07-16',",
                f"    tick_stream_heartbeat_path=Path({str(self.heartbeat_path)!r}),",
                f"    spool_path=Path({str(self.spool_path)!r}),",
                f"    detector_heartbeat_path=Path({str(self.detector_heartbeat_path)!r}),",
                "    poll_seconds=0.01,",
                ")",
                "def one_cycle(*_args, **_kwargs):",
                "    marker.write_text('started', encoding='utf-8')",
                "    time.sleep(0.5)",
                "    finished.write_text('finished', encoding='utf-8')",
                "    return detector._result(status='detector_idle_caught_up', cursor_before=None, cursor_after=None, durable_through=None)",
                "detector.run_detector_once = one_cycle",
                "raise SystemExit(detector.serve_detector(config))",
            ]
        )
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def cleanup_process() -> None:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass

        self.addCleanup(cleanup_process)
        deadline = time.monotonic() + 5.0
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(marker.exists(), "detector child did not start its cycle")

        process.send_signal(signal.SIGTERM)
        exit_code = process.wait(timeout=5.0)

        heartbeat = json.loads(
            self.detector_heartbeat_path.read_text(encoding="utf-8")
        )
        self.assertEqual(0, exit_code)
        self.assertTrue(finished.exists())
        self.assertEqual("detector_stopped_unready", heartbeat["status"])
        self.assertFalse(heartbeat["ready"])
        self.assertTrue(heartbeat["stopped"])


if __name__ == "__main__":
    unittest.main()
