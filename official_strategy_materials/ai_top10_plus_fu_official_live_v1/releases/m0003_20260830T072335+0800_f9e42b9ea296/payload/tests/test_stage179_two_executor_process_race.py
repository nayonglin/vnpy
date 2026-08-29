from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_official_live_execution_ledger as ledger  # noqa: E402
from qmt_roll_official_live_execution_service import (  # noqa: E402
    ExecutionResult,
    ExecutorAlreadyRunningError,
    ExecutorServicePaths,
    SQLiteIntentSpool,
    TdReadinessLease,
    serve_executor,
)
import qmt_roll_official_live_intent_spool as spool  # noqa: E402
from qmt_roll_official_live_runtime_profile import (  # noqa: E402
    ExecutionRuntimeProfile,
    OrderScope,
    resolve_runtime_profile,
)
from qmt_roll_official_live_tick_types import DurableTickCursor  # noqa: E402
from qmt_roll_official_live_time import utc_iso_from_epoch_ns  # noqa: E402
from qmt_roll_official_live_trace import ClockStamp, LatencyTrace  # noqa: E402


def _evidence_root() -> Path | None:
    raw = os.environ.get("STAGE179_FAULT_EVIDENCE_DIR", "").strip()
    if not raw:
        return None
    root = Path(raw).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


class _IngressClock:
    def __init__(self, epoch_ns: int, monotonic_ns: int, domain: str) -> None:
        self._epoch_ns = epoch_ns
        self._monotonic_ns = monotonic_ns
        self._domain = domain

    def epoch_ns(self) -> int:
        return self._epoch_ns

    def monotonic_ns(self) -> int:
        return self._monotonic_ns

    def clock_domain_id(self) -> str:
        return self._domain


def _insert_intent(connection: Any, *, sequence: int) -> str:
    now_epoch_ns = time.time_ns()
    now_monotonic_ns = time.monotonic_ns()
    clock_domain_id = "stage179-process-race"
    trace = LatencyTrace.from_ingress_row(
        {
            "feed_session_id": "stage179-process-race-feed",
            "ingress_sequence": sequence,
            "symbol_sequence": sequence,
            "ingress_epoch_ns": now_epoch_ns,
            "ingress_monotonic_ns": now_monotonic_ns,
            "clock_domain_id": clock_domain_id,
            "received_at_utc": utc_iso_from_epoch_ns(now_epoch_ns),
            "trace_id": f"stage179-tick/stage179-process-race-feed/{sequence}",
            "vt_symbol": "JM609.DCE",
        },
        clock=_IngressClock(now_epoch_ns, now_monotonic_ns, clock_domain_id),
    )
    trace = trace.record_stamp(
        "stage904_detected",
        ClockStamp(
            epoch_ns=now_epoch_ns + 1,
            monotonic_ns=now_monotonic_ns + 1,
            clock_domain_id=clock_domain_id,
            utc_iso=utc_iso_from_epoch_ns(now_epoch_ns + 1),
        ),
    ).record_stamp(
        "stage905_intent_ready",
        ClockStamp(
            epoch_ns=now_epoch_ns + 2,
            monotonic_ns=now_monotonic_ns + 2,
            clock_domain_id=clock_domain_id,
            utc_iso=utc_iso_from_epoch_ns(now_epoch_ns + 2),
        ),
    )
    intent_id = f"stage179-process-race-{sequence:03d}"
    payload = {
        "intent_id": intent_id,
        "trace_id": trace.trace_id,
        "target_date": "2026-07-18",
        "source": "stage904_c9_intraday_retry_open",
        "offset": "open",
        "executor_status": "dry_run_order_request_payload_ready",
        "deadline_epoch_ns": trace.deadline_epoch_ns,
        "deadline_monotonic_ns": trace.deadline_monotonic_ns,
        "state_generation": f"epoch-{sequence}:1",
        "position_epoch_id": f"epoch-{sequence}",
        "vt_symbol": "JM609.DCE",
        "planned_volume": 1,
        "limit_price": 1245.5,
        "source_feed_session_id": trace.feed_session_id,
        "source_ingress_sequence": sequence,
        "source_symbol_sequence": sequence,
        "durable_cursor_feed_session_id": trace.feed_session_id,
        "durable_cursor_ingress_sequence": sequence,
        "durable_cursor_journal_byte_offset": sequence * 100,
        "durable_cursor_journal_schema": "stage179_framed_v1",
    }
    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    cursor = DurableTickCursor(
        feed_session_id=trace.feed_session_id,
        ingress_sequence=sequence,
        journal_byte_offset=sequence * 100,
    )
    previous = spool.read_detector_cursor(connection, consumer_id="stage179-race")
    spool.commit_detector_batch(
        connection,
        consumer_id="stage179-race",
        expected_cursor=previous,
        next_cursor=cursor,
        intents=[
            {
                **payload,
                "trace_json": trace.to_json(),
                "spool_payload_json": payload_json,
                "payload_sha256": hashlib.sha256(
                    payload_json.encode("utf-8")
                ).hexdigest(),
            }
        ],
        now_epoch_ns=now_epoch_ns + 3,
        now_monotonic_ns=now_monotonic_ns + 3,
        clock_domain_id=clock_domain_id,
    )
    spool.record_trace_observation(
        connection,
        intent_id=intent_id,
        stage="spool_committed",
        epoch_ns=now_epoch_ns + 4,
        monotonic_ns=now_monotonic_ns + 4,
        clock_domain_id=clock_domain_id,
    )
    return intent_id


