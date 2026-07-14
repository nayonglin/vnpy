from __future__ import annotations

import json
import hashlib
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
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
            },
        )
        self.assertEqual(
            watermarks["I609.DCE"],
            {
                "received_at": "",
                "stream_sequence": 0,
                "symbol_stream_sequence": 0,
            },
        )
        self.assertNotIn("OLD609.DCE", watermarks)

    def test_gateway_ingress_stamp_precedes_event_engine_backlog(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

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
        tick = self._ingress_tick()

        envelope = pipeline.capture_ingress(tick)
        tick.last_price = 9999.0
        cutoff_ns = 200
        clock.monotonic = 300
        observation = pipeline.observe_handler(tick)

        self.assertIsNotNone(envelope)
        self.assertIsNotNone(observation)
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


if __name__ == "__main__":
    unittest.main()
