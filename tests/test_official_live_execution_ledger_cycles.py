from __future__ import annotations

import hashlib
import importlib
import json
import multiprocessing
import sys
import tempfile
import threading
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

_config_stub = types.ModuleType("qmt_roll_official_live_phase_d_config")
_config_stub.LIVE_EXECUTION_LEDGER_PATH = PROJECT_DIR / ".unit-test-execution-ledger.jsonl"
_config_module_name = "qmt_roll_official_live_phase_d_config"
_previous_config_module = sys.modules.get(_config_module_name)
sys.modules[_config_module_name] = _config_stub
try:
    ledger = importlib.import_module("qmt_roll_official_live_execution_ledger")
finally:
    if _previous_config_module is None:
        sys.modules.pop(_config_module_name, None)
    else:
        sys.modules[_config_module_name] = _previous_config_module


TARGET_DATE = "2026-07-13"
VT_SYMBOL = "JM2609.DCE"
ROOT_POSITION_ID = "JM2609.DCE:short:2026-07-13"


def _order_request(*, offset: str = "open", price: float = 1245.5) -> dict[str, object]:
    return {
        "vt_symbol": VT_SYMBOL,
        "symbol": "JM2609",
        "exchange": "DCE",
        "direction": "short",
        "offset": offset,
        "volume": 2,
        "price": price,
        "reference": "stage931",
    }


def _legacy_digest(*, offset: str = "open", intent_role: str = "") -> str:
    payload: dict[str, object] = {
        "target_date": TARGET_DATE,
        "vt_symbol": VT_SYMBOL,
        "symbol": "JM2609",
        "exchange": "DCE",
        "direction": "short",
        "offset": offset,
        "volume": 2.0,
    }
    if intent_role:
        payload["intent_role"] = intent_role
    stable = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _cycle_row(*, cycle_no: int, intent_role: str, offset: str = "open") -> dict[str, object]:
    return {
        "source": "official_live",
        "source_reason": "unit_test",
        "root_position_id": ROOT_POSITION_ID,
        "position_cycle_id": f"{ROOT_POSITION_ID}:cycle:{cycle_no}",
        "position_cycle_no": cycle_no,
        "intent_role": intent_role,
        "strategy_entry_price": 1245.5,
        "strategy_initial_stop_price": 1255.5,
        "strategy_stop_price": 1255.5,
        "retry_trigger_price": 1240.0,
        "retry_stop_price": 1252.0,
        "offset": offset,
    }


def _intent_and_fingerprint(*, cycle_no: int, intent_role: str) -> tuple[str, dict[str, object]]:
    return ledger.intent_fingerprint(
        TARGET_DATE,
        _cycle_row(cycle_no=cycle_no, intent_role=intent_role),
        _order_request(),
    )


def _reservation(fingerprint: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "target_date": TARGET_DATE,
        "event_type": "reserved",
        "intent_fingerprint": fingerprint,
        "intent_payload": payload,
    }


def _fill(
    fingerprint: str,
    *,
    price: float,
    volume: float,
    vt_tradeid: str = "",
) -> dict[str, object]:
    row: dict[str, object] = {
        "target_date": TARGET_DATE,
        "event_type": "filled_or_part_filled",
        "intent_fingerprint": fingerprint,
        "fill_price_source": "event_trade_weighted_avg",
        "trade_volume_delta": volume,
        "price": price,
    }
    if vt_tradeid:
        row["vt_tradeid"] = vt_tradeid
    return row


def _known_zero_close_terminal(
    fingerprint: str,
    *,
    attempt_no: int = 1,
    generated_at: str,
    event_type: str = "rejected_or_inactive",
    reason: str = "terminal_cancelled_zero_fill",
) -> dict[str, object]:
    row: dict[str, object] = {
        "target_date": TARGET_DATE,
        "generated_at": generated_at,
        "event_type": event_type,
        "intent_fingerprint": fingerprint,
        "close_retry_audit_version": 1,
        "close_submit_attempt_no": attempt_no,
        "close_retry_known_zero": 1,
        "close_retry_unlock_eligible": int(attempt_no == 1),
        "close_retry_known_zero_reason": reason,
        "volume": 2,
        "order_traded_volume": 0,
        "trade_event_total_volume": 0,
        "trade_event_priced_volume": 0,
        "trade_callback_count": 0,
        "unpriced_volume": 0,
        "residual_volume": 2,
        "req_order_insert_audit_observed": 1,
        "order_callback_observed": 1,
        "vt_orderid": "CTP.1",
    }
    if event_type == "send_order_returned_empty":
        row.update(
            {
                "main_engine_send_order_returned_empty": 1,
                "req_order_insert_accepted": 0,
                "req_order_insert_request_ret": -2,
                "order_callback_observed": 0,
                "vt_orderid": "",
            }
        )
    else:
        row.update(
            {
                "req_order_insert_accepted": 1,
                "req_order_insert_request_ret": 0,
                "close_terminal_status_class": (
                    "rejected" if "rejected" in reason else "cancelled"
                ),
            }
        )
    return row


def _reserve_worker(path_text: str, worker_id: int, result_queue: object) -> None:
    path = Path(path_text)
    result = ledger.reserve_execution_api_slot(
        target_date=TARGET_DATE,
        slot_type="send_order",
        daily_limit=1,
        base_event={"worker_id": worker_id, "intent_fingerprint": f"worker-{worker_id}"},
        path=path,
    )
    result_queue.put(bool(result.get("reserved")))


def _close_attempt2_reserve(path: Path, worker_id: int) -> dict[str, object]:
    return ledger.reserve_execution_ledger_intent(
        target_date=TARGET_DATE,
        row=_cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        ),
        order_request=_order_request(offset="close"),
        close_retry_after_cancel_seconds=1,
        close_retry_attempt2_lease_seconds=300,
        base_event={"intent_id": f"close-attempt2-{worker_id}"},
        path=path,
    )


def _close_attempt2_reserve_worker(
    path_text: str,
    worker_id: int,
    start_event: object,
    result_queue: object,
) -> None:
    start_event.wait(timeout=5)
    result = _close_attempt2_reserve(Path(path_text), worker_id)
    result_queue.put(
        {
            "reserved": bool(result.get("reserved")),
            "token": str(result.get("close_attempt_lease_token", "")),
            "blocker": str(result.get("duplicate_blocker", "")),
        }
    )


