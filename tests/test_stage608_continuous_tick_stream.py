from __future__ import annotations

import errno
import json
import hashlib
import threading
import io
import os
from collections import deque
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import sys
import tempfile
import unittest
import types
from unittest.mock import patch


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_ctp_stage608_readonly_tick_snapshot_probe as stage608


class ContinuousTickStreamTest(unittest.TestCase):
    @staticmethod
    def _ingress_tick(last_price: float = 1245.5) -> SimpleNamespace:
        return SimpleNamespace(
            vt_symbol="JM609.DCE",
            symbol="JM609",
            exchange=SimpleNamespace(value="DCE"),
            datetime=datetime(2026, 7, 13, 21, 1, 2, 3000),
            last_price=last_price,
            bid_price_1=last_price - 0.5,
            ask_price_1=last_price,
            bid_volume_1=10,
            ask_volume_1=12,
            limit_up=1370.0,
            limit_down=1120.0,
        )

    def test_tick_row_preserves_arrival_identity_and_market_fields(self) -> None:
        tick = SimpleNamespace(
            vt_symbol="JM609.DCE",
            symbol="JM609",
            exchange=SimpleNamespace(value="DCE"),
            datetime=datetime(2026, 7, 13, 21, 1, 2, 3000),
            last_price=1245.5,
            bid_price_1=1245.0,
            ask_price_1=1245.5,
            bid_volume_1=10,
            ask_volume_1=12,
            limit_up=1370.0,
            limit_down=1120.0,
        )
        received = datetime(2026, 7, 13, 21, 1, 2, 987654)
        row = stage608._stream_tick_row(
            tick,
            feed_session_id="feed-a",
            stream_sequence=7,
            symbol_stream_sequence=3,
            received_at=received,
        )

        self.assertEqual(row["feed_session_id"], "feed-a")
        self.assertEqual(row["stream_sequence"], 7)
        self.assertEqual(row["symbol_stream_sequence"], 3)
        self.assertEqual(row["received_at"], "2026-07-13T21:01:02.987654")
        self.assertEqual(row["exchange_datetime"], "2026-07-13T21:01:02.003000")
        self.assertEqual(row["vt_symbol"], "JM609.DCE")
        self.assertEqual(row["last_price"], 1245.5)
        self.assertEqual(row["bid_price_1"], 1245.0)
        self.assertEqual(row["ask_price_1"], 1245.5)

    def test_ndjson_append_and_atomic_json_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "ticks.ndjson"
            heartbeat = root / "heartbeat.json"
            stage608._append_ndjson(journal, {"stream_sequence": 1})
            stage608._append_ndjson(journal, {"stream_sequence": 2})
            stage608._atomic_write_json(heartbeat, {"stream_ready": True, "stream_sequence": 2})

            lines = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["stream_sequence"] for row in lines], [1, 2])
            self.assertEqual(json.loads(heartbeat.read_text(encoding="utf-8"))["stream_sequence"], 2)
            self.assertFalse(list(root.glob("*.tmp")))

    def test_journal_write_all_handles_partial_raw_file_writes(self) -> None:
        from qmt_roll_official_live_tick_journal import _write_all

        class PartialWriter:
            def __init__(self, max_chunk: int) -> None:
                self.max_chunk = max_chunk
                self.payload = bytearray()

            def write(self, payload: object) -> int:
                chunk = bytes(payload)[: self.max_chunk]
                self.payload.extend(chunk)
                return len(chunk)

        writer = PartialWriter(max_chunk=3)
        _write_all(writer, b"stage179-frame")

        self.assertEqual(bytes(writer.payload), b"stage179-frame")

    def test_tick_snapshot_commit_hashes_exact_bytes_and_commits_heartbeat_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tick_path = root / "ticks.csv"
            heartbeat_path = root / "heartbeat.json"
            rows = [
                {
                    "feed_session_id": "feed-a",
                    "stream_sequence": 7,
                    "symbol_stream_sequence": 3,
                    "received_at": "2026-07-13T21:01:02.987654",
                    "vt_symbol": "JM609.DCE",
                    "last_price": 1245.5,
                }
            ]
            heartbeat = {
                "feed_session_id": "feed-a",
                "stream_sequence": 7,
                "buffered_tick_count": 1,
                "stream_ready": True,
            }
            writes: list[Path] = []
            atomic_write = stage608._atomic_write_bytes

            def recording_write(path: Path, payload: bytes) -> None:
                writes.append(path)
                atomic_write(path, payload)

            with patch.object(
                stage608, "_atomic_write_bytes", side_effect=recording_write
            ):
                committed = stage608._publish_tick_snapshot_commit(
                    tick_path=tick_path,
                    heartbeat_path=heartbeat_path,
                    tick_rows=rows,
                    heartbeat=heartbeat,
                )

            persisted = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            commit = persisted["tick_snapshot_commit"]
            self.assertEqual(writes, [tick_path, heartbeat_path])
            self.assertEqual(commit, committed["tick_snapshot_commit"])
            self.assertEqual(commit["row_count"], 1)
            self.assertEqual(commit["stream_sequence"], 7)
            self.assertEqual(
                commit["sha256"], hashlib.sha256(tick_path.read_bytes()).hexdigest()
            )
            self.assertEqual(
                persisted["tick_snapshot_generation_uuid"],
                commit["generation_uuid"],
            )
            self.assertEqual(
                persisted["heartbeat_revision_uuid"],
                commit["generation_uuid"],
            )
            self.assertFalse(list(root.glob("*.tmp")))

    def test_dry_run_stream_never_calls_order_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = stage608._run_stream(
                connect=False,
                pre_subscribe_wait_seconds=0,
                target_symbols=["JM609.DCE"],
                watch_manifest=None,
                journal_path=Path(tmp) / "ticks.ndjson",
                heartbeat_path=Path(tmp) / "heartbeat.json",
                duration_seconds=1,
                heartbeat_seconds=0.2,
                max_buffer_ticks=10,
            )

        self.assertEqual(result["status"], "stream_dry_run_not_connected")
        self.assertEqual(result["send_order_api_called_count"], 0)
        self.assertEqual(result["cancel_order_api_called_count"], 0)

    def test_stage608_live_wiring_publishes_only_durable_ingress_aliases(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                self.on_tick(self_test._ingress_tick())

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("read-only Stage608 must not send orders")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("read-only Stage608 must not cancel orders")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        self_test = self
        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "ticks.ndjson"
            heartbeat = root / "heartbeat.json"
            tick_snapshot = root / "ticks.csv"
            with (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(stage608, "_ctp_setting_from_env", return_value={}),
                patch.object(stage608, "TICK_PATH", tick_snapshot),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=journal,
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )

            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))
            persisted_segment = Path(persisted["journal_segment_path"])
            journal_rows = [
                json.loads(line)
                for line in persisted_segment.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(result["send_order_api_called_count"], 0)
        self.assertEqual(result["cancel_order_api_called_count"], 0)
        self.assertEqual(result["last_ingress_sequence"], 1)
        self.assertEqual(result["durable_ingress_sequence"], 1)
        self.assertEqual(persisted["stream_sequence"], 1)
        self.assertEqual(persisted["journal_tick_count"], 1)
        self.assertEqual(persisted["durable_ingress_sequence"], 1)
        self.assertTrue(persisted["stopped"])
        self.assertFalse(persisted["stream_ready"])
        self.assertNotEqual(persisted_segment, journal)
        self.assertEqual(
            [
                row["ingress_sequence"]
                for row in journal_rows
                if "ingress_sequence" in row
            ],
            [1],
        )

    def test_shutdown_quiesces_ingress_before_md_close_and_restores_afterward(self) -> None:
        calls: list[str] = []

        class FakePipeline:
            def stop_accepting(self) -> None:
                calls.append("stop_accepting")

        class FakeMdApi:
            def __init__(self, gateway: "FakeGateway") -> None:
                self.gateway = gateway

            def close(self) -> None:
                calls.append("md_close")
                self.gateway.on_tick(object())

        class FakeGateway:
            def __init__(self) -> None:
                self.on_tick = lambda _tick: calls.append("wrapped_tick")
                self.md_api = FakeMdApi(self)

            def close(self) -> None:
                calls.append("aggregate_close")

        gateway = FakeGateway()

        def restore() -> None:
            calls.append("restore_wrapper")

        errors = stage608._quiesce_market_data_ingress(
            gateway,
            FakePipeline(),
            restore,
        )

        self.assertEqual(errors, {})
        self.assertEqual(
            calls,
            [
                "stop_accepting",
                "md_close",
                "wrapped_tick",
                "restore_wrapper",
            ],
        )

    def test_prior_recovery_gap_permanently_revokes_new_session_readiness(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamGap

        all_fresh_without_prior_gap = stage608._tick_stream_ready(
            transport_ready=True,
            expected_symbol_count=1,
            missing_tick_symbol_count=0,
            durable_stream_ready=True,
            prior_gap=None,
            stopped=False,
            starting=False,
        )
        blocked_by_prior_gap = stage608._tick_stream_ready(
            transport_ready=True,
            expected_symbol_count=1,
            missing_tick_symbol_count=0,
            durable_stream_ready=True,
            prior_gap=TickStreamGap(
                feed_session_id="feed-old",
                start_ingress_sequence=8,
                end_ingress_sequence=10,
                reason="prior_uncommitted_suffix",
            ),
            stopped=False,
            starting=False,
        )

        self.assertTrue(all_fresh_without_prior_gap)
        self.assertFalse(blocked_by_prior_gap)

    def test_disconnect_log_revokes_transport_readiness_until_relogin(self) -> None:
        disconnected = stage608._analyze_logs(
            [
                {"msg": "行情服务器连接成功"},
                {"msg": "行情服务器登录成功"},
                {"msg": "行情服务器连接断开，原因4097"},
            ]
        )
        relogged = stage608._analyze_logs(
            [
                {"msg": "行情服务器连接成功"},
                {"msg": "行情服务器登录成功"},
                {"msg": "行情服务器连接断开，原因4097"},
                {"msg": "行情服务器连接成功"},
                {"msg": "行情服务器登录成功"},
            ]
        )

        self.assertFalse(disconnected["md_connected"])
        self.assertFalse(disconnected["md_login_success"])
        self.assertTrue(disconnected["md_disconnected_after_connect"])
        self.assertTrue(relogged["md_connected"])
        self.assertTrue(relogged["md_login_success"])
        self.assertFalse(relogged["md_disconnected_after_connect"])

    def test_callback_state_snapshot_is_safe_while_symbols_are_added(self) -> None:
        lock = threading.Lock()
        logs: list[dict] = []
        ticks: deque[dict] = deque(maxlen=500)
        latest: dict[str, dict] = {}
        done = threading.Event()

        def writer() -> None:
            for sequence in range(1, 2001):
                row = {
                    "stream_sequence": sequence,
                    "vt_symbol": f"S{sequence}.DCE",
                    "received_at": f"2026-07-13T21:00:{sequence % 60:02d}",
                }
                with lock:
                    ticks.append(row)
                    latest[row["vt_symbol"]] = row
            done.set()

        worker = threading.Thread(target=writer)
        worker.start()
        observed = 0
        while not done.is_set():
            snapshot = stage608._snapshot_stream_collections(
                lock,
                logs=logs,
                tick_buffer=ticks,
                latest_by_symbol=latest,
                sequence=2000,
            )
            observed = max(observed, len(snapshot["latest_by_symbol"]))
        worker.join(timeout=2)
        final = stage608._snapshot_stream_collections(
            lock,
            logs=logs,
            tick_buffer=ticks,
            latest_by_symbol=latest,
            sequence=2000,
        )

        self.assertFalse(worker.is_alive())
        self.assertEqual(len(final["latest_by_symbol"]), 2000)
        self.assertEqual(final["sequence"], 2000)
        self.assertGreaterEqual(observed, 0)

    def test_symbol_watermarks_are_one_row_per_current_watch_symbol(self) -> None:
        latest = {
            "JM609.DCE": {
                "received_at": "2026-07-13T21:00:01.123456",
                "stream_sequence": 17,
                "symbol_stream_sequence": 9,
                "last_price": 1245.0,
            },
            "OLD609.DCE": {
                "received_at": "2026-07-13T20:59:00.000000",
                "stream_sequence": 3,
            },
        }

        watermarks = stage608._symbol_tick_watermarks(
            ["JM609.DCE", "I609.DCE", "JM609.DCE"], latest
        )

        self.assertEqual(list(watermarks), ["I609.DCE", "JM609.DCE"])
        self.assertEqual(
            watermarks["JM609.DCE"],
            {
                "received_at": "2026-07-13T21:00:01.123456",
                "stream_sequence": 17,
                "symbol_stream_sequence": 9,
                "durable_symbol_sequence": 0,
                "first_buffered_symbol_sequence": 0,
                "evicted_through_symbol_sequence": 0,
            },
        )
        self.assertEqual(
            watermarks["I609.DCE"],
            {
                "received_at": "",
                "stream_sequence": 0,
                "symbol_stream_sequence": 0,
                "durable_symbol_sequence": 0,
                "first_buffered_symbol_sequence": 0,
                "evicted_through_symbol_sequence": 0,
            },
        )
        self.assertNotIn("OLD609.DCE", watermarks)

    def test_gateway_ingress_stamp_precedes_event_engine_backlog(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            TICK_INGRESS_ENVELOPE_ATTR,
            TickStreamPipeline,
            install_gateway_tick_ingress,
        )

        class FakeClock:
            def __init__(self) -> None:
                self.epoch = 1_784_000_000_123_456_000
                self.monotonic = 100

            def epoch_ns(self) -> int:
                return self.epoch

            def monotonic_ns(self) -> int:
                return self.monotonic

            def sleep(self, seconds: float) -> None:
                self.monotonic += int(seconds * 1_000_000_000)

        clock = FakeClock()
        pipeline = TickStreamPipeline(
            feed_session_id="feed-a",
            journal_segment_path=Path("unused.ndjson"),
            clock=clock,
            queue_capacity=4,
            max_buffer_ticks=4,
        )
        enqueued_ticks: list[SimpleNamespace] = []

        class Gateway:
            stamped_at_enqueue = False

            def on_tick(self, queued_tick: SimpleNamespace) -> None:
                self.stamped_at_enqueue = hasattr(
                    queued_tick, TICK_INGRESS_ENVELOPE_ATTR
                )
                enqueued_ticks.append(queued_tick)

        gateway = Gateway()
        restore = install_gateway_tick_ingress(gateway, pipeline)
        tick = self._ingress_tick()

        gateway.on_tick(tick)
        envelope = getattr(tick, TICK_INGRESS_ENVELOPE_ATTR)
        tick.last_price = 9999.0
        cutoff_ns = 200
        clock.monotonic = 300
        observation = pipeline.observe_handler(enqueued_ticks.pop())
        restore()

        self.assertIsNotNone(envelope)
        self.assertIsNotNone(observation)
        self.assertTrue(gateway.stamped_at_enqueue)
        self.assertEqual(envelope.tick_row["last_price"], 1245.5)
        with self.assertRaises(TypeError):
            envelope.tick_row["last_price"] = 1.0
        self.assertLess(envelope.ingress_monotonic_ns, cutoff_ns)
        self.assertGreater(observation.handler_received_monotonic_ns, cutoff_ns)
        self.assertEqual(envelope.received_at_utc, envelope.tick_row["received_at"])

    def test_queue_overflow_latches_exact_gap_and_never_auto_recovers(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            TICK_INGRESS_ENVELOPE_ATTR,
            TickStreamPipeline,
            install_gateway_tick_ingress,
        )

        class FakeClock:
            def __init__(self) -> None:
                self.epoch = 1_784_000_000_000_000_000
                self.monotonic = 10

            def epoch_ns(self) -> int:
                self.epoch += 1
                return self.epoch

            def monotonic_ns(self) -> int:
                self.monotonic += 1
                return self.monotonic

            def sleep(self, seconds: float) -> None:
                self.monotonic += int(seconds * 1_000_000_000)

        forwarded_sequences: list[int] = []

        class Gateway:
            def on_tick(self, tick: SimpleNamespace) -> None:
                envelope = getattr(tick, TICK_INGRESS_ENVELOPE_ATTR)
                forwarded_sequences.append(envelope.ingress_sequence)

        pipeline = TickStreamPipeline(
            feed_session_id="feed-overflow",
            journal_segment_path=Path("unused.ndjson"),
            clock=FakeClock(),
            queue_capacity=1,
            max_buffer_ticks=1,
        )
        gateway = Gateway()
        restore = install_gateway_tick_ingress(gateway, pipeline)

        gateway.on_tick(self._ingress_tick(1.0))
        gateway.on_tick(self._ingress_tick(2.0))
        pipeline.take_ingress_nowait()
        gateway.on_tick(self._ingress_tick(3.0))
        snapshot = pipeline.snapshot()
        restore()
        restore()

        self.assertEqual(snapshot.dropped_tick_count, 2)
        self.assertEqual(
            (snapshot.gap.start_ingress_sequence, snapshot.gap.end_ingress_sequence),
            (2, 3),
        )
        self.assertFalse(snapshot.stream_ready)
        self.assertEqual(forwarded_sequences, [1, 2, 3])

    def test_fault_racing_enqueue_extends_published_gap_without_hot_path_lock(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def __init__(self) -> None:
                self.now = 1_784_000_000_000_000_000

            def epoch_ns(self) -> int:
                self.now += 1
                return self.now

            def monotonic_ns(self) -> int:
                return self.now

            def sleep(self, seconds: float) -> None:
                return None

        pipeline = TickStreamPipeline(
            feed_session_id="feed-enqueue-race",
            journal_segment_path=Path("unused-enqueue-race.ndjson"),
            clock=FakeClock(),
            queue_capacity=2,
            max_buffer_ticks=2,
        )
        pipeline.capture_ingress(self._ingress_tick(1.0))
        enqueue_entered = threading.Event()
        release_enqueue = threading.Event()
        original_put_nowait = pipeline._ingress_queue.put_nowait

        def blocking_put(item: object) -> None:
            enqueue_entered.set()
            self.assertTrue(release_enqueue.wait(timeout=1.0))
            original_put_nowait(item)

        with patch.object(
            pipeline._ingress_queue,
            "put_nowait",
            side_effect=blocking_put,
        ):
            producer = threading.Thread(
                target=pipeline.capture_ingress,
                args=(self._ingress_tick(2.0),),
            )
            # Preserve the single-producer identity for this deterministic
            # interleaving; only the queue call runs in the helper thread.
            pipeline._producer_thread_id = None
            producer.start()
            self.assertTrue(enqueue_entered.wait(timeout=1.0))
            pipeline._merge_suffix_gap(
                start_ingress_sequence=1,
                end_ingress_sequence=1,
                reason="journal_write_error",
            )
            release_enqueue.set()
            producer.join(timeout=1.0)

        snapshot = pipeline.durable_snapshot()
        self.assertEqual(snapshot.last_ingress_sequence, 2)
        self.assertIsNotNone(snapshot.gap)
        self.assertEqual(
            (
                snapshot.gap.start_ingress_sequence,
                snapshot.gap.end_ingress_sequence,
            ),
            (1, 2),
        )
        self.assertFalse(snapshot.stream_ready)

    def test_shutdown_does_not_relabel_an_existing_overflow_gap(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def __init__(self) -> None:
                self.now = 1_784_000_000_000_000_000

            def epoch_ns(self) -> int:
                self.now += 1
                return self.now

            def monotonic_ns(self) -> int:
                return self.now

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            pipeline = TickStreamPipeline(
                feed_session_id="feed-overflow-shutdown",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick(1.0))
            pipeline.capture_ingress(self._ingress_tick(2.0))
            pipeline.start()
            report = pipeline.shutdown(timeout_seconds=2.0)

        self.assertFalse(report.drained)
        self.assertIsNone(report.writer_fault)
        self.assertEqual(report.uncommitted_tick_count, 1)
        self.assertIsNotNone(report.gap)
        self.assertEqual(report.gap.reason, "ingress_queue_full")
        self.assertEqual(
            (
                report.gap.start_ingress_sequence,
                report.gap.end_ingress_sequence,
            ),
            (2, 2),
        )

    def test_gateway_forwarding_survives_capture_and_fault_latch_errors(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            TickStreamPipeline,
            install_gateway_tick_ingress,
        )

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        forwarded: list[SimpleNamespace] = []

        class Gateway:
            def on_tick(self, tick: SimpleNamespace) -> None:
                forwarded.append(tick)

        pipeline = TickStreamPipeline(
            feed_session_id="feed-capture-fault",
            journal_segment_path=Path("unused.ndjson"),
            clock=FakeClock(),
            queue_capacity=1,
            max_buffer_ticks=1,
        )
        gateway = Gateway()
        install_gateway_tick_ingress(gateway, pipeline)
        tick = self._ingress_tick()

        with (
            patch.object(
                pipeline, "capture_ingress", side_effect=RuntimeError("capture")
            ),
            patch.object(
                pipeline,
                "latch_capture_exception",
                side_effect=RuntimeError("latch"),
            ),
        ):
            gateway.on_tick(tick)

        self.assertEqual(forwarded, [tick])
        snapshot = pipeline.snapshot()
        self.assertFalse(snapshot.stream_ready)
        self.assertEqual(snapshot.dropped_tick_count, 1)
        self.assertEqual(snapshot.fault.kind, "ingress_fault_latch_exception")
        self.assertEqual(
            (
                snapshot.gap.start_ingress_sequence,
                snapshot.gap.end_ingress_sequence,
            ),
            (1, 1),
        )

    def test_ingress_scalar_copy_does_not_call_deepcopy(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class NoDeepcopyFloat(float):
            def __deepcopy__(self, memo: dict[int, object]) -> float:
                raise AssertionError("gateway hot path must not call deepcopy")

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        tick = self._ingress_tick(NoDeepcopyFloat(1245.5))
        pipeline = TickStreamPipeline(
            feed_session_id="feed-scalar-copy",
            journal_segment_path=Path("unused.ndjson"),
            clock=FakeClock(),
            queue_capacity=1,
            max_buffer_ticks=1,
        )

        envelope = pipeline.capture_ingress(tick)

        self.assertEqual(envelope.tick_row["last_price"], 1245.5)

    def test_event_handler_observation_is_diagnostic_only(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            TICK_INGRESS_ENVELOPE_ATTR,
            TickStreamPipeline,
        )

        class FakeClock:
            def __init__(self) -> None:
                self.epoch = 1_784_000_000_999_000_000
                self.monotonic = 500

            def epoch_ns(self) -> int:
                return self.epoch

            def monotonic_ns(self) -> int:
                self.monotonic += 100
                return self.monotonic

            def sleep(self, seconds: float) -> None:
                self.monotonic += int(seconds * 1_000_000_000)

        pipeline = TickStreamPipeline(
            feed_session_id="feed-observation",
            journal_segment_path=Path("unused.ndjson"),
            clock=FakeClock(),
            queue_capacity=4,
            max_buffer_ticks=4,
        )
        tick = self._ingress_tick()
        before = pipeline.capture_ingress(tick)

        observation = pipeline.observe_handler(tick)
        after = getattr(tick, TICK_INGRESS_ENVELOPE_ATTR)

        self.assertIsNotNone(observation)
        self.assertIs(after, before)
        self.assertEqual(
            after.tick_row["ingress_epoch_ns"], before.tick_row["ingress_epoch_ns"]
        )
        self.assertNotIn("handler_received_monotonic_ns", after.tick_row)

    def test_fsync_precedes_durable_watermark_and_snapshot_publish(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            fsync_entered = threading.Event()
            release_fsync = threading.Event()
            barrier_calls = 0

            def blocking_batch_barrier(fd: int) -> None:
                nonlocal barrier_calls
                barrier_calls += 1
                if barrier_calls == 1:
                    os.fsync(fd)
                    return
                fsync_entered.set()
                self.assertTrue(release_fsync.wait(timeout=1.0))
                os.fsync(fd)

            pipeline = TickStreamPipeline(
                feed_session_id="feed-fsync-order",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=4,
                max_buffer_ticks=4,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            with patch(
                "qmt_roll_official_live_tick_journal._durability_barrier",
                side_effect=blocking_batch_barrier,
            ):
                pipeline.start()
                self.assertTrue(fsync_entered.wait(timeout=1.0))
                before = pipeline.durable_snapshot()
                release_fsync.set()
                self.assertTrue(
                    pipeline.wait_until_durable(1, timeout_seconds=1.0)
                )
                after = pipeline.durable_snapshot()
            pipeline.shutdown(timeout_seconds=2.0)

        self.assertEqual(before.durable_ingress_sequence, 0)
        self.assertEqual(before.rows, ())
        self.assertEqual(after.durable_ingress_sequence, 1)
        self.assertEqual(
            [row["ingress_sequence"] for row in after.rows],
            [1],
        )

    def test_writer_error_latches_fault_and_rejects_ready_heartbeat(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            barrier_calls = 0

            def fail_batch_barrier(fd: int) -> None:
                nonlocal barrier_calls
                barrier_calls += 1
                if barrier_calls == 1:
                    os.fsync(fd)
                    return
                raise OSError(errno.ENOSPC, "disk full")

            pipeline = TickStreamPipeline(
                feed_session_id="feed-writer-error",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=4,
                max_buffer_ticks=4,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            with patch(
                "qmt_roll_official_live_tick_journal._durability_barrier",
                side_effect=fail_batch_barrier,
            ):
                pipeline.start()
                self.assertTrue(pipeline.wait_until_writer_stops(timeout_seconds=1.0))
            snapshot = pipeline.durable_snapshot()
            pipeline.shutdown(timeout_seconds=0.1)

        self.assertEqual(snapshot.durable_ingress_sequence, 0)
        self.assertIsNotNone(snapshot.writer_fault)
        self.assertEqual(snapshot.writer_fault.kind, "journal_write_error")
        self.assertFalse(snapshot.stream_ready)
        self.assertEqual(
            (
                snapshot.gap.start_ingress_sequence,
                snapshot.gap.end_ingress_sequence,
            ),
            (1, 1),
        )

    def test_writer_validates_batch_before_persisting_commit_frame(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_HEADER_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            TickIngressEnvelope,
            TickStreamPipeline,
        )

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "invalid-batch.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-valid",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            invalid = TickIngressEnvelope(
                feed_session_id="feed-wrong",
                ingress_sequence=1,
                symbol_sequence=1,
                received_at_utc="2026-07-14T13:00:00.000000000Z",
                ingress_epoch_ns=1,
                ingress_monotonic_ns=1,
                trace_id="invalid",
                tick_row=MappingProxyType(
                    {
                        "feed_session_id": "feed-wrong",
                        "ingress_sequence": 1,
                        "symbol_sequence": 1,
                        "vt_symbol": "JM609.DCE",
                    }
                ),
            )
            pipeline._last_ingress_sequence = 1
            pipeline._ingress_queue.put_nowait(invalid)
            pipeline.start()
            self.assertTrue(
                pipeline.wait_until_writer_stops(timeout_seconds=1.0)
            )
            persisted = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]
            snapshot = pipeline.durable_snapshot()

        self.assertEqual(snapshot.durable_ingress_sequence, 0)
        self.assertIsNotNone(snapshot.writer_fault)
        self.assertEqual(len(persisted), 1)
        self.assertEqual(
            persisted[0].get(JOURNAL_RECORD_TYPE_FIELD),
            JOURNAL_HEADER_RECORD_TYPE,
        )

    def test_graceful_shutdown_drains_all_enqueued_ticks_within_two_seconds(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def __init__(self) -> None:
                self.epoch = 1_784_000_000_000_000_000
                self.monotonic = 0

            def epoch_ns(self) -> int:
                self.epoch += 1
                return self.epoch

            def monotonic_ns(self) -> int:
                self.monotonic += 1
                return self.monotonic

            def sleep(self, seconds: float) -> None:
                return None

        expected_count = 9
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = TickStreamPipeline(
                feed_session_id="feed-drain",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=expected_count,
                max_buffer_ticks=expected_count,
                writer_batch_size=4,
                writer_flush_seconds=0.001,
            )
            for sequence in range(1, expected_count + 1):
                pipeline.capture_ingress(self._ingress_tick(float(sequence)))
            pipeline.start()
            report = pipeline.shutdown(timeout_seconds=2.0)

        self.assertTrue(report.drained)
        self.assertEqual(report.remaining_queue_depth, 0)
        self.assertIsNotNone(report.durable_through)
        self.assertEqual(report.durable_through.ingress_sequence, expected_count)
        self.assertIsNone(report.gap)
        self.assertIsNone(report.writer_fault)

    def test_durable_ring_capacity_records_per_symbol_eviction(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def __init__(self) -> None:
                self.epoch = 1_784_000_000_000_000_000

            def epoch_ns(self) -> int:
                self.epoch += 1
                return self.epoch

            def monotonic_ns(self) -> int:
                return self.epoch

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            pipeline = TickStreamPipeline(
                feed_session_id="feed-eviction",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=2,
                max_buffer_ticks=1,
                writer_batch_size=2,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick(1245.0))
            second = self._ingress_tick(540.0)
            second.vt_symbol = "I609.DCE"
            second.symbol = "I609"
            pipeline.capture_ingress(second)
            pipeline.start()
            report = pipeline.shutdown(timeout_seconds=2.0)
            snapshot = pipeline.durable_snapshot()

        self.assertTrue(report.drained)
        self.assertEqual(
            [row["vt_symbol"] for row in snapshot.rows],
            ["I609.DCE"],
        )
        self.assertEqual(
            snapshot.symbol_watermarks[
                "JM609.DCE"
            ].evicted_through_symbol_sequence,
            1,
        )
        self.assertEqual(
            snapshot.symbol_watermarks[
                "I609.DCE"
            ].first_buffered_symbol_sequence,
            1,
        )

    def test_shutdown_timeout_prevents_late_durable_commit(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            fsync_entered = threading.Event()
            release_fsync = threading.Event()
            barrier_calls = 0

            def blocking_batch_barrier(fd: int) -> None:
                nonlocal barrier_calls
                barrier_calls += 1
                if barrier_calls == 1:
                    os.fsync(fd)
                    return
                fsync_entered.set()
                self.assertTrue(release_fsync.wait(timeout=1.0))
                os.fsync(fd)

            pipeline = TickStreamPipeline(
                feed_session_id="feed-shutdown-timeout",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            with patch(
                "qmt_roll_official_live_tick_journal._durability_barrier",
                side_effect=blocking_batch_barrier,
            ):
                pipeline.start()
                self.assertTrue(fsync_entered.wait(timeout=1.0))
                report = pipeline.shutdown(timeout_seconds=0.01)
                release_fsync.set()
                self.assertTrue(
                    pipeline.wait_until_writer_stops(timeout_seconds=1.0)
                )
                after_release = pipeline.durable_snapshot()

        self.assertFalse(report.drained)
        self.assertEqual(report.writer_fault.kind, "shutdown_drain_timeout")
        self.assertEqual(
            (
                report.gap.start_ingress_sequence,
                report.gap.end_ingress_sequence,
            ),
            (1, 1),
        )
        self.assertEqual(after_release.durable_ingress_sequence, 0)

    def test_shutdown_timeout_revocation_is_atomic_with_writer_commit(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            fsync_entered = threading.Event()
            release_fsync = threading.Event()
            interleaving_started = threading.Event()
            barrier_calls = 0

            def blocking_batch_barrier(fd: int) -> None:
                nonlocal barrier_calls
                barrier_calls += 1
                if barrier_calls == 1:
                    os.fsync(fd)
                    return
                fsync_entered.set()
                self.assertTrue(release_fsync.wait(timeout=1.0))
                os.fsync(fd)

            pipeline = TickStreamPipeline(
                feed_session_id="feed-shutdown-linearization",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            original_merge = pipeline._merge_suffix_gap

            def force_commit_at_timeout_boundary(**kwargs: object) -> None:
                original_merge(**kwargs)
                if interleaving_started.is_set():
                    return
                interleaving_started.set()
                release_fsync.set()
                self.assertTrue(
                    pipeline.wait_until_writer_stops(timeout_seconds=1.0)
                )

            with (
                patch(
                    "qmt_roll_official_live_tick_journal._durability_barrier",
                    side_effect=blocking_batch_barrier,
                ),
                patch.object(
                    pipeline,
                    "_merge_suffix_gap",
                    side_effect=force_commit_at_timeout_boundary,
                ),
            ):
                pipeline.start()
                self.assertTrue(fsync_entered.wait(timeout=1.0))
                report = pipeline.shutdown(timeout_seconds=0.01)
                release_fsync.set()
                self.assertTrue(
                    pipeline.wait_until_writer_stops(timeout_seconds=1.0)
                )
                final_snapshot = pipeline.durable_snapshot()

        self.assertFalse(report.drained)
        self.assertEqual(report.writer_fault.kind, "shutdown_drain_timeout")
        self.assertEqual(report.durable_through, None)
        self.assertEqual(final_snapshot.durable_ingress_sequence, 0)
        self.assertEqual(
            (
                final_snapshot.gap.start_ingress_sequence,
                final_snapshot.gap.end_ingress_sequence,
            ),
            (1, 1),
        )

    def test_dirty_tail_recovery_isolates_partial_line_and_discloses_gap(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "feed-old.ndjson"
            journal.write_bytes(
                b"".join(
                    (
                        json.dumps(
                            {
                                "feed_session_id": "feed-old",
                                "ingress_sequence": sequence,
                            },
                            separators=(",", ":"),
                        ).encode("utf-8")
                        + b"\n"
                    )
                    for sequence in range(1, 8)
                )
                +
                b'{"feed_session_id":"feed-old","ingress_sequence":8'
            )
            result = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-old",
                    "last_ingress_sequence": 10,
                    "durable_ingress_sequence": 7,
                },
            )

            trusted_rows = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]
            isolated = result.isolated_tail_path

        self.assertIsNotNone(result.previous_durable_cursor)
        self.assertEqual(result.previous_durable_cursor.ingress_sequence, 7)
        self.assertEqual(
            (
                result.disclosed_gap.start_ingress_sequence,
                result.disclosed_gap.end_ingress_sequence,
            ),
            (8, 10),
        )
        self.assertEqual(
            [row["ingress_sequence"] for row in trusted_rows],
            list(range(1, 8)),
        )
        self.assertIsNotNone(isolated)
        self.assertGreater(result.isolated_byte_count, 0)

    def test_recovery_rebuilds_committed_batches_beyond_stale_heartbeat(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
            TickStreamPipeline,
            recover_or_isolate_dirty_tail,
        )

        class FakeClock:
            def __init__(self) -> None:
                self.now = 1_784_000_000_000_000_000

            def epoch_ns(self) -> int:
                self.now += 1
                return self.now

            def monotonic_ns(self) -> int:
                return self.now

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "feed-framed.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-framed",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=3,
                max_buffer_ticks=3,
                writer_batch_size=3,
                writer_flush_seconds=0.001,
            )
            for sequence in range(1, 4):
                pipeline.capture_ingress(self._ingress_tick(float(sequence)))
            pipeline.start()
            report = pipeline.shutdown(timeout_seconds=2.0)
            self.assertTrue(report.drained)

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-framed",
                    "durable_ingress_sequence": 1,
                    "last_ingress_sequence": 1,
                },
            )
            replay = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=DurableTickCursor("feed-framed", 3),
            )

        self.assertIsNotNone(recovered.previous_durable_cursor)
        self.assertEqual(recovered.previous_durable_cursor.ingress_sequence, 3)
        self.assertIsNone(recovered.disclosed_gap)
        self.assertIsNone(recovered.isolated_tail_path)
        self.assertEqual(recovered.isolated_byte_count, 0)
        self.assertEqual(
            [row["ingress_sequence"] for row in replay.records],
            [1, 2, 3],
        )
        self.assertTrue(replay.caught_up)

    def test_recovery_rejects_framed_segment_whose_header_is_missing(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_HEADER_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            TickStreamPipeline,
            recover_or_isolate_dirty_tail,
        )

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "missing-header.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-missing-header",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=2.0).drained)
            lines = journal.read_text(encoding="utf-8").splitlines(keepends=True)
            without_header = [
                line
                for line in lines
                if json.loads(line).get(JOURNAL_RECORD_TYPE_FIELD)
                != JOURNAL_HEADER_RECORD_TYPE
            ]
            journal.write_text("".join(without_header), encoding="utf-8")

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-missing-header",
                    "durable_ingress_sequence": 1,
                    "last_ingress_sequence": 1,
                },
            )

        self.assertIsNone(recovered.previous_durable_cursor)
        self.assertIsNotNone(recovered.disclosed_gap)
        self.assertEqual(
            (
                recovered.disclosed_gap.start_ingress_sequence,
                recovered.disclosed_gap.end_ingress_sequence,
            ),
            (1, 1),
        )
        self.assertIsNotNone(recovered.isolated_tail_path)

    def test_recovery_stops_at_first_bad_framed_batch_checksum(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_RECORD_TYPE_FIELD,
            TickStreamPipeline,
            recover_or_isolate_dirty_tail,
        )

        class FakeClock:
            def __init__(self) -> None:
                self.now = 1_784_000_000_000_000_000

            def epoch_ns(self) -> int:
                self.now += 1
                return self.now

            def monotonic_ns(self) -> int:
                return self.now

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "bad-second-batch.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-bad-second-batch",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=4,
                max_buffer_ticks=4,
                writer_batch_size=2,
                writer_flush_seconds=0.001,
            )
            for sequence in range(1, 5):
                pipeline.capture_ingress(self._ingress_tick(float(sequence)))
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=2.0).drained)

            rows = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]
            for row in rows:
                if row.get("ingress_sequence") == 3:
                    row["last_price"] = 999_999.0
                    break
            journal.write_text(
                "".join(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                    for row in rows
                ),
                encoding="utf-8",
            )

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-bad-second-batch",
                    "durable_ingress_sequence": 4,
                    "last_ingress_sequence": 4,
                },
            )
            retained = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIsNotNone(recovered.previous_durable_cursor)
        self.assertEqual(recovered.previous_durable_cursor.ingress_sequence, 2)
        self.assertIsNotNone(recovered.disclosed_gap)
        self.assertEqual(
            (
                recovered.disclosed_gap.start_ingress_sequence,
                recovered.disclosed_gap.end_ingress_sequence,
            ),
            (3, 4),
        )
        self.assertEqual(
            [row["ingress_sequence"] for row in retained if "ingress_sequence" in row],
            [1, 2],
        )
        self.assertTrue(
            any(JOURNAL_RECORD_TYPE_FIELD in row for row in retained)
        )

    def test_recovery_finalizes_complete_frame_after_ambiguous_barrier_error(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            TickStreamPipeline,
            recover_or_isolate_dirty_tail,
        )

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "ambiguous-frame.ndjson"
            barrier_calls = 0

            def ambiguous_batch_barrier(fd: int) -> None:
                nonlocal barrier_calls
                barrier_calls += 1
                os.fsync(fd)
                if barrier_calls == 2:
                    raise OSError(errno.EIO, "ambiguous fsync result")

            pipeline = TickStreamPipeline(
                feed_session_id="feed-ambiguous-frame",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            with patch(
                "qmt_roll_official_live_tick_journal._durability_barrier",
                side_effect=ambiguous_batch_barrier,
            ):
                pipeline.start()
                self.assertTrue(
                    pipeline.wait_until_writer_stops(timeout_seconds=1.0)
                )
            self.assertEqual(pipeline.durable_snapshot().durable_ingress_sequence, 0)

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-ambiguous-frame",
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 1,
                    "gap_end_ingress_sequence": 1,
                },
            )

        self.assertIsNotNone(recovered.previous_durable_cursor)
        self.assertEqual(recovered.previous_durable_cursor.ingress_sequence, 1)
        self.assertIsNone(recovered.disclosed_gap)
        self.assertIsNone(recovered.isolated_tail_path)

    def test_recovery_never_certifies_non_contiguous_legacy_prefix(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "feed-corrupt.ndjson"
            journal.write_text(
                "".join(
                    json.dumps(
                        {
                            "feed_session_id": "feed-corrupt",
                            "ingress_sequence": sequence,
                        }
                    )
                    + "\n"
                    for sequence in (1, 3)
                ),
                encoding="utf-8",
            )
            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-corrupt",
                    "durable_ingress_sequence": 3,
                    "last_ingress_sequence": 3,
                },
            )
            remaining = [
                json.loads(line)["ingress_sequence"]
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIsNotNone(recovered.previous_durable_cursor)
        self.assertEqual(recovered.previous_durable_cursor.ingress_sequence, 1)
        self.assertIsNotNone(recovered.disclosed_gap)
        self.assertEqual(
            (
                recovered.disclosed_gap.start_ingress_sequence,
                recovered.disclosed_gap.end_ingress_sequence,
            ),
            (2, 3),
        )
        self.assertEqual(remaining, [1])
        self.assertIsNotNone(recovered.isolated_tail_path)

    def test_reader_rejects_cross_session_cursor_and_undurable_tail(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "feed-a.ndjson"
            journal.write_text(
                "".join(
                    json.dumps(
                        {
                            "feed_session_id": "feed-a",
                            "ingress_sequence": sequence,
                        }
                    )
                    + "\n"
                    for sequence in range(1, 4)
                ),
                encoding="utf-8",
            )
            reader = TickStreamJournalReader(journal)
            durable = DurableTickCursor("feed-a", 2)

            batch = reader.read_after(None, durable_through=durable)
            cross_session = reader.read_after(
                DurableTickCursor("feed-b", 1),
                durable_through=durable,
            )

        self.assertEqual(
            [row["ingress_sequence"] for row in batch.records],
            [1, 2],
        )
        self.assertTrue(batch.caught_up)
        self.assertIsNotNone(cross_session.gap)
        self.assertEqual(cross_session.gap.reason, "cursor_session_mismatch")

    def test_reader_stops_before_gap_and_never_advances_cursor_past_it(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "feed-gap.ndjson"
            journal.write_text(
                "".join(
                    json.dumps(
                        {
                            "feed_session_id": "feed-gap",
                            "ingress_sequence": sequence,
                        }
                    )
                    + "\n"
                    for sequence in (1, 3, 4)
                ),
                encoding="utf-8",
            )
            batch = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=DurableTickCursor("feed-gap", 4),
            )

        self.assertEqual(
            [row["ingress_sequence"] for row in batch.records],
            [1],
        )
        self.assertIsNotNone(batch.next_cursor)
        self.assertEqual(batch.next_cursor.ingress_sequence, 1)
        self.assertIsNotNone(batch.gap)
        self.assertEqual(
            (
                batch.gap.start_ingress_sequence,
                batch.gap.end_ingress_sequence,
            ),
            (2, 2),
        )
        self.assertFalse(batch.caught_up)

    def test_reader_never_exposes_framed_rows_without_valid_commit_marker(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            JOURNAL_BATCH_COMMIT_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            TickStreamJournalReader,
            TickStreamPipeline,
        )

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "missing-marker.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-missing-marker",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=2.0).drained)
            lines = journal.read_text(encoding="utf-8").splitlines(keepends=True)
            journal.write_text(
                "".join(
                    line
                    for line in lines
                    if json.loads(line).get(JOURNAL_RECORD_TYPE_FIELD)
                    != JOURNAL_BATCH_COMMIT_RECORD_TYPE
                ),
                encoding="utf-8",
            )

            batch = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=DurableTickCursor("feed-missing-marker", 1),
            )

        self.assertEqual(batch.records, ())
        self.assertIsNone(batch.next_cursor)
        self.assertIsNotNone(batch.gap)
        self.assertEqual(
            (
                batch.gap.start_ingress_sequence,
                batch.gap.end_ingress_sequence,
            ),
            (1, 1),
        )
        self.assertFalse(batch.caught_up)


if __name__ == "__main__":
    unittest.main()
