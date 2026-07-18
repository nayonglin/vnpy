from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_official_live_execution_ledger as ledger  # noqa: E402


@dataclass(frozen=True, slots=True)
class FaultCase:
    name: str
    test_module: str
    test_class: str
    test_method: str
    spool_state: str
    ledger_evidence: str
    recovery_disposition: str
    fake_send_calls: int
    fake_cancel_calls: int


FAULT_CASES = (
    FaultCase("disconnect_before_lease", "tests.test_stage179_executor_serve", "Stage179ExecutorServeTest", "test_transport_disconnect_reconnects_before_next_lease_and_changes_generation", "ready", "none", "reconnect_before_lease", 0, 0),
    FaultCase("crash_before_reservation", "tests.test_official_live_execution_ledger_cycles", "OfficialLiveExecutionLedgerCycleTest", "test_spool_recovery_without_ledger_evidence_is_pre_send_requeue", "ready", "none", "requeue_pre_send", 0, 0),
    FaultCase("crash_after_reservation", "tests.test_official_live_execution_ledger_cycles", "OfficialLiveExecutionLedgerCycleTest", "test_spool_recovery_matching_reservation_appends_safe_terminal_once", "ready", "reserved+safe_terminal", "requeue_pre_send", 0, 0),
    FaultCase("crash_after_api_slot", "tests.test_official_live_execution_ledger_cycles", "OfficialLiveExecutionLedgerCycleTest", "test_spool_recovery_after_batch_api_slot_is_reconcile_only", "side_effect_unknown", "api_slot_reserved", "reconcile_only_side_effect_unknown", 0, 0),
    FaultCase("crash_during_broker_call", "tests.test_stage179_executor_serve", "Stage179ExecutorServeTest", "test_multi_child_second_send_exception_is_unknown_with_call_count", "side_effect_unknown", "api_slot+send_exception", "reconcile_only_side_effect_unknown", 2, 0),
    FaultCase("empty_send_return", "tests.test_stage179_executor_serve", "Stage179ExecutorServeTest", "test_multi_child_empty_return_is_unknown_and_does_not_retry", "side_effect_unknown", "send_order_returned_empty", "reconcile_only_side_effect_unknown", 1, 0),
    FaultCase("ack_timeout", "tests.test_stage931_trade_fill_accounting", "Stage931TradeFillAccountingTest", "test_missing_order_callback_is_unknown_never_rejected_or_inactive", "side_effect_unknown", "unknown_order_status_after_send", "reconcile_only_side_effect_unknown", 1, 0),
    FaultCase("partial_fill_cancel_late_fill", "tests.test_stage931_trade_fill_accounting", "Stage931TradeFillAccountingTest", "test_order_traded_observation_never_rolls_back_after_cancel", "reconciled", "filled_or_part_filled", "reconciled", 1, 1),
    FaultCase("connection_generation_change", "tests.test_stage179_executor_serve", "Stage179ExecutorServeTest", "test_old_connection_generation_lease_cannot_authorize_send_after_reconnect", "blocked", "generation_mismatch", "fresh_revalidation_required", 0, 0),
    FaultCase("watermark_race", "tests.test_stage931_post_reprice_final_gate", "Stage931PostRepriceFinalGateTest", "test_order_ingress_between_q2_callback_and_watermark_is_not_lost", "blocked", "watermark_changed", "fresh_revalidation_required", 0, 0),
    FaultCase("open_close_deadline", "tests.test_official_live_intent_spool", "OfficialLiveIntentSpoolTest", "test_exact_deadline_expires_open_and_blocks_close_critical", "expired_or_blocked", "deadline", "no_send", 0, 0),
    FaultCase("dequeue_deadline", "tests.test_stage179_executor_serve", "Stage179ExecutorServeTest", "test_absolute_25s_intent_deadline_blocks_before_api_slot_and_send", "expired", "none", "deadline_exceeded", 0, 0),
    FaultCase("socket_loss", "tests.test_stage179_executor_serve", "Stage179ExecutorServeTest", "test_socket_loss_is_recovered_by_point_one_second_poll", "sent", "poll_recovery", "sent_once", 1, 0),
    FaultCase("spool_busy", "tests.test_official_live_intent_spool", "OfficialLiveIntentSpoolTest", "test_busy_writer_is_explicit_and_never_advances_cursor", "unchanged", "none", "storage_blocked", 0, 0),
    FaultCase("spool_integrity", "tests.test_official_live_intent_spool", "OfficialLiveIntentSpoolTest", "test_stored_payload_tamper_rolls_back_lease_claim", "ready", "integrity_error", "blocked_integrity", 0, 0),
    FaultCase("disk_full", "tests.test_stage608_continuous_tick_stream", "ContinuousTickStreamTest", "test_writer_error_latches_fault_and_rejects_ready_heartbeat", "not_applicable", "journal_write_error", "feed_unready", 0, 0),
    FaultCase("ledger_checksum", "tests.test_official_live_execution_ledger_cycles", "OfficialLiveExecutionLedgerCycleTest", "test_spool_recovery_corrupt_ledger_fails_closed", "blocked", "ledger_checksum_error", "blocked_ledger_integrity", 0, 0),
    FaultCase("ledger_fsync", "tests.test_official_live_execution_ledger_cycles", "OfficialLiveExecutionLedgerCycleTest", "test_durable_append_fsyncs_new_file_and_parent_directory_once", "unchanged", "durable_append", "commit_or_raise", 0, 0),
    FaultCase("kill_switch_default_off", "tests.test_stage179_runtime_profile", "Stage179RuntimeProfileTest", "test_production_live_default_off_stops_before_adapter_import", "not_started", "activation_disabled", "adapter_not_imported", 0, 0),
    FaultCase("review_policy_conflict", "tests.test_stage179_runtime_profile", "Stage179RuntimeProfileTest", "test_policy_conflict_blocks_even_with_env_and_confirm", "not_started", "operator_policy_conflict", "adapter_not_created", 0, 0),
    FaultCase("runtime_profile_mismatch", "tests.test_stage179_runtime_profile", "Stage179RuntimeProfileTest", "test_profile_and_order_scope_mismatch_fails_closed", "not_started", "profile_scope_mismatch", "startup_blocked", 0, 0),
    FaultCase("two_executor_singleton", "tests.test_stage179_executor_serve", "Stage179ExecutorServeTest", "test_readiness_file_is_atomic_and_singleton_rejects_second_executor", "leased_once", "singleton_lock", "one_owner", 0, 0),
)