def _seed_known_zero_close(path: Path) -> tuple[str, dict[str, object], dict[str, object]]:
    close_row = _cycle_row(
        cycle_no=0,
        intent_role="c9_initial_stop_close",
        offset="close",
    )
    close_request = _order_request(offset="close")
    first = ledger.reserve_execution_ledger_intent(
        target_date=TARGET_DATE,
        row=close_row,
        order_request=close_request,
        close_retry_after_cancel_seconds=1,
        base_event={"intent_id": "close-attempt1"},
        path=path,
    )
    fingerprint = str(first["intent_fingerprint"])
    ledger.append_execution_ledger_event(
        {
            "event_type": "send_order_called",
            "target_date": TARGET_DATE,
            "intent_fingerprint": fingerprint,
            "close_submit_attempt_no": 1,
        },
        path=path,
    )
    ledger.append_execution_ledger_event(
        _known_zero_close_terminal(
            fingerprint,
            generated_at=(datetime.now() - timedelta(seconds=5)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        ),
        path=path,
    )
    return fingerprint, close_row, close_request


def _close_send_slot_event(
    fingerprint: str,
    token: str,
    *,
    attempt_no: int,
    child_index: int = 0,
) -> dict[str, object]:
    return {
        "target_date": TARGET_DATE,
        "intent_id": f"close-attempt{attempt_no}",
        "intent_fingerprint": fingerprint,
        "close_submit_attempt_no": attempt_no,
        "close_attempt_lease_token": token,
        "child_order_id": f"{fingerprint}:{child_index + 1}/2",
        "child_order_index": child_index,
        "child_order_offset": "close",
    }


def _attempt2_send_slot_event(fingerprint: str, token: str) -> dict[str, object]:
    return _close_send_slot_event(
        fingerprint,
        token,
        attempt_no=2,
    )


def _attempt1_send_slot_cas(
    path: Path,
    fingerprint: str,
    token: str,
    worker_id: int,
) -> dict[str, object]:
    return ledger.reserve_execution_api_slots(
        target_date=TARGET_DATE,
        slot_type="send_order",
        daily_limit=12,
        base_events=[
            {
                **_close_send_slot_event(
                    fingerprint,
                    token,
                    attempt_no=1,
                ),
                "worker_id": worker_id,
            }
        ],
        path=path,
    )


def _attempt1_send_slot_cas_worker(
    path_text: str,
    fingerprint: str,
    token: str,
    worker_id: int,
    start_event: object,
    result_queue: object,
) -> None:
    start_event.wait(timeout=5)
    result = _attempt1_send_slot_cas(
        Path(path_text), fingerprint, token, worker_id
    )
    result_queue.put(
        {
            "worker_id": worker_id,
            "reserved": bool(result.get("reserved")),
            "blocker": str(result.get("blocker", "")),
        }
    )


def _seed_expired_attempt1_lease(path: Path) -> tuple[str, str, dict[str, object], dict[str, object]]:
    close_row = _cycle_row(
        cycle_no=0,
        intent_role="c9_initial_stop_close",
        offset="close",
    )
    close_request = _order_request(offset="close")
    fingerprint, payload = ledger.intent_fingerprint(
        TARGET_DATE, close_row, close_request
    )
    old_token = "attempt1-worker-a-token"
    ledger.append_execution_ledger_event(
        {
            "event_type": "reserved",
            "target_date": TARGET_DATE,
            "intent_fingerprint": fingerprint,
            "intent_payload": payload,
            "close_submit_attempt_no": 1,
            "close_attempt_lease_token": old_token,
            "close_attempt_lease_seconds": 1,
            "close_attempt_retry_cooldown_seconds": 1,
            "generated_at": (
                datetime.now() - timedelta(seconds=5)
            ).strftime("%Y-%m-%d %H:%M:%S"),
        },
        path=path,
    )
    return fingerprint, old_token, close_row, close_request


class OfficialLiveExecutionLedgerCycleTest(unittest.TestCase):
    def test_partial_v2_identity_is_rejected_instead_of_silent_v1_fallback(self) -> None:
        row = {
            "source": "official_live",
            "root_position_id": ROOT_POSITION_ID,
            "strategy_entry_price": 1245.5,
            "strategy_stop_price": 1255.5,
            "retry_trigger_price": 1240.0,
        }

        with self.assertRaisesRegex(ValueError, "incomplete_v2_intent_identity"):
            ledger.intent_fingerprint(TARGET_DATE, row, _order_request())

    def test_v1_with_legacy_intent_role_remains_compatible(self) -> None:
        role = "initial_entry"
        fingerprint, payload = ledger.intent_fingerprint(
            TARGET_DATE,
            {"intent_role": role},
            _order_request(),
        )

        self.assertEqual(fingerprint, _legacy_digest(intent_role=role))
        self.assertNotIn("fingerprint_version", payload)

    def test_v2_requires_full_identity_and_separates_position_cycles(self) -> None:
        first_row = _cycle_row(cycle_no=0, intent_role="initial_stop_close", offset="close")
        first_fingerprint, first_payload = ledger.intent_fingerprint(
            TARGET_DATE,
            first_row,
            _order_request(offset="close"),
        )
        price_changed_fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE,
            {**first_row, "source_reason": "different", "strategy_stop_price": 1260.0},
            _order_request(offset="close", price=1260.0),
        )
        retry_row = _cycle_row(cycle_no=1, intent_role="retry_failure_stop_close", offset="close")
        retry_fingerprint, retry_payload = ledger.intent_fingerprint(
            TARGET_DATE,
            retry_row,
            _order_request(offset="close"),
        )

        self.assertEqual(first_payload["fingerprint_version"], 2)
        self.assertEqual(retry_payload["fingerprint_version"], 2)
        self.assertEqual(first_fingerprint, price_changed_fingerprint)
        self.assertNotEqual(first_fingerprint, retry_fingerprint)

        rows = [{"event_type": "filled_or_part_filled", "intent_fingerprint": first_fingerprint}]
        first_blocker, *_ = ledger.duplicate_blocker(
            rows=rows,
            target_date=TARGET_DATE,
            row=first_row,
            order_request=_order_request(offset="close"),
            close_retry_after_cancel_seconds=30,
        )
        retry_blocker, *_ = ledger.duplicate_blocker(
            rows=rows,
            target_date=TARGET_DATE,
            row=retry_row,
            order_request=_order_request(offset="close"),
            close_retry_after_cancel_seconds=30,
        )

        self.assertEqual(first_blocker, "ledger_duplicate_close_intent:filled_or_part_filled")
        self.assertEqual(retry_blocker, "")

    def test_position_epoch_separates_same_day_same_cycle_intents(self) -> None:
        first_row = {
            **_cycle_row(cycle_no=0, intent_role="c9_initial_stop_close", offset="close"),
            "position_epoch_id": "epoch-001",
        }
        second_row = {**first_row, "position_epoch_id": "epoch-002"}
        first_fingerprint, first_payload = ledger.intent_fingerprint(
            TARGET_DATE, first_row, _order_request(offset="close")
        )
        second_fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE, second_row, _order_request(offset="close")
        )

        blocker, *_ = ledger.duplicate_blocker(
            rows=[_reservation(first_fingerprint, first_payload)],
            target_date=TARGET_DATE,
            row=second_row,
            order_request=_order_request(offset="close"),
            close_retry_after_cancel_seconds=30,
        )

        self.assertNotEqual(first_fingerprint, second_fingerprint)
        self.assertEqual(blocker, "")

    def test_legacy_alias_blocks_initial_open_initial_stop_and_retry_open_only(self) -> None:
        cases = [
            (0, "c9_initial_open", "open", _legacy_digest(offset="open"), True),
            (0, "c9_initial_stop_close", "close", _legacy_digest(offset="close"), True),
            (1, "c9_retry_open_once", "open", _legacy_digest(offset="open", intent_role="c9_retry_open_once"), True),
            (1, "c9_retry_failed_stop_close", "close", _legacy_digest(offset="close"), False),
        ]
        for cycle_no, role, offset, legacy_fingerprint, should_block in cases:
            with self.subTest(role=role):
                blocker, *_ = ledger.duplicate_blocker(
                    rows=[
                        {
                            "target_date": TARGET_DATE,
                            "event_type": "send_order_called",
                            "intent_fingerprint": legacy_fingerprint,
                        }
                    ],
                    target_date=TARGET_DATE,
                    row=_cycle_row(cycle_no=cycle_no, intent_role=role, offset=offset),
                    order_request=_order_request(offset=offset),
                    close_retry_after_cancel_seconds=30,
                )
                self.assertEqual(bool(blocker), should_block)

    def test_normalize_propagates_cycle_and_strategy_metadata(self) -> None:
        row = _cycle_row(cycle_no=1, intent_role="stop_retry_reentry")
        row.update(
            {
                "parent_position_cycle_id": f"{ROOT_POSITION_ID}:cycle:0",
                "parent_intent_fingerprint": "parent-fingerprint",
                "retry_original_fill_price": 1245.5,
                "root_entry_price": 1245.5,
                "root_initial_stop_price": 1255.5,
                "root_entry_volume": 2,
                "position_epoch_id": "epoch-001",
            }
        )

        payload = ledger.normalize_intent_payload(TARGET_DATE, row, _order_request())

        self.assertEqual(payload["root_position_id"], ROOT_POSITION_ID)
        self.assertEqual(payload["position_cycle_id"], f"{ROOT_POSITION_ID}:cycle:1")
        self.assertEqual(payload["position_cycle_no"], 1.0)
        self.assertEqual(payload["strategy_entry_price"], 1245.5)
        self.assertEqual(payload["strategy_stop_price"], 1255.5)
        self.assertEqual(payload["retry_trigger_price"], 1240.0)
        self.assertEqual(payload["parent_intent_fingerprint"], "parent-fingerprint")
        self.assertEqual(payload["position_epoch_id"], "epoch-001")
        self.assertEqual(payload["fingerprint_version"], 2)

    def test_corrupt_or_checksum_invalid_row_blocks_duplicate_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            path.write_text('{"event_type":"send_order_called"\n', encoding="utf-8")
            rows = ledger.read_execution_ledger(path)
            blocker, *_ = ledger.duplicate_blocker(
                rows=rows,
                target_date=TARGET_DATE,
                row=_cycle_row(cycle_no=0, intent_role="c9_initial_open"),
                order_request=_order_request(),
                close_retry_after_cancel_seconds=30,
            )
            self.assertTrue(blocker.startswith("ledger_integrity_error:ledger_decode_error"))

            path.unlink()
            written = ledger.append_execution_ledger_event(
                {"event_type": "send_order_called", "target_date": TARGET_DATE, "volume": 2},
                path=path,
            )
            tampered = {**written, "volume": 3}
            path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
            rows = ledger.read_execution_ledger(path)
            self.assertEqual(rows[0]["event_type"], "ledger_checksum_error")

    def test_durable_append_fsyncs_new_file_and_parent_directory_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            with (
                mock.patch.object(ledger.os, "fsync", wraps=ledger.os.fsync) as fsync,
                mock.patch.object(
                    ledger,
                    "_fsync_parent_directory",
                    wraps=ledger._fsync_parent_directory,
                ) as parent_fsync,
            ):
                ledger.append_execution_ledger_event(
                    {"event_type": "test", "target_date": TARGET_DATE}, path=path
                )
                ledger.append_execution_ledger_event(
                    {"event_type": "test-2", "target_date": TARGET_DATE}, path=path
                )
            # First append: file + directory.  Second append: file only.
            self.assertEqual(fsync.call_count, 3)
            parent_fsync.assert_called_once_with(path)

    def test_pre_send_intent_leases_do_not_consume_api_quota(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            for index in range(12):
                root = f"{ROOT_POSITION_ID}:pre-gate:{index}"
                reserved = ledger.reserve_execution_ledger_intent(
                    target_date=TARGET_DATE,
                    row={
                        **_cycle_row(cycle_no=0, intent_role="c9_initial_open"),
                        "root_position_id": root,
                        "position_cycle_id": f"{root}:cycle:0",
                    },
                    order_request=_order_request(),
                    close_retry_after_cancel_seconds=30,
                    base_event={"intent_id": f"pre-gate-{index}"},
                    max_daily_send_orders=12,
                    max_daily_cancel_orders=20,
                    path=path,
                )
                self.assertTrue(reserved["reserved"])
                fingerprint = reserved["intent_fingerprint"]
                ledger.append_execution_ledger_event(
                    {
                        "event_type": "final_pre_send_gate_blocked_after_reserve",
                        "target_date": TARGET_DATE,
                        "intent_fingerprint": fingerprint,
                    },
                    path=path,
                )
            counts = ledger.ledger_order_api_counts(ledger.read_execution_ledger(path), TARGET_DATE)
            self.assertEqual(counts["send_order_slot_usage"], 0)
            self.assertEqual(counts["cancel_order_slot_usage"], 0)

            slots = [
                ledger.reserve_execution_api_slot(
                    target_date=TARGET_DATE,
                    slot_type="send_order",
                    daily_limit=12,
                    base_event={"intent_fingerprint": f"send-{index}"},
                    path=path,
                )
                for index in range(13)
            ]
            self.assertTrue(all(row["reserved"] for row in slots[:12]))
            self.assertFalse(slots[12]["reserved"])
            self.assertEqual(slots[12]["blocker"], "ledger_daily_send_order_limit_reached")
            counts = ledger.ledger_order_api_counts(ledger.read_execution_ledger(path), TARGET_DATE)
            self.assertEqual(counts["send_order_slot_usage"], 12)
            self.assertEqual(counts["cancel_order_slot_usage"], 0)

    def test_concurrent_send_slot_reservation_has_single_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            context = multiprocessing.get_context("fork")
            result_queue = context.Queue()
            workers = [
                context.Process(target=_reserve_worker, args=(str(path), worker_id, result_queue))
                for worker_id in (1, 2)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=10)
                self.assertEqual(worker.exitcode, 0)
            results = [result_queue.get(timeout=2) for _ in workers]

            self.assertEqual(sum(results), 1)
            self.assertEqual(
                ledger.ledger_order_api_counts(ledger.read_execution_ledger(path), TARGET_DATE)[
                    "send_order_slot_usage"
                ],
                1,
            )
            self.assertEqual(
                ledger.ledger_order_api_counts(ledger.read_execution_ledger(path), TARGET_DATE)[
                    "cancel_order_slot_usage"
                ],
                0,
            )

    def test_close_exception_after_send_slot_is_unknown_not_time_retryable(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, payload = ledger.intent_fingerprint(
            TARGET_DATE,
            close_row,
            close_request,
        )
        rows = [
            {
                **_reservation(fingerprint, payload),
                "close_submit_attempt_no": 1,
                "close_attempt_lease_token": "attempt1-token",
                "close_attempt_lease_seconds": 30,
                "close_attempt_retry_cooldown_seconds": 30,
            },
            {
                "target_date": TARGET_DATE,
                "event_type": "adapter_exception_after_reserve",
                "intent_fingerprint": fingerprint,
                "close_submit_attempt_no": 1,
                "close_attempt_lease_token": "attempt1-token",
                "generated_at": "2026-07-13 09:00:00",
                "send_slot_reserved": 1,
            },
        ]

        blocker, _, _, _ = ledger.duplicate_blocker(
            rows=rows,
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=1,
        )

        self.assertEqual(
            blocker,
            "ledger_duplicate_close_intent:send_order_side_effect_unknown_after_exception",
        )

    def test_pre_send_close_exception_keeps_lease_retry_semantics(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, payload = ledger.intent_fingerprint(
            TARGET_DATE, close_row, close_request
        )
        now = datetime.now()
        exception = {
            "target_date": TARGET_DATE,
            "event_type": "adapter_exception_after_reserve",
            "intent_fingerprint": fingerprint,
            "close_submit_attempt_no": 1,
            "close_attempt_lease_token": "attempt1-token",
            "pre_send_exception_confirmed": 1,
            "send_slot_reserved": 0,
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
        reservation = {
            **_reservation(fingerprint, payload),
            "close_submit_attempt_no": 1,
            "close_attempt_lease_token": "attempt1-token",
            "close_attempt_lease_seconds": 30,
            "close_attempt_retry_cooldown_seconds": 30,
        }
        throttled, *_ = ledger.duplicate_blocker(
            rows=[reservation, exception],
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=30,
        )
        exception["generated_at"] = (now - timedelta(seconds=31)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        allowed, *_ = ledger.duplicate_blocker(
            rows=[reservation, exception],
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=30,
        )

        self.assertTrue(
            throttled.startswith("ledger_close_attempt1_safe_terminal_throttled:")
        )
        self.assertEqual(allowed, "")

    def test_pre_send_exception_after_send_api_slot_is_permanent(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE, close_row, close_request
        )
        blocker, *_ = ledger.duplicate_blocker(
            rows=[
                {
                    "event_type": "api_slot_reserved",
                    "api_slot_type": "send_order",
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 1,
                },
                {
                    "event_type": "adapter_exception_after_reserve",
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 1,
                    "generated_at": "2026-07-13 09:00:00",
                },
            ],
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=1,
        )

        self.assertEqual(
            blocker,
            "ledger_duplicate_close_intent:send_order_side_effect_unknown_after_exception",
        )

    def test_known_zero_close_is_throttled_then_allows_one_retry(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE, close_row, close_request
        )
        now = datetime.now()
        send_event = {
            "target_date": TARGET_DATE,
            "event_type": "send_order_called",
            "intent_fingerprint": fingerprint,
            "close_submit_attempt_no": 1,
        }
        terminal = _known_zero_close_terminal(
            fingerprint,
            generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        )

        throttled, *_ = ledger.duplicate_blocker(
            rows=[send_event, terminal],
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=30,
        )
        terminal["generated_at"] = (now - timedelta(seconds=31)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        allowed, *_ = ledger.duplicate_blocker(
            rows=[
                send_event,
                terminal,
                {
                    "target_date": TARGET_DATE,
                    "event_type": "converted_order_batch_failed_closed",
                    "intent_fingerprint": fingerprint,
                    "generated_at": terminal["generated_at"],
                },
            ],
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=30,
        )

        self.assertTrue(throttled.startswith("ledger_close_known_zero_retry_throttled:"))
        self.assertEqual(allowed, "")

    def test_second_known_zero_close_attempt_is_permanently_blocked(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE, close_row, close_request
        )
        old = (datetime.now() - timedelta(minutes=2)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        rows = [
            {
                "event_type": "send_order_called",
                "intent_fingerprint": fingerprint,
                "close_submit_attempt_no": 1,
            },
            _known_zero_close_terminal(
                fingerprint, attempt_no=1, generated_at=old
            ),
            {
                "event_type": "send_order_called",
                "intent_fingerprint": fingerprint,
                "close_submit_attempt_no": 2,
            },
            _known_zero_close_terminal(
                fingerprint, attempt_no=2, generated_at=old
            ),
        ]

        blocker, *_ = ledger.duplicate_blocker(
            rows=rows,
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=1,
        )

        self.assertEqual(
            blocker,
            "ledger_duplicate_close_intent:known_zero_retry_limit_reached",
        )

    def test_known_req_order_insert_nonacceptance_can_unlock_once(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE, close_row, close_request
        )
        old = (datetime.now() - timedelta(minutes=2)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        blocker, *_ = ledger.duplicate_blocker(
            rows=[
                {
                    "event_type": "send_order_called",
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 1,
                },
                _known_zero_close_terminal(
                    fingerprint,
                    generated_at=old,
                    event_type="send_order_returned_empty",
                    reason="req_order_insert_not_accepted",
                ),
            ],
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=30,
        )

        self.assertEqual(blocker, "")

    def test_unflagged_unknown_and_partial_close_evidence_never_unlocks(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE, close_row, close_request
        )
        cases = {
            "unflagged": [
                {
                    "event_type": "rejected_or_inactive",
                    "intent_fingerprint": fingerprint,
                    "generated_at": "2026-07-13 09:00:00",
                }
            ],
            "unknown": [
                {
                    "event_type": "unknown_order_status_after_send",
                    "intent_fingerprint": fingerprint,
                    "generated_at": "2026-07-13 09:00:00",
                }
            ],
            "partial": [
                {
                    "event_type": "filled_or_part_filled",
                    "intent_fingerprint": fingerprint,
                    "trade_volume_delta": 1,
                    "generated_at": "2026-07-13 09:00:00",
                }
            ],
        }
        for name, rows in cases.items():
            with self.subTest(name=name):
                blocker, *_ = ledger.duplicate_blocker(
                    rows=rows,
                    target_date=TARGET_DATE,
                    row=close_row,
                    order_request=close_request,
                    close_retry_after_cancel_seconds=1,
                )
                self.assertTrue(blocker)

    def test_atomic_close_reservation_labels_the_single_retry_attempt(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            first = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                base_event={"intent_id": "close"},
                path=path,
            )
            self.assertTrue(first["reserved"])
            self.assertEqual(first["close_submit_attempt_no"], 1)
            fingerprint = first["intent_fingerprint"]
            ledger.append_execution_ledger_event(
                {
                    "event_type": "send_order_called",
                    "target_date": TARGET_DATE,
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 1,
                },
                path=path,
            )
            terminal = _known_zero_close_terminal(
                fingerprint,
                generated_at=(datetime.now() - timedelta(seconds=2)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            )
            ledger.append_execution_ledger_event(terminal, path=path)
            retry = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                base_event={"intent_id": "close"},
                path=path,
            )

        self.assertTrue(retry["reserved"])
        self.assertEqual(retry["close_submit_attempt_no"], 2)
        self.assertTrue(retry["close_attempt_lease_token"])

    def test_concurrent_threads_can_create_only_one_attempt2_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            _seed_known_zero_close(path)
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        lambda worker_id: _close_attempt2_reserve(path, worker_id),
                        (1, 2),
                    )
                )

            winners = [result for result in results if result.get("reserved")]
            losers = [result for result in results if not result.get("reserved")]
            attempt2_reservations = [
                row
                for row in ledger.read_execution_ledger(path)
                if row.get("event_type") == "reserved"
                and row.get("close_submit_attempt_no") == 2
            ]

        self.assertEqual(len(winners), 1)
        self.assertEqual(len(losers), 1)
        self.assertTrue(winners[0]["close_attempt_lease_token"])
        self.assertTrue(
            str(losers[0]["duplicate_blocker"]).startswith(
                "ledger_close_attempt2_lease_active:"
            )
        )
        self.assertEqual(len(attempt2_reservations), 1)

    def test_concurrent_processes_can_create_only_one_attempt2_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            _seed_known_zero_close(path)
            context = multiprocessing.get_context("fork")
            start_event = context.Event()
            result_queue = context.Queue()
            workers = [
                context.Process(
                    target=_close_attempt2_reserve_worker,
                    args=(str(path), worker_id, start_event, result_queue),
                )
                for worker_id in (1, 2)
            ]
            for worker in workers:
                worker.start()
            start_event.set()
            for worker in workers:
                worker.join(timeout=10)
                self.assertEqual(worker.exitcode, 0)
            results = [result_queue.get(timeout=2) for _ in workers]
            attempt2_reservations = [
                row
                for row in ledger.read_execution_ledger(path)
                if row.get("event_type") == "reserved"
                and row.get("close_submit_attempt_no") == 2
            ]

        self.assertEqual(sum(int(result["reserved"]) for result in results), 1)
        self.assertEqual(len(attempt2_reservations), 1)
        self.assertTrue(attempt2_reservations[0]["close_attempt_lease_token"])

    def test_attempt1_takeover_thread_race_allows_only_new_worker_send_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            fingerprint, old_token, close_row, close_request = (
                _seed_expired_attempt1_lease(path)
            )
            takeover = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                base_event={"intent_id": "attempt1-worker-b"},
                path=path,
            )
            new_token = str(takeover["close_attempt_lease_token"])
            barrier = threading.Barrier(2)

            def reserve_slot(worker: tuple[int, str]) -> tuple[int, dict[str, object]]:
                worker_id, token = worker
                barrier.wait(timeout=5)
                return (
                    worker_id,
                    _attempt1_send_slot_cas(
                        path, fingerprint, token, worker_id
                    ),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = dict(
                    executor.map(reserve_slot, ((1, old_token), (2, new_token)))
                )

        self.assertTrue(takeover["reserved"])
        self.assertEqual(takeover["close_submit_attempt_no"], 1)
        self.assertEqual(takeover["close_attempt_lease_takeover_from"], old_token)
        self.assertFalse(results[1]["reserved"])
        self.assertEqual(
            results[1]["blocker"],
            "close_attempt_api_slot_lease_cas_stale_token",
        )
        self.assertTrue(results[2]["reserved"])
        self.assertNotEqual(new_token, old_token)

    def test_attempt1_takeover_process_race_allows_only_new_worker_send_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            fingerprint, old_token, close_row, close_request = (
                _seed_expired_attempt1_lease(path)
            )
            takeover = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                base_event={"intent_id": "attempt1-worker-b"},
                path=path,
            )
            new_token = str(takeover["close_attempt_lease_token"])
            context = multiprocessing.get_context("fork")
            start_event = context.Event()
            result_queue = context.Queue()
            workers = [
                context.Process(
                    target=_attempt1_send_slot_cas_worker,
                    args=(
                        str(path),
                        fingerprint,
                        token,
                        worker_id,
                        start_event,
                        result_queue,
                    ),
                )
                for worker_id, token in ((1, old_token), (2, new_token))
            ]
            for worker in workers:
                worker.start()
            start_event.set()
            for worker in workers:
                worker.join(timeout=10)
                self.assertEqual(worker.exitcode, 0)
            results = {
                int(result["worker_id"]): result
                for result in (
                    result_queue.get(timeout=2),
                    result_queue.get(timeout=2),
                )
            }

        self.assertFalse(results[1]["reserved"])
        self.assertEqual(
            results[1]["blocker"],
            "close_attempt_api_slot_lease_cas_stale_token",
        )
        self.assertTrue(results[2]["reserved"])

    def test_attempt1_lease_persists_cooldown_and_cannot_be_shortened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            close_row = _cycle_row(
                cycle_no=0,
                intent_role="c9_initial_stop_close",
                offset="close",
            )
            close_request = _order_request(offset="close")
            fingerprint, payload = ledger.intent_fingerprint(
                TARGET_DATE, close_row, close_request
            )
            ledger.append_execution_ledger_event(
                {
                    "event_type": "reserved",
                    "target_date": TARGET_DATE,
                    "intent_fingerprint": fingerprint,
                    "intent_payload": payload,
                    "close_submit_attempt_no": 1,
                    "close_attempt_lease_token": "attempt1-long-token",
                    "close_attempt_lease_seconds": 30,
                    "close_attempt_retry_cooldown_seconds": 30,
                    "generated_at": (
                        datetime.now() - timedelta(seconds=5)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                path=path,
            )
            shortening = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                base_event={"intent_id": "attempt1-cannot-shorten"},
                path=path,
            )

        self.assertFalse(shortening["reserved"])
        self.assertTrue(
            str(shortening["duplicate_blocker"]).startswith(
                "ledger_close_attempt1_lease_active:"
            )
        )

    def test_attempt1_safe_terminal_uses_persisted_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            close_row = _cycle_row(
                cycle_no=0,
                intent_role="c9_initial_stop_close",
                offset="close",
            )
            close_request = _order_request(offset="close")
            reservation = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=30,
                base_event={"intent_id": "attempt1-persisted-cooldown"},
                path=path,
            )
            fingerprint = str(reservation["intent_fingerprint"])
            token = str(reservation["close_attempt_lease_token"])
            terminal = {
                "event_type": "final_pre_send_gate_blocked_after_reserve",
                "target_date": TARGET_DATE,
                "intent_fingerprint": fingerprint,
                "close_submit_attempt_no": 1,
                "close_attempt_lease_token": token,
                "generated_at": (
                    datetime.now() - timedelta(seconds=5)
                ).strftime("%Y-%m-%d %H:%M:%S"),
            }
            ledger.append_execution_ledger_event(terminal, path=path)
            shortened = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                base_event={"intent_id": "attempt1-too-early"},
                path=path,
            )
            ledger.append_execution_ledger_event(
                {
                    **terminal,
                    "generated_at": (
                        datetime.now() - timedelta(seconds=31)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                path=path,
            )
            after_cooldown = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                base_event={"intent_id": "attempt1-after-cooldown"},
                path=path,
            )

        self.assertFalse(shortened["reserved"])
        self.assertTrue(
            str(shortened["duplicate_blocker"]).startswith(
                "ledger_close_attempt1_safe_terminal_throttled:"
            )
        )
        self.assertTrue(after_cooldown["reserved"])
        self.assertEqual(after_cooldown["close_submit_attempt_no"], 1)
        self.assertNotEqual(after_cooldown["close_attempt_lease_token"], token)

    def test_legacy_close_reservation_without_token_fails_closed(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        close_request = _order_request(offset="close")
        fingerprint, payload = ledger.intent_fingerprint(
            TARGET_DATE, close_row, close_request
        )
        blocker, *_ = ledger.duplicate_blocker(
            rows=[
                {
                    **_reservation(fingerprint, payload),
                    "generated_at": (
                        datetime.now() - timedelta(minutes=10)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                }
            ],
            target_date=TARGET_DATE,
            row=close_row,
            order_request=close_request,
            close_retry_after_cancel_seconds=1,
        )

        self.assertEqual(
            blocker,
            "ledger_close_attempt_lease_attempt_missing_or_invalid",
        )

    def test_legacy_close_api_slot_without_attempt_or_token_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = ledger.reserve_execution_api_slots(
                target_date=TARGET_DATE,
                slot_type="send_order",
                daily_limit=12,
                base_events=[
                    {
                        "intent_fingerprint": "legacy-close-fingerprint",
                        "child_order_offset": "close",
                    }
                ],
                path=Path(directory) / "ledger.jsonl",
            )

        self.assertFalse(result["reserved"])
        self.assertEqual(
            result["blocker"],
            "close_attempt_api_slot_batch_attempt_missing_or_mismatch",
        )

    def test_close_api_slot_batch_requires_consistent_attempt_token_and_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            close_row = _cycle_row(
                cycle_no=0,
                intent_role="c9_initial_stop_close",
                offset="close",
            )
            close_request = _order_request(offset="close")
            reservation = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=30,
                base_event={"intent_id": "batch-consistency"},
                path=path,
            )
            fingerprint = str(reservation["intent_fingerprint"])
            token = str(reservation["close_attempt_lease_token"])
            valid_children = [
                _close_send_slot_event(
                    fingerprint,
                    token,
                    attempt_no=1,
                    child_index=index,
                )
                for index in (0, 1)
            ]
            cases = {
                "attempt": [
                    valid_children[0],
                    {**valid_children[1], "close_submit_attempt_no": 2},
                ],
                "token": [
                    valid_children[0],
                    {**valid_children[1], "close_attempt_lease_token": "wrong"},
                ],
                "fingerprint": [
                    valid_children[0],
                    {**valid_children[1], "intent_fingerprint": "wrong"},
                ],
                "offset": [
                    valid_children[0],
                    {**valid_children[1], "child_order_offset": "open"},
                ],
            }
            blocked = {
                name: ledger.reserve_execution_api_slots(
                    target_date=TARGET_DATE,
                    slot_type="send_order",
                    daily_limit=12,
                    base_events=children,
                    path=path,
                )
                for name, children in cases.items()
            }
            valid = ledger.reserve_execution_api_slots(
                target_date=TARGET_DATE,
                slot_type="send_order",
                daily_limit=12,
                base_events=valid_children,
                path=path,
            )

        self.assertEqual(
            blocked["attempt"]["blocker"],
            "close_attempt_api_slot_batch_attempt_missing_or_mismatch",
        )
        self.assertEqual(
            blocked["token"]["blocker"],
            "close_attempt_api_slot_batch_lease_token_missing_or_mismatch",
        )
        self.assertEqual(
            blocked["fingerprint"]["blocker"],
            "close_attempt_api_slot_batch_fingerprint_missing_or_mismatch",
        )
        self.assertEqual(
            blocked["offset"]["blocker"],
            "close_attempt_api_slot_batch_offset_missing_or_mismatch",
        )
        self.assertTrue(valid["reserved"])

    def test_explicit_open_api_slot_batch_remains_token_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = ledger.reserve_execution_api_slots(
                target_date=TARGET_DATE,
                slot_type="send_order",
                daily_limit=12,
                base_events=[
                    {
                        "intent_fingerprint": "open-fingerprint",
                        "child_order_offset": "open",
                    }
                ],
                path=Path(directory) / "ledger.jsonl",
            )

        self.assertTrue(result["reserved"])

    def test_close_api_slot_cas_accepts_consistent_minimal_child_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            close_row = _cycle_row(
                cycle_no=0,
                intent_role="c9_initial_stop_close",
                offset="close",
            )
            reservation = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=_order_request(offset="close"),
                close_retry_after_cancel_seconds=30,
                base_event={"intent_id": "minimal-close-cas"},
                path=path,
            )
            result = ledger.reserve_execution_api_slots(
                target_date=TARGET_DATE,
                slot_type="send_order",
                daily_limit=12,
                base_events=[
                    {
                        "intent_fingerprint": reservation[
                            "intent_fingerprint"
                        ],
                        "close_submit_attempt_no": 1,
                        "close_attempt_lease_token": reservation[
                            "close_attempt_lease_token"
                        ],
                    }
                ],
                path=path,
            )

        self.assertTrue(result["reserved"])

    def test_expired_attempt2_takeover_makes_old_api_slot_cas_lose(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            fingerprint, close_row, close_request = _seed_known_zero_close(path)
            old_token = "attempt2-old-token"
            ledger.append_execution_ledger_event(
                {
                    "event_type": "reserved",
                    "target_date": TARGET_DATE,
                    "intent_id": "close-attempt2-old",
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 2,
                    "close_attempt_lease_token": old_token,
                    "close_attempt_lease_seconds": 1,
                    "close_attempt_retry_cooldown_seconds": 1,
                    "generated_at": (
                        datetime.now() - timedelta(seconds=5)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                path=path,
            )
            takeover = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                close_retry_attempt2_lease_seconds=1,
                base_event={"intent_id": "close-attempt2-takeover"},
                path=path,
            )
            new_token = str(takeover["close_attempt_lease_token"])
            old_cas = ledger.reserve_execution_api_slots(
                target_date=TARGET_DATE,
                slot_type="send_order",
                daily_limit=12,
                base_events=[_attempt2_send_slot_event(fingerprint, old_token)],
                path=path,
            )
            new_cas = ledger.reserve_execution_api_slots(
                target_date=TARGET_DATE,
                slot_type="send_order",
                daily_limit=12,
                base_events=[_attempt2_send_slot_event(fingerprint, new_token)],
                path=path,
            )

        self.assertTrue(takeover["reserved"])
        self.assertEqual(takeover["close_submit_attempt_no"], 2)
        self.assertNotEqual(new_token, old_token)
        self.assertEqual(takeover["close_attempt_lease_takeover_from"], old_token)
        self.assertFalse(old_cas["reserved"])
        self.assertEqual(
            old_cas["blocker"],
            "close_attempt_api_slot_lease_cas_stale_token",
        )
        self.assertTrue(new_cas["reserved"])

    def test_attempt2_takeover_cannot_shorten_recorded_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            fingerprint, close_row, close_request = _seed_known_zero_close(path)
            ledger.append_execution_ledger_event(
                {
                    "event_type": "reserved",
                    "target_date": TARGET_DATE,
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 2,
                    "close_attempt_lease_token": "long-lease-token",
                    "close_attempt_lease_seconds": 300,
                    "close_attempt_retry_cooldown_seconds": 1,
                    "generated_at": (
                        datetime.now() - timedelta(seconds=5)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                path=path,
            )
            attempted_shortening = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=1,
                close_retry_attempt2_lease_seconds=1,
                base_event={"intent_id": "cannot-shorten-existing-lease"},
                path=path,
            )

        self.assertFalse(attempted_shortening["reserved"])
        self.assertTrue(
            str(attempted_shortening["duplicate_blocker"]).startswith(
                "ledger_close_attempt2_lease_active:"
            )
        )

    def test_attempt2_safe_pre_send_terminal_retries_with_new_token_same_attempt(self) -> None:
        terminal_cases = {
            "final_pre_send_gate_blocked_after_reserve": {},
            "api_slot_reservation_blocked": {
                "api_slot_type": "send_order",
                "api_slot_blocker": "ledger_daily_send_order_limit_reached",
            },
            "adapter_exception_after_reserve": {
                "pre_send_exception_confirmed": 1,
                "send_slot_reserved": 0,
                "exception": "RuntimeError('pre-send')",
            },
        }
        for event_type, extra in terminal_cases.items():
            with self.subTest(event_type=event_type), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "ledger.jsonl"
                fingerprint, _, _ = _seed_known_zero_close(path)
                first_retry = _close_attempt2_reserve(path, 1)
                first_token = str(first_retry["close_attempt_lease_token"])
                ledger.append_execution_ledger_event(
                    {
                        "event_type": event_type,
                        "target_date": TARGET_DATE,
                        "intent_fingerprint": fingerprint,
                        "close_submit_attempt_no": 2,
                        "close_attempt_lease_token": first_token,
                        "generated_at": (
                            datetime.now() - timedelta(seconds=5)
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        **extra,
                    },
                    path=path,
                )
                second_retry = _close_attempt2_reserve(path, 2)

                self.assertTrue(second_retry["reserved"])
                self.assertEqual(second_retry["close_submit_attempt_no"], 2)
                self.assertTrue(second_retry["close_attempt_lease_token"])
                self.assertNotEqual(
                    second_retry["close_attempt_lease_token"], first_token
                )

    def test_attempt2_safe_terminal_must_match_exact_lease_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            fingerprint, _, _ = _seed_known_zero_close(path)
            first_retry = _close_attempt2_reserve(path, 1)
            ledger.append_execution_ledger_event(
                {
                    "event_type": "final_pre_send_gate_blocked_after_reserve",
                    "target_date": TARGET_DATE,
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 2,
                    "close_attempt_lease_token": "wrong-token",
                    "generated_at": (
                        datetime.now() - timedelta(seconds=5)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                path=path,
            )
            blocked = _close_attempt2_reserve(path, 2)

        self.assertFalse(blocked["reserved"])
        self.assertTrue(
            str(blocked["duplicate_blocker"]).startswith(
                "ledger_close_attempt2_lease_active:"
            )
        )
        self.assertTrue(first_retry["reserved"])

    def test_attempt1_safe_terminal_must_match_exact_lease_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            close_row = _cycle_row(
                cycle_no=0,
                intent_role="c9_initial_stop_close",
                offset="close",
            )
            close_request = _order_request(offset="close")
            reservation = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=30,
                base_event={"intent_id": "attempt1-safe-terminal"},
                path=path,
            )
            fingerprint = str(reservation["intent_fingerprint"])
            ledger.append_execution_ledger_event(
                {
                    "event_type": "final_pre_send_gate_blocked_after_reserve",
                    "target_date": TARGET_DATE,
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 1,
                    "close_attempt_lease_token": "wrong-token",
                    "generated_at": (
                        datetime.now() - timedelta(minutes=1)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                path=path,
            )
            blocked = ledger.reserve_execution_ledger_intent(
                target_date=TARGET_DATE,
                row=close_row,
                order_request=close_request,
                close_retry_after_cancel_seconds=30,
                base_event={"intent_id": "attempt1-wrong-terminal"},
                path=path,
            )

        self.assertFalse(blocked["reserved"])
        self.assertTrue(
            str(blocked["duplicate_blocker"]).startswith(
                "ledger_close_attempt1_lease_active:"
            )
        )

    def test_attempt2_api_slot_is_permanent_even_if_safe_terminal_is_appended(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            fingerprint, _, _ = _seed_known_zero_close(path)
            retry = _close_attempt2_reserve(path, 1)
            token = str(retry["close_attempt_lease_token"])
            api_slot = ledger.reserve_execution_api_slots(
                target_date=TARGET_DATE,
                slot_type="send_order",
                daily_limit=12,
                base_events=[_attempt2_send_slot_event(fingerprint, token)],
                path=path,
            )
            ledger.append_execution_ledger_event(
                {
                    "event_type": "final_pre_send_gate_blocked_after_reserve",
                    "target_date": TARGET_DATE,
                    "intent_fingerprint": fingerprint,
                    "close_submit_attempt_no": 2,
                    "close_attempt_lease_token": token,
                    "generated_at": (
                        datetime.now() - timedelta(seconds=5)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                path=path,
            )
            duplicate = _close_attempt2_reserve(path, 2)

        self.assertTrue(api_slot["reserved"])
        self.assertFalse(duplicate["reserved"])
        self.assertEqual(
            duplicate["duplicate_blocker"],
            "ledger_duplicate_close_intent:known_zero_retry_limit_reached",
        )

    def test_partial_initial_close_residual_gets_a_distinct_retry_fingerprint(self) -> None:
        close_row = _cycle_row(
            cycle_no=0,
            intent_role="c9_initial_stop_close",
            offset="close",
        )
        original_request = _order_request(offset="close")
        residual_request = {**original_request, "volume": 1}
        original_fingerprint, original_payload = ledger.intent_fingerprint(
            TARGET_DATE,
            close_row,
            original_request,
        )
        residual_fingerprint, _ = ledger.intent_fingerprint(
            TARGET_DATE,
            close_row,
            residual_request,
        )
        rows = [
            _reservation(original_fingerprint, original_payload),
            _fill(
                original_fingerprint,
                price=1252.0,
                volume=1,
                vt_tradeid="CTP.partial-close-1",
            ),
        ]

        blocker, selected_fingerprint, _, _ = ledger.duplicate_blocker(
            rows=rows,
            target_date=TARGET_DATE,
            row=close_row,
            order_request=residual_request,
            close_retry_after_cancel_seconds=30,
        )

        self.assertNotEqual(original_fingerprint, residual_fingerprint)
        self.assertEqual(selected_fingerprint, residual_fingerprint)
        self.assertEqual(blocker, "")

    def test_cycle_filtered_weighting_deduplicates_trade_ids(self) -> None:
        original_fingerprint, original_payload = _intent_and_fingerprint(cycle_no=0, intent_role="initial_entry")
        retry_fingerprint, retry_payload = _intent_and_fingerprint(cycle_no=1, intent_role="stop_retry_reentry")
        rows = [
            _reservation(original_fingerprint, original_payload),
            _fill(original_fingerprint, price=1245.5, volume=2, vt_tradeid="CTP.T0"),
            _fill(original_fingerprint, price=1245.5, volume=2, vt_tradeid="CTP.T0"),
            _reservation(retry_fingerprint, retry_payload),
            _fill(retry_fingerprint, price=1246.0, volume=2, vt_tradeid="CTP.T1"),
            _fill(retry_fingerprint, price=1246.0, volume=2, vt_tradeid="CTP.T1"),
        ]

        all_fills = ledger.weighted_open_fill(rows, TARGET_DATE, VT_SYMBOL, "short")
        original_fill = ledger.weighted_open_fill(
            rows,
            TARGET_DATE,
            VT_SYMBOL,
            "short",
            root_position_id=ROOT_POSITION_ID,
            position_cycle_id=f"{ROOT_POSITION_ID}:cycle:0",
            intent_role="initial_entry",
        )
        retry_fill = ledger.weighted_open_fill(
            rows,
            TARGET_DATE,
            VT_SYMBOL,
            "short",
            root_position_id=ROOT_POSITION_ID,
            position_cycle_id=f"{ROOT_POSITION_ID}:cycle:1",
        )

        self.assertIsNotNone(all_fills)
        self.assertIsNotNone(original_fill)
        self.assertIsNotNone(retry_fill)
        assert all_fills is not None and original_fill is not None and retry_fill is not None
        self.assertEqual(all_fills["volume"], 4.0)
        self.assertEqual(all_fills["price"], 1245.75)
        self.assertEqual(all_fills["trade_count"], 2)
        self.assertEqual(original_fill["volume"], 2.0)
        self.assertEqual(original_fill["price"], 1245.5)
        self.assertEqual(retry_fill["volume"], 2.0)
        self.assertEqual(retry_fill["price"], 1246.0)
        self.assertEqual(retry_fill["intent_role"], "stop_retry_reentry")

    def test_latest_cycle_prefers_cycle_number_over_late_event_order(self) -> None:
        original_fingerprint, original_payload = _intent_and_fingerprint(cycle_no=0, intent_role="initial_entry")
        retry_fingerprint, retry_payload = _intent_and_fingerprint(cycle_no=1, intent_role="stop_retry_reentry")
        rows = [
            _reservation(original_fingerprint, original_payload),
            _fill(original_fingerprint, price=1245.5, volume=1, vt_tradeid="CTP.T0"),
            _reservation(retry_fingerprint, retry_payload),
            _fill(retry_fingerprint, price=1246.0, volume=2, vt_tradeid="CTP.T1"),
            _fill(original_fingerprint, price=1245.0, volume=1, vt_tradeid="CTP.T2"),
        ]

        latest = ledger.latest_position_cycle_open_fill(
            rows,
            TARGET_DATE,
            VT_SYMBOL,
            "short",
            root_position_id=ROOT_POSITION_ID,
        )

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["position_cycle_id"], f"{ROOT_POSITION_ID}:cycle:1")
        self.assertEqual(latest["intent_role"], "stop_retry_reentry")
        self.assertEqual(latest["volume"], 2.0)
        self.assertEqual(latest["price"], 1246.0)

    def test_latest_epoch_cycle0_is_not_eclipsed_by_old_epoch_cycle1(self) -> None:
        old_initial_row = {
            **_cycle_row(cycle_no=0, intent_role="c9_initial_open"),
            "position_epoch_id": "epoch-old",
        }
        old_retry_row = {
            **_cycle_row(cycle_no=1, intent_role="c9_retry_open_once"),
            "position_epoch_id": "epoch-old",
        }
        new_initial_row = {
            **_cycle_row(cycle_no=0, intent_role="c9_initial_open"),
            "position_epoch_id": "epoch-new",
        }
        old_initial_fp, old_initial_payload = ledger.intent_fingerprint(
            TARGET_DATE, old_initial_row, _order_request()
        )
        old_retry_fp, old_retry_payload = ledger.intent_fingerprint(
            TARGET_DATE, old_retry_row, _order_request()
        )
        new_initial_fp, new_initial_payload = ledger.intent_fingerprint(
            TARGET_DATE, new_initial_row, _order_request(price=1230.0)
        )
        rows = [
            _reservation(old_initial_fp, old_initial_payload),
            _fill(old_initial_fp, price=1245.5, volume=2, vt_tradeid="OLD-0"),
            _reservation(old_retry_fp, old_retry_payload),
            _fill(old_retry_fp, price=1246.0, volume=1, vt_tradeid="OLD-1"),
            _reservation(new_initial_fp, new_initial_payload),
            _fill(new_initial_fp, price=1230.0, volume=2, vt_tradeid="NEW-0"),
            # A delayed callback from the old epoch is appended last; it must
            # not make the old epoch current again.
            _fill(old_retry_fp, price=1247.0, volume=1, vt_tradeid="OLD-LATE"),
        ]

        latest = ledger.latest_position_cycle_open_fill(
            rows, TARGET_DATE, VT_SYMBOL, "short", root_position_id=ROOT_POSITION_ID
        )
        old_retry = ledger.latest_position_cycle_open_fill(
            rows,
            TARGET_DATE,
            VT_SYMBOL,
            "short",
            root_position_id=ROOT_POSITION_ID,
            position_epoch_id="epoch-old",
            intent_role="c9_retry_open_once",
        )

        self.assertIsNotNone(latest)
        self.assertIsNotNone(old_retry)
        assert latest is not None and old_retry is not None
        self.assertEqual(latest["position_epoch_id"], "epoch-new")
        self.assertEqual(latest["position_cycle_no"], 0.0)
        self.assertEqual(latest["price"], 1230.0)
        self.assertEqual(old_retry["position_epoch_id"], "epoch-old")
        self.assertEqual(old_retry["volume"], 2.0)

    def test_legacy_fills_without_trade_ids_are_not_dropped(self) -> None:
        legacy_payload = {
            "target_date": TARGET_DATE,
            "vt_symbol": VT_SYMBOL,
            "direction": "short",
            "offset": "open",
        }
        rows = [
            {
                **_fill("legacy", price=1245.0, volume=1),
                "intent_payload": legacy_payload,
            },
            {
                **_fill("legacy", price=1247.0, volume=1),
                "intent_payload": legacy_payload,
            },
        ]

        fills = ledger.open_fill_rows(rows, TARGET_DATE, VT_SYMBOL, "short")
        weighted = ledger.weighted_open_fill(rows, TARGET_DATE, VT_SYMBOL, "short")

        self.assertEqual(len(fills), 2)
        self.assertIsNotNone(weighted)
        assert weighted is not None
        self.assertEqual(weighted["volume"], 2.0)
        self.assertEqual(weighted["price"], 1246.0)
        self.assertEqual(weighted["trade_count"], 2)


if __name__ == "__main__":
    unittest.main()