class _ProcessFakeSession:
    def __init__(
        self,
        *,
        runtime: Any,
        ledger_path: Path,
        physical_send_log: Path,
    ) -> None:
        self.runtime = runtime
        self.ledger_path = ledger_path
        self.physical_send_log = physical_send_log
        self.service_generation = f"service-{os.getpid()}-{uuid.uuid4().hex}"
        self.connection_generation = ""
        self.send_count = 0

    def connect(self) -> None:
        self.connection_generation = uuid.uuid4().hex

    def readiness_lease(self, *, now_epoch_ns: int) -> TdReadinessLease:
        return TdReadinessLease(
            service_generation=self.service_generation,
            connection_generation=self.connection_generation,
            runtime_profile=self.runtime.profile.value,
            official_version="stage179-process-race",
            capital=200_000.0,
            issued_epoch_ns=now_epoch_ns,
            expires_epoch_ns=now_epoch_ns + 5_000_000_000,
            last_complete_startup_bundle_epoch_ns=now_epoch_ns,
        )

    def transport_blockers(self) -> list[str]:
        return []

    def pre_lease_blockers(self) -> list[str]:
        return []

    def reconnect(self) -> None:
        self.connect()

    def execute_spool_lease(
        self,
        *,
        lease: Any,
        hard_deadline_monotonic: float,
        api_slot_durable: Any = None,
    ) -> ExecutionResult:
        if time.monotonic() >= hard_deadline_monotonic:
            return ExecutionResult.blocked(
                lease.intent.intent_id,
                "stage179_process_race_deadline",
            )
        reservation = ledger.reserve_execution_api_slots(
            target_date=lease.intent.target_date,
            slot_type="send_order",
            daily_limit=100,
            base_events=[
                {
                    "intent_id": lease.intent.intent_id,
                    "intent_fingerprint": lease.intent.intent_id,
                    "adapter": "Stage179ProcessFakeAdapter",
                }
            ],
            path=self.ledger_path,
        )
        if not reservation.get("reserved"):
            return ExecutionResult.blocked(
                lease.intent.intent_id,
                str(reservation.get("blocker", "api_slot_blocked")),
            )
        batch_id = str(reservation.get("api_slot_batch_id", ""))
        if api_slot_durable is None or not api_slot_durable(batch_id):
            return ExecutionResult(
                intent_id=lease.intent.intent_id,
                disposition="side_effect_unknown",
                ledger_fingerprint=lease.intent.intent_id,
                api_slot_batch_id=batch_id,
                blockers=("stage179_process_race_spool_cas_lost",),
                send_order_call_count=0,
                cancel_order_call_count=0,
            )
        time.sleep(0.02)
        descriptor = os.open(
            self.physical_send_log,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(
                descriptor,
                (
                    json.dumps(
                        {
                            "intent_id": lease.intent.intent_id,
                            "pid": os.getpid(),
                            "api_slot_batch_id": batch_id,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8"),
            )
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.send_count += 1
        return ExecutionResult(
            intent_id=lease.intent.intent_id,
            disposition="sent",
            ledger_fingerprint=lease.intent.intent_id,
            api_slot_batch_id=batch_id,
            blockers=(),
            send_order_call_count=1,
            cancel_order_call_count=0,
        )

    def close(self) -> None:
        self.connection_generation = ""


def _executor_worker(
    *,
    spool_path: str,
    ledger_path: str,
    runtime_root: str,
    physical_send_log: str,
    barrier: Any,
    result_queue: Any,
) -> None:
    runtime = resolve_runtime_profile(
        profile=ExecutionRuntimeProfile.SIMNOW,
        order_scope=OrderScope.TEST,
        repo_root=ROOT,
        output_root=Path(runtime_root),
    )
    paths = ExecutorServicePaths.for_spool(
        spool_path=spool_path,
        ledger_path=ledger_path,
        readiness_path=runtime.readiness_path,
    )
    connection = spool.open_spool(spool_path)
    session = _ProcessFakeSession(
        runtime=runtime,
        ledger_path=Path(ledger_path),
        physical_send_log=Path(physical_send_log),
    )
    deadline = time.monotonic() + 0.4
    barrier.wait(timeout=10)
    status = "completed"
    try:
        serve_executor(
            paths=paths,
            spool=SQLiteIntentSpool(connection, ledger_path=ledger_path),
            backend_factory=lambda: session,
            runtime=runtime,
            stop_requested=lambda: session.send_count >= 1
            or time.monotonic() >= deadline,
            poll_seconds=0.01,
            clock_domain_id="stage179-process-race",
        )
    except ExecutorAlreadyRunningError:
        status = "singleton_rejected"
    finally:
        connection.close()
    result_queue.put(
        {
            "pid": os.getpid(),
            "status": status,
            "physical_fake_send_calls": session.send_count,
        }
    )


class Stage179TwoExecutorProcessRaceTest(unittest.TestCase):
    def test_one_hundred_real_executor_process_races_send_each_intent_once(self) -> None:
        context = multiprocessing.get_context("fork")
        rounds: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spool_path = root / "shared-spool.sqlite3"
            ledger_path = root / "shared-ledger.ndjson"
            physical_send_log = root / "physical-fake-send.ndjson"
            runtime_root = root / "runtime"
            parent_connection = spool.open_spool(spool_path)
            try:
                for index in range(1, 101):
                    intent_id = _insert_intent(parent_connection, sequence=index)
                    barrier = context.Barrier(2)
                    result_queue = context.Queue()
                    workers = [
                        context.Process(
                            target=_executor_worker,
                            kwargs={
                                "spool_path": str(spool_path),
                                "ledger_path": str(ledger_path),
                                "runtime_root": str(runtime_root),
                                "physical_send_log": str(physical_send_log),
                                "barrier": barrier,
                                "result_queue": result_queue,
                            },
                        )
                        for _ in range(2)
                    ]
                    for worker in workers:
                        worker.start()
                    for worker in workers:
                        worker.join(timeout=10)
                        self.assertEqual(0, worker.exitcode)
                    results = [result_queue.get(timeout=2) for _ in workers]
                    result_queue.close()
                    result_queue.join_thread()
                    rows = [
                        json.loads(line)
                        for line in physical_send_log.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if line.strip()
                    ]
                    sends_for_intent = [
                        row for row in rows if row.get("intent_id") == intent_id
                    ]
                    state = parent_connection.execute(
                        "SELECT state FROM intents WHERE intent_id = ?",
                        (intent_id,),
                    ).fetchone()[0]
                    self.assertEqual(1, len(sends_for_intent))
                    self.assertEqual(1, sum(row["physical_fake_send_calls"] for row in results))
                    self.assertEqual("sent", state)
                    rounds.append(
                        {
                            "round": index,
                            "intent_id": intent_id,
                            "worker_results": results,
                            "physical_fake_send_calls": len(sends_for_intent),
                            "spool_final_state": state,
                        }
                    )
            finally:
                parent_connection.close()

            send_rows = [
                json.loads(line)
                for line in physical_send_log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            ledger_counts = ledger.ledger_order_api_counts(
                ledger.read_execution_ledger(ledger_path),
                "2026-07-18",
            )

        payload = {
            "status": "passed",
            "round_count": len(rounds),
            "executor_processes_per_round": 2,
            "physical_fake_send_call_count": len(send_rows),
            "unique_physical_fake_send_intent_count": len(
                {row["intent_id"] for row in send_rows}
            ),
            "ledger_send_slot_usage": ledger_counts["send_order_slot_usage"],
            "real_send_order_api_called_count": 0,
            "real_cancel_order_api_called_count": 0,
            "rounds": rounds,
        }
        evidence_root = _evidence_root()
        if evidence_root is not None:
            (evidence_root / "stage179_two_executor_process_races.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        self.assertEqual(100, len(rounds))
        self.assertEqual(100, len(send_rows))
        self.assertEqual(100, ledger_counts["send_order_slot_usage"])


if __name__ == "__main__":
    unittest.main()