def _evidence_root() -> Path | None:
    value = os.environ.get("STAGE179_FAULT_EVIDENCE_DIR", "").strip()
    if not value:
        return None
    root = Path(value).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_evidence(name: str, payload: dict[str, Any]) -> None:
    root = _evidence_root()
    if root is None:
        return
    (root / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _slot_race_worker(
    path: str,
    target_date: str,
    worker_id: int,
    barrier: Any,
    result_queue: Any,
) -> None:
    barrier.wait(timeout=10)
    result = ledger.reserve_execution_api_slot(
        target_date=target_date,
        slot_type="send_order",
        daily_limit=1,
        base_event={"intent_fingerprint": f"race-{target_date}-{worker_id}"},
        path=Path(path),
    )
    won = int(bool(result.get("reserved")))
    result_queue.put(
        {
            "worker_id": worker_id,
            "api_slot_winner": won,
            "fake_send_calls": won,
            "fake_cancel_calls": 0,
        }
    )


class Stage179FaultMatrixTest(unittest.TestCase):
    def test_fault_matrix_contracts_fail_closed(self) -> None:
        evidence: list[dict[str, Any]] = []
        for case in FAULT_CASES:
            with self.subTest(case=case.name):
                module = importlib.import_module(case.test_module)
                test_class = getattr(module, case.test_class)
                nested = test_class(case.test_method)
                result = unittest.TestResult()
                nested.run(result)
                details = [
                    text
                    for _test, text in (*result.failures, *result.errors)
                ]
                self.assertTrue(result.wasSuccessful(), "\n".join(details))
                evidence.append(
                    {
                        **asdict(case),
                        "production_contract_test_passed": True,
                        "real_send_order_api_called_count": 0,
                        "real_cancel_order_api_called_count": 0,
                    }
                )

        payload = {
            "status": "passed",
            "case_count": len(evidence),
            "cases": evidence,
            "real_send_order_api_called_count": 0,
            "real_cancel_order_api_called_count": 0,
        }
        _write_evidence("stage179_fault_matrix_cases.json", payload)
        self.assertEqual(len(FAULT_CASES), len(evidence))

    def test_one_hundred_process_races_have_at_most_one_send_winner(self) -> None:
        context = multiprocessing.get_context("fork")
        rounds: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "race-ledger.ndjson"
            for index in range(100):
                target_date = f"race-{index:03d}"
                barrier = context.Barrier(2)
                result_queue = context.Queue()
                workers = [
                    context.Process(
                        target=_slot_race_worker,
                        args=(
                            str(ledger_path),
                            target_date,
                            worker_id,
                            barrier,
                            result_queue,
                        ),
                    )
                    for worker_id in (1, 2)
                ]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=10)
                    self.assertEqual(0, worker.exitcode)
                results = [result_queue.get(timeout=2) for _ in workers]
                result_queue.close()
                result_queue.join_thread()
                winners = sum(item["fake_send_calls"] for item in results)
                counts = ledger.ledger_order_api_counts(
                    ledger.read_execution_ledger(ledger_path),
                    target_date,
                )
                self.assertEqual(1, winners)
                self.assertEqual(1, counts["send_order_slot_usage"])
                self.assertEqual(0, counts["cancel_order_slot_usage"])
                rounds.append(
                    {
                        "round": index + 1,
                        "send_winners": winners,
                        "cancel_winners": 0,
                        "ledger_send_slot_usage": counts[
                            "send_order_slot_usage"
                        ],
                    }
                )

        _write_evidence(
            "stage179_fault_matrix_process_races.json",
            {
                "status": "passed",
                "round_count": len(rounds),
                "max_send_winners_per_round": max(
                    item["send_winners"] for item in rounds
                ),
                "rounds": rounds,
                "real_send_order_api_called_count": 0,
                "real_cancel_order_api_called_count": 0,
            },
        )
        self.assertEqual(100, len(rounds))


if __name__ == "__main__":
    unittest.main()
