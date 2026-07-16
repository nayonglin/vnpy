from __future__ import annotations

import errno
import copy
import json
import hashlib
import threading
import io
import os
import signal
import time
from collections import deque
from contextlib import ExitStack, redirect_stderr, redirect_stdout
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

    @staticmethod
    def _lifecycle_fakes(
        *,
        register_failure_event: str = "",
    ) -> SimpleNamespace:
        state: dict[str, object] = {
            "event_engines": [],
            "main_close_count": 0,
            "td_close_count": 0,
            "md_close_count": 0,
        }

        class FakeThread:
            def __init__(self) -> None:
                self.alive = False

            def is_alive(self) -> bool:
                return self.alive

        class FakeEventEngine:
            def __init__(self) -> None:
                self._active = False
                self._thread = FakeThread()
                self._timer = FakeThread()
                state["event_engines"].append(self)

            def start(self) -> None:
                self._active = True
                self._thread.alive = True
                self._timer.alive = True

            def stop(self) -> None:
                self._active = False
                self._thread.alive = False
                self._timer.alive = False

            def register(self, event_type: str, _handler: object) -> None:
                if event_type == register_failure_event:
                    raise RuntimeError(f"register failed: {event_type}")

        class FakeTdApi:
            def close(self) -> None:
                state["td_close_count"] += 1

            def onRspQryInvestorPosition(
                self,
                data: dict[str, object],
                error: dict[str, object],
                reqid: int,
                last: bool,
            ) -> None:
                return None

        class FakeMdApi:
            def close(self) -> None:
                state["md_close_count"] += 1

        class FakeCtpGateway:
            default_name = "CTP"

            def __init__(self, event_engine: FakeEventEngine) -> None:
                self.event_engine = event_engine
                self.td_api = FakeTdApi()
                self.md_api = FakeMdApi()

            def on_tick(self, _tick: object) -> None:
                return None

            def send_order(self, _request: object) -> str:
                raise AssertionError("read-only runner must not send")

            def cancel_order(self, _request: object) -> None:
                raise AssertionError("read-only runner must not cancel")

            def close(self) -> None:
                self.td_api.close()
                self.md_api.close()

        class FakeMainEngine:
            def __init__(self, event_engine: FakeEventEngine) -> None:
                self.event_engine = event_engine
                self.engines: dict[str, object] = {}
                self.gateway: FakeCtpGateway | None = None
                event_engine.start()

            def add_gateway(self, _gateway_class: object) -> FakeCtpGateway:
                self.gateway = FakeCtpGateway(self.event_engine)
                return self.gateway

            def connect(self, _setting: object, _gateway_name: str) -> None:
                return None

            def subscribe(self, _request: object, _gateway_name: str) -> None:
                return None

            def close(self) -> None:
                state["main_close_count"] += 1
                self.event_engine.stop()
                if self.gateway is not None:
                    self.gateway.close()

        return SimpleNamespace(
            state=state,
            EventEngine=FakeEventEngine,
            MainEngine=FakeMainEngine,
            CtpGateway=FakeCtpGateway,
            CtpTdApi=FakeTdApi,
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

    def test_journal_parser_normalizes_python_integer_limit_value_error(self) -> None:
        from qmt_roll_official_live_tick_journal import _parse_record_line

        raw_line = b'{"ingress_sequence":' + (b"9" * 5_000) + b"}\n"
        row, error = _parse_record_line(raw_line)

        self.assertIsNone(row)
        self.assertEqual(error, "journal_invalid_json_before_durable_watermark")

    def test_split_journal_module_preserves_legacy_public_imports(self) -> None:
        from qmt_roll_official_live_tick_journal import (
            TickStreamJournalReader,
            recover_or_isolate_dirty_tail,
        )
        from qmt_roll_official_live_tick_reader import (
            TickStreamJournalReader as SplitReader,
        )
        from qmt_roll_official_live_tick_recovery import (
            recover_or_isolate_dirty_tail as split_recovery,
        )

        self.assertIs(TickStreamJournalReader, SplitReader)
        self.assertIs(recover_or_isolate_dirty_tail, split_recovery)

    def test_writer_rejects_batch_payload_above_bounded_memory_limit(self) -> None:
        from qmt_roll_official_live_tick_journal import (
            MAX_JOURNAL_BATCH_BYTES,
            AsyncTickJournalWriter,
        )
        from qmt_roll_official_live_tick_stream import TickIngressEnvelope

        blob = "x" * (MAX_JOURNAL_BATCH_BYTES // 2)
        batch = [
            TickIngressEnvelope(
                feed_session_id="feed-bounded-payload",
                ingress_sequence=sequence,
                symbol_sequence=sequence,
                received_at_utc="2026-07-15T00:00:00.000000+00:00",
                ingress_epoch_ns=sequence,
                ingress_monotonic_ns=sequence,
                trace_id=f"stage179-tick/feed-bounded-payload/{sequence}",
                tick_row=MappingProxyType(
                    {
                        "feed_session_id": "feed-bounded-payload",
                        "ingress_sequence": sequence,
                        "blob": blob,
                    }
                ),
            )
            for sequence in (1, 2)
        ]

        with self.assertRaisesRegex(ValueError, "batch_payload_limit"):
            AsyncTickJournalWriter._serialized_batch(batch)

    def test_pipeline_rejects_oversized_feed_session_id(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "feed_session_id.*too long"):
                TickStreamPipeline(
                    feed_session_id="会" * 100,
                    journal_segment_path=Path(tmp) / "ticks.ndjson",
                    clock=FakeClock(),
                    queue_capacity=1,
                    max_buffer_ticks=1,
                )

    def test_writer_rejects_oversized_header_and_commit_control_records(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_journal import AsyncTickJournalWriter
        from qmt_roll_official_live_tick_stream import TickIngressEnvelope

        writer = object.__new__(AsyncTickJournalWriter)
        writer.pipeline = SimpleNamespace(feed_session_id="feed-control-bound")
        envelope = TickIngressEnvelope(
            feed_session_id="feed-control-bound",
            ingress_sequence=1,
            symbol_sequence=1,
            received_at_utc="2026-07-15T00:00:00.000000+00:00",
            ingress_epoch_ns=1,
            ingress_monotonic_ns=1,
            trace_id="stage179-tick/feed-control-bound/1",
            tick_row=MappingProxyType({"ingress_sequence": 1}),
        )

        with patch.object(journal_module, "MAX_JOURNAL_LINE_BYTES", 64):
            with self.assertRaisesRegex(ValueError, "control_record_too_large"):
                writer._serialized_header()
            with self.assertRaisesRegex(ValueError, "control_record_too_large"):
                AsyncTickJournalWriter._serialized_commit_frame(
                    [envelope],
                    b'{"ingress_sequence":1}\n',
                )

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

    def test_atomic_publication_propagates_parent_directory_open_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "heartbeat.json"
            prior = {
                "feed_session_id": "feed-parent-fsync-failure",
                "journal_authority_committed": True,
                "stream_ready": True,
            }
            target.write_text(json.dumps(prior), encoding="utf-8")
            with patch.object(
                stage608.os,
                "open",
                side_effect=OSError("injected parent directory open failure"),
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "injected parent directory open failure",
                ):
                    stage608._atomic_write_bytes(
                        target,
                        json.dumps(prior).encode("utf-8"),
                    )

            self.assertEqual(target.read_bytes(), b"")
            self.assertEqual(
                stage608._heartbeat_owned_by_session(
                    target,
                    "feed-parent-fsync-failure",
                ),
                {},
            )

    def test_atomic_publication_revokes_both_possible_inodes_after_directory_barrier_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "heartbeat.json"
            rollback_alias = root / "pre_replace_authority.json"
            prior = {
                "feed_session_id": "feed-directory-rollback",
                "journal_authority_committed": True,
                "journal_session_state": "clean_stopped",
                "stream_ready": False,
                "transport_ready": False,
                "stopped": True,
                "clean_shutdown": True,
            }
            target.write_text(json.dumps(prior), encoding="utf-8")
            os.link(target, rollback_alias)

            with patch.object(
                stage608,
                "_fsync_directory_fd",
                side_effect=OSError("injected directory barrier failure"),
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "injected directory barrier failure",
                ):
                    stage608._atomic_write_bytes(target, b'{"new":true}')

            self.assertEqual(target.read_bytes(), b"")
            self.assertEqual(rollback_alias.read_bytes(), b"")
            self.assertEqual(
                stage608._heartbeat_owned_by_session(
                    rollback_alias,
                    "feed-directory-rollback",
                ),
                {},
            )

    def test_atomic_publication_reports_barrier_and_invalidation_double_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "heartbeat.json"
            target.write_text(
                json.dumps(
                    {
                        "feed_session_id": "feed-double-failure",
                        "journal_authority_committed": True,
                        "stream_ready": True,
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(
                    stage608,
                    "_fsync_directory_fd",
                    side_effect=OSError("injected directory barrier failure"),
                ),
                patch.object(
                    stage608,
                    "_invalidate_open_authority",
                    side_effect=OSError("injected invalidation failure"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "atomic_publish_authority_invalidation_failed",
                ):
                    stage608._atomic_write_bytes(target, b'{"new":true}')

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
        published_heartbeats: list[dict[str, object]] = []
        real_publish = stage608._publish_tick_snapshot_commit

        def capture_publish(**kwargs: object) -> dict[str, object]:
            published_heartbeats.append(copy.deepcopy(kwargs["heartbeat"]))
            return real_publish(**kwargs)

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
                patch.object(
                    stage608,
                    "_publish_tick_snapshot_commit",
                    side_effect=capture_publish,
                ),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=journal,
                        heartbeat_path=heartbeat,
                        duration_seconds=1,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                    )

            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))
            persisted_segment = Path(persisted["journal_segment_path"])
            journal_rows = [
                json.loads(line)
                for line in persisted_segment.read_text(encoding="utf-8").splitlines()
            ]
            persisted_segment_size = persisted_segment.stat().st_size

        self.assertEqual(result["send_order_api_called_count"], 0)
        self.assertEqual(result["cancel_order_api_called_count"], 0)
        self.assertEqual(result["last_ingress_sequence"], 1)
        self.assertEqual(result["durable_ingress_sequence"], 1)
        self.assertEqual(persisted["stream_sequence"], 1)
        self.assertEqual(persisted["journal_tick_count"], 1)
        self.assertEqual(persisted["durable_ingress_sequence"], 1)
        self.assertTrue(persisted["stopped"])
        self.assertTrue(persisted["clean_shutdown"])
        self.assertEqual(persisted["journal_session_state"], "clean_stopped")
        self.assertEqual(persisted["journal_schema"], "stage179_framed_v1")
        self.assertTrue(persisted["journal_authority_committed"])
        self.assertEqual(
            persisted["durable_journal_byte_offset"],
            persisted_segment_size,
        )
        self.assertEqual(
            persisted["journal_commit_revoked_from_ingress_sequence"],
            0,
        )
        self.assertFalse(persisted["stream_ready"])
        published_states = {
            str(row.get("journal_session_state")) for row in published_heartbeats
        }
        self.assertTrue(
            {"starting", "running", "clean_stopped"}.issubset(published_states),
            published_states,
        )
        for heartbeat_row in published_heartbeats:
            self.assertIs(
                type(heartbeat_row["symbol_eviction_watermark_schema_version"]),
                int,
            )
            self.assertEqual(
                heartbeat_row["symbol_eviction_watermark_schema_version"],
                1,
            )
        self.assertNotEqual(persisted_segment, journal)
        self.assertEqual(
            [
                row["ingress_sequence"]
                for row in journal_rows
                if "ingress_sequence" in row
            ],
            [1],
        )

    def test_gateway_restore_waits_for_inflight_capture_and_fences_late_callback(self) -> None:
        capture_entered = threading.Event()
        release_capture = threading.Event()
        restore_done = threading.Event()
        captures: list[object] = []
        forwarded: list[object] = []

        class BlockingPipeline:
            def capture_ingress(self, tick: object) -> None:
                capture_entered.set()
                self.assert_release()
                captures.append(tick)

            @staticmethod
            def assert_release() -> None:
                if not release_capture.wait(timeout=1.0):
                    raise AssertionError("capture release timed out")

            def latch_capture_exception(self, _exc: Exception) -> None:
                raise AssertionError("capture must not fail")

        class Gateway:
            def on_tick(self, tick: object) -> None:
                forwarded.append(tick)

        gateway = Gateway()
        restore = stage608.install_gateway_tick_ingress(
            gateway,
            BlockingPipeline(),
        )
        first_tick = object()
        callback_thread = threading.Thread(
            target=gateway.on_tick,
            args=(first_tick,),
        )
        callback_thread.start()
        self.assertTrue(capture_entered.wait(timeout=1.0))

        restore_thread = threading.Thread(
            target=lambda: (restore(), restore_done.set()),
        )
        restore_thread.start()
        try:
            self.assertFalse(restore_done.wait(timeout=0.05))
        finally:
            release_capture.set()
            callback_thread.join(timeout=1.0)
            restore_thread.join(timeout=1.0)
        self.assertTrue(restore_done.is_set())
        self.assertFalse(callback_thread.is_alive())
        self.assertFalse(restore_thread.is_alive())

        late_tick = object()
        gateway.on_tick(late_tick)
        self.assertEqual(captures, [first_tick])
        self.assertEqual(forwarded, [first_tick, late_tick])

    def test_gateway_restore_waits_for_original_forwarding_to_finish(self) -> None:
        forwarding_entered = threading.Event()
        release_forwarding = threading.Event()
        restore_done = threading.Event()

        class Pipeline:
            def capture_ingress(self, _tick: object) -> None:
                return None

            def latch_capture_exception(self, _exc: Exception) -> None:
                raise AssertionError("capture must not fail")

        class Gateway:
            def on_tick(self, _tick: object) -> None:
                forwarding_entered.set()
                if not release_forwarding.wait(timeout=1.0):
                    raise AssertionError("forwarding release timed out")

        gateway = Gateway()
        restore = stage608.install_gateway_tick_ingress(gateway, Pipeline())
        callback_thread = threading.Thread(target=gateway.on_tick, args=(object(),))
        callback_thread.start()
        self.assertTrue(forwarding_entered.wait(timeout=1.0))
        restore_thread = threading.Thread(
            target=lambda: (restore(), restore_done.set())
        )
        restore_thread.start()
        try:
            self.assertFalse(restore_done.wait(timeout=0.05))
        finally:
            release_forwarding.set()
            callback_thread.join(timeout=1.0)
            restore_thread.join(timeout=1.0)
        self.assertTrue(restore_done.is_set())
        self.assertFalse(callback_thread.is_alive())
        self.assertFalse(restore_thread.is_alive())

    def test_saved_stale_gateway_wrapper_only_forwards_after_restore(self) -> None:
        captures: list[object] = []
        forwarded: list[object] = []

        class Pipeline:
            def capture_ingress(self, tick: object) -> None:
                captures.append(tick)

            def latch_capture_exception(self, _exc: Exception) -> None:
                raise AssertionError("capture must not fail")

        class Gateway:
            def on_tick(self, tick: object) -> None:
                forwarded.append(tick)

        gateway = Gateway()
        restore = stage608.install_gateway_tick_ingress(gateway, Pipeline())
        stale_wrapper = gateway.on_tick
        restore()
        late_tick = object()
        stale_wrapper(late_tick)

        self.assertEqual(captures, [])
        self.assertEqual(forwarded, [late_tick])

    def test_late_capture_after_shutdown_report_forces_fault_stopped(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        self_test = self

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, _setting: dict[str, object]) -> None:
                self.on_tick(self_test._ingress_tick())
                time.sleep(0.1)

            def subscribe(self, _request: object) -> None:
                return None

            def send_order(self, _request: object) -> str:
                raise AssertionError("read-only runner must not send")

            def cancel_order(self, _request: object) -> None:
                raise AssertionError("read-only runner must not cancel")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        real_shutdown = stage608.TickStreamPipeline.shutdown
        parent_checks = 0

        def shutdown_then_late_capture(
            pipeline: object,
            timeout_seconds: float,
        ) -> object:
            report = real_shutdown(
                pipeline,
                timeout_seconds=timeout_seconds,
            )
            pipeline.capture_ingress(self._ingress_tick(1246.0))
            return report

        def parent_probe(_pid: int, _signum: int) -> None:
            nonlocal parent_checks
            parent_checks += 1
            if parent_checks > 1:
                raise ProcessLookupError

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            with (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(
                    stage608,
                    "_ctp_setting_from_env",
                    return_value={},
                ),
                patch.object(
                    stage608,
                    "_analyze_logs",
                    return_value={
                        "md_login_success": True,
                        "td_login_success": True,
                    },
                ),
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(
                    stage608.MainEngine,
                    "write_log",
                    return_value=None,
                ),
                patch.object(stage608.os, "kill", side_effect=parent_probe),
                patch.object(
                    stage608.TickStreamPipeline,
                    "shutdown",
                    new=shutdown_then_late_capture,
                ),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                    parent_pid=999_999,
                )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertTrue(result["ever_stream_ready"])
        self.assertEqual(
            persisted["symbol_eviction_watermark_schema_version"],
            1,
        )
        self.assertTrue(persisted["gap_latched"])
        self.assertEqual(
            persisted["journal_session_state"],
            "fault_stopped",
        )
        self.assertFalse(persisted["clean_shutdown"])
        self.assertEqual(
            stage608._stream_exit_code(connect=True, result=result),
            2,
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
                self.original_on_tick = lambda _tick: calls.append("original_tick")
                self.on_tick = lambda _tick: calls.append("wrapped_tick")
                self.md_api = FakeMdApi(self)

            def close(self) -> None:
                calls.append("aggregate_close")
                self.on_tick(object())

        gateway = FakeGateway()

        def restore() -> None:
            calls.append("restore_wrapper")
            gateway.on_tick = gateway.original_on_tick

        errors = stage608._quiesce_market_data_ingress(
            gateway,
            FakePipeline(),
            restore,
        )

        gateway.close()
        restore()

        self.assertEqual(errors, {})
        self.assertEqual(
            calls,
            [
                "stop_accepting",
                "md_close",
                "wrapped_tick",
                "aggregate_close",
                "wrapped_tick",
                "restore_wrapper",
            ],
        )

    def test_shutdown_keeps_wrapper_installed_when_md_close_fails(self) -> None:
        calls: list[str] = []

        class FakePipeline:
            def stop_accepting(self) -> None:
                calls.append("stop_accepting")

        class FailingMdApi:
            def close(self) -> None:
                calls.append("md_close")
                raise RuntimeError("md close failed")

        gateway = SimpleNamespace(md_api=FailingMdApi())

        def restore() -> None:
            calls.append("restore_wrapper")

        errors = stage608._quiesce_market_data_ingress(
            gateway,
            FakePipeline(),
            restore,
        )

        self.assertIn("market_data_close_error", errors)
        self.assertEqual(calls, ["stop_accepting", "md_close"])

    def test_shutdown_fences_non_idempotent_md_close_before_aggregate_close(self) -> None:
        calls: list[str] = []

        class FakePipeline:
            def stop_accepting(self) -> None:
                calls.append("stop_accepting")

        class NonIdempotentMdApi:
            def close(self) -> None:
                calls.append("md_close")
                if calls.count("md_close") > 1:
                    raise RuntimeError("native md exit called twice")

        class FakeGateway:
            def __init__(self) -> None:
                self.md_api = NonIdempotentMdApi()

            def close(self) -> None:
                calls.append("aggregate_close")
                self.md_api.close()

        gateway = FakeGateway()
        errors = stage608._quiesce_market_data_ingress(
            gateway,
            FakePipeline(),
            lambda: None,
        )
        gateway.close()

        self.assertEqual(errors, {})
        self.assertEqual(
            calls,
            ["stop_accepting", "md_close", "aggregate_close"],
        )

    def test_event_engine_fallback_retries_when_active_flag_cleared_but_threads_live(self) -> None:
        calls: list[str] = []

        class FakeThread:
            def __init__(self) -> None:
                self.alive = True

            def is_alive(self) -> bool:
                return self.alive

        class HalfStoppedEventEngine:
            def __init__(self) -> None:
                self._active = False
                self._timer = FakeThread()
                self._thread = FakeThread()

            def stop(self) -> None:
                calls.append("stop")
                self._timer.alive = False
                self._thread.alive = False

        event_engine = HalfStoppedEventEngine()
        error = stage608._stop_event_engine_after_close_failure(event_engine)

        self.assertEqual(error, "")
        self.assertEqual(calls, ["stop"])
        self.assertFalse(event_engine._timer.is_alive())
        self.assertFalse(event_engine._thread.is_alive())

    def test_blocked_recovery_preserves_authoritative_prior_journal_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            old_segment = root / "old-feed.ndjson"
            prior = {
                "feed_session_id": "old-feed",
                "journal_segment_path": str(old_segment),
                "journal_schema": "stage179_framed_v1",
                "durable_ingress_sequence": 7,
                "last_ingress_sequence": 8,
                "stream_ready": True,
                "transport_ready": True,
                "stopped": False,
            }
            prior_bytes = json.dumps(prior).encode("utf-8")
            heartbeat.write_bytes(prior_bytes)

            with (
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(
                    stage608,
                    "recover_or_isolate_dirty_tail",
                    side_effect=OSError("recovery barrier failed"),
                ),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )

            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))
            persisted_bytes = heartbeat.read_bytes()
            attempt = json.loads(
                stage608._startup_attempt_path(heartbeat).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result["status"], "stream_blocked_journal_recovery_error")
        self.assertEqual(persisted["feed_session_id"], "old-feed")
        self.assertEqual(persisted["journal_segment_path"], str(old_segment))
        self.assertEqual(persisted["durable_ingress_sequence"], 7)
        self.assertNotEqual(persisted_bytes, prior_bytes)
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])
        self.assertTrue(persisted["stopped"])
        self.assertFalse(persisted["clean_shutdown"])
        self.assertEqual(
            persisted["journal_session_state"],
            "fault_stopped",
        )
        self.assertTrue(attempt["recovery_blocked"])
        self.assertEqual(
            attempt["status"],
            "stream_blocked_journal_recovery_error",
        )

    def test_blocked_startup_rotates_revision_and_removes_old_snapshot_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = Path(tmp) / "heartbeat.json"
            previous = {
                "feed_session_id": "old-feed",
                "journal_segment_path": str(Path(tmp) / "old.ndjson"),
                "journal_schema": "stage179_framed_v1",
                "journal_authority_committed": True,
                "journal_session_state": "running",
                "durable_ingress_sequence": 7,
                "last_ingress_sequence": 8,
                "stream_ready": True,
                "transport_ready": True,
                "writer_alive": True,
                "stopped": False,
                "clean_shutdown": False,
                "heartbeat_revision_uuid": "old-revision",
                "tick_snapshot_generation_uuid": "old-generation",
                "tick_snapshot_commit": {
                    "generation_uuid": "old-generation",
                    "stream_sequence": 7,
                },
            }
            persisted = stage608._publish_blocked_stream_startup(
                heartbeat,
                summary={
                    "status": "stream_blocked_missing_env",
                    "feed_session_id": "startup-attempt",
                },
                previous_heartbeat=previous,
            )

        self.assertNotEqual(
            persisted["heartbeat_revision_uuid"],
            previous["heartbeat_revision_uuid"],
        )
        self.assertNotIn("tick_snapshot_generation_uuid", persisted)
        self.assertNotIn("tick_snapshot_commit", persisted)
        self.assertFalse(persisted["writer_alive"])
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])

    def test_corrupt_heartbeat_is_preserved_and_gets_startup_attempt_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            corrupt_bytes = b'{"feed_session_id":"old-feed"'
            heartbeat.write_bytes(corrupt_bytes)

            with (
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )

            attempt = json.loads(
                stage608._startup_attempt_path(heartbeat).read_text(
                    encoding="utf-8"
                )
            )
            persisted_bytes = heartbeat.read_bytes()
            heartbeat_resolved = str(heartbeat.resolve())

        self.assertEqual(result["status"], "stream_blocked_heartbeat_read_error")
        self.assertEqual(persisted_bytes, corrupt_bytes)
        self.assertTrue(attempt["recovery_blocked"])
        self.assertFalse(attempt["journal_authority_committed"])
        self.assertEqual(
            attempt["authoritative_heartbeat_path"],
            heartbeat_resolved,
        )

    def test_contending_stream_owner_never_connects_or_mutates_active_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            active = {
                "feed_session_id": "active-owner",
                "journal_authority_committed": True,
                "stream_ready": True,
                "transport_ready": True,
                "stopped": False,
            }
            active_bytes = json.dumps(active, sort_keys=True).encode("utf-8")
            heartbeat.write_bytes(active_bytes)

            with stage608._exclusive_stream_owner_lock(heartbeat):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )

            self.assertEqual(heartbeat.read_bytes(), active_bytes)
            self.assertFalse(stage608._startup_attempt_path(heartbeat).exists())

        self.assertEqual(result["status"], "stream_blocked_owner_lock_contended")
        self.assertEqual(result["send_order_api_called_count"], 0)
        self.assertEqual(result["cancel_order_api_called_count"], 0)
        self.assertEqual(
            stage608._stream_exit_code(connect=True, result=result),
            2,
        )

    def test_preflight_block_preserves_authoritative_prior_journal_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            old_segment = root / "old-feed.ndjson"
            prior = {
                "feed_session_id": "old-feed",
                "journal_segment_path": str(old_segment),
                "journal_schema": "stage179_framed_v1",
                "durable_ingress_sequence": 7,
                "stream_ready": False,
                "stopped": True,
                "clean_shutdown": True,
            }
            prior_bytes = json.dumps(prior).encode("utf-8")
            heartbeat.write_bytes(prior_bytes)

            with (
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(
                    stage608,
                    "_required_env_missing",
                    return_value=["CTP_USERID"],
                ),
                patch.object(stage608, "_env_status", return_value={}),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )

            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))
            persisted_bytes = heartbeat.read_bytes()
            attempt = json.loads(
                stage608._startup_attempt_path(heartbeat).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result["status"], "stream_blocked_missing_env")
        self.assertEqual(persisted["feed_session_id"], "old-feed")
        self.assertEqual(persisted["journal_segment_path"], str(old_segment))
        self.assertEqual(persisted["durable_ingress_sequence"], 7)
        self.assertNotEqual(persisted_bytes, prior_bytes)
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])
        self.assertTrue(persisted["stopped"])
        self.assertTrue(persisted["clean_shutdown"])
        self.assertEqual(persisted["journal_session_state"], "clean_stopped")
        self.assertTrue(attempt["recovery_blocked"])
        self.assertEqual(
            attempt["status"],
            "stream_blocked_missing_env",
        )

    def test_pipeline_initialization_close_error_still_revokes_old_readiness(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        event_engine_stop_calls: list[int] = []
        real_event_engine_stop = stage608.EventEngine.stop

        def recording_event_engine_stop(engine: object) -> None:
            event_engine_stop_calls.append(id(engine))
            real_event_engine_stop(engine)

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                return None

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("must remain read-only")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("must remain read-only")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            old_segment = root / "old.ndjson"
            prior = {
                "feed_session_id": "old-ready",
                "journal_segment_path": str(old_segment),
                "journal_schema": "stage179_framed_v1",
                "journal_session_state": "clean_stopped",
                "durable_ingress_sequence": 0,
                "last_ingress_sequence": 0,
                "stream_ready": True,
                "transport_ready": True,
                "stopped": True,
                "clean_shutdown": True,
            }
            heartbeat.write_text(json.dumps(prior), encoding="utf-8")
            with (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(
                    stage608,
                    "TickStreamPipeline",
                    side_effect=RuntimeError("pipeline init failed"),
                ),
                patch.object(
                    stage608.MainEngine,
                    "close",
                    side_effect=RuntimeError("aggregate close failed"),
                ),
                patch.object(
                    stage608.EventEngine,
                    "stop",
                    new=recording_event_engine_stop,
                ),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(
            result["status"],
            "stream_blocked_pipeline_initialization_error",
        )
        self.assertIn("pipeline_initialization_close_error", result)
        self.assertEqual(len(event_engine_stop_calls), 1)
        self.assertEqual(persisted["feed_session_id"], "old-ready")
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])

    def test_main_engine_constructor_failure_stops_started_event_engine_and_revokes_heartbeat(self) -> None:
        from qmt_roll_official_live_tick_stream import JournalRecoveryResult

        class FakeThread:
            def __init__(self) -> None:
                self.alive = False

            def is_alive(self) -> bool:
                return self.alive

        class FakeEventEngine:
            def __init__(self) -> None:
                self._active = False
                self._thread = FakeThread()
                self._timer = FakeThread()

            def start(self) -> None:
                self._active = True
                self._thread.alive = True
                self._timer.alive = True

            def stop(self) -> None:
                self._active = False
                self._thread.alive = False
                self._timer.alive = False

        created_event_engines: list[FakeEventEngine] = []

        def make_event_engine() -> FakeEventEngine:
            engine = FakeEventEngine()
            created_event_engines.append(engine)
            return engine

        class ExplodingMainEngine:
            def __init__(self, event_engine: FakeEventEngine) -> None:
                event_engine.start()
                raise RuntimeError("main engine constructor failed")

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = SimpleNamespace(default_name="CTP")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "feed_session_id": "old-ready",
                        "journal_segment_path": str(root / "old.ndjson"),
                        "journal_schema": "stage179_framed_v1",
                        "journal_authority_committed": True,
                        "journal_session_state": "running",
                        "durable_ingress_sequence": 7,
                        "last_ingress_sequence": 8,
                        "stream_ready": True,
                        "transport_ready": True,
                        "writer_alive": True,
                        "stopped": False,
                        "clean_shutdown": False,
                        "heartbeat_revision_uuid": "old-revision",
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(
                    stage608,
                    "_recover_previous_journal",
                    return_value=JournalRecoveryResult(
                        previous_durable_cursor=None,
                        isolated_tail_path=None,
                        isolated_byte_count=0,
                        disclosed_gap=None,
                        disclosed_gaps=(),
                        journal_schema="stage179_framed_v1",
                    ),
                ),
                patch.object(stage608, "EventEngine", new=make_event_engine),
                patch.object(stage608, "MainEngine", new=ExplodingMainEngine),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(
            result["status"],
            "stream_blocked_pipeline_initialization_error",
        )
        self.assertEqual(len(created_event_engines), 1)
        self.assertFalse(created_event_engines[0]._thread.is_alive())
        self.assertFalse(created_event_engines[0]._timer.is_alive())
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])
        self.assertNotEqual(
            persisted["heartbeat_revision_uuid"],
            "old-revision",
        )

    def test_stream_handler_registration_failure_stops_resources_and_revokes_readiness(self) -> None:
        fakes = self._lifecycle_fakes(
            register_failure_event=stage608.EVENT_LOG,
        )
        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = fakes.CtpGateway
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "feed_session_id": "old-ready",
                        "journal_segment_path": str(root / "old.ndjson"),
                        "journal_schema": "stage179_framed_v1",
                        "journal_session_state": "clean_stopped",
                        "durable_ingress_sequence": 0,
                        "last_ingress_sequence": 0,
                        "stream_ready": True,
                        "transport_ready": True,
                        "stopped": True,
                        "clean_shutdown": True,
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(stage608, "EventEngine", new=fakes.EventEngine),
                patch.object(stage608, "MainEngine", new=fakes.MainEngine),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        event_engine = fakes.state["event_engines"][0]
        self.assertFalse(event_engine._active)
        self.assertFalse(event_engine._thread.is_alive())
        self.assertFalse(event_engine._timer.is_alive())
        self.assertEqual(fakes.state["main_close_count"], 1)
        self.assertEqual(fakes.state["td_close_count"], 1)
        self.assertEqual(fakes.state["md_close_count"], 1)
        self.assertIn("register failed", result["exception"])
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])

    def test_stream_partial_signal_install_failure_restores_handlers_and_revokes_readiness(self) -> None:
        fakes = self._lifecycle_fakes()
        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = fakes.CtpGateway
        old_handlers = {
            signal.SIGTERM: "old-sigterm",
            signal.SIGINT: "old-sigint",
        }
        signal_calls: list[tuple[object, object]] = []

        def flaky_signal(signum: object, handler: object) -> object:
            signal_calls.append((signum, handler))
            if len(signal_calls) == 2:
                raise RuntimeError("second signal install failed")
            return old_handlers[signum]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "feed_session_id": "old-ready",
                        "journal_segment_path": str(root / "old.ndjson"),
                        "journal_schema": "stage179_framed_v1",
                        "journal_session_state": "clean_stopped",
                        "durable_ingress_sequence": 0,
                        "last_ingress_sequence": 0,
                        "stream_ready": True,
                        "transport_ready": True,
                        "stopped": True,
                        "clean_shutdown": True,
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(stage608, "EventEngine", new=fakes.EventEngine),
                patch.object(stage608, "MainEngine", new=fakes.MainEngine),
                patch.object(
                    stage608.signal,
                    "getsignal",
                    side_effect=lambda signum: old_handlers[signum],
                ),
                patch.object(
                    stage608.signal,
                    "signal",
                    side_effect=flaky_signal,
                ),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(
            [(call[0], call[1]) for call in signal_calls],
            [
                (signal.SIGTERM, signal_calls[0][1]),
                (signal.SIGINT, signal_calls[1][1]),
                (signal.SIGTERM, "old-sigterm"),
            ],
        )
        event_engine = fakes.state["event_engines"][0]
        self.assertFalse(event_engine._active)
        self.assertEqual(fakes.state["main_close_count"], 1)
        self.assertIn("second signal install failed", result["exception"])
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])

    def test_stream_persists_stopped_before_signal_restore_and_downgrades_restore_failure(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        self_test = self

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, _setting: dict[str, object]) -> None:
                self.on_tick(self_test._ingress_tick())
                time.sleep(0.1)

            def subscribe(self, _request: object) -> None:
                return None

            def send_order(self, _request: object) -> str:
                raise AssertionError("read-only runner must not send")

            def cancel_order(self, _request: object) -> None:
                raise AssertionError("read-only runner must not cancel")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        for fail_restore in (False, True):
            with self.subTest(fail_restore=fail_restore):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    heartbeat = root / "heartbeat.json"
                    old_handlers = {
                        signal.SIGTERM: "old-sigterm",
                        signal.SIGINT: "old-sigint",
                    }
                    restore_observations: list[dict[str, object]] = []
                    parent_checks = 0

                    def observe_signal(
                        signum: object,
                        handler: object,
                    ) -> object:
                        if handler in old_handlers.values():
                            restore_observations.append(
                                json.loads(
                                    heartbeat.read_text(encoding="utf-8")
                                )
                            )
                            if fail_restore and signum == signal.SIGINT:
                                raise RuntimeError("sigint restore failed")
                        return old_handlers[signum]

                    def parent_probe(_pid: int, _signum: int) -> None:
                        nonlocal parent_checks
                        parent_checks += 1
                        if parent_checks > 1:
                            raise ProcessLookupError

                    with (
                        patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                        patch.object(
                            stage608,
                            "_gateway_import_status",
                            return_value={"ctp_gateway_import_available": True},
                        ),
                        patch.object(
                            stage608,
                            "_required_env_missing",
                            return_value=[],
                        ),
                        patch.object(stage608, "_env_status", return_value={}),
                        patch.object(
                            stage608,
                            "_ctp_setting_from_env",
                            return_value={},
                        ),
                        patch.object(
                            stage608,
                            "_analyze_logs",
                            return_value={
                                "md_login_success": True,
                                "td_login_success": True,
                            },
                        ),
                        patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                        patch.object(
                            stage608.MainEngine,
                            "write_log",
                            return_value=None,
                        ),
                        patch.object(
                            stage608.signal,
                            "getsignal",
                            side_effect=lambda signum: old_handlers[signum],
                        ),
                        patch.object(
                            stage608.signal,
                            "signal",
                            side_effect=observe_signal,
                        ),
                        patch.object(
                            stage608.os,
                            "kill",
                            side_effect=parent_probe,
                        ),
                    ):
                        result = stage608._run_stream(
                            connect=True,
                            pre_subscribe_wait_seconds=0,
                            target_symbols=["JM609.DCE"],
                            watch_manifest=None,
                            journal_path=root / "ticks.ndjson",
                            heartbeat_path=heartbeat,
                            duration_seconds=0,
                            heartbeat_seconds=0.2,
                            max_buffer_ticks=10,
                            parent_pid=999_999,
                        )
                    persisted = json.loads(
                        heartbeat.read_text(encoding="utf-8")
                    )

                self.assertTrue(result["ever_stream_ready"])
                self.assertEqual(len(restore_observations), 2)
                self.assertTrue(
                    all(row["stopped"] is True for row in restore_observations)
                )
                self.assertTrue(
                    all(
                        row["stream_ready"] is False
                        for row in restore_observations
                    )
                )
                if fail_restore:
                    self.assertIn("sigint_restore_error", result)
                    self.assertEqual(
                        persisted["journal_session_state"],
                        "fault_stopped",
                    )
                    self.assertFalse(persisted["clean_shutdown"])
                else:
                    self.assertEqual(
                        persisted["journal_session_state"],
                        "clean_stopped",
                    )
                    self.assertTrue(persisted["clean_shutdown"])

    def test_signal_restore_double_publish_failure_leaves_guard_for_safe_takeover(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        self_test = self
        connect_calls: list[str] = []

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, _setting: dict[str, object]) -> None:
                connect_calls.append("connect")
                self.on_tick(self_test._ingress_tick())
                time.sleep(0.1)

            def subscribe(self, _request: object) -> None:
                return None

            def send_order(self, _request: object) -> str:
                raise AssertionError("read-only runner must not send")

            def cancel_order(self, _request: object) -> None:
                raise AssertionError("read-only runner must not cancel")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        old_handlers = {
            signal.SIGTERM: "old-sigterm",
            signal.SIGINT: "old-sigint",
        }
        parent_checks = 0

        def fail_sigint_restore(signum: object, handler: object) -> object:
            if signum == signal.SIGINT and handler == "old-sigint":
                raise RuntimeError("injected sigint restore failure")
            return old_handlers[signum]

        def parent_probe(_pid: int, _signum: int) -> None:
            nonlocal parent_checks
            parent_checks += 1
            if parent_checks > 1:
                raise ProcessLookupError

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            guard_path = stage608._startup_attempt_path(heartbeat)
            real_publish = stage608._publish_tick_snapshot_commit
            real_atomic_json = stage608._atomic_write_json

            def fail_fault_snapshot_publish(**kwargs: object) -> dict[str, object]:
                payload = kwargs["heartbeat"]
                if payload.get("journal_session_state") == "fault_stopped":
                    raise OSError("injected fault snapshot publish failure")
                return real_publish(**kwargs)

            def fail_direct_fault_publish(
                path: Path,
                payload: dict[str, object],
            ) -> None:
                if (
                    Path(path) == heartbeat
                    and payload.get("journal_session_state") == "fault_stopped"
                ):
                    raise OSError("injected direct fault publish failure")
                real_atomic_json(path, payload)

            common_patches = (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(stage608, "_ctp_setting_from_env", return_value={}),
                patch.object(
                    stage608,
                    "_analyze_logs",
                    return_value={
                        "md_login_success": True,
                        "td_login_success": True,
                    },
                ),
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
            )
            with ExitStack() as stack:
                for patcher in common_patches:
                    stack.enter_context(patcher)
                stack.enter_context(patch.object(
                    stage608.signal,
                    "getsignal",
                    side_effect=lambda signum: old_handlers[signum],
                ))
                stack.enter_context(patch.object(
                    stage608.signal,
                    "signal",
                    side_effect=fail_sigint_restore,
                ))
                stack.enter_context(
                    patch.object(stage608.os, "kill", side_effect=parent_probe)
                )
                stack.enter_context(patch.object(
                    stage608,
                    "_publish_tick_snapshot_commit",
                    side_effect=fail_fault_snapshot_publish,
                ))
                stack.enter_context(patch.object(
                    stage608,
                    "_atomic_write_json",
                    side_effect=fail_direct_fault_publish,
                ))
                first = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                    parent_pid=999_999,
                )

            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))
            guard = json.loads(guard_path.read_text(encoding="utf-8"))
            self.assertTrue(
                first["gateway_capture_quiesced"],
                repr(
                    {
                        key: first.get(key)
                        for key in (
                            "aggregate_close_error",
                            "aggregate_close_skipped_market_data_uncertain",
                            "aggregate_close_skipped_trading_api_unfenced",
                            "market_data_close_error",
                            "gateway_restore_error",
                            "gateway_capture_quiesced",
                            "pipeline_quiesced",
                        )
                    }
                ),
            )
            self.assertEqual(guard["phase"], "terminal_commit", repr(guard))
            self.assertTrue(guard["capture_quiesced"])
            self.assertTrue(guard["pipeline_quiesced"])
            connect_count_before_restart = len(connect_calls)

            with (
                patch.dict(sys.modules, {"vnpy_ctp": fake_vnpy_ctp}),
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(
                    stage608.os,
                    "kill",
                    side_effect=ProcessLookupError,
                ),
            ):
                second = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                    parent_pid=999_999,
                )

        self.assertTrue(first["journal_authority_unsafe"])
        self.assertEqual(persisted["journal_session_state"], "clean_stopped")
        self.assertTrue(persisted["clean_shutdown"])
        self.assertTrue(guard["lifecycle_guard_active"])
        self.assertEqual(second["status"], "tick_stream_stopped")
        self.assertEqual(
            second["lifecycle_guard_reconciled"],
            "stale_clean_authority_revoked",
        )
        self.assertEqual(len(connect_calls), connect_count_before_restart + 1)
        self.assertFalse(guard_path.exists())
        self.assertEqual(
            stage608._stream_exit_code(connect=True, result=second),
            2,
        )

    def test_dead_owner_lifecycle_guard_revokes_running_authority_under_owner_fence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "running-segment.ndjson"
            segment_path.write_bytes(b"header\n")
            previous = {
                "feed_session_id": "feed-dead-owner",
                "heartbeat_revision_uuid": "revision-running",
                "journal_segment_path": str(segment_path.resolve()),
                "journal_authority_committed": True,
                "journal_session_state": "running",
                "stopped": False,
                "clean_shutdown": False,
                "stream_ready": True,
                "transport_ready": True,
                "writer_alive": True,
            }
            heartbeat_path.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )
            stage608._publish_lifecycle_guard(
                heartbeat_path,
                feed_session_id="feed-dead-owner",
                summary={"journal_segment_path": str(segment_path.resolve())},
                phase="startup_handoff",
                previous_heartbeat=previous,
                owner_pid=999_999,
            )

            with (
                patch.object(
                    stage608.os,
                    "kill",
                    side_effect=ProcessLookupError,
                ),
                stage608._exclusive_stream_owner_lock(heartbeat_path),
            ):
                reconciled, evidence = stage608._reconcile_lifecycle_guard(
                    heartbeat_path,
                    previous_heartbeat=previous,
                )

            active, error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )
            persisted = json.loads(
                heartbeat_path.read_text(encoding="utf-8")
            )

        self.assertEqual(error, "")
        self.assertEqual(active, {})
        self.assertEqual(reconciled["journal_session_state"], "fault_stopped")
        self.assertTrue(reconciled["stopped"])
        self.assertFalse(reconciled["clean_shutdown"])
        self.assertFalse(reconciled["stream_ready"])
        self.assertFalse(reconciled["transport_ready"])
        self.assertFalse(reconciled["writer_alive"])
        self.assertTrue(reconciled["recovery_blocked"])
        self.assertEqual(persisted, reconciled)
        self.assertEqual(
            evidence["lifecycle_guard_reconciled"],
            "unclean_authority_revoked",
        )

    def test_no_guard_running_authority_is_revoked_before_journal_recovery(self) -> None:
        observed: dict[str, object] = {}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "orphan-running.ndjson"
            segment_path.write_bytes(b"header\n")
            heartbeat_path.write_text(
                json.dumps(
                    {
                        "feed_session_id": "feed-orphan-running",
                        "heartbeat_revision_uuid": "orphan-running-revision",
                        "journal_segment_path": str(segment_path.resolve()),
                        "journal_authority_committed": True,
                        "journal_session_state": "running",
                        "stopped": False,
                        "clean_shutdown": False,
                        "stream_ready": True,
                        "transport_ready": True,
                        "writer_alive": True,
                        "accepting": True,
                    }
                ),
                encoding="utf-8",
            )

            def observe_recovery_boundary(**_kwargs: object) -> object:
                persisted = json.loads(
                    heartbeat_path.read_text(encoding="utf-8")
                )
                observed.update(persisted)
                raise RuntimeError("stop after authority revocation")

            with (
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(
                    stage608,
                    "_recover_previous_journal",
                    side_effect=observe_recovery_boundary,
                ),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=[],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat_path,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                    parent_pid=0,
                )
            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )

        self.assertEqual(result["status"], "stream_blocked_journal_recovery_error")
        self.assertEqual(observed["journal_session_state"], "fault_stopped")
        self.assertTrue(observed["stopped"])
        self.assertFalse(observed["stream_ready"])
        self.assertFalse(observed["transport_ready"])
        self.assertFalse(observed["writer_alive"])
        self.assertFalse(observed["accepting"])
        self.assertTrue(observed["recovery_blocked"])
        self.assertEqual(guard_error, "")
        self.assertEqual(guard, {})

    def test_running_authority_revoke_write_failure_keeps_guard_and_skips_recovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "orphan-write-failure.ndjson"
            segment_path.write_bytes(b"header\n")
            heartbeat_path.write_text(
                json.dumps(
                    {
                        "feed_session_id": "feed-orphan-write-failure",
                        "heartbeat_revision_uuid": "orphan-write-failure-revision",
                        "journal_segment_path": str(segment_path.resolve()),
                        "journal_authority_committed": True,
                        "journal_session_state": "running",
                        "stopped": False,
                        "clean_shutdown": False,
                        "stream_ready": True,
                        "transport_ready": True,
                        "writer_alive": True,
                        "accepting": True,
                    }
                ),
                encoding="utf-8",
            )
            real_atomic_write = stage608._atomic_write_json

            def fail_primary_heartbeat_write(
                path: Path,
                payload: object,
            ) -> None:
                if Path(path).resolve() == heartbeat_path.resolve():
                    raise OSError("primary heartbeat revoke failed")
                real_atomic_write(path, payload)

            with (
                patch.object(
                    stage608,
                    "_gateway_import_status",
                    return_value={"ctp_gateway_import_available": True},
                ),
                patch.object(stage608, "_required_env_missing", return_value=[]),
                patch.object(stage608, "_env_status", return_value={}),
                patch.object(
                    stage608,
                    "_atomic_write_json",
                    side_effect=fail_primary_heartbeat_write,
                ),
                patch.object(stage608, "_recover_previous_journal") as recover,
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=[],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat_path,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                    parent_pid=0,
                )
            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )
            persisted = json.loads(
                heartbeat_path.read_text(encoding="utf-8")
            )

        self.assertEqual(
            result["status"],
            "stream_blocked_prior_authority_revoke_error",
        )
        self.assertTrue(result["journal_authority_unsafe"])
        self.assertEqual(guard_error, "")
        self.assertTrue(guard["lifecycle_guard_active"])
        self.assertEqual(persisted["journal_session_state"], "running")
        recover.assert_not_called()

    def test_post_revoke_guard_clear_failure_is_recoverable_after_owner_death(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "post-revoke-clear-failure.ndjson"
            segment_path.write_bytes(b"header\n")
            previous = {
                "feed_session_id": "feed-post-revoke-clear-failure",
                "heartbeat_revision_uuid": "pre-revoke-revision",
                "journal_segment_path": str(segment_path.resolve()),
                "journal_authority_committed": True,
                "journal_session_state": "running",
                "stopped": False,
                "clean_shutdown": False,
                "stream_ready": True,
                "transport_ready": True,
                "writer_alive": True,
                "accepting": True,
            }
            heartbeat_path.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )

            with (
                stage608._exclusive_stream_owner_lock(heartbeat_path),
                patch.object(
                    stage608,
                    "_clear_lifecycle_guard",
                    side_effect=OSError("guard clear failed"),
                ),
                patch.object(stage608.os, "getpid", return_value=999_999),
            ):
                with self.assertRaisesRegex(OSError, "guard clear failed"):
                    stage608._revoke_unclean_previous_authority_before_recovery(
                        heartbeat_path,
                        previous_heartbeat=previous,
                    )
            persisted = json.loads(
                heartbeat_path.read_text(encoding="utf-8")
            )
            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )
            with (
                stage608._exclusive_stream_owner_lock(heartbeat_path),
                patch.object(
                    stage608.os,
                    "kill",
                    side_effect=ProcessLookupError,
                ),
            ):
                reconciled, evidence = stage608._reconcile_lifecycle_guard(
                    heartbeat_path,
                    previous_heartbeat=persisted,
                )
            remaining_guard, remaining_error = (
                stage608._load_active_lifecycle_guard(heartbeat_path)
            )

        self.assertEqual(persisted["journal_session_state"], "fault_stopped")
        self.assertEqual(guard_error, "")
        self.assertTrue(guard["lifecycle_guard_active"])
        self.assertEqual(
            guard["feed_session_id"],
            "feed-post-revoke-clear-failure",
        )
        self.assertEqual(reconciled, persisted)
        self.assertEqual(
            evidence["lifecycle_guard_reconciled"],
            "unclean_authority",
        )
        self.assertEqual(remaining_error, "")
        self.assertEqual(remaining_guard, {})

    def test_terminal_guard_downgrades_stale_clean_authority_before_takeover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "terminal-segment.ndjson"
            segment_path.write_bytes(b"header\n")
            previous = {
                "feed_session_id": "feed-terminal-guard",
                "heartbeat_revision_uuid": "revision-clean",
                "journal_segment_path": str(segment_path.resolve()),
                "journal_authority_committed": True,
                "journal_session_state": "clean_stopped",
                "stopped": True,
                "clean_shutdown": True,
                "stream_ready": False,
                "transport_ready": False,
                "writer_alive": False,
            }
            heartbeat_path.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )
            stage608._publish_lifecycle_guard(
                heartbeat_path,
                feed_session_id="feed-terminal-guard",
                summary={
                    "journal_segment_path": str(segment_path.resolve()),
                    "gateway_capture_quiesced": True,
                    "writer_quiesced": True,
                    "pipeline_quiesced": True,
                },
                phase="terminal_commit",
                previous_heartbeat=previous,
            )

            with stage608._exclusive_stream_owner_lock(heartbeat_path):
                reconciled, evidence = stage608._reconcile_lifecycle_guard(
                    heartbeat_path,
                    previous_heartbeat=previous,
                )
            persisted = json.loads(
                heartbeat_path.read_text(encoding="utf-8")
            )

        self.assertEqual(
            reconciled["journal_session_state"],
            "fault_stopped",
        )
        self.assertFalse(reconciled["clean_shutdown"])
        self.assertEqual(persisted, reconciled)
        self.assertEqual(
            evidence["lifecycle_guard_reconciled"],
            "stale_clean_authority_revoked",
        )

    def test_terminal_guard_revokes_stale_running_readiness_before_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "running-segment.ndjson"
            segment_path.write_bytes(b"header\n")
            previous = {
                "feed_session_id": "feed-running-guard",
                "heartbeat_revision_uuid": "revision-running",
                "journal_segment_path": str(segment_path.resolve()),
                "journal_authority_committed": True,
                "journal_session_state": "running",
                "stopped": False,
                "clean_shutdown": False,
                "stream_ready": True,
                "transport_ready": True,
                "writer_alive": True,
            }
            heartbeat_path.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )
            stage608._publish_lifecycle_guard(
                heartbeat_path,
                feed_session_id="feed-running-guard",
                summary={
                    "journal_segment_path": str(segment_path.resolve()),
                    "gateway_capture_quiesced": True,
                    "writer_quiesced": True,
                    "pipeline_quiesced": True,
                },
                phase="terminal_commit",
                previous_heartbeat=previous,
            )

            with stage608._exclusive_stream_owner_lock(heartbeat_path):
                reconciled, evidence = stage608._reconcile_lifecycle_guard(
                    heartbeat_path,
                    previous_heartbeat=previous,
                )
            persisted = json.loads(
                heartbeat_path.read_text(encoding="utf-8")
            )

        self.assertEqual(reconciled["journal_session_state"], "fault_stopped")
        self.assertTrue(reconciled["stopped"])
        self.assertFalse(reconciled["stream_ready"])
        self.assertFalse(reconciled["transport_ready"])
        self.assertFalse(reconciled["writer_alive"])
        self.assertTrue(reconciled["recovery_blocked"])
        self.assertEqual(persisted, reconciled)
        self.assertEqual(
            evidence["lifecycle_guard_reconciled"],
            "unclean_authority_revoked",
        )

    def test_terminal_guard_with_live_unquiesced_pipeline_blocks_takeover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "writer-live-segment.ndjson"
            segment_path.write_bytes(b"header\n")
            previous = {
                "feed_session_id": "feed-writer-live",
                "heartbeat_revision_uuid": "revision-writer-live",
                "journal_segment_path": str(segment_path.resolve()),
                "journal_authority_committed": True,
                "journal_session_state": "fault_stopped",
                "stopped": True,
                "clean_shutdown": False,
                "stream_ready": False,
                "transport_ready": False,
                "writer_alive": True,
            }
            heartbeat_path.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )
            stage608._publish_lifecycle_guard(
                heartbeat_path,
                feed_session_id="feed-writer-live",
                summary={
                    "journal_segment_path": str(segment_path.resolve()),
                    "gateway_capture_quiesced": True,
                    "writer_quiesced": False,
                    "pipeline_quiesced": False,
                },
                phase="terminal_commit",
                previous_heartbeat=previous,
            )

            with stage608._exclusive_stream_owner_lock(heartbeat_path):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "owner_still_alive",
                ):
                    stage608._reconcile_lifecycle_guard(
                        heartbeat_path,
                        previous_heartbeat=previous,
                    )
            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )

        self.assertEqual(guard_error, "")
        self.assertTrue(guard["lifecycle_guard_active"])

    def test_lifecycle_guard_identity_mismatch_remains_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            segment_path = root / "guarded-segment.ndjson"
            segment_path.write_bytes(b"header\n")
            previous = {
                "feed_session_id": "different-authority",
                "journal_authority_committed": True,
                "journal_session_state": "running",
                "stopped": False,
                "clean_shutdown": False,
            }
            stage608._publish_lifecycle_guard(
                heartbeat_path,
                feed_session_id="guarded-feed",
                summary={"journal_segment_path": str(segment_path.resolve())},
                phase="terminal_commit",
                previous_heartbeat=previous,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "feed_session_mismatch",
            ):
                stage608._reconcile_lifecycle_guard(
                    heartbeat_path,
                    previous_heartbeat=previous,
                )
            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )

        self.assertEqual(guard_error, "")
        self.assertTrue(guard["lifecycle_guard_active"])

    def test_capture_fence_timeout_keeps_order_and_lifecycle_guards(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        gateways: list[BaseGateway] = []

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, **kwargs)
                gateways.append(self)

            def connect(self, _setting: dict[str, object]) -> None:
                return None

            def subscribe(self, _request: object) -> None:
                return None

            def send_order(self, _request: object) -> str:
                return "unsafe-original-send"

            def cancel_order(self, _request: object) -> None:
                return None

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway

        heartbeat_path: Path | None = None
        terminal_guard_seen_before_restore = False

        def fail_capture_restore() -> None:
            nonlocal terminal_guard_seen_before_restore
            self.assertIsNotNone(heartbeat_path)
            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )
            self.assertEqual(guard_error, "")
            terminal_guard_seen_before_restore = bool(
                guard.get("phase") == "terminal_commit"
            )
            raise TimeoutError("gateway ingress capture fence timed out")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
                patch.object(
                    stage608,
                    "install_gateway_tick_ingress",
                    return_value=fail_capture_restore,
                ),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=[],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat_path,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                    parent_pid=999_999,
                )
            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )
            persisted = json.loads(
                heartbeat_path.read_text(encoding="utf-8")
            )
            with stage608._exclusive_stream_owner_lock(heartbeat_path):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "owner_still_alive",
                ):
                    stage608._reconcile_lifecycle_guard(
                        heartbeat_path,
                        previous_heartbeat=persisted,
                    )

        self.assertEqual(guard_error, "")
        self.assertTrue(guard["lifecycle_guard_active"])
        self.assertTrue(terminal_guard_seen_before_restore)
        self.assertIn("gateway_restore_error", result)
        self.assertEqual(
            stage608._stream_exit_code(connect=True, result=result),
            2,
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "readonly_order_guard_blocked_send_order",
        ):
            gateways[0].send_order(object())

    def test_capture_timeout_and_terminal_guard_publish_failure_failstops_before_owner_unlock(
        self,
    ) -> None:
        from vnpy.trader.gateway import BaseGateway

        class FatalProcessExit(BaseException):
            pass

        connect_count = 0

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, _setting: dict[str, object]) -> None:
                nonlocal connect_count
                connect_count += 1

            def subscribe(self, _request: object) -> None:
                return None

            def send_order(self, _request: object) -> str:
                return "unsafe-original-send"

            def cancel_order(self, _request: object) -> None:
                return None

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway

        def fail_capture_restore() -> None:
            raise TimeoutError("gateway ingress capture fence timed out")

        real_publish_guard = stage608._publish_lifecycle_guard

        def fail_terminal_guard(
            heartbeat_path: Path,
            *,
            feed_session_id: str,
            summary: object,
            phase: str = "startup_handoff",
            previous_heartbeat: object = None,
            owner_pid: int | None = None,
        ) -> object:
            if phase == "terminal_commit":
                raise OSError("terminal guard publication failed")
            return real_publish_guard(
                heartbeat_path,
                feed_session_id=feed_session_id,
                summary=summary,
                phase=phase,
                previous_heartbeat=previous_heartbeat,
                owner_pid=owner_pid,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            exit_calls: list[int] = []

            def intercept_fatal_exit(exit_code: int) -> None:
                exit_calls.append(exit_code)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "stream_owner_lock_contended",
                ):
                    with stage608._exclusive_stream_owner_lock(
                        heartbeat_path
                    ):
                        pass
                raise FatalProcessExit("fatal exit intercepted")

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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
                patch.object(
                    stage608,
                    "install_gateway_tick_ingress",
                    return_value=fail_capture_restore,
                ),
                patch.object(
                    stage608,
                    "_publish_lifecycle_guard",
                    side_effect=fail_terminal_guard,
                ),
                patch.object(
                    stage608.os,
                    "_exit",
                    side_effect=intercept_fatal_exit,
                ),
            ):
                with self.assertRaises(FatalProcessExit):
                    stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=[],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat_path,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )

            guard, guard_error = stage608._load_active_lifecycle_guard(
                heartbeat_path
            )

        self.assertEqual(connect_count, 1)
        self.assertEqual(exit_calls, [2])
        self.assertEqual(guard_error, "")
        self.assertEqual(guard, {})

    def test_authority_handoff_waits_for_durable_header_before_connect(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        connect_calls: list[dict[str, object]] = []

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                connect_calls.append(setting)

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

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            old_segment = root / "old-clean.ndjson"
            prior = {
                "feed_session_id": "old-clean",
                "journal_segment_path": str(old_segment),
                "journal_schema": "stage179_framed_v1",
                "journal_session_state": "clean_stopped",
                "durable_ingress_sequence": 0,
                "last_ingress_sequence": 0,
                "stream_ready": False,
                "stopped": True,
                "clean_shutdown": True,
            }
            prior_bytes = json.dumps(prior).encode("utf-8")
            heartbeat.write_bytes(prior_bytes)
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
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(
                    stage608.TickStreamPipeline,
                    "wait_until_journal_ready",
                    return_value=False,
                ),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                    )
            persisted_bytes = heartbeat.read_bytes()
            attempt = json.loads(
                stage608._startup_attempt_path(heartbeat).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            result["status"],
            "stream_blocked_journal_header_not_durable",
        )
        self.assertEqual(connect_calls, [])
        self.assertNotEqual(persisted_bytes, prior_bytes)
        persisted = json.loads(persisted_bytes)
        self.assertEqual(persisted["feed_session_id"], "old-clean")
        self.assertEqual(persisted["journal_segment_path"], str(old_segment))
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])
        self.assertTrue(persisted["stopped"])
        self.assertTrue(persisted["clean_shutdown"])
        self.assertEqual(persisted["journal_session_state"], "clean_stopped")
        self.assertTrue(attempt["recovery_blocked"])

    def test_dead_writer_after_header_never_reaches_connect_or_authority_handoff(self) -> None:
        from vnpy.trader.gateway import BaseGateway
        from qmt_roll_official_live_tick_journal import AsyncTickJournalWriter

        connect_calls: list[dict[str, object]] = []

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                connect_calls.append(setting)

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("must remain read-only")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("must remain read-only")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        real_wait = stage608.TickStreamPipeline.wait_until_journal_ready

        def wait_for_writer_failure(
            pipeline: object,
            *,
            timeout_seconds: float,
        ) -> bool:
            ready = real_wait(pipeline, timeout_seconds=timeout_seconds)
            pipeline.wait_until_writer_stops(timeout_seconds=1.0)
            return ready

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
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
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(
                    AsyncTickJournalWriter,
                    "_next_batch",
                    side_effect=RuntimeError("writer died after durable header"),
                ),
                patch.object(
                    stage608.TickStreamPipeline,
                    "wait_until_journal_ready",
                    new=wait_for_writer_failure,
                ),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(connect_calls, [])
        self.assertEqual(result["status"], "stream_blocked_journal_writer_not_live")
        self.assertFalse(persisted["journal_authority_committed"])
        self.assertFalse(persisted["stream_ready"])

    def test_writer_dying_during_authority_publish_never_reaches_connect(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        connect_calls: list[dict[str, object]] = []
        pipeline_holder: dict[str, object] = {}

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                connect_calls.append(setting)

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("must remain read-only")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("must remain read-only")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        real_pipeline_type = stage608.TickStreamPipeline
        real_publish = stage608._publish_tick_snapshot_commit
        initial_publish_seen = False

        def capture_pipeline(*args: object, **kwargs: object) -> object:
            pipeline = real_pipeline_type(*args, **kwargs)
            pipeline_holder["pipeline"] = pipeline
            return pipeline

        def stop_writer_after_publish(**kwargs: object) -> dict[str, object]:
            nonlocal initial_publish_seen
            published = real_publish(**kwargs)
            if not initial_publish_seen:
                initial_publish_seen = True
                pipeline = pipeline_holder["pipeline"]
                pipeline._writer.request_stop()
                self.assertTrue(
                    pipeline.wait_until_writer_stops(timeout_seconds=1.0)
                )
            return published

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
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
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(
                    stage608,
                    "TickStreamPipeline",
                    side_effect=capture_pipeline,
                ),
                patch.object(
                    stage608,
                    "_publish_tick_snapshot_commit",
                    side_effect=stop_writer_after_publish,
                ),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(connect_calls, [])
        self.assertEqual(result["terminal_reason"], "stream_blocked_journal_writer_not_live")
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["writer_alive"])

    def test_journal_ready_waits_for_header_parent_directory_fsync(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            entered_parent_fsync = threading.Event()
            release_parent_fsync = threading.Event()
            real_parent_fsync = journal_module._fsync_parent

            def blocking_parent_fsync(path: Path) -> None:
                entered_parent_fsync.set()
                self.assertTrue(release_parent_fsync.wait(timeout=1.0))
                real_parent_fsync(path)

            pipeline = TickStreamPipeline(
                feed_session_id="feed-header-parent-fsync",
                journal_segment_path=Path(tmp) / "ticks.ndjson",
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            with patch.object(
                journal_module,
                "_fsync_parent",
                side_effect=blocking_parent_fsync,
            ):
                pipeline.start()
                self.assertTrue(entered_parent_fsync.wait(timeout=1.0))
                self.assertFalse(
                    pipeline.wait_until_journal_ready(timeout_seconds=0.01)
                )
                release_parent_fsync.set()
                self.assertTrue(
                    pipeline.wait_until_journal_ready(timeout_seconds=1.0)
                )
                self.assertTrue(pipeline.shutdown(timeout_seconds=1.0).drained)

    def test_md_close_failure_skips_unsafe_aggregate_gateway_retry(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        self_test = self
        aggregate_close_calls: list[str] = []

        class FailingMdApi:
            def close(self) -> None:
                raise RuntimeError("md close failed")

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def __init__(self, event_engine: object, gateway_name: str) -> None:
                super().__init__(event_engine, gateway_name)
                self.md_api = FailingMdApi()

            def connect(self, setting: dict[str, object]) -> None:
                return None

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
                aggregate_close_calls.append("aggregate_close")
                self.on_tick(self_test._ingress_tick())

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(aggregate_close_calls, [])
        self.assertTrue(result["aggregate_close_skipped_market_data_uncertain"])
        self.assertEqual(result["send_order_api_called_count"], 0)
        self.assertEqual(result["cancel_order_api_called_count"], 0)
        self.assertFalse(persisted["clean_shutdown"])
        self.assertEqual(persisted["journal_session_state"], "fault_stopped")
        self.assertEqual(persisted["last_ingress_sequence"], 0)
        self.assertEqual(persisted["durable_ingress_sequence"], 0)
        self.assertFalse(persisted["gap_latched"])
        self.assertEqual(persisted["journal_commit_revoked_from_ingress_sequence"], 0)

    def test_aggregate_close_failure_still_closes_td_exactly_once(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        td_close_calls: list[str] = []

        class FakeMdApi:
            def __init__(self) -> None:
                self.connect_status = True
                self.login_status = True

            def close(self) -> None:
                return None

        class NonIdempotentTdApi:
            def close(self) -> None:
                td_close_calls.append("td_close")
                if len(td_close_calls) > 1:
                    raise RuntimeError("native td exit called twice")

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def __init__(self, event_engine: object, gateway_name: str) -> None:
                super().__init__(event_engine, gateway_name)
                self.md_api = FakeMdApi()
                self.td_api = NonIdempotentTdApi()

            def connect(self, setting: dict[str, object]) -> None:
                return None

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
                self.td_api.close()
                self.md_api.close()

        def fail_after_event_stop(main_engine: object) -> None:
            main_engine.event_engine.stop()
            raise RuntimeError("aggregate close stopped before gateways")

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.MainEngine, "close", new=fail_after_event_stop),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(td_close_calls, ["td_close"])
        self.assertTrue(result["trading_api_close_entered"])
        self.assertTrue(result["trading_api_close_completed"])
        self.assertEqual(result["trading_api_close_attempt_count"], 1)
        self.assertIn("aggregate_close_error", result)
        self.assertFalse(persisted["clean_shutdown"])
        self.assertEqual(persisted["journal_session_state"], "fault_stopped")

    def test_ambiguous_initial_handoff_is_revoked_as_current_authority(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        connect_calls: list[dict[str, object]] = []

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                connect_calls.append(setting)

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("must remain read-only")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("must remain read-only")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
            old_segment = root / "old.ndjson"
            heartbeat.write_text(
                json.dumps(
                    {
                        "feed_session_id": "old-clean",
                        "journal_segment_path": str(old_segment),
                        "journal_schema": "stage179_framed_v1",
                        "journal_session_state": "clean_stopped",
                        "durable_ingress_sequence": 0,
                        "last_ingress_sequence": 0,
                        "stopped": True,
                        "clean_shutdown": True,
                    }
                ),
                encoding="utf-8",
            )
            real_publish = stage608._publish_tick_snapshot_commit
            publish_calls = 0

            def ambiguous_first_publish(**kwargs: object) -> dict[str, object]:
                nonlocal publish_calls
                publish_calls += 1
                committed = real_publish(**kwargs)
                if publish_calls == 1:
                    raise OSError("parent fsync ambiguous after replace")
                return committed

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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(
                    stage608,
                    "_publish_tick_snapshot_commit",
                    side_effect=ambiguous_first_publish,
                ),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(connect_calls, [])
        self.assertNotEqual(persisted["feed_session_id"], "old-clean")
        self.assertTrue(persisted["stopped"])
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])
        self.assertEqual(persisted["journal_session_state"], "fault_stopped")
        self.assertIn("exception", result)

    def test_final_heartbeat_failure_gets_atomic_fail_closed_fallback(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                self.on_tick(self_test._ingress_tick())

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("must remain read-only")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("must remain read-only")

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
            heartbeat = root / "heartbeat.json"
            real_publish = stage608._publish_tick_snapshot_commit
            publish_calls = 0

            def fail_final_publish(**kwargs: object) -> dict[str, object]:
                nonlocal publish_calls
                publish_calls += 1
                if publish_calls == 2:
                    raise OSError("final heartbeat replace failed")
                return real_publish(**kwargs)

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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
                patch.object(
                    stage608,
                    "_publish_tick_snapshot_commit",
                    side_effect=fail_final_publish,
                ),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertIn("final_heartbeat_error", result)
        self.assertFalse(result.get("journal_authority_unsafe", False))
        self.assertTrue(persisted["stopped"])
        self.assertFalse(persisted["stream_ready"])
        self.assertFalse(persisted["transport_ready"])
        self.assertEqual(
            persisted["journal_session_state"],
            "recovery_required_stopped",
        )
        self.assertNotIn("tick_snapshot_commit", persisted)

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

    def test_scalar_recovery_gap_is_promoted_to_effective_gap_lineage(self) -> None:
        from qmt_roll_official_live_tick_stream import TickStreamGap

        gap = TickStreamGap(
            feed_session_id="old-feed",
            start_ingress_sequence=8,
            end_ingress_sequence=10,
            reason="legacy_scalar_gap",
        )
        recovery = SimpleNamespace(disclosed_gap=gap, disclosed_gaps=())

        self.assertEqual(stage608._effective_recovery_gaps(recovery), (gap,))

    def test_readonly_order_guard_blocks_send_and_cancel_forwarding(self) -> None:
        forwarded = {"send": 0, "cancel": 0}
        summary: dict[str, object] = {}

        class FakeGateway:
            def send_order(self, req: object) -> str:
                forwarded["send"] += 1
                return "unsafe"

            def cancel_order(self, req: object) -> None:
                forwarded["cancel"] += 1

        gateway = FakeGateway()
        restore = stage608._install_readonly_order_guards(gateway, summary)
        with self.assertRaisesRegex(RuntimeError, "send_order"):
            gateway.send_order(object())
        with self.assertRaisesRegex(RuntimeError, "cancel_order"):
            gateway.cancel_order(object())

        self.assertEqual(forwarded, {"send": 0, "cancel": 0})
        self.assertEqual(summary["send_order_api_attempted_count"], 1)
        self.assertEqual(summary["cancel_order_api_attempted_count"], 1)
        restore()
        self.assertEqual(gateway.send_order(object()), "unsafe")
        gateway.cancel_order(object())
        self.assertEqual(forwarded, {"send": 1, "cancel": 1})

    def test_live_runner_installs_order_guards_before_connect(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        forwarded = {"send": 0, "cancel": 0}

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                try:
                    self.send_order(object())
                except RuntimeError:
                    pass
                try:
                    self.cancel_order(object())
                except RuntimeError:
                    pass

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                forwarded["send"] += 1
                return "unsafe-order"

            def cancel_order(self, req: object) -> None:
                forwarded["cancel"] += 1

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat = root / "heartbeat.json"
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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=root / "ticks.ndjson",
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(forwarded, {"send": 0, "cancel": 0})
        self.assertEqual(result["send_order_api_attempted_count"], 1)
        self.assertEqual(result["cancel_order_api_attempted_count"], 1)
        self.assertEqual(result["order_api_called_count"], 0)
        self.assertFalse(persisted["stream_ready"])
        self.assertEqual(persisted["journal_session_state"], "fault_stopped")

    def test_snapshot_probe_installs_order_guards_before_connect(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        forwarded = {"send": 0, "cancel": 0}

        class FakeTdApi:
            def onRspQryInvestorPosition(
                self,
                data: dict[str, object],
                error: dict[str, object],
                reqid: int,
                last: bool,
            ) -> None:
                return None

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                try:
                    self.send_order(object())
                except RuntimeError:
                    pass
                try:
                    self.cancel_order(object())
                except RuntimeError:
                    pass

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                forwarded["send"] += 1
                return "unsafe-order"

            def cancel_order(self, req: object) -> None:
                forwarded["cancel"] += 1

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_root = types.ModuleType("vnpy_ctp")
        fake_root.CtpGateway = FakeCtpGateway
        fake_gateway_package = types.ModuleType("vnpy_ctp.gateway")
        fake_ctp_gateway = types.ModuleType("vnpy_ctp.gateway.ctp_gateway")
        fake_ctp_gateway.CtpTdApi = FakeTdApi
        fake_gateway_package.ctp_gateway = fake_ctp_gateway

        with (
            patch.dict(
                sys.modules,
                {
                    "vnpy_ctp": fake_root,
                    "vnpy_ctp.gateway": fake_gateway_package,
                    "vnpy_ctp.gateway.ctp_gateway": fake_ctp_gateway,
                },
            ),
            patch.object(
                stage608,
                "_gateway_import_status",
                return_value={"ctp_gateway_import_available": True},
            ),
            patch.object(stage608, "_required_env_missing", return_value=[]),
            patch.object(stage608, "_env_status", return_value={}),
            patch.object(stage608, "_ctp_setting_from_env", return_value={}),
            patch.object(stage608.time, "sleep", return_value=None),
            patch.object(
                stage608,
                "collect_snapshot_from_main_engine",
                return_value={},
            ),
            patch.object(stage608.MainEngine, "write_log", return_value=None),
        ):
            result = stage608._run_probe(
                connect=True,
                wait_seconds=0,
                pre_subscribe_wait_seconds=0,
                target_symbols=[],
            )

        self.assertEqual(forwarded, {"send": 0, "cancel": 0})
        self.assertEqual(result["send_order_api_attempted_count"], 1)
        self.assertEqual(result["cancel_order_api_attempted_count"], 1)
        self.assertEqual(result["order_api_called_count"], 0)

    def test_snapshot_probe_add_gateway_failure_stops_threads_and_restores_callback(self) -> None:
        from vnpy.event import EventEngine as RealEventEngine

        created_engines: list[object] = []

        class FakeTdApi:
            def onRspQryInvestorPosition(
                self,
                data: dict[str, object],
                error: dict[str, object],
                reqid: int,
                last: bool,
            ) -> None:
                return None

        original_callback = FakeTdApi.onRspQryInvestorPosition
        fake_root = types.ModuleType("vnpy_ctp")
        fake_root.CtpGateway = SimpleNamespace(default_name="CTP")
        fake_gateway_package = types.ModuleType("vnpy_ctp.gateway")
        fake_ctp_gateway = types.ModuleType("vnpy_ctp.gateway.ctp_gateway")
        fake_ctp_gateway.CtpTdApi = FakeTdApi
        fake_gateway_package.ctp_gateway = fake_ctp_gateway

        def event_engine_factory() -> object:
            engine = RealEventEngine(interval=0.01)
            created_engines.append(engine)
            return engine

        with (
            patch.dict(
                sys.modules,
                {
                    "vnpy_ctp": fake_root,
                    "vnpy_ctp.gateway": fake_gateway_package,
                    "vnpy_ctp.gateway.ctp_gateway": fake_ctp_gateway,
                },
            ),
            patch.object(
                stage608,
                "_gateway_import_status",
                return_value={"ctp_gateway_import_available": True},
            ),
            patch.object(stage608, "_required_env_missing", return_value=[]),
            patch.object(stage608, "_env_status", return_value={}),
            patch.object(stage608, "EventEngine", new=event_engine_factory),
            patch.object(
                stage608.MainEngine,
                "add_gateway",
                side_effect=RuntimeError("add gateway failed"),
            ),
        ):
            result = stage608._run_probe(
                connect=True,
                wait_seconds=0,
                pre_subscribe_wait_seconds=0,
                target_symbols=[],
            )

        self.assertEqual(result["status"], "probe_initialization_exception")
        self.assertEqual(len(created_engines), 1)
        self.assertFalse(created_engines[0]._timer.is_alive())
        self.assertFalse(created_engines[0]._thread.is_alive())
        self.assertIs(FakeTdApi.onRspQryInvestorPosition, original_callback)

    def test_snapshot_probe_handler_registration_failure_closes_resources_and_restores_callback(self) -> None:
        fakes = self._lifecycle_fakes(
            register_failure_event=stage608.EVENT_ACCOUNT,
        )
        original_callback = fakes.CtpTdApi.onRspQryInvestorPosition
        fake_root = types.ModuleType("vnpy_ctp")
        fake_root.CtpGateway = fakes.CtpGateway
        fake_gateway_package = types.ModuleType("vnpy_ctp.gateway")
        fake_ctp_gateway = types.ModuleType("vnpy_ctp.gateway.ctp_gateway")
        fake_ctp_gateway.CtpTdApi = fakes.CtpTdApi
        fake_gateway_package.ctp_gateway = fake_ctp_gateway
        with (
            patch.dict(
                sys.modules,
                {
                    "vnpy_ctp": fake_root,
                    "vnpy_ctp.gateway": fake_gateway_package,
                    "vnpy_ctp.gateway.ctp_gateway": fake_ctp_gateway,
                },
            ),
            patch.object(
                stage608,
                "_gateway_import_status",
                return_value={"ctp_gateway_import_available": True},
            ),
            patch.object(stage608, "_required_env_missing", return_value=[]),
            patch.object(stage608, "_env_status", return_value={}),
            patch.object(stage608, "EventEngine", new=fakes.EventEngine),
            patch.object(stage608, "MainEngine", new=fakes.MainEngine),
        ):
            result = stage608._run_probe(
                connect=True,
                wait_seconds=0,
                pre_subscribe_wait_seconds=0,
                target_symbols=[],
            )

        event_engine = fakes.state["event_engines"][0]
        self.assertFalse(event_engine._active)
        self.assertFalse(event_engine._thread.is_alive())
        self.assertFalse(event_engine._timer.is_alive())
        self.assertEqual(fakes.state["main_close_count"], 1)
        self.assertEqual(fakes.state["td_close_count"], 1)
        self.assertEqual(fakes.state["md_close_count"], 1)
        self.assertIn("register failed", result["exception"])
        self.assertIs(
            fakes.CtpTdApi.onRspQryInvestorPosition,
            original_callback,
        )

    def test_snapshot_probe_aggregate_close_failure_still_closes_td_and_md_once(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        close_calls: list[str] = []

        class FakeTdApi:
            def close(self) -> None:
                close_calls.append("td_close")
                if close_calls.count("td_close") > 1:
                    raise RuntimeError("td close called twice")

            def onRspQryInvestorPosition(
                self,
                data: dict[str, object],
                error: dict[str, object],
                reqid: int,
                last: bool,
            ) -> None:
                return None

        class FakeMdApi:
            def close(self) -> None:
                close_calls.append("md_close")
                if close_calls.count("md_close") > 1:
                    raise RuntimeError("md close called twice")

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def __init__(self, event_engine: object, gateway_name: str) -> None:
                super().__init__(event_engine, gateway_name)
                self.td_api = FakeTdApi()
                self.md_api = FakeMdApi()

            def connect(self, setting: dict[str, object]) -> None:
                return None

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("read-only probe must not send")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("read-only probe must not cancel")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                self.td_api.close()
                self.md_api.close()

        def fail_before_gateway_close(main_engine: object) -> None:
            main_engine.event_engine.stop()
            raise RuntimeError("aggregate close stopped before gateway")

        fake_root = types.ModuleType("vnpy_ctp")
        fake_root.CtpGateway = FakeCtpGateway
        fake_gateway_package = types.ModuleType("vnpy_ctp.gateway")
        fake_ctp_gateway = types.ModuleType("vnpy_ctp.gateway.ctp_gateway")
        fake_ctp_gateway.CtpTdApi = FakeTdApi
        fake_gateway_package.ctp_gateway = fake_ctp_gateway
        with (
            patch.dict(
                sys.modules,
                {
                    "vnpy_ctp": fake_root,
                    "vnpy_ctp.gateway": fake_gateway_package,
                    "vnpy_ctp.gateway.ctp_gateway": fake_ctp_gateway,
                },
            ),
            patch.object(
                stage608,
                "_gateway_import_status",
                return_value={"ctp_gateway_import_available": True},
            ),
            patch.object(stage608, "_required_env_missing", return_value=[]),
            patch.object(stage608, "_env_status", return_value={}),
            patch.object(stage608, "_ctp_setting_from_env", return_value={}),
            patch.object(stage608.time, "sleep", return_value=None),
            patch.object(
                stage608,
                "collect_snapshot_from_main_engine",
                return_value={},
            ),
            patch.object(stage608.MainEngine, "write_log", return_value=None),
            patch.object(
                stage608.MainEngine,
                "close",
                new=fail_before_gateway_close,
            ),
        ):
            result = stage608._run_probe(
                connect=True,
                wait_seconds=0,
                pre_subscribe_wait_seconds=0,
                target_symbols=[],
            )

        self.assertEqual(close_calls, ["td_close", "md_close"])
        self.assertTrue(result["trading_api_close_completed"])
        self.assertTrue(result["market_data_api_close_completed"])
        self.assertEqual(result["trading_api_close_attempt_count"], 1)
        self.assertEqual(result["market_data_api_close_attempt_count"], 1)
        self.assertIn("aggregate_close_error", result)

    def test_snapshot_probe_guard_restore_failure_still_restores_ctp_callback(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        restore_calls: list[str] = []

        class FakeTdApi:
            def onRspQryInvestorPosition(
                self,
                data: dict[str, object],
                error: dict[str, object],
                reqid: int,
                last: bool,
            ) -> None:
                return None

        original_callback = FakeTdApi.onRspQryInvestorPosition

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                return None

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("read-only probe must not send")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("read-only probe must not cancel")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        def restore_order_guards() -> None:
            restore_calls.append("restore")
            raise RuntimeError("guard restore failed")

        fake_root = types.ModuleType("vnpy_ctp")
        fake_root.CtpGateway = FakeCtpGateway
        fake_gateway_package = types.ModuleType("vnpy_ctp.gateway")
        fake_ctp_gateway = types.ModuleType("vnpy_ctp.gateway.ctp_gateway")
        fake_ctp_gateway.CtpTdApi = FakeTdApi
        fake_gateway_package.ctp_gateway = fake_ctp_gateway
        with (
            patch.dict(
                sys.modules,
                {
                    "vnpy_ctp": fake_root,
                    "vnpy_ctp.gateway": fake_gateway_package,
                    "vnpy_ctp.gateway.ctp_gateway": fake_ctp_gateway,
                },
            ),
            patch.object(
                stage608,
                "_gateway_import_status",
                return_value={"ctp_gateway_import_available": True},
            ),
            patch.object(stage608, "_required_env_missing", return_value=[]),
            patch.object(stage608, "_env_status", return_value={}),
            patch.object(stage608, "_ctp_setting_from_env", return_value={}),
            patch.object(stage608.time, "sleep", return_value=None),
            patch.object(
                stage608,
                "collect_snapshot_from_main_engine",
                return_value={},
            ),
            patch.object(
                stage608,
                "_install_readonly_order_guards",
                return_value=restore_order_guards,
            ),
        ):
            result = stage608._run_probe(
                connect=True,
                wait_seconds=0,
                pre_subscribe_wait_seconds=0,
                target_symbols=[],
            )

        self.assertEqual(restore_calls, ["restore"])
        self.assertIn("order_guard_restore_error", result)
        self.assertIs(FakeTdApi.onRspQryInvestorPosition, original_callback)

    def test_non_authoritative_bootstrap_never_reinterprets_existing_base_journal(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, setting: dict[str, object]) -> None:
                return None

            def subscribe(self, req: object) -> None:
                return None

            def send_order(self, req: object) -> str:
                raise AssertionError("must remain read-only")

            def cancel_order(self, req: object) -> None:
                raise AssertionError("must remain read-only")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_journal = root / "legacy-base.ndjson"
            base_bytes = b'{"feed_session_id":"legacy","ingress_sequence":1}\n'
            base_journal.write_bytes(base_bytes)
            heartbeat = root / "heartbeat.json"
            with patch.object(
                stage608,
                "_gateway_import_status",
                return_value={"ctp_gateway_import_available": True},
            ):
                first = stage608._run_stream(
                    connect=False,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=base_journal,
                    heartbeat_path=heartbeat,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                )
            tombstone = json.loads(heartbeat.read_text(encoding="utf-8"))
            self.assertFalse(tombstone["journal_authority_committed"])

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
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    second = stage608._run_stream(
                        connect=True,
                        pre_subscribe_wait_seconds=0,
                        target_symbols=["JM609.DCE"],
                        watch_manifest=None,
                        journal_path=base_journal,
                        heartbeat_path=heartbeat,
                        duration_seconds=0,
                        heartbeat_seconds=0.2,
                        max_buffer_ticks=10,
                        parent_pid=999_999,
                    )
            persisted = json.loads(heartbeat.read_text(encoding="utf-8"))
            persisted_base_bytes = base_journal.read_bytes()
            persisted_segment_path = Path(persisted["journal_segment_path"])

        self.assertEqual(first["status"], "stream_dry_run_not_connected")
        self.assertEqual(persisted_base_bytes, base_bytes)
        self.assertNotEqual(persisted_segment_path, base_journal)
        self.assertTrue(persisted["journal_authority_committed"])
        self.assertEqual(second["order_api_called_count"], 0)

    def test_non_authoritative_tombstone_rejects_readiness_and_snapshot_commit(self) -> None:
        base = {
            "feed_session_id": "bootstrap-feed",
            "journal_schema": "stage179_framed_v1",
            "journal_format": "stage179_framed_ndjson_v1",
            "journal_schema_version": 1,
            "journal_authority_committed": False,
            "journal_session_state": "clean_stopped",
            "stream_ready": False,
            "transport_ready": False,
            "writer_alive": False,
            "stopped": True,
            "clean_shutdown": True,
            "durable_ingress_sequence": 0,
            "last_ingress_sequence": 0,
        }
        contradictions = (
            {"stream_ready": True},
            {"transport_ready": True},
            {"writer_alive": True},
            {"gap_latched": "true"},
            {"journal_schema_version": True},
            {"real_order_enabled": True},
            {"order_api_called_count": 1},
            {"tick_snapshot_generation_uuid": "stale-generation"},
            {
                "tick_snapshot_commit": {
                    "generation_uuid": "stale-generation",
                    "stream_sequence": 0,
                }
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            for override in contradictions:
                with self.subTest(override=override):
                    with self.assertRaisesRegex(
                        ValueError,
                        "non-authoritative heartbeat contract invalid",
                    ):
                        stage608._recover_previous_journal(
                            previous_heartbeat={**base, **override},
                            journal_path=Path(tmp) / "missing.ndjson",
                        )

    def test_failed_emergency_revocation_marks_authority_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = Path(tmp) / "heartbeat.json"
            current = {
                "feed_session_id": "feed-unsafe",
                "journal_authority_committed": True,
                "stream_ready": True,
                "transport_ready": True,
                "stopped": False,
            }
            heartbeat.write_text(json.dumps(current), encoding="utf-8")
            summary: dict[str, object] = {
                "status": "tick_stream_running",
                "final_heartbeat_error": "OSError('failed')",
            }
            with patch.object(
                stage608,
                "_atomic_write_json",
                side_effect=OSError("disk unavailable"),
            ):
                revoked = stage608._publish_fail_closed_current_authority(
                    heartbeat,
                    feed_session_id="feed-unsafe",
                    summary=summary,
                    fallback_heartbeat=current,
                )

        self.assertEqual(revoked, {})
        self.assertTrue(summary["journal_authority_unsafe"])
        self.assertEqual(summary["status"], "stream_authority_unsafe")
        self.assertEqual(
            stage608._stream_exit_code(connect=True, result=summary),
            2,
        )

    def test_emergency_revocation_publishes_shutdown_cursor_and_gap_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = Path(tmp) / "heartbeat.json"
            current = {
                "feed_session_id": "feed-emergency-cursor",
                "journal_authority_committed": True,
                "journal_schema": "stage179_framed_v1",
                "journal_format": "stage179_framed_ndjson_v1",
                "journal_schema_version": 1,
                "journal_segment_path": str(Path(tmp) / "segment.ndjson"),
                "stream_sequence": 0,
                "journal_tick_count": 0,
                "durable_ingress_sequence": 0,
                "durable_journal_byte_offset": 0,
                "last_ingress_sequence": 0,
                "stream_ready": True,
                "transport_ready": True,
                "stopped": False,
            }
            heartbeat.write_text(json.dumps(current), encoding="utf-8")
            summary: dict[str, object] = {
                "status": "tick_stream_exception",
                "final_heartbeat_error": "OSError('failed')",
                "shutdown_report": {
                    "drained": False,
                    "durable_through": {
                        "feed_session_id": "feed-emergency-cursor",
                        "ingress_sequence": 2,
                        "journal_byte_offset": 321,
                        "journal_schema": "stage179_framed_v1",
                    },
                    "gap": {
                        "feed_session_id": "feed-emergency-cursor",
                        "start_ingress_sequence": 3,
                        "end_ingress_sequence": 3,
                        "reason": "shutdown_drain_timeout",
                    },
                    "writer_fault": {
                        "kind": "shutdown_drain_timeout",
                        "detail": "timeout",
                        "occurred_epoch_ns": 0,
                    },
                },
            }
            revoked = stage608._publish_fail_closed_current_authority(
                heartbeat,
                feed_session_id="feed-emergency-cursor",
                summary=summary,
                fallback_heartbeat=current,
                journal_session_state="fault_stopped",
            )

        self.assertEqual(revoked["durable_ingress_sequence"], 2)
        self.assertEqual(revoked["stream_sequence"], 2)
        self.assertEqual(revoked["journal_tick_count"], 2)
        self.assertEqual(revoked["durable_journal_byte_offset"], 321)
        self.assertEqual(revoked["last_ingress_sequence"], 3)
        self.assertEqual(revoked["gap_start_ingress_sequence"], 3)
        self.assertEqual(
            revoked["journal_commit_revoked_from_ingress_sequence"],
            3,
        )

    def test_connect_stream_exit_code_fails_closed_on_block_or_fault(self) -> None:
        passing = {
            "journal_session_state": "clean_stopped",
            "journal_authority_committed": True,
            "ever_stream_ready": True,
            "stopped": True,
            "clean_shutdown": True,
            "stream_ready": False,
            "transport_ready": False,
            "gap_latched": False,
            "writer_fault": None,
            "writer_alive": False,
            "accepting": False,
            "queue_depth": 0,
            "dropped_tick_count": 0,
            "last_ingress_sequence": 1,
            "durable_ingress_sequence": 1,
            "durable_journal_byte_offset": 128,
            "journal_schema": "stage179_framed_v1",
            "real_order_enabled": False,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "send_order_api_attempted_count": 0,
            "cancel_order_api_attempted_count": 0,
            "order_api_called_count": 0,
        }
        self.assertEqual(
            stage608._stream_exit_code(
                connect=True,
                result={"status": "stream_blocked_missing_env"},
            ),
            2,
        )
        self.assertEqual(
            stage608._stream_exit_code(
                connect=True,
                result={"journal_session_state": "fault_stopped"},
            ),
            2,
        )
        self.assertEqual(
            stage608._stream_exit_code(
                connect=False,
                result={"status": "stream_dry_run_not_connected"},
            ),
            0,
        )
        self.assertEqual(
            stage608._stream_exit_code(
                connect=True,
                result=passing,
            ),
            0,
        )
        for override in (
            {"journal_authority_committed": False},
            {"stopped": False},
            {"clean_shutdown": False},
            {"stream_ready": True},
            {"transport_ready": True},
            {"gap_latched": True},
            {"writer_fault": {"kind": "journal_write_error"}},
            {"writer_alive": True},
            {"accepting": True},
            {"queue_depth": 1},
            {"dropped_tick_count": 1},
            {"last_ingress_sequence": 2},
            {"durable_journal_byte_offset": 0},
            {"journal_schema": "legacy_ndjson_v0"},
        ):
            with self.subTest(terminal_override=override):
                self.assertEqual(
                    stage608._stream_exit_code(
                        connect=True,
                        result={**passing, **override},
                    ),
                    2,
                )
        for missing_field in (
            "journal_authority_committed",
            "accepting",
            "durable_journal_byte_offset",
            "journal_schema",
        ):
            with self.subTest(missing_terminal_field=missing_field):
                candidate = dict(passing)
                candidate.pop(missing_field)
                self.assertEqual(
                    stage608._stream_exit_code(
                        connect=True,
                        result=candidate,
                    ),
                    2,
                )
        self.assertEqual(
            stage608._stream_exit_code(
                connect=True,
                result={"journal_session_state": "clean_stopped"},
            ),
            2,
        )

    def test_snapshot_probe_exit_code_requires_readonly_login_and_position_gate(self) -> None:
        passing = {
            "status": "readonly_tick_snapshots_received",
            "target_symbol_count": 1,
            "target_symbols": ["JM609.DCE"],
            "received_target_symbols": ["JM609.DCE"],
            "missing_target_tick_symbols": [],
            "row_counts": {"ticks": 1},
            "real_order_enabled": False,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "send_order_api_attempted_count": 0,
            "cancel_order_api_attempted_count": 0,
            "order_api_called_count": 0,
            "log_analysis": {
                "td_login_success": True,
                "md_login_success": True,
            },
            "broker_snapshot": {
                "position_snapshot_state": "confirmed_flat",
                "position_query_last_seen": True,
                "position_query_error_rows": 0,
            },
        }
        self.assertEqual(
            stage608._probe_exit_code(connect=True, result=passing),
            0,
        )
        self.assertEqual(
            stage608._probe_exit_code(
                connect=True,
                result={**passing, "send_order_api_attempted_count": 1},
            ),
            2,
        )
        self.assertEqual(
            stage608._probe_exit_code(
                connect=True,
                result={**passing, "log_analysis": {}},
            ),
            2,
        )
        self.assertEqual(
            stage608._probe_exit_code(
                connect=True,
                result={**passing, "status": "connect_exception"},
            ),
            2,
        )
        self.assertEqual(
            stage608._probe_exit_code(
                connect=True,
                result={
                    **passing,
                    "missing_target_tick_symbols": ["JM609.DCE"],
                    "row_counts": {"ticks": 0},
                },
            ),
            2,
        )
        self.assertEqual(
            stage608._probe_exit_code(
                connect=True,
                result={
                    **passing,
                    "broker_snapshot": {
                        "position_snapshot_state": "positions_received",
                        "position_query_last_seen": False,
                        "position_query_error_rows": 1,
                    },
                },
            ),
            2,
        )
        self.assertEqual(
            stage608._probe_exit_code(connect=False, result={}),
            0,
        )

    def test_readonly_exit_codes_reject_side_effect_and_cleanup_evidence(self) -> None:
        stream_passing = {
            "journal_session_state": "clean_stopped",
            "journal_authority_committed": True,
            "ever_stream_ready": True,
            "stopped": True,
            "clean_shutdown": True,
            "stream_ready": False,
            "transport_ready": False,
            "gap_latched": False,
            "writer_fault": None,
            "writer_alive": False,
            "accepting": False,
            "queue_depth": 0,
            "dropped_tick_count": 0,
            "last_ingress_sequence": 1,
            "durable_ingress_sequence": 1,
            "real_order_enabled": False,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "send_order_api_attempted_count": 0,
            "cancel_order_api_attempted_count": 0,
            "order_api_called_count": 0,
        }
        probe_passing = {
            "status": "readonly_tick_snapshots_received",
            "target_symbol_count": 1,
            "received_target_symbols": ["JM609.DCE"],
            "missing_target_tick_symbols": [],
            "row_counts": {"ticks": 1},
            "real_order_enabled": False,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "send_order_api_attempted_count": 0,
            "cancel_order_api_attempted_count": 0,
            "order_api_called_count": 0,
            "log_analysis": {
                "td_login_success": True,
                "md_login_success": True,
            },
            "broker_snapshot": {
                "position_snapshot_state": "confirmed_flat",
                "position_query_last_seen": True,
                "position_query_error_rows": 0,
            },
        }
        side_effects = {
            "real_order_enabled": True,
            "send_order_api_called_count": 1,
            "cancel_order_api_called_count": 1,
            "send_order_api_attempted_count": 1,
            "cancel_order_api_attempted_count": 1,
            "order_api_called_count": 1,
        }
        for field, value in side_effects.items():
            with self.subTest(gate="stream", field=field):
                self.assertEqual(
                    stage608._stream_exit_code(
                        connect=True,
                        result={**stream_passing, field: value},
                    ),
                    2,
                )
            with self.subTest(gate="probe", field=field):
                self.assertEqual(
                    stage608._probe_exit_code(
                        connect=True,
                        result={**probe_passing, field: value},
                    ),
                    2,
                )
        for field in (
            "order_guard_restore_error",
            "position_callback_restore_error",
            "trading_api_close_error",
            "market_data_api_close_error",
            "event_engine_stop_error",
            "trading_api_close_fence_error",
            "market_data_api_close_fence_error",
            "engine_close_error:oms",
        ):
            with self.subTest(gate="probe", field=field):
                self.assertEqual(
                    stage608._probe_exit_code(
                        connect=True,
                        result={**probe_passing, field: "injected failure"},
                    ),
                    2,
                )

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
            journal_size = (Path(tmp) / "ticks.ndjson").stat().st_size

        self.assertEqual(before.durable_ingress_sequence, 0)
        self.assertEqual(before.durable_journal_byte_offset, 0)
        self.assertEqual(before.rows, ())
        self.assertEqual(after.durable_ingress_sequence, 1)
        self.assertEqual(after.durable_journal_byte_offset, journal_size)
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
            (
                snapshot.symbol_watermarks[
                    "JM609.DCE"
                ].durable_symbol_sequence,
                snapshot.symbol_watermarks[
                    "JM609.DCE"
                ].first_buffered_symbol_sequence,
            ),
            (1, 0),
        )
        self.assertEqual(
            snapshot.symbol_watermarks[
                "I609.DCE"
            ].first_buffered_symbol_sequence,
            1,
        )
        self.assertEqual(
            (
                snapshot.symbol_watermarks[
                    "I609.DCE"
                ].durable_symbol_sequence,
                snapshot.symbol_watermarks[
                    "I609.DCE"
                ].evicted_through_symbol_sequence,
            ),
            (1, 0),
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

    def test_shutdown_timeout_revocation_survives_restart_recovery(self) -> None:
        from dataclasses import asdict

        from qmt_roll_official_live_tick_stream import (
            JOURNAL_SCHEMA_FRAMED_V1,
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
            journal = Path(tmp) / "revoked.ndjson"
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
                feed_session_id="feed-persisted-revocation",
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
                side_effect=blocking_batch_barrier,
            ):
                pipeline.start()
                self.assertTrue(fsync_entered.wait(timeout=1.0))
                report = pipeline.shutdown(timeout_seconds=0.01)
                release_fsync.set()
                self.assertTrue(
                    pipeline.wait_until_writer_stops(timeout_seconds=1.0)
                )

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-persisted-revocation",
                    "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 1,
                    "gap_latched": True,
                    "gap_start_ingress_sequence": 1,
                    "gap_end_ingress_sequence": 1,
                    "gap_reason": "shutdown_drain_timeout",
                    "writer_fault": asdict(report.writer_fault),
                    "stopped": True,
                    "clean_shutdown": False,
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

    def test_writer_rejects_envelope_row_identity_mismatch_before_tick_bytes(self) -> None:
        from dataclasses import replace

        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "identity-mismatch.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-envelope-identity",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            envelope = pipeline.capture_ingress(self._ingress_tick())
            queued = pipeline.take_ingress_nowait()
            pipeline._ingress_queue.task_done()
            self.assertIs(queued, envelope)
            mismatched_row = dict(envelope.tick_row)
            mismatched_row["feed_session_id"] = "evil-feed"
            mismatched_row["ingress_sequence"] = 99
            pipeline._ingress_queue.put_nowait(
                replace(
                    envelope,
                    tick_row=MappingProxyType(mismatched_row),
                )
            )
            pipeline.start()
            self.assertTrue(pipeline.wait_until_writer_stops(timeout_seconds=1.0))
            persisted = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIsNotNone(pipeline.durable_snapshot().writer_fault)
        self.assertFalse(any("ingress_sequence" in row for row in persisted))

    def test_writer_rejects_bool_alias_for_integer_identity_before_tick_bytes(self) -> None:
        from dataclasses import replace

        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "bool-identity-alias.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-bool-identity",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            envelope = pipeline.capture_ingress(self._ingress_tick())
            queued = pipeline.take_ingress_nowait()
            pipeline._ingress_queue.task_done()
            self.assertIs(queued, envelope)
            mismatched_row = dict(envelope.tick_row)
            mismatched_row["ingress_sequence"] = True
            pipeline._ingress_queue.put_nowait(
                replace(
                    envelope,
                    tick_row=MappingProxyType(mismatched_row),
                )
            )
            pipeline.start()
            committed = pipeline.wait_until_durable(1, timeout_seconds=0.2)
            report = pipeline.shutdown(timeout_seconds=1.0)
            persisted = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]

        self.assertFalse(committed)
        self.assertIsNotNone(report.writer_fault)
        self.assertFalse(any("ingress_sequence" in row for row in persisted))

    def test_writer_rejects_non_integer_alias_when_envelope_and_row_agree(self) -> None:
        from dataclasses import replace

        from qmt_roll_official_live_tick_stream import TickStreamPipeline

        class FakeClock:
            def epoch_ns(self) -> int:
                return 1_784_000_000_000_000_000

            def monotonic_ns(self) -> int:
                return 1

            def sleep(self, seconds: float) -> None:
                return None

        identity_fields = {
            "ingress_sequence": ("ingress_sequence", "stream_sequence"),
            "symbol_sequence": ("symbol_sequence", "symbol_stream_sequence"),
            "ingress_epoch_ns": ("ingress_epoch_ns",),
            "ingress_monotonic_ns": ("ingress_monotonic_ns",),
        }
        for envelope_field, row_fields in identity_fields.items():
            for alias in (True, 1.0):
                with self.subTest(field=envelope_field, alias=alias):
                    with tempfile.TemporaryDirectory() as tmp:
                        journal = Path(tmp) / "non-integer-alias.ndjson"
                        pipeline = TickStreamPipeline(
                            feed_session_id="feed-non-integer-alias",
                            journal_segment_path=journal,
                            clock=FakeClock(),
                            queue_capacity=1,
                            max_buffer_ticks=1,
                            writer_batch_size=1,
                            writer_flush_seconds=0.001,
                        )
                        envelope = pipeline.capture_ingress(
                            self._ingress_tick()
                        )
                        queued = pipeline.take_ingress_nowait()
                        pipeline._ingress_queue.task_done()
                        self.assertIs(queued, envelope)
                        aliased_row = dict(envelope.tick_row)
                        for row_field in row_fields:
                            aliased_row[row_field] = alias
                        pipeline._ingress_queue.put_nowait(
                            replace(
                                envelope,
                                **{envelope_field: alias},
                                tick_row=MappingProxyType(aliased_row),
                            )
                        )
                        pipeline.start()
                        committed = pipeline.wait_until_durable(
                            1,
                            timeout_seconds=0.2,
                        )
                        report = pipeline.shutdown(timeout_seconds=1.0)
                        persisted = [
                            json.loads(line)
                            for line in journal.read_text(
                                encoding="utf-8"
                            ).splitlines()
                        ]

                    self.assertFalse(committed)
                    self.assertIsNotNone(report.writer_fault)
                    self.assertFalse(
                        any(
                            "ingress_sequence" in row
                            for row in persisted
                        )
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
                    "journal_schema": "legacy_ndjson_v0",
                    "journal_session_state": "recovery_required_stopped",
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

    def test_recovery_discloses_unknown_partial_suffix_when_heartbeat_is_stale_zero(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            JOURNAL_HEADER_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            recover_or_isolate_dirty_tail,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "partial-first-tick.ndjson"
            header = {
                JOURNAL_RECORD_TYPE_FIELD: JOURNAL_HEADER_RECORD_TYPE,
                "schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
                "feed_session_id": "feed-partial-zero",
                "segment_id": "feed-partial-zero",
                "first_ingress_sequence": 1,
            }
            journal.write_bytes(
                (
                    json.dumps(
                        header,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
                + b'{"feed_session_id":"feed-partial-zero","ingress_sequence":'
            )

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-partial-zero",
                    "journal_schema": "stage179_framed_v1",
                    "journal_session_state": "recovery_required_stopped",
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 0,
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

    def test_recovery_discloses_unclean_zero_write_session(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            JOURNAL_HEADER_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            JOURNAL_SCHEMA_FRAMED_V1,
            recover_or_isolate_dirty_tail,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "unclean-zero-write.ndjson"
            journal.write_text(
                json.dumps(
                    {
                        JOURNAL_RECORD_TYPE_FIELD: JOURNAL_HEADER_RECORD_TYPE,
                        "schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
                        "feed_session_id": "feed-unclean-zero",
                        "segment_id": "feed-unclean-zero",
                        "first_ingress_sequence": 1,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-unclean-zero",
                    "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 0,
                    "stopped": False,
                    "clean_shutdown": False,
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
        self.assertEqual(recovered.disclosed_gap.reason, "prior_session_unclean")

    def test_recovery_never_downgrades_declared_framed_journal_to_legacy(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_SCHEMA_FRAMED_V1,
            recover_or_isolate_dirty_tail,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "stripped-framed-controls.ndjson"
            journal.write_text(
                json.dumps(
                    {
                        "feed_session_id": "feed-declared-framed",
                        "ingress_sequence": 1,
                    },
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-declared-framed",
                    "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
                    "durable_ingress_sequence": 1,
                    "last_ingress_sequence": 1,
                    "stopped": True,
                    "clean_shutdown": True,
                },
            )

        self.assertIsNone(recovered.previous_durable_cursor)
        self.assertIsNotNone(recovered.disclosed_gap)
        self.assertEqual(recovered.disclosed_gap.reason, "journal_header_missing")
        self.assertIsNotNone(recovered.isolated_tail_path)

    def test_prior_gap_lineage_survives_multiple_clean_generations(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_SCHEMA_FRAMED_V1,
            recover_or_isolate_dirty_tail,
        )

        original_gap = {
            "feed_session_id": "feed-original-gap",
            "start_ingress_sequence": 8,
            "end_ingress_sequence": 10,
            "reason": "journal_uncommitted_suffix",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = recover_or_isolate_dirty_tail(
                root / "clean-generation-one.ndjson",
                {
                    "feed_session_id": "feed-clean-one",
                    "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 0,
                    "stopped": True,
                    "clean_shutdown": True,
                    "prior_uncommitted_gaps": [original_gap],
                },
            )
            second = recover_or_isolate_dirty_tail(
                root / "clean-generation-two.ndjson",
                {
                    "feed_session_id": "feed-clean-two",
                    "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 0,
                    "stopped": True,
                    "clean_shutdown": True,
                    "prior_uncommitted_gaps": [
                        {
                            "feed_session_id": gap.feed_session_id,
                            "start_ingress_sequence": gap.start_ingress_sequence,
                            "end_ingress_sequence": gap.end_ingress_sequence,
                            "reason": gap.reason,
                        }
                        for gap in first.disclosed_gaps
                    ],
                },
            )

        self.assertEqual(len(first.disclosed_gaps), 1)
        self.assertEqual(len(second.disclosed_gaps), 1)
        self.assertEqual(second.disclosed_gaps[0].feed_session_id, "feed-original-gap")
        self.assertEqual(
            (
                second.disclosed_gaps[0].start_ingress_sequence,
                second.disclosed_gaps[0].end_ingress_sequence,
            ),
            (8, 10),
        )

    def test_missing_unclean_segment_discloses_unknown_gap(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            recovered = recover_or_isolate_dirty_tail(
                Path(tmp) / "missing-running-segment.ndjson",
                {
                    "feed_session_id": "feed-missing-running",
                    "journal_schema": "stage179_framed_v1",
                    "journal_session_state": "running",
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 0,
                    "stopped": False,
                },
            )

        self.assertIsNotNone(recovered.disclosed_gap)
        self.assertEqual(
            (
                recovered.disclosed_gap.start_ingress_sequence,
                recovered.disclosed_gap.end_ingress_sequence,
            ),
            (1, 1),
        )
        self.assertEqual(recovered.disclosed_gap.reason, "prior_session_unclean")

    def test_malformed_lineage_or_unknown_schema_never_mutates_journal(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "evidence.ndjson"
            original = b'{"feed_session_id":"feed-evidence","ingress_sequence":1'
            journal.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "prior gap"):
                recover_or_isolate_dirty_tail(
                    journal,
                    {
                        "feed_session_id": "feed-evidence",
                        "journal_schema": "stage179_framed_v1",
                        "journal_session_state": "running",
                        "prior_uncommitted_gaps": [
                            {
                                "feed_session_id": "feed-old",
                                "start_ingress_sequence": 0,
                                "end_ingress_sequence": 1,
                                "reason": "bad",
                            }
                        ],
                    },
                )
            self.assertEqual(journal.read_bytes(), original)
            self.assertFalse(list(root.glob("*.dirty.*")))

            with self.assertRaisesRegex(ValueError, "prior gap"):
                recover_or_isolate_dirty_tail(
                    journal,
                    {
                        "feed_session_id": "feed-evidence",
                        "journal_schema": "stage179_framed_v1",
                        "journal_session_state": "running",
                        "prior_uncommitted_gaps": [
                            {
                                "feed_session_id": "feed-old",
                                "start_ingress_sequence": True,
                                "end_ingress_sequence": 1,
                                "reason": "bool-alias",
                            }
                        ],
                    },
                )
            self.assertEqual(journal.read_bytes(), original)
            self.assertFalse(list(root.glob("*.dirty.*")))

            with self.assertRaisesRegex(
                ValueError,
                "journal_schema_missing_or_unsupported",
            ):
                recover_or_isolate_dirty_tail(
                    journal,
                    {
                        "feed_session_id": "feed-evidence",
                        "journal_schema": "unknown-v99",
                        "journal_session_state": "running",
                    },
                )
            self.assertEqual(journal.read_bytes(), original)
            self.assertFalse(list(root.glob("*.dirty.*")))

    def test_recovery_rejects_contradictory_heartbeat_before_mutating_journal(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        base = {
            "feed_session_id": "feed-contract",
            "journal_schema": "stage179_framed_v1",
            "journal_session_state": "clean_stopped",
            "journal_authority_committed": True,
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        contradictions = (
            (
                {"journal_format": "legacy_ndjson_v0"},
                "journal_format",
            ),
            (
                {"journal_schema_version": 0},
                "journal_schema_version",
            ),
            (
                {"clean_shutdown": False},
                "clean_shutdown",
            ),
            (
                {"stopped": False},
                "stopped",
            ),
            (
                {"journal_authority_committed": False},
                "journal_authority",
            ),
            (
                {"writer_fault": {"kind": "journal_write_error"}},
                "clean_stopped",
            ),
            (
                {
                    "gap_latched": True,
                    "gap_start_ingress_sequence": 1,
                    "gap_end_ingress_sequence": 1,
                    "gap_reason": "journal_write_error",
                },
                "gap|clean_stopped",
            ),
            (
                {
                    "journal_session_state": "running",
                    "stopped": True,
                    "clean_shutdown": False,
                },
                "stopped",
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (override, expected_error) in enumerate(contradictions):
                with self.subTest(override=override):
                    journal = root / f"contract-{index}.ndjson"
                    original = b'{"feed_session_id":"feed-contract"'
                    journal.write_bytes(original)
                    with self.assertRaisesRegex(ValueError, expected_error):
                        recover_or_isolate_dirty_tail(
                            journal,
                            {**base, **override},
                        )
                    self.assertEqual(journal.read_bytes(), original)
                    self.assertFalse(
                        list(root.glob(f"{journal.name}.dirty.*"))
                    )

    def test_recovery_rejects_noncanonical_numeric_and_gap_evidence(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        base = {
            "feed_session_id": "feed-numeric-contract",
            "journal_schema": "stage179_framed_v1",
            "journal_session_state": "running",
            "durable_ingress_sequence": 0,
            "last_ingress_sequence": 1,
            "stopped": False,
            "clean_shutdown": False,
        }
        invalid = (
            ({"durable_ingress_sequence": True}, "heartbeat integer"),
            ({"last_ingress_sequence": 1.5}, "heartbeat integer"),
            ({"durable_journal_byte_offset": True}, "heartbeat integer"),
            ({"durable_journal_byte_offset": -1}, "negative heartbeat integer"),
            (
                {"durable_journal_byte_offset": 1},
                "framed_zero_sequence_offset_nonzero",
            ),
            (
                {
                    "durable_ingress_sequence": 2,
                    "last_ingress_sequence": 1,
                },
                "exceeds",
            ),
            ({"stream_sequence": 1}, "stream_sequence"),
            ({"journal_tick_count": 1}, "journal_tick_count"),
            (
                {
                    "gap_latched": False,
                    "gap_start_ingress_sequence": 1,
                    "gap_end_ingress_sequence": 1,
                    "gap_reason": "journal_write_error",
                },
                "gap tuple",
            ),
            (
                {
                    "journal_commit_revoked_from_ingress_sequence": 2,
                    "journal_commit_revoked_through_ingress_sequence": 1,
                    "journal_commit_revocation_reason": "shutdown_drain_timeout",
                },
                "revocation tuple",
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (override, expected_error) in enumerate(invalid):
                with self.subTest(override=override):
                    journal = root / f"numeric-{index}.ndjson"
                    original = b'{"feed_session_id":"feed-numeric-contract"'
                    journal.write_bytes(original)
                    with self.assertRaisesRegex(ValueError, expected_error):
                        recover_or_isolate_dirty_tail(
                            journal,
                            {**base, **override},
                        )
                    self.assertEqual(journal.read_bytes(), original)
                    self.assertFalse(
                        list(root.glob(f"{journal.name}.dirty.*"))
                    )

    def test_recovery_requires_committed_authority_or_empty_bootstrap(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        heartbeat = {
            "feed_session_id": "feed-non-authority",
            "journal_schema": "stage179_framed_v1",
            "journal_session_state": "clean_stopped",
            "journal_authority_committed": False,
            "durable_ingress_sequence": 0,
            "last_ingress_sequence": 0,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.ndjson"
            bootstrap = recover_or_isolate_dirty_tail(missing, heartbeat)
            self.assertIsNone(bootstrap.previous_durable_cursor)

            existing = root / "existing.ndjson"
            original = b"legacy-evidence-must-not-be-touched\n"
            existing.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "authority"):
                recover_or_isolate_dirty_tail(existing, heartbeat)
            self.assertEqual(existing.read_bytes(), original)
            self.assertFalse(list(root.glob("*.dirty.*")))

            authoritative_missing = root / "authoritative-missing.ndjson"
            with self.assertRaisesRegex(ValueError, "authoritative_journal_missing"):
                recover_or_isolate_dirty_tail(
                    authoritative_missing,
                    {
                        **heartbeat,
                        "feed_session_id": "feed-authoritative-missing",
                        "journal_authority_committed": True,
                    },
                )

            authoritative_empty = root / "authoritative-empty.ndjson"
            authoritative_empty.touch()
            with self.assertRaisesRegex(ValueError, "authoritative_journal_empty"):
                recover_or_isolate_dirty_tail(
                    authoritative_empty,
                    {
                        **heartbeat,
                        "feed_session_id": "feed-authoritative-empty",
                        "journal_authority_committed": True,
                    },
                )

    def test_pre_stage179_clean_stopped_heartbeat_discloses_unproven_legacy_ticks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "old-stage608.ndjson"
            original = (
                b'{"feed_session_id":"old-feed","stream_sequence":1,'
                b'"vt_symbol":"JM609.DCE"}\n'
                b'{"feed_session_id":"old-feed","stream_sequence":2,'
                b'"vt_symbol":"JM609.DCE"}\n'
            )
            journal.write_bytes(original)
            heartbeat = {
                "model_tag": stage608.MODEL_TAG,
                "mode": "continuous_tick_stream",
                "feed_session_id": "old-feed",
                "journal_path": str(journal),
                "stream_sequence": 1,
                "journal_tick_count": 1,
                "stream_ready": False,
                "transport_ready": False,
                "stopped": True,
                "status": "tick_stream_stopped",
                "real_order_enabled": False,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            }

            migrated = stage608._recover_previous_journal(
                previous_heartbeat=heartbeat,
                journal_path=journal,
            )
            self.assertIsNone(migrated.previous_durable_cursor)
            self.assertEqual(len(migrated.disclosed_gaps), 1)
            self.assertEqual(
                (
                    migrated.disclosed_gap.start_ingress_sequence,
                    migrated.disclosed_gap.end_ingress_sequence,
                    migrated.disclosed_gap.reason,
                ),
                (1, 2, "legacy_pre_stage179_durability_unproven"),
            )
            self.assertEqual(journal.read_bytes(), original)
            self.assertFalse(list(root.glob("*.dirty.*")))

            empty_migration = stage608._recover_previous_journal(
                previous_heartbeat={
                    **heartbeat,
                    "feed_session_id": "empty-old-feed",
                    "journal_path": str(root / "missing-empty.ndjson"),
                    "stream_sequence": 0,
                    "journal_tick_count": 0,
                },
                journal_path=root / "missing-empty.ndjson",
            )
            self.assertEqual(empty_migration.disclosed_gaps, ())

            with self.assertRaisesRegex(ValueError, "legacy.*cleanly_stopped"):
                stage608._recover_previous_journal(
                    previous_heartbeat={
                        **heartbeat,
                        "stream_ready": True,
                        "stopped": False,
                        "status": "tick_stream_ready",
                    },
                    journal_path=journal,
                )

    def test_pre_stage179_nonempty_corrupt_journal_never_migrates_gap_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "corrupt-old-stage608.ndjson"
            original = b'{"feed_session_id":"old-feed","stream_sequence":'
            journal.write_bytes(original)
            migrated = stage608._recover_previous_journal(
                previous_heartbeat={
                    "model_tag": stage608.MODEL_TAG,
                    "mode": "continuous_tick_stream",
                    "status": "tick_stream_stopped",
                    "feed_session_id": "old-feed",
                    "journal_path": str(journal),
                    "stream_sequence": 0,
                    "journal_tick_count": 0,
                    "stream_ready": False,
                    "transport_ready": False,
                    "stopped": True,
                    "real_order_enabled": False,
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                    "order_api_called_count": 0,
                },
                journal_path=journal,
            )
            persisted_bytes = journal.read_bytes()

        self.assertIsNone(migrated.previous_durable_cursor)
        self.assertIsNotNone(migrated.disclosed_gap)
        self.assertEqual(
            (
                migrated.disclosed_gap.start_ingress_sequence,
                migrated.disclosed_gap.end_ingress_sequence,
                migrated.disclosed_gap.reason,
            ),
            (1, 1, "legacy_pre_stage179_durability_unproven"),
        )
        self.assertEqual(persisted_bytes, original)

    def test_pre_stage179_huge_integer_json_is_disclosed_as_unproven_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "huge-integer-old-stage608.ndjson"
            original = b'{"feed_session_id":"old-feed","x":' + (b"9" * 5_000) + b"}\n"
            journal.write_bytes(original)
            migrated = stage608._recover_previous_journal(
                previous_heartbeat={
                    "model_tag": stage608.MODEL_TAG,
                    "mode": "continuous_tick_stream",
                    "status": "tick_stream_stopped",
                    "feed_session_id": "old-feed",
                    "journal_path": str(journal),
                    "stream_sequence": 0,
                    "journal_tick_count": 0,
                    "stream_ready": False,
                    "transport_ready": False,
                    "stopped": True,
                    "real_order_enabled": False,
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                    "order_api_called_count": 0,
                },
                journal_path=journal,
            )
            persisted_bytes = journal.read_bytes()

        self.assertEqual(
            (
                migrated.disclosed_gap.start_ingress_sequence,
                migrated.disclosed_gap.end_ingress_sequence,
                migrated.disclosed_gap.reason,
            ),
            (1, 1, "legacy_pre_stage179_durability_unproven"),
        )
        self.assertEqual(persisted_bytes, original)

    def test_pre_stage179_existing_non_regular_journal_is_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal_directory = Path(tmp) / "legacy-journal-directory"
            journal_directory.mkdir()
            heartbeat = {
                "model_tag": stage608.MODEL_TAG,
                "mode": "continuous_tick_stream",
                "status": "tick_stream_stopped",
                "feed_session_id": "old-feed",
                "journal_path": str(journal_directory),
                "stream_sequence": 0,
                "journal_tick_count": 0,
                "stream_ready": False,
                "transport_ready": False,
                "stopped": True,
                "real_order_enabled": False,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            }
            with self.assertRaisesRegex(
                ValueError,
                "legacy_journal_not_regular_file",
            ):
                stage608._recover_previous_journal(
                    previous_heartbeat=heartbeat,
                    journal_path=journal_directory,
                )

    def test_recovery_preserves_explicit_shutdown_revocation_reason(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "shutdown-gap.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-shutdown","ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-shutdown","ingress_sequence":2'
            )
            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-shutdown",
                    "journal_schema": "legacy_ndjson_v0",
                    "journal_session_state": "fault_stopped",
                    "durable_ingress_sequence": 1,
                    "last_ingress_sequence": 2,
                    "gap_latched": True,
                    "gap_start_ingress_sequence": 2,
                    "gap_end_ingress_sequence": 2,
                    "gap_reason": "shutdown_drain_timeout",
                    "journal_commit_revoked_from_ingress_sequence": 2,
                    "journal_commit_revoked_through_ingress_sequence": 2,
                    "journal_commit_revocation_reason": "shutdown_drain_timeout",
                    "stopped": True,
                    "clean_shutdown": False,
                },
            )

        self.assertEqual(recovered.disclosed_gap.reason, "shutdown_drain_timeout")
        self.assertEqual(
            (
                recovered.disclosed_gap.start_ingress_sequence,
                recovered.disclosed_gap.end_ingress_sequence,
            ),
            (2, 2),
        )

    def test_recovery_reports_corruption_before_claimed_durable_boundary(self) -> None:
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "corrupt-before-durable.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-corrupt","ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-corrupt","ingress_sequence":2'
            )
            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": "feed-corrupt",
                    "journal_schema": "legacy_ndjson_v0",
                    "journal_session_state": "fault_stopped",
                    "durable_ingress_sequence": 2,
                    "last_ingress_sequence": 3,
                    "gap_latched": True,
                    "gap_start_ingress_sequence": 3,
                    "gap_end_ingress_sequence": 3,
                    "gap_reason": "shutdown_drain_timeout",
                    "journal_commit_revoked_from_ingress_sequence": 3,
                    "journal_commit_revoked_through_ingress_sequence": 3,
                    "journal_commit_revocation_reason": "shutdown_drain_timeout",
                    "stopped": True,
                    "clean_shutdown": False,
                },
            )

        self.assertEqual(
            recovered.disclosed_gap.reason,
            "journal_partial_line_before_durable_watermark",
        )
        self.assertEqual(
            (
                recovered.disclosed_gap.start_ingress_sequence,
                recovered.disclosed_gap.end_ingress_sequence,
            ),
            (2, 3),
        )

    def test_recovery_revalidates_authority_after_acquiring_owner_fence(self) -> None:
        from contextlib import contextmanager

        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        heartbeat = {
            "feed_session_id": "feed-raced-authority",
            "journal_schema": "stage179_framed_v1",
            "journal_session_state": "clean_stopped",
            "journal_authority_committed": False,
            "durable_ingress_sequence": 0,
            "last_ingress_sequence": 0,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "raced.ndjson"
            raced_bytes = b"raced-owner-evidence\n"

            @contextmanager
            def create_file_at_lock(_path: Path):
                journal.write_bytes(raced_bytes)
                yield

            with patch.object(
                journal_module,
                "_exclusive_journal_lock",
                side_effect=create_file_at_lock,
            ):
                with self.assertRaisesRegex(ValueError, "authority"):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertEqual(journal.read_bytes(), raced_bytes)
            self.assertFalse(list(Path(tmp).glob("*.dirty.*")))

    def test_recovery_never_truncates_a_replaced_segment_inode(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "replace-race.ndjson"
            trusted = b'{"feed_session_id":"feed-replace","ingress_sequence":1}\n'
            journal.write_bytes(
                trusted
                + b'{"feed_session_id":"feed-replace","ingress_sequence":2'
            )
            replacement = root / "replacement.ndjson"
            replacement_bytes = b"new-owner-must-remain-byte-exact\n"
            replacement.write_bytes(replacement_bytes)
            real_parent_fsync = journal_module._fsync_parent
            parent_fsync_calls = 0

            def replace_after_dirty_fsync(path: Path) -> None:
                nonlocal parent_fsync_calls
                parent_fsync_calls += 1
                if parent_fsync_calls == 1:
                    os.replace(replacement, journal)
                real_parent_fsync(path)

            with patch.object(
                journal_module,
                "_fsync_parent",
                side_effect=replace_after_dirty_fsync,
            ):
                with self.assertRaisesRegex(RuntimeError, "changed.*recovery"):
                    recover_or_isolate_dirty_tail(
                        journal,
                        {
                            "feed_session_id": "feed-replace",
                            "journal_schema": "legacy_ndjson_v0",
                            "journal_session_state": "recovery_required_stopped",
                            "durable_ingress_sequence": 1,
                            "last_ingress_sequence": 2,
                        },
                    )

            self.assertEqual(journal.read_bytes(), replacement_bytes)

    def test_recovery_refuses_segment_while_writer_owner_lock_is_held(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "owned.ndjson"
            journal.write_bytes(b"owned-segment\n")
            heartbeat = {
                "feed_session_id": "feed-owned",
                "journal_schema": "stage179_framed_v1",
                "journal_session_state": "running",
                "durable_ingress_sequence": 0,
                "last_ingress_sequence": 0,
                "stopped": False,
                "clean_shutdown": False,
            }
            with journal_module._exclusive_journal_lock(journal):
                with self.assertRaisesRegex(RuntimeError, "lock_contended"):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertEqual(journal.read_bytes(), b"owned-segment\n")
            self.assertFalse(list(Path(tmp).glob("*.dirty.*")))

    def test_recovery_fsyncs_dirty_directory_entry_before_truncating_source(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "dirty-order.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-dirty-order","ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-dirty-order","ingress_sequence":2'
            )
            real_fsync_parent = journal_module._fsync_parent
            fsync_parent_calls: list[Path] = []

            def record_parent_fsync(path: Path) -> None:
                fsync_parent_calls.append(path)
                real_fsync_parent(path)

            with patch.object(
                journal_module,
                "_fsync_parent",
                side_effect=record_parent_fsync,
            ):
                recovered = recover_or_isolate_dirty_tail(
                    journal,
                    {
                        "feed_session_id": "feed-dirty-order",
                        "journal_schema": "legacy_ndjson_v0",
                        "journal_session_state": "recovery_required_stopped",
                        "durable_ingress_sequence": 1,
                        "last_ingress_sequence": 2,
                    },
                )

        self.assertIsNotNone(recovered.isolated_tail_path)
        self.assertEqual(len(fsync_parent_calls), 3)
        self.assertEqual(fsync_parent_calls[0], recovered.isolated_tail_path)
        self.assertEqual(fsync_parent_calls[1], recovered.recovery_manifest_path)
        self.assertEqual(fsync_parent_calls[2], journal)

    def test_recovery_replays_durable_manifest_after_crash_post_truncate(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import (
            acknowledge_recovery_manifest,
            recover_or_isolate_dirty_tail,
        )

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-recovery-redo",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "recovery-redo.ndjson"
            trusted_prefix = (
                b'{"feed_session_id":"feed-recovery-redo","ingress_sequence":1}\n'
            )
            journal.write_bytes(
                trusted_prefix
                + b'{"feed_session_id":"feed-recovery-redo","ingress_sequence":2'
            )
            real_barrier = journal_module._durability_barrier
            barrier_calls = 0

            def crash_after_truncated_source_is_durable(fd: int) -> None:
                nonlocal barrier_calls
                barrier_calls += 1
                real_barrier(fd)
                descriptor_stat = os.fstat(fd)
                path_stat = journal.stat()
                if (
                    descriptor_stat.st_ino == path_stat.st_ino
                    and descriptor_stat.st_size == len(trusted_prefix)
                ):
                    raise InjectedCrash("after source truncate fsync")

            with patch.object(
                journal_module,
                "_durability_barrier",
                side_effect=crash_after_truncated_source_is_durable,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertEqual(journal.read_bytes(), trusted_prefix)
            replayed = recover_or_isolate_dirty_tail(journal, heartbeat)
            self.assertIsNotNone(replayed.disclosed_gap)
            self.assertEqual(
                (
                    replayed.disclosed_gap.start_ingress_sequence,
                    replayed.disclosed_gap.end_ingress_sequence,
                ),
                (2, 2),
            )
            self.assertTrue(replayed.recovery_transaction_id)
            self.assertIsNotNone(replayed.recovery_manifest_path)
            self.assertTrue(replayed.recovery_manifest_path.exists())
            self.assertTrue(replayed.recovery_ack_required)
            self.assertEqual(len(list(Path(tmp).glob("*.dirty.*"))), 1)

            committed_heartbeat = {
                "journal_authority_committed": True,
                "journal_session_state": "starting",
                "stopped": False,
                "stream_ready": False,
                "transport_ready": False,
                "prior_recovery_transaction_id": (
                    replayed.recovery_transaction_id
                ),
                "prior_recovery_manifest_path": str(
                    replayed.recovery_manifest_path.resolve()
                ),
                "prior_uncommitted_gaps": [
                    {
                        "feed_session_id": replayed.disclosed_gap.feed_session_id,
                        "start_ingress_sequence": (
                            replayed.disclosed_gap.start_ingress_sequence
                        ),
                        "end_ingress_sequence": (
                            replayed.disclosed_gap.end_ingress_sequence
                        ),
                        "reason": replayed.disclosed_gap.reason,
                    }
                ],
            }
            committed_heartbeat_path = Path(tmp) / "committed-heartbeat.json"
            committed_heartbeat_path.write_text(
                json.dumps(
                    {
                        **committed_heartbeat,
                        "prior_uncommitted_gaps": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "not_committed_in_heartbeat",
            ):
                acknowledge_recovery_manifest(
                    replayed,
                    committed_heartbeat_path,
                )
            self.assertTrue(replayed.recovery_manifest_path.exists())
            committed_heartbeat_path.write_text(
                json.dumps(
                    {
                        **committed_heartbeat,
                        "stream_ready": True,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "not_committed_in_heartbeat",
            ):
                acknowledge_recovery_manifest(
                    replayed,
                    committed_heartbeat_path,
                )
            self.assertTrue(replayed.recovery_manifest_path.exists())
            committed_heartbeat_path.write_text(
                json.dumps(committed_heartbeat),
                encoding="utf-8",
            )
            acknowledge_recovery_manifest(replayed, committed_heartbeat_path)
            self.assertFalse(replayed.recovery_manifest_path.exists())

    def test_recovery_replays_manifest_after_crash_before_truncate(self) -> None:
        import qmt_roll_official_live_tick_recovery as recovery_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-recovery-pretruncate",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "recovery-pretruncate.ndjson"
            trusted_prefix = (
                b'{"feed_session_id":"feed-recovery-pretruncate",'
                b'"ingress_sequence":1}\n'
            )
            original = (
                trusted_prefix
                + b'{"feed_session_id":"feed-recovery-pretruncate",'
                b'"ingress_sequence":2'
            )
            journal.write_bytes(original)
            real_manifest_write = recovery_module._atomic_write_recovery_manifest

            def crash_after_manifest_commit(
                manifest_path: Path,
                payload: object,
            ) -> None:
                real_manifest_write(manifest_path, payload)
                raise InjectedCrash("after recovery manifest commit")

            with patch.object(
                recovery_module,
                "_atomic_write_recovery_manifest",
                side_effect=crash_after_manifest_commit,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertEqual(journal.read_bytes(), original)
            replayed = recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertEqual(journal.read_bytes(), trusted_prefix)
            self.assertEqual(
                (
                    replayed.disclosed_gap.start_ingress_sequence,
                    replayed.disclosed_gap.end_ingress_sequence,
                ),
                (2, 2),
            )
            self.assertTrue(replayed.recovery_transaction_id)
            self.assertEqual(len(list(Path(tmp).glob("*.dirty.*"))), 1)

    def test_restart_idempotently_acks_manifest_from_committed_fault_successor(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            acknowledge_committed_recovery_manifest,
            recover_or_isolate_dirty_tail,
        )

        heartbeat = {
            "feed_session_id": "feed-restart-ack",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "restart-ack.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-restart-ack",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-restart-ack",'
                b'"ingress_sequence":2'
            )
            recovered = recover_or_isolate_dirty_tail(journal, heartbeat)
            committed_path = root / "heartbeat.json"
            committed_path.write_text(
                json.dumps(
                    {
                        "journal_authority_committed": True,
                        "journal_session_state": "fault_stopped",
                        "stopped": True,
                        "clean_shutdown": False,
                        "stream_ready": False,
                        "transport_ready": False,
                        "writer_alive": False,
                        "prior_recovery_transaction_id": (
                            recovered.recovery_transaction_id
                        ),
                        "prior_recovery_manifest_path": str(
                            recovered.recovery_manifest_path.resolve()
                        ),
                        "prior_uncommitted_gaps": [
                            {
                                "feed_session_id": gap.feed_session_id,
                                "start_ingress_sequence": (
                                    gap.start_ingress_sequence
                                ),
                                "end_ingress_sequence": (
                                    gap.end_ingress_sequence
                                ),
                                "reason": gap.reason,
                            }
                            for gap in recovered.disclosed_gaps
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                acknowledge_committed_recovery_manifest(committed_path)
            )
            self.assertFalse(recovered.recovery_manifest_path.exists())
            self.assertFalse(
                acknowledge_committed_recovery_manifest(committed_path)
            )

    def test_recovery_manifest_ack_rejects_outer_result_not_bound_to_transaction_core(
        self,
    ) -> None:
        import qmt_roll_official_live_tick_recovery as recovery_module
        from qmt_roll_official_live_tick_stream import (
            acknowledge_committed_recovery_manifest,
            acknowledge_recovery_manifest,
            recover_or_isolate_dirty_tail,
        )

        heartbeat = {
            "feed_session_id": "feed-ack-result-binding",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }

        def prepare_case(root: Path, suffix: str) -> tuple[object, Path]:
            case_root = root / suffix
            case_root.mkdir()
            journal = case_root / "ticks.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-ack-result-binding",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-ack-result-binding",'
                b'"ingress_sequence":2'
            )
            recovered = recover_or_isolate_dirty_tail(journal, heartbeat)
            committed_path = case_root / "heartbeat.json"
            committed_path.write_text(
                json.dumps(
                    {
                        "journal_authority_committed": True,
                        "journal_session_state": "fault_stopped",
                        "stopped": True,
                        "clean_shutdown": False,
                        "stream_ready": False,
                        "transport_ready": False,
                        "writer_alive": False,
                        "prior_recovery_transaction_id": (
                            recovered.recovery_transaction_id
                        ),
                        "prior_recovery_manifest_path": str(
                            recovered.recovery_manifest_path.resolve()
                        ),
                        "prior_uncommitted_gaps": [
                            {
                                "feed_session_id": gap.feed_session_id,
                                "start_ingress_sequence": (
                                    gap.start_ingress_sequence
                                ),
                                "end_ingress_sequence": (
                                    gap.end_ingress_sequence
                                ),
                                "reason": gap.reason,
                            }
                            for gap in recovered.disclosed_gaps
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manifest_path = recovered.recovery_manifest_path
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["result"] = {
                **payload["result"],
                "disclosed_gap": None,
                "disclosed_gaps": [],
            }
            unsigned = dict(payload)
            unsigned.pop("manifest_sha256", None)
            payload["manifest_sha256"] = hashlib.sha256(
                recovery_module._canonical_json_bytes(unsigned)
            ).hexdigest()
            manifest_path.write_bytes(
                recovery_module._canonical_json_bytes(payload) + b"\n"
            )
            return recovered, committed_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recovered, committed_path = prepare_case(root, "restart")
            with self.assertRaisesRegex(
                ValueError,
                "recovery_manifest_result_mismatch",
            ):
                acknowledge_committed_recovery_manifest(committed_path)
            self.assertTrue(recovered.recovery_manifest_path.exists())

            recovered, committed_path = prepare_case(root, "direct")
            with self.assertRaisesRegex(
                ValueError,
                "recovery_manifest_result_mismatch",
            ):
                acknowledge_recovery_manifest(recovered, committed_path)
            self.assertTrue(recovered.recovery_manifest_path.exists())

    def test_restart_ack_rejects_prepared_manifest_before_source_truncate(self) -> None:
        import qmt_roll_official_live_tick_recovery as recovery_module
        from qmt_roll_official_live_tick_stream import (
            acknowledge_committed_recovery_manifest,
            recover_or_isolate_dirty_tail,
        )

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-prepared-not-applied",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "prepared-not-applied.ndjson"
            original = (
                b'{"feed_session_id":"feed-prepared-not-applied",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-prepared-not-applied",'
                b'"ingress_sequence":2'
            )
            journal.write_bytes(original)
            real_manifest_write = recovery_module._atomic_write_recovery_manifest

            def crash_after_manifest_commit(
                manifest_path: Path,
                payload: object,
            ) -> None:
                real_manifest_write(manifest_path, payload)
                raise InjectedCrash("prepared but source not truncated")

            with patch.object(
                recovery_module,
                "_atomic_write_recovery_manifest",
                side_effect=crash_after_manifest_commit,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            manifest_path = recovery_module._recovery_manifest_path(journal)
            payload = json.loads(manifest_path.read_bytes())
            committed_path = root / "heartbeat.json"
            committed_path.write_text(
                json.dumps(
                    {
                        "journal_authority_committed": True,
                        "journal_session_state": "starting",
                        "stopped": False,
                        "clean_shutdown": False,
                        "stream_ready": False,
                        "transport_ready": False,
                        "prior_recovery_transaction_id": payload[
                            "transaction_id"
                        ],
                        "prior_recovery_manifest_path": str(
                            manifest_path.resolve()
                        ),
                        "prior_uncommitted_gaps": payload["result"][
                            "disclosed_gaps"
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "recovery_source_not_applied",
            ):
                acknowledge_committed_recovery_manifest(committed_path)
            self.assertEqual(journal.read_bytes(), original)
            self.assertTrue(manifest_path.exists())

    def test_ack_rejects_same_inode_same_size_heartbeat_mutation_during_barrier_and_preserves_manifest(
        self,
    ) -> None:
        import qmt_roll_official_live_tick_recovery as recovery_module
        from qmt_roll_official_live_tick_stream import (
            acknowledge_committed_recovery_manifest,
            recover_or_isolate_dirty_tail,
        )

        heartbeat = {
            "feed_session_id": "feed-heartbeat-byte-fence",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "heartbeat-byte-fence.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-heartbeat-byte-fence",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-heartbeat-byte-fence",'
                b'"ingress_sequence":2'
            )
            recovered = recover_or_isolate_dirty_tail(journal, heartbeat)
            committed_path = root / "heartbeat.json"
            committed_path.write_text(
                json.dumps(
                    {
                        "journal_authority_committed": True,
                        "journal_session_state": "starting",
                        "stopped": False,
                        "clean_shutdown": False,
                        "stream_ready": False,
                        "transport_ready": False,
                        "prior_recovery_transaction_id": (
                            recovered.recovery_transaction_id
                        ),
                        "prior_recovery_manifest_path": str(
                            recovered.recovery_manifest_path.resolve()
                        ),
                        "prior_uncommitted_gaps": [
                            {
                                "feed_session_id": gap.feed_session_id,
                                "start_ingress_sequence": (
                                    gap.start_ingress_sequence
                                ),
                                "end_ingress_sequence": (
                                    gap.end_ingress_sequence
                                ),
                                "reason": gap.reason,
                            }
                            for gap in recovered.disclosed_gaps
                        ],
                    },
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            heartbeat_inode = committed_path.stat().st_ino
            real_barrier = recovery_module.tick_journal._durability_barrier
            injected = False

            def mutate_same_inode_after_first_barrier(descriptor: int) -> None:
                nonlocal injected
                real_barrier(descriptor)
                if injected or os.fstat(descriptor).st_ino != heartbeat_inode:
                    return
                injected = True
                original = committed_path.read_bytes()
                transaction = recovered.recovery_transaction_id.encode()
                mutated = original.replace(transaction, b"0" * len(transaction))
                self.assertEqual(len(mutated), len(original))
                mutation_fd = os.open(str(committed_path), os.O_WRONLY)
                try:
                    written = os.write(mutation_fd, mutated)
                    self.assertEqual(written, len(mutated))
                    os.fsync(mutation_fd)
                finally:
                    os.close(mutation_fd)

            with patch.object(
                recovery_module.tick_journal,
                "_durability_barrier",
                side_effect=mutate_same_inode_after_first_barrier,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "recovery_heartbeat_changed_during_ack",
                ):
                    acknowledge_committed_recovery_manifest(committed_path)

            self.assertTrue(injected)
            self.assertTrue(recovered.recovery_manifest_path.exists())

    def test_recovery_manifest_accepts_monotonic_fault_revoke_of_prior_authority(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-recovery-revoked",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "running",
            "journal_authority_committed": True,
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 2,
            "stopped": False,
            "clean_shutdown": False,
            "stream_ready": True,
            "transport_ready": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "recovery-revoked.ndjson"
            trusted_prefix = (
                b'{"feed_session_id":"feed-recovery-revoked",'
                b'"ingress_sequence":1}\n'
            )
            journal.write_bytes(
                trusted_prefix
                + b'{"feed_session_id":"feed-recovery-revoked",'
                b'"ingress_sequence":2'
            )
            real_barrier = journal_module._durability_barrier

            def crash_after_source_barrier(descriptor: int) -> None:
                real_barrier(descriptor)
                if os.fstat(descriptor).st_size == len(trusted_prefix):
                    raise InjectedCrash("after source durability barrier")

            with patch.object(
                journal_module,
                "_durability_barrier",
                side_effect=crash_after_source_barrier,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            revoked = {
                **heartbeat,
                "journal_session_state": "fault_stopped",
                "stopped": True,
                "clean_shutdown": False,
                "stream_ready": False,
                "transport_ready": False,
                "writer_alive": False,
                "status": "stream_blocked_journal_recovery_error",
                "recovery_blocked": True,
            }
            replayed = recover_or_isolate_dirty_tail(journal, revoked)

            self.assertEqual(journal.read_bytes(), trusted_prefix)
            self.assertEqual(
                (
                    replayed.disclosed_gap.start_ingress_sequence,
                    replayed.disclosed_gap.end_ingress_sequence,
                ),
                (2, 2),
            )

    def test_existing_sidecar_is_redurable_before_manifest_and_truncate(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-sidecar-redurable",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "sidecar-redurable.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-sidecar-redurable",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-sidecar-redurable",'
                b'"ingress_sequence":2'
            )
            real_parent_fsync = journal_module._fsync_parent
            parent_calls = 0

            def crash_before_sidecar_parent_fsync(path: Path) -> None:
                nonlocal parent_calls
                parent_calls += 1
                if parent_calls == 1:
                    raise InjectedCrash("sidecar parent fsync not confirmed")
                real_parent_fsync(path)

            with patch.object(
                journal_module,
                "_fsync_parent",
                side_effect=crash_before_sidecar_parent_fsync,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            sidecar = next(root.glob("*.dirty.*"))
            sidecar_inode = sidecar.stat().st_ino
            barrier_inodes: list[int] = []
            fsynced_paths: list[Path] = []
            real_barrier = journal_module._durability_barrier

            def record_barrier(descriptor: int) -> None:
                barrier_inodes.append(os.fstat(descriptor).st_ino)
                real_barrier(descriptor)

            def record_parent_fsync(path: Path) -> None:
                fsynced_paths.append(Path(path).resolve())
                real_parent_fsync(path)

            with (
                patch.object(
                    journal_module,
                    "_durability_barrier",
                    side_effect=record_barrier,
                ),
                patch.object(
                    journal_module,
                    "_fsync_parent",
                    side_effect=record_parent_fsync,
                ),
            ):
                recovered = recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertIn(sidecar_inode, barrier_inodes)
            self.assertEqual(fsynced_paths[0], sidecar.resolve())
            self.assertEqual(fsynced_paths[1], recovered.recovery_manifest_path)

    def test_visible_manifest_is_redurable_before_replay_truncates_source(self) -> None:
        import qmt_roll_official_live_tick_journal as journal_module
        import qmt_roll_official_live_tick_recovery as recovery_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-manifest-redurable",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "manifest-redurable.ndjson"
            journal.write_bytes(
                b'{"feed_session_id":"feed-manifest-redurable",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-manifest-redurable",'
                b'"ingress_sequence":2'
            )
            real_parent_fsync = journal_module._fsync_parent
            parent_calls = 0

            def crash_before_manifest_parent_fsync(path: Path) -> None:
                nonlocal parent_calls
                parent_calls += 1
                if parent_calls == 2:
                    raise InjectedCrash("manifest parent fsync not confirmed")
                real_parent_fsync(path)

            with patch.object(
                journal_module,
                "_fsync_parent",
                side_effect=crash_before_manifest_parent_fsync,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            manifest = recovery_module._recovery_manifest_path(journal)
            sidecar = next(root.glob("*.dirty.*"))
            manifest_inode = manifest.stat().st_ino
            sidecar_inode = sidecar.stat().st_ino
            source_inode = journal.stat().st_ino
            barrier_inodes: list[int] = []
            fsynced_paths: list[Path] = []
            real_barrier = journal_module._durability_barrier

            def record_barrier(descriptor: int) -> None:
                barrier_inodes.append(os.fstat(descriptor).st_ino)
                real_barrier(descriptor)

            def record_parent_fsync(path: Path) -> None:
                fsynced_paths.append(Path(path).resolve())
                real_parent_fsync(path)

            with (
                patch.object(
                    journal_module,
                    "_durability_barrier",
                    side_effect=record_barrier,
                ),
                patch.object(
                    journal_module,
                    "_fsync_parent",
                    side_effect=record_parent_fsync,
                ),
            ):
                recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertLess(
                barrier_inodes.index(sidecar_inode),
                barrier_inodes.index(source_inode),
            )
            self.assertLess(
                barrier_inodes.index(manifest_inode),
                barrier_inodes.index(source_inode),
            )
            self.assertEqual(fsynced_paths[:2], [sidecar.resolve(), manifest.resolve()])

    def test_manifest_replay_rejects_same_inode_size_change_between_stat_and_open(self) -> None:
        import qmt_roll_official_live_tick_recovery as recovery_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-replay-open-race",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "replay-open-race.ndjson"
            original = (
                b'{"feed_session_id":"feed-replay-open-race",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-replay-open-race",'
                b'"ingress_sequence":2'
            )
            journal.write_bytes(original)
            real_manifest_write = recovery_module._atomic_write_recovery_manifest

            def crash_after_manifest_commit(
                manifest_path: Path,
                payload: object,
            ) -> None:
                real_manifest_write(manifest_path, payload)
                raise InjectedCrash("after recovery manifest commit")

            with patch.object(
                recovery_module,
                "_atomic_write_recovery_manifest",
                side_effect=crash_after_manifest_commit,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            real_open = os.open
            injected = False

            def append_between_stat_and_open(
                path: object,
                flags: int,
                mode: int = 0o777,
            ) -> int:
                nonlocal injected
                candidate = Path(path)
                if (
                    not injected
                    and candidate.resolve() == journal.resolve()
                    and flags & os.O_RDWR
                ):
                    injected = True
                    append_fd = real_open(
                        str(journal),
                        os.O_WRONLY | os.O_APPEND,
                    )
                    try:
                        os.write(append_fd, b"X")
                        os.fsync(append_fd)
                    finally:
                        os.close(append_fd)
                return real_open(path, flags, mode)

            with patch.object(
                recovery_module.os,
                "open",
                side_effect=append_between_stat_and_open,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "(size|changed).*replay",
                ):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertTrue(injected)
            self.assertEqual(journal.read_bytes(), original + b"X")
            self.assertTrue(
                recovery_module._recovery_manifest_path(journal).exists()
            )

    def test_recovery_manifest_never_truncates_replaced_source_inode(self) -> None:
        import qmt_roll_official_live_tick_recovery as recovery_module
        from qmt_roll_official_live_tick_stream import recover_or_isolate_dirty_tail

        class InjectedCrash(BaseException):
            pass

        heartbeat = {
            "feed_session_id": "feed-recovery-replaced",
            "journal_schema": "legacy_ndjson_v0",
            "journal_session_state": "clean_stopped",
            "durable_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "stopped": True,
            "clean_shutdown": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "recovery-replaced.ndjson"
            original = (
                b'{"feed_session_id":"feed-recovery-replaced",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-recovery-replaced",'
                b'"ingress_sequence":2'
            )
            journal.write_bytes(original)
            real_manifest_write = recovery_module._atomic_write_recovery_manifest

            def crash_after_manifest_commit(
                manifest_path: Path,
                payload: object,
            ) -> None:
                real_manifest_write(manifest_path, payload)
                raise InjectedCrash("after recovery manifest commit")

            with patch.object(
                recovery_module,
                "_atomic_write_recovery_manifest",
                side_effect=crash_after_manifest_commit,
            ):
                with self.assertRaises(InjectedCrash):
                    recover_or_isolate_dirty_tail(journal, heartbeat)

            replacement = root / "replacement.ndjson"
            replacement.write_bytes(original)
            os.replace(replacement, journal)
            with self.assertRaisesRegex(RuntimeError, "changed.*replay"):
                recover_or_isolate_dirty_tail(journal, heartbeat)

            self.assertEqual(journal.read_bytes(), original)
            self.assertTrue(
                recovery_module._recovery_manifest_path(journal).exists()
            )

    def test_stage608_acks_recovery_manifest_only_after_starting_heartbeat(self) -> None:
        from vnpy.trader.gateway import BaseGateway

        self_test = self

        class FakeCtpGateway(BaseGateway):
            default_name = "CTP"
            exchanges = []

            def connect(self, _setting: dict[str, object]) -> None:
                self.on_tick(self_test._ingress_tick())

            def subscribe(self, _request: object) -> None:
                return None

            def send_order(self, _request: object) -> str:
                raise AssertionError("read-only runner must not send")

            def cancel_order(self, _request: object) -> None:
                raise AssertionError("read-only runner must not cancel")

            def query_account(self) -> None:
                return None

            def query_position(self) -> None:
                return None

            def close(self) -> None:
                return None

        fake_vnpy_ctp = types.ModuleType("vnpy_ctp")
        fake_vnpy_ctp.CtpGateway = FakeCtpGateway
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat_path = root / "heartbeat.json"
            prior_journal = root / "prior.ndjson"
            prior_journal.write_bytes(
                b'{"feed_session_id":"feed-prior-ack",'
                b'"ingress_sequence":1}\n'
                b'{"feed_session_id":"feed-prior-ack",'
                b'"ingress_sequence":2'
            )
            heartbeat_path.write_text(
                json.dumps(
                    {
                        "feed_session_id": "feed-prior-ack",
                        "journal_segment_path": str(prior_journal),
                        "journal_schema": "legacy_ndjson_v0",
                        "journal_session_state": "clean_stopped",
                        "journal_authority_committed": True,
                        "durable_ingress_sequence": 1,
                        "last_ingress_sequence": 1,
                        "stopped": True,
                        "clean_shutdown": True,
                        "stream_ready": False,
                        "transport_ready": False,
                        "real_order_enabled": False,
                    }
                ),
                encoding="utf-8",
            )
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
                patch.object(
                    stage608,
                    "_analyze_logs",
                    return_value={
                        "md_login_success": True,
                        "td_login_success": True,
                    },
                ),
                patch.object(stage608, "TICK_PATH", root / "ticks.csv"),
                patch.object(stage608.MainEngine, "write_log", return_value=None),
                patch.object(stage608.os, "kill", side_effect=ProcessLookupError),
            ):
                result = stage608._run_stream(
                    connect=True,
                    pre_subscribe_wait_seconds=0,
                    target_symbols=["JM609.DCE"],
                    watch_manifest=None,
                    journal_path=root / "ticks.ndjson",
                    heartbeat_path=heartbeat_path,
                    duration_seconds=0,
                    heartbeat_seconds=0.2,
                    max_buffer_ticks=10,
                    parent_pid=999_999,
                )
            persisted = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            manifest_path = Path(result["prior_recovery_manifest_path"])
            manifest_exists_before_cleanup = manifest_path.exists()

        self.assertTrue(result["recovery_manifest_acknowledged"])
        self.assertTrue(result["prior_recovery_transaction_id"])
        self.assertFalse(manifest_exists_before_cleanup)
        self.assertEqual(
            persisted["prior_recovery_transaction_id"],
            result["prior_recovery_transaction_id"],
        )
        self.assertEqual(
            (
                persisted["prior_uncommitted_gap"][
                    "start_ingress_sequence"
                ],
                persisted["prior_uncommitted_gap"]["end_ingress_sequence"],
            ),
            (2, 2),
        )
        self.assertEqual(result["send_order_api_attempted_count"], 0)
        self.assertEqual(result["cancel_order_api_attempted_count"], 0)

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
                    "journal_schema": "stage179_framed_v1",
                    "journal_session_state": "recovery_required_stopped",
                    "durable_ingress_sequence": 1,
                    "last_ingress_sequence": 1,
                },
            )
            replay = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=recovered.previous_durable_cursor,
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
                    "journal_schema": "stage179_framed_v1",
                    "journal_session_state": "clean_stopped",
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
                    "journal_schema": "stage179_framed_v1",
                    "journal_session_state": "clean_stopped",
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
                    "journal_schema": "stage179_framed_v1",
                    "journal_session_state": "recovery_required_stopped",
                    "durable_ingress_sequence": 0,
                    "last_ingress_sequence": 1,
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
                    "journal_schema": "legacy_ndjson_v0",
                    "journal_session_state": "clean_stopped",
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

    def test_recovery_never_certifies_boolean_sequence_alias(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            JOURNAL_BATCH_COMMIT_RECORD_TYPE,
            JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            JOURNAL_HEADER_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            recover_or_isolate_dirty_tail,
        )

        feed = "feed-bool-journal"
        header = {
            JOURNAL_RECORD_TYPE_FIELD: JOURNAL_HEADER_RECORD_TYPE,
            "schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            "feed_session_id": feed,
            "segment_id": feed,
            "first_ingress_sequence": 1,
        }
        tick = {
            "feed_session_id": feed,
            "ingress_sequence": True,
        }
        tick_bytes = (
            json.dumps(
                tick,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        commit = {
            JOURNAL_RECORD_TYPE_FIELD: JOURNAL_BATCH_COMMIT_RECORD_TYPE,
            "schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            "feed_session_id": feed,
            "segment_id": feed,
            "previous_durable_ingress_sequence": 0,
            "first_ingress_sequence": 1,
            "last_ingress_sequence": 1,
            "row_count": 1,
            "payload_byte_count": len(tick_bytes),
            "payload_sha256": hashlib.sha256(tick_bytes).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "bool-sequence.ndjson"
            journal.write_bytes(
                (
                    json.dumps(
                        header,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
                + tick_bytes
                + (
                    json.dumps(
                        commit,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
            )
            recovered = recover_or_isolate_dirty_tail(
                journal,
                {
                    "feed_session_id": feed,
                    "journal_schema": "stage179_framed_v1",
                    "journal_session_state": "recovery_required_stopped",
                    "durable_ingress_sequence": 1,
                    "last_ingress_sequence": 1,
                },
            )

        self.assertIsNone(recovered.previous_durable_cursor)
        self.assertIsNotNone(recovered.disclosed_gap)
        self.assertIsNotNone(recovered.isolated_tail_path)

    def test_reader_and_recovery_reject_invalid_framed_row_identity(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            JOURNAL_BATCH_COMMIT_RECORD_TYPE,
            JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
            JOURNAL_HEADER_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            JOURNAL_SCHEMA_FRAMED_V1,
            TickStreamJournalReader,
            recover_or_isolate_dirty_tail,
        )

        feed = "feed-framed-identity"
        invalid_mutations = [
            (f"{field}:{type(alias).__name__}", {field: alias})
            for field in (
                "ingress_sequence",
                "stream_sequence",
                "symbol_sequence",
                "symbol_stream_sequence",
                "ingress_epoch_ns",
                "ingress_monotonic_ns",
            )
            for alias in (True, 1.0)
        ] + [
            ("stream_sequence:mismatch", {"stream_sequence": 2}),
            (
                "symbol_stream_sequence:mismatch",
                {"symbol_stream_sequence": 2},
            ),
        ]
        for mutation, updates in invalid_mutations:
            with self.subTest(mutation=mutation):
                    header = {
                        JOURNAL_RECORD_TYPE_FIELD: JOURNAL_HEADER_RECORD_TYPE,
                        "schema_version": JOURNAL_BATCH_COMMIT_SCHEMA_VERSION,
                        "feed_session_id": feed,
                        "segment_id": feed,
                        "first_ingress_sequence": 1,
                    }
                    tick = {
                        "feed_session_id": feed,
                        "ingress_sequence": 1,
                        "stream_sequence": 1,
                        "symbol_sequence": 1,
                        "symbol_stream_sequence": 1,
                        "ingress_epoch_ns": 1,
                        "ingress_monotonic_ns": 1,
                        "trace_id": f"stage179-tick/{feed}/1",
                    }
                    tick.update(updates)
                    tick_bytes = (
                        json.dumps(
                            tick,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                    commit = {
                        JOURNAL_RECORD_TYPE_FIELD: (
                            JOURNAL_BATCH_COMMIT_RECORD_TYPE
                        ),
                        "schema_version": (
                            JOURNAL_BATCH_COMMIT_SCHEMA_VERSION
                        ),
                        "feed_session_id": feed,
                        "segment_id": feed,
                        "previous_durable_ingress_sequence": 0,
                        "first_ingress_sequence": 1,
                        "last_ingress_sequence": 1,
                        "row_count": 1,
                        "payload_byte_count": len(tick_bytes),
                        "payload_sha256": hashlib.sha256(
                            tick_bytes
                        ).hexdigest(),
                    }
                    payload = (
                        (
                            json.dumps(
                                header,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                        + tick_bytes
                        + (
                            json.dumps(
                                commit,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                    )
                    with tempfile.TemporaryDirectory() as tmp:
                        journal = Path(tmp) / "identity.ndjson"
                        journal.write_bytes(payload)
                        durable = DurableTickCursor(
                            feed,
                            1,
                            journal_byte_offset=len(payload),
                            journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
                        )
                        batch = TickStreamJournalReader(journal).read_after(
                            None,
                            durable_through=durable,
                        )
                        recovered = recover_or_isolate_dirty_tail(
                            journal,
                            {
                                "feed_session_id": feed,
                                "journal_schema": JOURNAL_SCHEMA_FRAMED_V1,
                                "journal_session_state": (
                                    "recovery_required_stopped"
                                ),
                                "durable_ingress_sequence": 1,
                                "last_ingress_sequence": 1,
                            },
                        )

                    self.assertEqual(batch.records, ())
                    self.assertFalse(batch.caught_up)
                    self.assertIsNotNone(batch.gap)
                    self.assertIsNone(recovered.previous_durable_cursor)
                    self.assertIsNotNone(recovered.disclosed_gap)
                    self.assertIsNotNone(recovered.isolated_tail_path)

    def test_reader_rejects_cross_session_cursor_and_undurable_tail(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            JOURNAL_SCHEMA_LEGACY_V0,
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
            durable = DurableTickCursor(
                "feed-a",
                2,
                journal_schema=JOURNAL_SCHEMA_LEGACY_V0,
            )

            batch = reader.read_after(None, durable_through=durable)
            cross_session = reader.read_after(
                DurableTickCursor(
                    "feed-b",
                    1,
                    journal_schema=JOURNAL_SCHEMA_LEGACY_V0,
                ),
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
            JOURNAL_SCHEMA_LEGACY_V0,
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
                durable_through=DurableTickCursor(
                    "feed-gap",
                    4,
                    journal_schema=JOURNAL_SCHEMA_LEGACY_V0,
                ),
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
            JOURNAL_SCHEMA_FRAMED_V1,
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
                durable_through=DurableTickCursor(
                    "feed-missing-marker",
                    1,
                    journal_byte_offset=journal.stat().st_size,
                    journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
                ),
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

    def test_reader_defaults_to_framed_and_requires_explicit_legacy_schema(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            JOURNAL_SCHEMA_LEGACY_V0,
            TickStreamJournalReader,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "tick-only.ndjson"
            journal.write_text(
                json.dumps(
                    {
                        "feed_session_id": "feed-explicit-legacy",
                        "ingress_sequence": 1,
                    },
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            reader = TickStreamJournalReader(journal)
            default_framed = reader.read_after(
                None,
                durable_through=DurableTickCursor(
                    "feed-explicit-legacy",
                    1,
                    journal_byte_offset=journal.stat().st_size,
                ),
            )
            explicit_legacy = reader.read_after(
                None,
                durable_through=DurableTickCursor(
                    "feed-explicit-legacy",
                    1,
                    journal_byte_offset=journal.stat().st_size,
                    journal_schema=JOURNAL_SCHEMA_LEGACY_V0,
                ),
            )

        self.assertEqual(default_framed.records, ())
        self.assertIsNotNone(default_framed.gap)
        self.assertEqual(
            [row["ingress_sequence"] for row in explicit_legacy.records],
            [1],
        )
        self.assertTrue(explicit_legacy.caught_up)

    def test_framed_reader_resume_requires_reachable_header_ancestry(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
            TickStreamPipeline,
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
            journal = Path(tmp) / "incremental.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-incremental",
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
            snapshot = pipeline.durable_snapshot()
            durable = DurableTickCursor(
                snapshot.feed_session_id,
                snapshot.durable_ingress_sequence,
                journal_byte_offset=snapshot.durable_journal_byte_offset,
                journal_schema=snapshot.journal_schema,
            )
            reader = TickStreamJournalReader(journal)
            first = reader.read_after(None, durable_through=durable, limit=2)
            with journal.open("r+b") as handle:
                handle.write(b"!")
                handle.flush()
                os.fsync(handle.fileno())
            second = reader.read_after(
                first.next_cursor,
                durable_through=durable,
                limit=2,
            )

        self.assertEqual(
            [row["ingress_sequence"] for row in first.records],
            [1, 2],
        )
        self.assertFalse(first.caught_up)
        self.assertEqual(second.records, ())
        self.assertFalse(second.caught_up)
        self.assertIsNotNone(second.gap)
        self.assertIn("journal_", second.gap.reason)

    def test_framed_reader_limit_never_splits_committed_batches(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
            TickStreamPipeline,
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
            journal = Path(tmp) / "atomic-limit.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-atomic-limit",
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
            snapshot = pipeline.durable_snapshot()
            durable = DurableTickCursor(
                snapshot.feed_session_id,
                snapshot.durable_ingress_sequence,
                journal_byte_offset=snapshot.durable_journal_byte_offset,
                journal_schema=snapshot.journal_schema,
            )
            reader = TickStreamJournalReader(journal)
            first = reader.read_after(None, durable_through=durable, limit=3)
            second = reader.read_after(
                first.next_cursor,
                durable_through=durable,
                limit=3,
            )

        self.assertEqual(
            [row["ingress_sequence"] for row in first.records],
            [1, 2],
        )
        self.assertFalse(first.caught_up)
        self.assertEqual(
            [row["ingress_sequence"] for row in second.records],
            [3, 4],
        )
        self.assertTrue(second.caught_up)

    def test_framed_reader_returns_first_whole_batch_when_it_exceeds_limit(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
            TickStreamPipeline,
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
            journal = Path(tmp) / "oversized-first-batch.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-oversized-first",
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
            self.assertTrue(pipeline.shutdown(timeout_seconds=2.0).drained)
            snapshot = pipeline.durable_snapshot()
            durable = DurableTickCursor(
                snapshot.feed_session_id,
                snapshot.durable_ingress_sequence,
                journal_byte_offset=snapshot.durable_journal_byte_offset,
                journal_schema=snapshot.journal_schema,
            )
            batch = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=durable,
                limit=2,
            )

        self.assertEqual(
            [row["ingress_sequence"] for row in batch.records],
            [1, 2, 3],
        )
        self.assertTrue(batch.caught_up)

    def test_reader_and_recovery_never_use_path_read_bytes(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            TickStreamJournalReader,
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
            journal = Path(tmp) / "streaming-only.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-streaming-only",
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
            with patch.object(
                Path,
                "read_bytes",
                side_effect=AssertionError("unbounded read_bytes forbidden"),
            ):
                recovered = recover_or_isolate_dirty_tail(
                    journal,
                    {
                        "feed_session_id": "feed-streaming-only",
                        "journal_schema": "stage179_framed_v1",
                        "journal_session_state": "clean_stopped",
                        "durable_ingress_sequence": 1,
                        "last_ingress_sequence": 1,
                    },
                )
                replay = TickStreamJournalReader(journal).read_after(
                    None,
                    durable_through=recovered.previous_durable_cursor,
                )

        self.assertEqual(
            [row["ingress_sequence"] for row in replay.records],
            [1],
        )
        self.assertTrue(replay.caught_up)

    def test_reader_validates_schema_and_offsets_before_caught_up_fast_paths(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
        )

        with tempfile.TemporaryDirectory() as tmp:
            reader = TickStreamJournalReader(Path(tmp) / "missing.ndjson")
            framed_missing_offset = DurableTickCursor(
                "feed-fast-path",
                1,
                journal_byte_offset=0,
                journal_schema="stage179_framed_v1",
            )
            equal_framed = reader.read_after(
                framed_missing_offset,
                durable_through=framed_missing_offset,
            )
            unknown_equal_cursor = DurableTickCursor(
                "feed-fast-path",
                1,
                journal_byte_offset=123,
                journal_schema="unknown-v99",
            )
            equal_unknown = reader.read_after(
                unknown_equal_cursor,
                durable_through=unknown_equal_cursor,
            )
            zero_unknown = reader.read_after(
                None,
                durable_through=DurableTickCursor(
                    "feed-fast-path",
                    0,
                    journal_byte_offset=0,
                    journal_schema="unknown-v99",
                ),
            )

        self.assertEqual(
            equal_framed.gap.reason,
            "framed_durable_cursor_offset_missing",
        )
        self.assertEqual(
            equal_unknown.gap.reason,
            "journal_schema_missing_or_unsupported",
        )
        self.assertEqual(
            zero_unknown.gap.reason,
            "journal_schema_missing_or_unsupported",
        )

    def test_reader_rejects_noncanonical_cursor_numeric_and_feed_fields(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "legacy.ndjson"
            row = {"feed_session_id": "feed-reader-fields", "ingress_sequence": 1}
            journal.write_text(
                json.dumps(row, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            size = journal.stat().st_size
            reader = TickStreamJournalReader(journal)
            valid_durable = DurableTickCursor(
                "feed-reader-fields",
                1,
                journal_byte_offset=size,
                journal_schema="legacy_ndjson_v0",
            )
            for bad_value in (-1, 1.5, "1", True):
                with self.subTest(durable_sequence=bad_value):
                    result = reader.read_after(
                        None,
                        durable_through=DurableTickCursor(
                            "feed-reader-fields",
                            bad_value,
                            journal_byte_offset=size,
                            journal_schema="legacy_ndjson_v0",
                        ),
                    )
                    self.assertEqual(
                        result.gap.reason,
                        "durable_cursor_numeric_fields_invalid",
                    )
                with self.subTest(cursor_offset=bad_value):
                    result = reader.read_after(
                        DurableTickCursor(
                            "feed-reader-fields",
                            0,
                            journal_byte_offset=bad_value,
                            journal_schema="legacy_ndjson_v0",
                        ),
                        durable_through=valid_durable,
                    )
                    self.assertEqual(result.gap.reason, "cursor_fields_invalid")

            empty_feed = reader.read_after(
                None,
                durable_through=DurableTickCursor(
                    "",
                    1,
                    journal_byte_offset=size,
                    journal_schema="legacy_ndjson_v0",
                ),
            )
            framed_zero_with_offset = reader.read_after(
                None,
                durable_through=DurableTickCursor(
                    "feed-reader-fields",
                    0,
                    journal_byte_offset=1,
                    journal_schema="stage179_framed_v1",
                ),
            )

        self.assertEqual(
            empty_feed.gap.reason,
            "durable_feed_session_id_missing",
        )
        self.assertEqual(
            framed_zero_with_offset.gap.reason,
            "framed_zero_sequence_offset_nonzero",
        )

    def test_reader_stops_at_full_page_before_parsing_next_batch(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
            TickStreamPipeline,
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
            journal = Path(tmp) / "page-boundary.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-page-boundary",
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
            self.assertTrue(pipeline.shutdown(timeout_seconds=1.0).drained)
            snapshot = pipeline.durable_snapshot()
            payload = journal.read_bytes()
            corrupted = payload.replace(
                b'"last_price":3.0',
                b'"last_price":9.0',
                1,
            )
            self.assertNotEqual(corrupted, payload)
            journal.write_bytes(corrupted)
            result = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=DurableTickCursor(
                    snapshot.feed_session_id,
                    snapshot.durable_ingress_sequence,
                    journal_byte_offset=snapshot.durable_journal_byte_offset,
                    journal_schema=snapshot.journal_schema,
                ),
                limit=2,
            )

        self.assertEqual(
            [row["ingress_sequence"] for row in result.records],
            [1, 2],
        )
        self.assertIsNone(result.gap)
        self.assertFalse(result.caught_up)

    def test_reader_page_bytes_are_bounded_and_limit_requires_exact_int(self) -> None:
        import qmt_roll_official_live_tick_reader as reader_module
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
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
            journal = Path(tmp) / "bounded-page.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-bounded-page",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=3,
                max_buffer_ticks=3,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            for sequence in range(1, 4):
                pipeline.capture_ingress(self._ingress_tick(float(sequence)))
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=1.0).drained)
            snapshot = pipeline.durable_snapshot()
            durable = DurableTickCursor(
                snapshot.feed_session_id,
                snapshot.durable_ingress_sequence,
                journal_byte_offset=snapshot.durable_journal_byte_offset,
                journal_schema=snapshot.journal_schema,
            )
            reader = TickStreamJournalReader(journal)
            with patch.object(reader_module, "MAX_JOURNAL_PAGE_BYTES", 1):
                page = reader.read_after(None, durable_through=durable, limit=1024)
            for invalid_limit in (True, 1.5, float("nan")):
                with self.subTest(limit=invalid_limit):
                    with self.assertRaisesRegex(ValueError, "exact positive integer"):
                        reader.read_after(
                            None,
                            durable_through=durable,
                            limit=invalid_limit,
                        )

        self.assertEqual(
            [row["ingress_sequence"] for row in page.records],
            [1],
        )
        self.assertFalse(page.caught_up)
        self.assertIsNone(page.gap)

    def test_framed_reader_never_parses_beyond_durable_byte_boundary(self) -> None:
        import qmt_roll_official_live_tick_reader as reader_module
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
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
            journal = Path(tmp) / "hard-boundary.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-hard-boundary",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=1,
                max_buffer_ticks=1,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick())
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=1.0).drained)
            real_parse = reader_module._parse_record_line
            with patch.object(
                reader_module,
                "_parse_record_line",
                wraps=real_parse,
            ) as parse_record:
                result = TickStreamJournalReader(journal).read_after(
                    None,
                    durable_through=DurableTickCursor(
                        "feed-hard-boundary",
                        1,
                        journal_byte_offset=1,
                        journal_schema="stage179_framed_v1",
                    ),
                )

        self.assertEqual(
            result.gap.reason,
            "journal_record_crosses_durable_offset",
        )
        self.assertEqual(parse_record.call_count, 0)

    def test_framed_reader_rejects_sequence_only_or_mid_record_cursor(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            JOURNAL_SCHEMA_FRAMED_V1,
            TickStreamJournalReader,
            TickStreamPipeline,
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
            journal = Path(tmp) / "bad-cursor.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-bad-cursor",
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
            snapshot = pipeline.durable_snapshot()
            durable = DurableTickCursor(
                snapshot.feed_session_id,
                snapshot.durable_ingress_sequence,
                journal_byte_offset=snapshot.durable_journal_byte_offset,
                journal_schema=snapshot.journal_schema,
            )
            reader = TickStreamJournalReader(journal)
            first = reader.read_after(None, durable_through=durable, limit=2)
            sequence_only = reader.read_after(
                DurableTickCursor(
                    "feed-bad-cursor",
                    2,
                    journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
                ),
                durable_through=durable,
            )
            mid_record = reader.read_after(
                DurableTickCursor(
                    "feed-bad-cursor",
                    2,
                    journal_byte_offset=first.next_cursor.journal_byte_offset - 1,
                    journal_schema=JOURNAL_SCHEMA_FRAMED_V1,
                ),
                durable_through=durable,
            )

        self.assertEqual(sequence_only.gap.reason, "framed_cursor_offset_missing")
        self.assertEqual(mid_record.gap.reason, "cursor_offset_not_record_boundary")

    def test_equal_watermark_cursor_must_point_to_matching_commit_record(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
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
            journal = Path(tmp) / "equal-forged-cursor.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-equal-forged",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=2,
                max_buffer_ticks=2,
                writer_batch_size=2,
                writer_flush_seconds=0.001,
            )
            pipeline.capture_ingress(self._ingress_tick(1.0))
            pipeline.capture_ingress(self._ingress_tick(2.0))
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=1.0).drained)
            lines = journal.read_bytes().splitlines(keepends=True)
            tick_line_end = len(lines[0]) + len(lines[1])
            forged = DurableTickCursor(
                "feed-equal-forged",
                2,
                journal_byte_offset=tick_line_end,
                journal_schema="stage179_framed_v1",
            )
            result = TickStreamJournalReader(journal).read_after(
                forged,
                durable_through=forged,
            )

        self.assertFalse(result.caught_up)
        self.assertEqual(
            result.gap.reason,
            "cursor_offset_not_matching_commit_record",
        )

    def test_reader_rejects_cursor_whose_certifying_batch_hash_is_corrupt(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            JOURNAL_BATCH_COMMIT_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            TickStreamJournalReader,
            TickStreamPipeline,
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
            journal = Path(tmp) / "cursor-corrupt-batch.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-cursor-corrupt",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=2,
                max_buffer_ticks=2,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            for sequence in (1, 2):
                pipeline.capture_ingress(self._ingress_tick(float(sequence)))
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=1.0).drained)
            snapshot = pipeline.durable_snapshot()
            durable = DurableTickCursor(
                snapshot.feed_session_id,
                snapshot.durable_ingress_sequence,
                journal_byte_offset=snapshot.durable_journal_byte_offset,
                journal_schema=snapshot.journal_schema,
            )
            reader = TickStreamJournalReader(journal)
            first = reader.read_after(None, durable_through=durable, limit=1)
            self.assertIsNotNone(first.next_cursor)

            lines = journal.read_bytes().splitlines(keepends=True)
            for index, raw_line in enumerate(lines):
                row = json.loads(raw_line)
                if (
                    row.get(JOURNAL_RECORD_TYPE_FIELD)
                    == JOURNAL_BATCH_COMMIT_RECORD_TYPE
                ):
                    row["payload_sha256"] = "0" * 64
                    replacement = (
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                    self.assertEqual(len(replacement), len(raw_line))
                    lines[index] = replacement
                    break
            journal.write_bytes(b"".join(lines))

            resumed = reader.read_after(
                first.next_cursor,
                durable_through=durable,
            )

        self.assertEqual(resumed.records, ())
        self.assertFalse(resumed.caught_up)
        self.assertIsNotNone(resumed.gap)
        self.assertIn("commit", resumed.gap.reason)

    def test_reader_rejects_locally_valid_cursor_not_reachable_from_header(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            JOURNAL_BATCH_COMMIT_RECORD_TYPE,
            JOURNAL_HEADER_RECORD_TYPE,
            JOURNAL_RECORD_TYPE_FIELD,
            TickStreamJournalReader,
            TickStreamPipeline,
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
            journal = Path(tmp) / "cursor-orphan-prefix.ndjson"
            pipeline = TickStreamPipeline(
                feed_session_id="feed-cursor-orphan",
                journal_segment_path=journal,
                clock=FakeClock(),
                queue_capacity=6,
                max_buffer_ticks=6,
                writer_batch_size=1,
                writer_flush_seconds=0.001,
            )
            for sequence in range(1, 7):
                pipeline.capture_ingress(self._ingress_tick(float(sequence)))
            pipeline.start()
            self.assertTrue(pipeline.shutdown(timeout_seconds=1.0).drained)

            kept: list[bytes] = []
            cursor_offset = 0
            for raw_line in journal.read_bytes().splitlines(keepends=True):
                row = json.loads(raw_line)
                record_type = row.get(JOURNAL_RECORD_TYPE_FIELD)
                sequence = row.get("ingress_sequence")
                last_sequence = row.get("last_ingress_sequence")
                if record_type == JOURNAL_HEADER_RECORD_TYPE or (
                    record_type == JOURNAL_BATCH_COMMIT_RECORD_TYPE
                    and last_sequence in {5, 6}
                ) or (not record_type and sequence in {5, 6}):
                    kept.append(raw_line)
                    if last_sequence == 5:
                        cursor_offset = sum(len(item) for item in kept)
            journal.write_bytes(b"".join(kept))
            cursor = DurableTickCursor(
                "feed-cursor-orphan",
                5,
                journal_byte_offset=cursor_offset,
                journal_schema="stage179_framed_v1",
            )
            durable = DurableTickCursor(
                "feed-cursor-orphan",
                6,
                journal_byte_offset=journal.stat().st_size,
                journal_schema="stage179_framed_v1",
            )
            resumed = TickStreamJournalReader(journal).read_after(
                cursor,
                durable_through=durable,
            )

        self.assertEqual(resumed.records, ())
        self.assertFalse(resumed.caught_up)
        self.assertIsNotNone(resumed.gap)
        self.assertIn(resumed.gap.reason, {"journal_sequence_gap", "cursor_not_reachable"})

    def test_legacy_durable_offset_must_end_at_its_declared_sequence(self) -> None:
        from qmt_roll_official_live_tick_stream import (
            DurableTickCursor,
            TickStreamJournalReader,
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "legacy-offset.ndjson"
            rows = [
                {
                    "feed_session_id": "feed-legacy-offset",
                    "ingress_sequence": sequence,
                }
                for sequence in (1, 2)
            ]
            journal.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            forged = DurableTickCursor(
                "feed-legacy-offset",
                1,
                journal_byte_offset=journal.stat().st_size,
                journal_schema="legacy_ndjson_v0",
            )
            result = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=forged,
            )
            zero_with_offset = TickStreamJournalReader(journal).read_after(
                None,
                durable_through=DurableTickCursor(
                    "feed-legacy-offset",
                    0,
                    journal_byte_offset=1,
                    journal_schema="legacy_ndjson_v0",
                ),
            )

        self.assertFalse(result.caught_up)
        self.assertEqual(
            result.gap.reason,
            "durable_offset_not_sequence_boundary",
        )
        self.assertFalse(zero_with_offset.caught_up)
        self.assertEqual(
            zero_with_offset.gap.reason,
            "legacy_zero_sequence_offset_nonzero",
        )


if __name__ == "__main__":
    unittest.main()
