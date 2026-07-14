from __future__ import annotations

import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from datetime import datetime, timedelta
from tempfile import TemporaryDirectory

import pandas as pd
from vnpy.event import Event, EventEngine
from vnpy.trader.constant import Product
from vnpy.trader.converter import OffsetConverter
from vnpy.trader.object import ContractData, PositionData


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931
import run_qmt_roll_stage930_official_live_c9_session_daemon as stage930


class Stage931TradeFillAccountingTest(unittest.TestCase):
    @staticmethod
    def _shfe_conversion_case(
        *,
        volume: float,
        yesterday_volume: float,
    ) -> tuple[object, dict[str, list[dict[str, object]]], stage931.OrderRequest]:
        contract = ContractData(
            symbol="rb2610",
            exchange=stage931.Exchange.SHFE,
            name="rb2610",
            product=Product.FUTURES,
            size=10,
            pricetick=1,
            gateway_name="CTP",
        )

        class FakeOms:
            @staticmethod
            def get_contract(vt_symbol: str) -> ContractData | None:
                return contract if vt_symbol == contract.vt_symbol else None

        converter = OffsetConverter(FakeOms())
        converter.update_position(
            PositionData(
                symbol=contract.symbol,
                exchange=contract.exchange,
                direction=stage931.Direction.SHORT,
                volume=volume,
                yd_volume=yesterday_volume,
                gateway_name="CTP",
            )
        )
        engine = SimpleNamespace(get_converter=lambda gateway: converter if gateway == "CTP" else None)
        rows: dict[str, list[dict[str, object]]] = {
            "positions": [
                {
                    "vt_symbol": contract.vt_symbol,
                    "direction": "short",
                    "volume": volume,
                    "today_volume": volume - yesterday_volume,
                    "yesterday_volume": yesterday_volume,
                    "frozen": 0.0,
                }
            ]
        }
        request = stage931.OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=stage931.Direction.LONG,
            type=stage931.OrderType.LIMIT,
            volume=volume,
            price=3201.0,
            offset=stage931.Offset.CLOSE,
            reference="test-stage931-offset-conversion",
        )
        return engine, rows, request

    def test_shfe_pure_today_close_is_converted_to_close_today(self) -> None:
        engine, rows, request = self._shfe_conversion_case(volume=2, yesterday_volume=0)

        result = stage931._final_offset_conversion(engine, rows, request)

        self.assertEqual(result["blockers"], [])
        self.assertEqual(
            [(child.offset, child.volume) for child in result["requests"]],
            [(stage931.Offset.CLOSETODAY, 2)],
        )

    def test_shfe_pure_yesterday_close_is_converted_to_close_yesterday(self) -> None:
        engine, rows, request = self._shfe_conversion_case(volume=2, yesterday_volume=2)

        result = stage931._final_offset_conversion(engine, rows, request)

        self.assertEqual(result["blockers"], [])
        self.assertEqual(
            [(child.offset, child.volume) for child in result["requests"]],
            [(stage931.Offset.CLOSEYESTERDAY, 2)],
        )

    def test_shfe_mixed_inventory_is_split_exactly_without_generic_close(self) -> None:
        engine, rows, request = self._shfe_conversion_case(volume=3, yesterday_volume=2)

        result = stage931._final_offset_conversion(engine, rows, request)
        children = result["requests"]

        self.assertEqual(result["blockers"], [])
        self.assertEqual(
            [(child.offset, child.volume) for child in children],
            [
                (stage931.Offset.CLOSETODAY, 1),
                (stage931.Offset.CLOSEYESTERDAY, 2),
            ],
        )
        self.assertNotIn(stage931.Offset.CLOSE, [child.offset for child in children])
        self.assertEqual(sum(float(child.volume) for child in children), request.volume)

    def test_shfe_conversion_missing_converter_fails_closed(self) -> None:
        _, rows, request = self._shfe_conversion_case(volume=1, yesterday_volume=0)
        engine = SimpleNamespace(get_converter=lambda _gateway: None)

        result = stage931._final_offset_conversion(engine, rows, request)

        self.assertEqual(result["requests"], [])
        self.assertEqual(result["blockers"], ["final_offset_converter_missing:CTP"])

    def test_atomic_send_slot_batch_counts_every_converted_child(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ledger.jsonl"
            events = [
                {
                    "intent_fingerprint": "parent",
                    "child_order_id": f"parent:{index + 1}/2",
                    "child_order_index": index,
                    "child_order_count": 2,
                }
                for index in range(2)
            ]
            reserved = stage931.reserve_execution_api_slots(
                target_date="2026-07-13",
                slot_type="send_order",
                daily_limit=2,
                base_events=events,
                path=path,
            )
            blocked = stage931.reserve_execution_api_slots(
                target_date="2026-07-13",
                slot_type="send_order",
                daily_limit=2,
                base_events=[events[0]],
                path=path,
            )
            rows = stage931.read_execution_ledger(path)

        self.assertTrue(reserved["reserved"])
        self.assertEqual(reserved["reserved_count"], 2)
        self.assertFalse(blocked["reserved"])
        self.assertEqual(
            blocked["blocker"], "ledger_daily_send_order_batch_limit_reached"
        )
        slot_rows = [row for row in rows if row.get("event_type") == "api_slot_reserved"]
        self.assertEqual(len(slot_rows), 1)
        self.assertEqual(slot_rows[0]["api_slot_reserved_count"], 2)
        self.assertEqual(
            [row["child_order_id"] for row in slot_rows[0]["api_slot_batch_children"]],
            ["parent:1/2", "parent:2/2"],
        )

    def test_physical_cycle_limit_counts_converted_children_not_parent_intents(self) -> None:
        self.assertEqual(
            stage931._converted_child_cycle_blocker(
                child_count=2,
                max_physical_orders=1,
                send_count=0,
            ),
            "final_converted_child_count_above_cycle_limit:children=2;remaining=1",
        )
        self.assertEqual(
            stage931._converted_child_cycle_blocker(
                child_count=2,
                max_physical_orders=3,
                send_count=1,
            ),
            "",
        )

    def test_stage930_one_logical_intent_allows_mixed_shfe_close_children(self) -> None:
        engine, rows, request = self._shfe_conversion_case(volume=3, yesterday_volume=2)
        conversion = stage931._final_offset_conversion(engine, rows, request)
        phase_d = stage931.build_phase_d_config()

        self.assertEqual(stage930.DEFAULT_MAX_SUBMIT_LOGICAL_INTENTS, 1)
        self.assertEqual(len(conversion["requests"]), 2)
        self.assertEqual(
            stage931._converted_child_cycle_blocker(
                child_count=len(conversion["requests"]),
                max_physical_orders=phase_d.hard_limits.max_order_count_per_cycle,
                send_count=0,
            ),
            "",
        )

    def test_future_tick_beyond_clock_skew_is_not_fresh(self) -> None:
        future = datetime.now() + timedelta(seconds=30)
        row = {"datetime": future.isoformat()}

        age = stage931._tick_age_seconds(row)

        self.assertIsNotNone(age)
        self.assertLess(age, -stage931.ALLOWED_TICK_CLOCK_SKEW_SECONDS)
        self.assertFalse(stage931._tick_age_is_fresh(age, 10))

    def test_future_tick_beyond_clock_skew_becomes_final_reprice_blocker(self) -> None:
        req = stage931.OrderRequest(
            symbol="jm2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.LONG,
            type=stage931.OrderType.LIMIT,
            volume=1,
            price=1252.0,
            offset=stage931.Offset.CLOSE,
            reference="test-future-tick",
        )
        future_tick = {
            "vt_symbol": req.vt_symbol,
            "datetime": (datetime.now() + timedelta(seconds=30)).isoformat(),
            "last_price": 1251.0,
            "bid_price_1": 1250.5,
            "ask_price_1": 1251.0,
        }
        intent = {
            "source": "stage904_c9_intraday_close",
            "vt_symbol": req.vt_symbol,
            "pricetick": 0.5,
        }
        engine = SimpleNamespace(subscribe=lambda *_args, **_kwargs: None)
        with patch.object(stage931, "_latest_fresh_tick_from_file", return_value=(None, None)):
            result = stage931._final_close_reprice(
                engine,
                {"ticks": [future_tick]},
                intent,
                req,
                max_tick_age_seconds=10,
                tick_wait_seconds=0,
            )

        self.assertEqual(
            result["final_reprice_status"],
            "skipped_no_fresh_tick_keep_stage905_price",
        )
        self.assertTrue(stage931._final_reprice_blockers(result))

    def test_converted_child_empty_send_is_audited_and_fails_closed(self) -> None:
        _, _, request = self._shfe_conversion_case(volume=1, yesterday_volume=0)
        request.offset = stage931.Offset.CLOSETODAY
        engine = SimpleNamespace(send_order=lambda _req, _gateway: "")
        args = SimpleNamespace(
            target_date="2026-07-13",
            fill_wait_seconds=0,
            trade_detail_wait_seconds=0,
            post_cancel_wait_seconds=0,
        )
        config = SimpleNamespace(
            hard_limits=SimpleNamespace(max_cancel_count_per_day=12)
        )
        ledger_events: list[dict[str, object]] = []
        with patch.object(
            stage931,
            "append_execution_ledger_event",
            side_effect=lambda event: ledger_events.append(dict(event)),
        ):
            result = stage931._submit_pre_reserved_child(
                main_engine=engine,
                rows={"trades": [], "orders": []},
                req=request,
                args=args,
                config=config,
                row={"intent_id": "intent-1", "vt_symbol": request.vt_symbol},
                fingerprint="fp",
                intent_metadata={},
                reprice_result={},
                child_index=0,
                child_count=2,
                send_slot_batch_id="batch",
            )

        self.assertEqual(result["send_called"], 1)
        self.assertTrue(result["blockers"])
        self.assertEqual(result["submitted_row"]["child_order_id"], "fp:1/2")
        self.assertEqual(
            [event["event_type"] for event in ledger_events],
            ["send_order_called", "send_order_returned_empty"],
        )
        self.assertTrue(all(event["child_order_id"] == "fp:1/2" for event in ledger_events))
        self.assertEqual(ledger_events[-1]["close_retry_unlock_eligible"], 0)
        self.assertEqual(ledger_events[-1]["req_order_insert_audit_observed"], 0)

    def test_empty_send_unlocks_once_only_with_explicit_raw_insert_nonacceptance(self) -> None:
        _, _, request = self._shfe_conversion_case(volume=1, yesterday_volume=0)
        request.offset = stage931.Offset.CLOSETODAY
        rows: dict[str, list[dict[str, object]]] = {
            "trades": [],
            "orders": [],
            "order_insert_requests": [],
        }

        def send_order(_req: object, _gateway: str) -> str:
            rows["order_insert_requests"].append(
                {"reqid": 17, "request_ret": -2, "exception": ""}
            )
            return ""

        args = SimpleNamespace(
            target_date="2026-07-13",
            fill_wait_seconds=0,
            trade_detail_wait_seconds=0,
            post_cancel_wait_seconds=0,
        )
        config = SimpleNamespace(
            hard_limits=SimpleNamespace(max_cancel_count_per_day=12)
        )
        ledger_events: list[dict[str, object]] = []
        with patch.object(
            stage931,
            "append_execution_ledger_event",
            side_effect=lambda event: ledger_events.append(dict(event)),
        ):
            result = stage931._submit_pre_reserved_child(
                main_engine=SimpleNamespace(send_order=send_order),
                rows=rows,
                req=request,
                args=args,
                config=config,
                row={"intent_id": "intent-1", "vt_symbol": request.vt_symbol},
                fingerprint="fp",
                intent_metadata={"close_submit_attempt_no": 1},
                reprice_result={},
                child_index=0,
                child_count=1,
                send_slot_batch_id="batch",
            )

        terminal = ledger_events[-1]
        self.assertTrue(result["blockers"])
        self.assertEqual(terminal["event_type"], "send_order_returned_empty")
        self.assertEqual(terminal["req_order_insert_request_ret"], -2)
        self.assertEqual(terminal["req_order_insert_accepted"], 0)
        self.assertEqual(terminal["close_retry_known_zero"], 1)
        self.assertEqual(terminal["close_retry_unlock_eligible"], 1)
        self.assertEqual(
            terminal["close_retry_known_zero_reason"],
            "req_order_insert_not_accepted",
        )

    def test_cancelled_or_rejected_zero_fill_has_versioned_retry_audit(self) -> None:
        for status, status_class in (("cancelled", "cancelled"), ("rejected", "rejected")):
            for attempt_no, expected_unlock in ((1, 1), (2, 0)):
                with self.subTest(status=status, attempt_no=attempt_no):
                    self._assert_known_zero_terminal_audit(
                        status=status,
                        status_class=status_class,
                        attempt_no=attempt_no,
                        expected_unlock=expected_unlock,
                    )

    def _assert_known_zero_terminal_audit(
        self,
        *,
        status: str,
        status_class: str,
        attempt_no: int,
        expected_unlock: int,
    ) -> None:
        rows: dict[str, list[dict[str, object]]] = {
            "trades": [],
            "orders": [],
            "order_insert_requests": [],
        }

        def send_order(_req: object, _gateway: str) -> str:
            rows["order_insert_requests"].append(
                {"reqid": 18, "request_ret": 0, "exception": ""}
            )
            rows["orders"].append(
                {
                    "gateway_name": "CTP",
                    "orderid": "1",
                    "status": status,
                    "traded": 0,
                }
            )
            return "CTP.1"

        request = stage931.OrderRequest(
            symbol="jm2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.LONG,
            type=stage931.OrderType.LIMIT,
            volume=1,
            price=100.0,
            offset=stage931.Offset.CLOSE,
            reference="test-known-zero-terminal",
        )
        args = SimpleNamespace(
            target_date="2026-07-13",
            fill_wait_seconds=0,
            trade_detail_wait_seconds=0,
            post_cancel_wait_seconds=0,
        )
        config = SimpleNamespace(
            hard_limits=SimpleNamespace(max_cancel_count_per_day=12)
        )
        ledger_events: list[dict[str, object]] = []
        with patch.object(
            stage931,
            "append_execution_ledger_event",
            side_effect=lambda event: ledger_events.append(dict(event)),
        ):
            result = stage931._submit_pre_reserved_child(
                main_engine=SimpleNamespace(send_order=send_order),
                rows=rows,
                req=request,
                args=args,
                config=config,
                row={
                    "intent_id": "intent-1",
                    "vt_symbol": request.vt_symbol,
                },
                fingerprint="fp",
                intent_metadata={"close_submit_attempt_no": attempt_no},
                reprice_result={},
                child_index=0,
                child_count=1,
                send_slot_batch_id="batch",
            )

        terminal = next(
            event
            for event in ledger_events
            if event.get("event_type") == "rejected_or_inactive"
        )
        self.assertTrue(result["blockers"])
        self.assertEqual(terminal["close_terminal_status_class"], status_class)
        self.assertEqual(terminal["order_traded_volume"], 0.0)
        self.assertEqual(terminal["trade_event_total_volume"], 0.0)
        self.assertEqual(terminal["trade_callback_count"], 0)
        self.assertEqual(terminal["close_retry_known_zero"], 1)
        self.assertEqual(terminal["close_retry_unlock_eligible"], expected_unlock)

    def test_missing_order_callback_is_unknown_never_rejected_or_inactive(self) -> None:
        rows: dict[str, list[dict[str, object]]] = {
            "trades": [],
            "orders": [],
            "order_insert_requests": [],
        }

        def send_order(_req: object, _gateway: str) -> str:
            rows["order_insert_requests"].append(
                {"reqid": 19, "request_ret": 0, "exception": ""}
            )
            return "CTP.1"

        request = stage931.OrderRequest(
            symbol="jm2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.LONG,
            type=stage931.OrderType.LIMIT,
            volume=1,
            price=100.0,
            offset=stage931.Offset.CLOSE,
            reference="test-missing-order-callback",
        )
        args = SimpleNamespace(
            target_date="2026-07-13",
            fill_wait_seconds=0,
            trade_detail_wait_seconds=0,
            post_cancel_wait_seconds=0,
        )
        config = SimpleNamespace(
            hard_limits=SimpleNamespace(max_cancel_count_per_day=12)
        )
        ledger_events: list[dict[str, object]] = []
        with (
            patch.object(stage931, "_wait_order_completion", return_value={}),
            patch.object(
                stage931,
                "reserve_execution_api_slot",
                return_value={"reserved": False, "blocker": "cancel_gate_blocked"},
            ),
            patch.object(
                stage931,
                "append_execution_ledger_event",
                side_effect=lambda event: ledger_events.append(dict(event)),
            ),
        ):
            result = stage931._submit_pre_reserved_child(
                main_engine=SimpleNamespace(send_order=send_order),
                rows=rows,
                req=request,
                args=args,
                config=config,
                row={"intent_id": "intent-1", "vt_symbol": request.vt_symbol},
                fingerprint="fp",
                intent_metadata={"close_submit_attempt_no": 1},
                reprice_result={},
                child_index=0,
                child_count=1,
                send_slot_batch_id="batch",
            )

        self.assertTrue(result["blockers"])
        self.assertFalse(
            any(
                event.get("event_type") == "rejected_or_inactive"
                for event in ledger_events
            )
        )
        self.assertTrue(
            any(
                event.get("event_type") == "api_slot_reservation_blocked"
                for event in ledger_events
            )
        )

    def test_trade_callbacks_are_deduplicated_by_vt_tradeid(self) -> None:
        rows = [
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t1", "volume": 1, "price": 1245.0},
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t1", "volume": 1, "price": 1245.0},
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t2", "volume": 1, "price": 1246.0},
            {"vt_orderid": "CTP.2", "vt_tradeid": "CTP.other", "volume": 9, "price": 999.0},
        ]
        details = stage931._trade_delta_details(rows, 0, "CTP.1")
        self.assertEqual(details["volume"], 2.0)
        self.assertEqual(details["vwap"], 1245.5)
        self.assertEqual(details["identities"], ["vt:CTP.t1", "vt:CTP.t2"])

    def test_mixed_priced_and_unpriced_trade_callbacks_remain_pending_and_idempotent(self) -> None:
        rows = [
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t1", "volume": 1, "price": 100.0},
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t2", "volume": 1, "price": 0.0},
            # Duplicate callbacks must not increase either total or priced volume.
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t1", "volume": 1, "price": 100.0},
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t2", "volume": 1, "price": 0.0},
        ]

        details = stage931._trade_delta_details(rows, 0, "CTP.1")
        priced_vwap_volume, priced_vwap, _ = stage931._trade_delta_vwap(
            rows,
            0,
            "CTP.1",
        )
        state = stage931._fill_reconciliation_state(
            order_traded_volume=2.0,
            trade_event_volume=details["priced_volume"],
            trade_event_total_volume=details["total_volume"],
            requested_volume=2.0,
        )

        self.assertEqual(details["total_volume"], 2.0)
        self.assertEqual(details["priced_volume"], 1.0)
        self.assertEqual(details["unpriced_volume"], 1.0)
        self.assertEqual(details["vwap"], 100.0)
        self.assertEqual(details["priced_identities"], ["vt:CTP.t1"])
        self.assertEqual(priced_vwap_volume, 1.0)
        self.assertEqual(priced_vwap, 100.0)
        self.assertTrue(state["pending"])
        self.assertEqual(state["effective_traded_volume"], 2.0)
        self.assertEqual(state["unpriced_volume"], 1.0)
        self.assertEqual(state["residual_volume"], 0.0)

    def test_mixed_trade_submit_ledgers_only_priced_volume_and_fails_closed(self) -> None:
        rows: dict[str, list[dict[str, object]]] = {"trades": [], "orders": []}

        def send_order(_request: object, _gateway: str) -> str:
            rows["orders"].append(
                {
                    "gateway_name": "CTP",
                    "orderid": "1",
                    "status": "all traded",
                    "traded": 2,
                }
            )
            rows["trades"].extend(
                [
                    {
                        "vt_orderid": "CTP.1",
                        "vt_tradeid": "CTP.t1",
                        "volume": 1,
                        "price": 100.0,
                    },
                    {
                        "vt_orderid": "CTP.1",
                        "vt_tradeid": "CTP.t2",
                        "volume": 1,
                        "price": 0.0,
                    },
                    # Duplicate callbacks exercise runtime idempotence.
                    {
                        "vt_orderid": "CTP.1",
                        "vt_tradeid": "CTP.t1",
                        "volume": 1,
                        "price": 100.0,
                    },
                    {
                        "vt_orderid": "CTP.1",
                        "vt_tradeid": "CTP.t2",
                        "volume": 1,
                        "price": 0.0,
                    },
                ]
            )
            return "CTP.1"

        request = stage931.OrderRequest(
            symbol="jm2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.SHORT,
            type=stage931.OrderType.LIMIT,
            volume=2,
            price=100.0,
            offset=stage931.Offset.OPEN,
            reference="test-mixed-fill",
        )
        engine = SimpleNamespace(send_order=send_order)
        args = SimpleNamespace(
            target_date="2026-07-13",
            fill_wait_seconds=0,
            trade_detail_wait_seconds=0,
            post_cancel_wait_seconds=0,
        )
        config = SimpleNamespace(
            hard_limits=SimpleNamespace(max_cancel_count_per_day=12)
        )
        ledger_events: list[dict[str, object]] = []
        with patch.object(
            stage931,
            "append_execution_ledger_event",
            side_effect=lambda event: ledger_events.append(dict(event)),
        ):
            result = stage931._submit_pre_reserved_child(
                main_engine=engine,
                rows=rows,
                req=request,
                args=args,
                config=config,
                row={"intent_id": "intent-1", "vt_symbol": request.vt_symbol},
                fingerprint="fp",
                intent_metadata={},
                reprice_result={},
                child_index=0,
                child_count=1,
                send_slot_batch_id="batch",
            )

        priced_fills = [
            event
            for event in ledger_events
            if event.get("event_type") == "filled_or_part_filled"
        ]
        pending = [
            event
            for event in ledger_events
            if event.get("event_type") == "fill_reconciliation_pending"
        ]
        self.assertEqual(len(priced_fills), 1)
        self.assertEqual(priced_fills[0]["trade_volume_delta"], 1.0)
        self.assertEqual(priced_fills[0]["price"], 100.0)
        self.assertEqual(priced_fills[0]["trade_identities"], ["vt:CTP.t1"])
        self.assertEqual(priced_fills[0]["unpriced_volume"], 1.0)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["trade_event_priced_volume"], 1.0)
        self.assertEqual(pending[0]["trade_event_total_volume"], 2.0)
        self.assertEqual(pending[0]["unpriced_volume"], 1.0)
        self.assertEqual(
            result["adapter_status"],
            "adapter_blocked_fill_reconciliation_pending",
        )
        self.assertEqual(result["submitted_row"]["trade_event_priced_volume_delta"], 1.0)
        self.assertEqual(result["submitted_row"]["trade_event_total_volume_delta"], 2.0)
        self.assertEqual(result["submitted_row"]["unpriced_volume"], 1.0)
        self.assertEqual(result["submitted_row"]["fill_price_volume"], 1.0)
        self.assertEqual(
            result["submitted_row"]["fill_price_scope"],
            "priced_event_trade_volume_only",
        )

    def test_final_trade_snapshot_ledgers_priced_callback_arriving_at_grace_boundary(self) -> None:
        rows: dict[str, list[dict[str, object]]] = {"trades": [], "orders": []}

        def send_order(_request: object, _gateway: str) -> str:
            rows["orders"].append(
                {
                    "gateway_name": "CTP",
                    "orderid": "1",
                    "status": "all traded",
                    "traded": 2,
                }
            )
            rows["trades"].append(
                {
                    "vt_orderid": "CTP.1",
                    "vt_tradeid": "CTP.t1",
                    "volume": 1,
                    "price": 100.0,
                }
            )
            return "CTP.1"

        def grace_boundary(
            trade_rows: list[dict[str, object]],
            start_trade_count: int,
            vt_orderid: str,
            _expected_volume: float,
            _deadline: float,
            **_kwargs: object,
        ) -> dict[str, object]:
            # Capture the grace result first, then emulate the second callback
            # arriving exactly as the wait returns.  The final snapshot must
            # ledger this identity once, including the duplicate callback.
            grace_result = stage931._trade_delta_details(
                trade_rows,
                start_trade_count,
                vt_orderid,
            )
            late = {
                "vt_orderid": "CTP.1",
                "vt_tradeid": "CTP.t2",
                "volume": 1,
                "price": 101.0,
            }
            trade_rows.extend([late, dict(late)])
            return grace_result

        request = stage931.OrderRequest(
            symbol="jm2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.LONG,
            type=stage931.OrderType.LIMIT,
            volume=2,
            price=101.0,
            offset=stage931.Offset.CLOSE,
            reference="test-final-fill-boundary",
        )
        args = SimpleNamespace(
            target_date="2026-07-13",
            fill_wait_seconds=0,
            trade_detail_wait_seconds=0,
            post_cancel_wait_seconds=0,
        )
        config = SimpleNamespace(
            hard_limits=SimpleNamespace(max_cancel_count_per_day=12)
        )
        ledger_events: list[dict[str, object]] = []
        with (
            patch.object(stage931, "_wait_trade_details", side_effect=grace_boundary),
            patch.object(
                stage931,
                "append_execution_ledger_event",
                side_effect=lambda event: ledger_events.append(dict(event)),
            ),
        ):
            result = stage931._submit_pre_reserved_child(
                main_engine=SimpleNamespace(send_order=send_order),
                rows=rows,
                req=request,
                args=args,
                config=config,
                row={"intent_id": "close-1", "vt_symbol": request.vt_symbol},
                fingerprint="fp-close",
                intent_metadata={},
                reprice_result={},
                child_index=0,
                child_count=1,
                send_slot_batch_id="batch",
            )

        priced_fills = [
            event
            for event in ledger_events
            if event.get("event_type") == "filled_or_part_filled"
        ]
        self.assertEqual(
            [event["trade_volume_delta"] for event in priced_fills],
            [1.0, 1.0],
        )
        self.assertEqual(
            [event["trade_identities"] for event in priced_fills],
            [["vt:CTP.t1"], ["vt:CTP.t2"]],
        )
        self.assertEqual(len({event["trade_fill_key"] for event in priced_fills}), 2)
        self.assertEqual(priced_fills[-1]["late_fill_at_final_reconciliation"], 1)
        self.assertFalse(
            any(
                event.get("event_type") == "fill_reconciliation_pending"
                for event in ledger_events
            )
        )
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["submitted_row"]["trade_event_priced_volume_delta"], 2.0)
        self.assertEqual(result["submitted_row"]["unpriced_volume"], 0.0)
        self.assertEqual(result["submitted_row"]["fill_price"], 100.5)

    def test_late_trade_rows_can_be_isolated_from_initial_snapshot(self) -> None:
        initial = [
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t1", "volume": 1, "price": 1245.0},
        ]
        initial_details = stage931._trade_delta_details(initial, 0, "CTP.1")
        post = initial + [
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t1", "volume": 1, "price": 1245.0},
            {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.t2", "volume": 1, "price": 1247.0},
        ]
        post_details = stage931._trade_delta_details(post, 0, "CTP.1")
        initial_ids = set(initial_details["identities"])
        late_rows = [
            row
            for identity, row in zip(post_details["identities"], post_details["rows"])
            if identity not in initial_ids
        ]
        volume, vwap = stage931._trade_rows_vwap(late_rows)
        self.assertEqual(post_details["volume"], 2.0)
        self.assertEqual(volume, 1.0)
        self.assertEqual(vwap, 1247.0)

    def test_stage931_outputs_use_atomic_replace_and_durable_summary_fsync(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary_path = root / "summary.json"
            csv_path = root / "orders.csv"
            original_replace = stage931.os.replace
            original_fsync = stage931.os.fsync
            with (
                patch.object(stage931.os, "replace", wraps=original_replace) as replace,
                patch.object(stage931.os, "fsync", wraps=original_fsync) as fsync,
            ):
                stage931._atomic_write_text(
                    summary_path,
                    '{"status":"ok"}',
                    durable=True,
                )
                stage931._write_df(csv_path, [{"orderid": "1", "status": "filled"}])

            self.assertEqual(summary_path.read_text(encoding="utf-8"), '{"status":"ok"}')
            written = pd.read_csv(csv_path, encoding="utf-8-sig")
            self.assertEqual(written.to_dict(orient="records"), [{"orderid": 1, "status": "filled"}])
            self.assertEqual(replace.call_count, 2)
            for call in replace.call_args_list:
                source, destination = (Path(value) for value in call.args)
                self.assertEqual(source.parent, destination.parent)
                self.assertNotEqual(source, destination)
                self.assertFalse(source.exists())
            # Durable summary: temporary file fsync plus destination-directory fsync.
            self.assertEqual(fsync.call_count, 2)

    def test_trade_detail_grace_waits_for_callback_after_order_fill(self) -> None:
        rows: list[dict[str, object]] = []
        clock = [0.0]

        def now() -> float:
            return clock[0]

        def sleep(seconds: float) -> None:
            clock[0] += seconds
            if clock[0] >= 0.2 and not rows:
                rows.append(
                    {"vt_orderid": "CTP.1", "vt_tradeid": "CTP.late", "volume": 2, "price": 1245.5}
                )

        details = stage931._wait_trade_details(
            rows,
            0,
            "CTP.1",
            2.0,
            1.0,
            clock=now,
            sleeper=sleep,
        )

        self.assertEqual(details["volume"], 2.0)
        self.assertEqual(details["vwap"], 1245.5)
        self.assertLess(clock[0], 1.0)

    def test_cycle_metadata_is_propagated_to_every_ledger_context(self) -> None:
        metadata = stage931._intent_ledger_metadata(
            {
                "root_position_id": "root",
                "position_epoch_id": "epoch-1",
                "position_cycle_id": "root:cycle1",
                "position_cycle_no": 1,
                "intent_role": "c9_retry_failed_stop_close",
                "strategy_entry_price": 1245.5,
                "strategy_stop_price": 1251.75,
                "unused": "ignored",
            }
        )
        self.assertEqual(metadata["root_position_id"], "root")
        self.assertEqual(metadata["position_epoch_id"], "epoch-1")
        self.assertEqual(metadata["position_cycle_id"], "root:cycle1")
        self.assertEqual(metadata["intent_role"], "c9_retry_failed_stop_close")
        self.assertNotIn("unused", metadata)

    def test_aggregate_fill_keys_are_stable_and_phase_distinct(self) -> None:
        identities = ["vt:CTP.t2", "vt:CTP.t1"]
        first = stage931._aggregate_trade_fill_key("CTP.1", identities, "initial")
        self.assertEqual(first, stage931._aggregate_trade_fill_key("CTP.1", list(reversed(identities)), "initial"))
        self.assertNotEqual(first, stage931._aggregate_trade_fill_key("CTP.1", identities, "post_cancel"))

    @staticmethod
    def _retry_request(*, price: float = 1245.5, direction: str = "short") -> SimpleNamespace:
        return SimpleNamespace(
            price=price,
            direction=SimpleNamespace(value=direction),
            offset=SimpleNamespace(value="open"),
            vt_symbol="jm2609.DCE",
        )

    @staticmethod
    def _retry_intent() -> dict[str, object]:
        return {
            "source": "stage904_c9_intraday_retry_open",
            "vt_symbol": "jm2609.DCE",
            "pricetick": 0.5,
            "retry_trigger_price": 1245.5,
            "strategy_entry_price": 1245.5,
        }

    def test_retry_open_is_blocked_when_latest_tick_loses_reclaim_condition(self) -> None:
        req = self._retry_request()
        tick = {"last_price": 1245.0, "bid_price_1": 1246.0, "ask_price_1": 1246.5}
        with patch.object(stage931, "_subscribe_and_wait_fresh_tick", return_value=(tick, 0.1, "test_tick")):
            result = stage931._final_close_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                tick_wait_seconds=0,
            )

        self.assertEqual(result["final_reprice_status"], "blocked_retry_reclaim_no_longer_favorable")
        self.assertEqual(req.price, 1245.5)
        self.assertTrue(stage931._final_reprice_blockers(result))

    def test_retry_open_uses_executable_quote_not_last_price_for_reclaim(self) -> None:
        req = self._retry_request()
        tick = {"last_price": 1246.0, "bid_price_1": 1245.5, "ask_price_1": 1246.0}
        with patch.object(stage931, "_subscribe_and_wait_fresh_tick", return_value=(tick, 0.1, "test_tick")):
            result = stage931._final_close_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                tick_wait_seconds=0,
            )

        self.assertEqual(result["final_reprice_status"], "applied")
        self.assertLessEqual(req.price, tick["bid_price_1"])

    def test_long_retry_open_uses_ask_for_reclaim_and_pricing(self) -> None:
        req = self._retry_request(direction="long")
        tick = {"last_price": 1246.0, "bid_price_1": 1245.0, "ask_price_1": 1245.5}
        with patch.object(stage931, "_subscribe_and_wait_fresh_tick", return_value=(tick, 0.1, "test_tick")):
            result = stage931._final_close_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                tick_wait_seconds=0,
            )

        self.assertEqual(result["final_reprice_status"], "applied")
        self.assertGreaterEqual(req.price, tick["ask_price_1"])

    def test_retry_open_uses_marketable_price_when_latest_tick_remains_favorable(self) -> None:
        req = self._retry_request()
        tick = {"last_price": 1245.0, "bid_price_1": 1244.5, "ask_price_1": 1245.0}
        with patch.object(stage931, "_subscribe_and_wait_fresh_tick", return_value=(tick, 0.1, "test_tick")):
            result = stage931._final_close_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                tick_wait_seconds=0,
            )

        self.assertEqual(result["final_reprice_status"], "applied")
        self.assertLessEqual(req.price, tick["bid_price_1"])
        self.assertEqual(stage931._final_reprice_blockers(result), [])

    def test_post_snapshot_retry_reprice_blocks_reclaim_lost_during_queries(self) -> None:
        req = self._retry_request()
        before_queries = {
            "last_price": 1245.0,
            "bid_price_1": 1245.0,
            "ask_price_1": 1245.5,
        }
        after_q2 = {
            "last_price": 1246.0,
            "bid_price_1": 1246.0,
            "ask_price_1": 1246.5,
        }
        with patch.object(
            stage931,
            "_subscribe_and_wait_fresh_tick",
            side_effect=[
                (before_queries, 0.1, "pre_snapshot_tick"),
                (after_q2, 0.1, "post_q2_tick"),
            ],
        ):
            warmup = stage931._final_close_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                tick_wait_seconds=2,
            )
            final = stage931._post_snapshot_final_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                q2_completed_monotonic=100.0,
                tick_wait_seconds=2,
            )

        self.assertEqual(warmup["final_reprice_status"], "applied")
        self.assertEqual(
            final["final_reprice_status"],
            "blocked_retry_reclaim_no_longer_favorable",
        )
        self.assertEqual(final["post_sandwich_reprice"], 1)
        self.assertTrue(stage931._final_reprice_blockers(final))

    def test_post_snapshot_retry_reprice_uses_quote_observed_after_q2(self) -> None:
        req = self._retry_request()
        before_queries = {
            "last_price": 1245.0,
            "bid_price_1": 1245.0,
            "ask_price_1": 1245.5,
        }
        after_q2 = {
            "last_price": 1244.0,
            "bid_price_1": 1244.0,
            "ask_price_1": 1244.5,
        }
        with patch.object(
            stage931,
            "_subscribe_and_wait_fresh_tick",
            side_effect=[
                (before_queries, 0.1, "pre_snapshot_tick"),
                (after_q2, 0.1, "post_q2_tick"),
            ],
        ):
            warmup = stage931._final_close_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                tick_wait_seconds=2,
            )
            warmup_price = req.price
            final = stage931._post_snapshot_final_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                q2_completed_monotonic=100.0,
                tick_wait_seconds=2,
            )

        self.assertEqual(warmup["final_reprice_status"], "applied")
        self.assertEqual(final["final_reprice_status"], "applied")
        self.assertEqual(final["final_reprice_source"], "post_q2_tick")
        self.assertEqual(final["post_sandwich_reprice"], 1)
        self.assertNotEqual(req.price, warmup_price)
        self.assertEqual(req.price, final["final_reprice_price_after"])
        self.assertLessEqual(req.price, after_q2["bid_price_1"])

    def test_post_snapshot_reprice_rejects_pre_q2_only_tick_without_file_fallback(self) -> None:
        req = self._retry_request()
        pre_q2_tick = {
            "vt_symbol": req.vt_symbol,
            "datetime": datetime.now().isoformat(),
            "received_monotonic": 99.9,
            "last_price": 1245.0,
            "bid_price_1": 1245.0,
            "ask_price_1": 1245.5,
        }
        engine = SimpleNamespace(subscribe=lambda *_args, **_kwargs: None)
        with patch.object(
            stage931,
            "_latest_fresh_tick_from_file",
            side_effect=AssertionError("post-Q2 gate must not use file fallback"),
        ):
            final = stage931._post_snapshot_final_reprice(
                engine,
                {"ticks": [pre_q2_tick]},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                q2_completed_monotonic=100.0,
                tick_wait_seconds=0,
            )

        self.assertEqual(
            final["final_reprice_status"],
            "skipped_no_fresh_tick_keep_stage905_price",
        )
        self.assertEqual(final["final_reprice_tick_file_fallback_allowed"], 0)
        self.assertTrue(stage931._final_reprice_blockers(final))

    def test_post_snapshot_reprice_requires_tick_strictly_after_q2(self) -> None:
        req = self._retry_request()
        equal_boundary_tick = {
            "vt_symbol": req.vt_symbol,
            "datetime": datetime.now().isoformat(),
            "received_monotonic": 100.0,
            "last_price": 1245.0,
            "bid_price_1": 1245.0,
            "ask_price_1": 1245.5,
        }
        engine = SimpleNamespace(subscribe=lambda *_args, **_kwargs: None)

        final = stage931._post_snapshot_final_reprice(
            engine,
            {"ticks": [equal_boundary_tick]},
            self._retry_intent(),
            req,
            max_tick_age_seconds=3,
            q2_completed_monotonic=100.0,
            tick_wait_seconds=0,
        )

        self.assertEqual(
            final["final_reprice_status"],
            "skipped_no_fresh_tick_keep_stage905_price",
        )
        self.assertTrue(stage931._final_reprice_blockers(final))

    def test_event_engine_backlog_cannot_redate_pre_q2_tick_for_retry_or_close(self) -> None:
        """The causal stamp belongs at gateway ingress, not consumer time."""

        rows: dict[str, list[dict[str, object]]] = {"ticks": []}
        blocker_entered = threading.Event()
        release_blocker = threading.Event()
        collector_finished = threading.Event()
        engine = EventEngine()

        def blocking_handler(_event: Event) -> None:
            blocker_entered.set()
            if not release_blocker.wait(timeout=2):
                raise TimeoutError("test_did_not_release_event_engine_backlog")

        def collecting_handler(event: Event) -> None:
            rows["ticks"].append(stage931._tick_event_row(event.data))
            collector_finished.set()

        engine.register(stage931.EVENT_TICK, blocking_handler)
        engine.register(stage931.EVENT_TICK, collecting_handler)
        engine.start()
        try:
            tick = SimpleNamespace(
                vt_symbol="jm2609.DCE",
                datetime=datetime.now(),
                last_price=1245.0,
                bid_price_1=1245.0,
                ask_price_1=1245.5,
            )
            stage931._stamp_tick_before_event_enqueue(tick)
            engine.put(Event(stage931.EVENT_TICK, tick))
            self.assertTrue(blocker_entered.wait(timeout=2))

            # Q2 completes while EVENT_TICK is already queued but its later
            # Stage931 consumer remains blocked behind another handler.
            q2_completed_monotonic = time.monotonic()
            release_blocker.set()
            self.assertTrue(collector_finished.wait(timeout=2))
        finally:
            release_blocker.set()
            engine.stop()

        collected = rows["ticks"][0]
        self.assertLess(
            float(collected["received_monotonic"]), q2_completed_monotonic
        )
        self.assertGreaterEqual(
            float(collected["handler_received_monotonic"]),
            q2_completed_monotonic,
        )

        engine_stub = SimpleNamespace(subscribe=lambda *_args, **_kwargs: None)
        retry_request = self._retry_request()
        close_request = SimpleNamespace(
            price=1252.0,
            direction=SimpleNamespace(value="long"),
            offset=SimpleNamespace(value="close"),
            vt_symbol="jm2609.DCE",
        )
        close_intent = {
            "source": "stage904_c9_intraday_close",
            "vt_symbol": "jm2609.DCE",
            "pricetick": 0.5,
        }
        with patch.object(
            stage931,
            "_latest_fresh_tick_from_file",
            side_effect=AssertionError("post-Q2 gate must not use file fallback"),
        ):
            retry_result = stage931._post_snapshot_final_reprice(
                engine_stub,
                rows,
                self._retry_intent(),
                retry_request,
                max_tick_age_seconds=3,
                q2_completed_monotonic=q2_completed_monotonic,
                tick_wait_seconds=0,
            )
            close_result = stage931._post_snapshot_final_reprice(
                engine_stub,
                rows,
                close_intent,
                close_request,
                max_tick_age_seconds=3,
                q2_completed_monotonic=q2_completed_monotonic,
                tick_wait_seconds=0,
            )

        for result in (retry_result, close_result):
            self.assertEqual(
                result["final_reprice_status"],
                "skipped_no_fresh_tick_keep_stage905_price",
            )
            self.assertTrue(stage931._final_reprice_blockers(result))

    def test_post_snapshot_reprice_accepts_only_event_tick_at_or_after_q2(self) -> None:
        req = self._retry_request()
        rows = {
            "ticks": [
                {
                    "vt_symbol": req.vt_symbol,
                    "datetime": datetime.now().isoformat(),
                    "received_monotonic": 100.1,
                    "last_price": 1244.0,
                    "bid_price_1": 1244.0,
                    "ask_price_1": 1244.5,
                }
            ]
        }
        engine = SimpleNamespace(subscribe=lambda *_args, **_kwargs: None)

        final = stage931._post_snapshot_final_reprice(
            engine,
            rows,
            self._retry_intent(),
            req,
            max_tick_age_seconds=3,
            q2_completed_monotonic=100.0,
            tick_wait_seconds=0,
        )

        self.assertEqual(final["final_reprice_status"], "applied")
        self.assertEqual(final["final_reprice_source"], "ctp_event_tick")
        self.assertEqual(final["final_reprice_tick_file_fallback_allowed"], 0)

    def test_retry_open_without_fresh_tick_fails_closed(self) -> None:
        req = self._retry_request()
        with (
            patch.object(stage931, "_subscribe_and_wait_fresh_tick", return_value=(None, None, "no_test_tick")),
            patch.object(stage931, "_latest_fresh_tick_from_file", return_value=(None, None)),
        ):
            result = stage931._final_close_reprice(
                SimpleNamespace(),
                {"ticks": []},
                self._retry_intent(),
                req,
                max_tick_age_seconds=3,
                tick_wait_seconds=0,
            )

        self.assertEqual(result["final_reprice_status"], "skipped_no_fresh_tick_keep_stage905_price")
        self.assertTrue(stage931._final_reprice_blockers(result))

    def test_retry_open_missing_or_crossed_executable_quote_fails_closed(self) -> None:
        for tick, expected in (
            ({"last_price": 1245.0, "bid_price_1": 1245.0}, "blocked_retry_reclaim_executable_quote_missing"),
            (
                {"last_price": 1245.0, "bid_price_1": 1245.5, "ask_price_1": 1245.0},
                "blocked_retry_reclaim_crossed_quote",
            ),
        ):
            with self.subTest(expected=expected):
                req = self._retry_request()
                with patch.object(stage931, "_subscribe_and_wait_fresh_tick", return_value=(tick, 0.1, "test_tick")):
                    result = stage931._final_close_reprice(
                        SimpleNamespace(),
                        {"ticks": []},
                        self._retry_intent(),
                        req,
                        max_tick_age_seconds=3,
                        tick_wait_seconds=0,
                    )
                self.assertEqual(result["final_reprice_status"], expected)
                self.assertTrue(stage931._final_reprice_blockers(result))

    def test_order_reported_fill_without_trade_detail_is_reconciliation_blocker(self) -> None:
        state = stage931._fill_reconciliation_state(
            order_traded_volume=1.0,
            trade_event_volume=0.0,
            requested_volume=2.0,
        )
        self.assertTrue(state["pending"])
        self.assertEqual(state["blocker"], "fill_reconciliation_pending")
        self.assertEqual(state["unpriced_volume"], 1.0)
        self.assertEqual(state["residual_volume"], 1.0)

        reconciled = stage931._fill_reconciliation_state(
            order_traded_volume=1.0,
            trade_event_volume=1.0,
            requested_volume=2.0,
        )
        self.assertFalse(reconciled["pending"])

    def test_order_traded_observation_never_rolls_back_after_cancel(self) -> None:
        self.assertEqual(
            stage931._monotonic_order_traded_volume({"traded": 0.0}, 1.0),
            1.0,
        )

    def test_daily_slot_gate_allows_eleven_and_blocks_twelve(self) -> None:
        self.assertEqual(
            stage931._ledger_daily_slot_blockers(
                {"send_order_slot_usage": 11, "cancel_order_slot_usage": 11},
                max_send_orders=12,
                max_cancel_orders=12,
            ),
            [],
        )
        self.assertEqual(
            stage931._ledger_daily_slot_blockers(
                {"send_order_slot_usage": 12, "cancel_order_slot_usage": 12},
                max_send_orders=12,
                max_cancel_orders=12,
            ),
            ["ledger_daily_send_order_limit_reached", "ledger_daily_cancel_order_limit_reached"],
        )

    def test_reduce_close_only_ignores_unrelated_blocked_open_but_checks_global_counts(self) -> None:
        intents = pd.DataFrame(
            [
                {
                    "intent_id": "close-1",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "executor_status": "dry_run_order_request_payload_ready",
                },
                {
                    "intent_id": "open-1",
                    "source": "stage904_c9_intraday_retry_open",
                    "offset": "open",
                    "executor_status": "blocked",
                },
            ]
        )
        summary = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_date": "2026-07-13",
            "executor_status": "executor_dry_run_blocked",
            "intent_count": 2,
            "ready_count": 1,
            "blocked_count": 1,
            "skipped_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
        }

        blockers = stage931._stage905_snapshot_blockers(
            summary,
            intents,
            target_date="2026-07-13",
            max_age_seconds=180,
            reduce_close_only=True,
        )
        self.assertEqual(blockers, [])

        ready_open_intents = intents.copy()
        ready_open_intents.loc[ready_open_intents["intent_id"].eq("open-1"), "executor_status"] = (
            "dry_run_order_request_payload_ready"
        )
        ready_open_summary = dict(
            summary,
            executor_status="executor_dry_run_ready",
            ready_count=2,
            blocked_count=0,
        )
        blockers = stage931._stage905_snapshot_blockers(
            ready_open_summary,
            ready_open_intents,
            target_date="2026-07-13",
            max_age_seconds=180,
            reduce_close_only=True,
        )
        self.assertEqual(blockers, [])

        inconsistent = dict(summary, ready_count=2)
        blockers = stage931._stage905_snapshot_blockers(
            inconsistent,
            intents,
            target_date="2026-07-13",
            max_age_seconds=180,
            reduce_close_only=True,
        )
        self.assertIn("stage905_ready_count_mismatch:2!=1", blockers)

        blocked_close_intents = intents.copy()
        blocked_close_intents.loc[blocked_close_intents["intent_id"].eq("close-1"), "executor_status"] = "blocked"
        blocked_close_summary = dict(
            summary,
            executor_status="executor_dry_run_blocked",
            ready_count=0,
            blocked_count=2,
        )
        blockers = stage931._stage905_snapshot_blockers(
            blocked_close_summary,
            blocked_close_intents,
            target_date="2026-07-13",
            max_age_seconds=180,
            reduce_close_only=True,
        )
        self.assertIn("stage905_no_ready_stage904_close_intent", blockers)
        self.assertIn("stage905_close_scope_nonready_count=1", blockers)

    def test_multiple_protective_closes_are_deterministically_deferred_not_globally_blocked(self) -> None:
        ready = pd.DataFrame(
            [
                {
                    "intent_id": "close-b",
                    "action_id": "b",
                    "vt_symbol": "RB2610.SHFE",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "checked_at": "2026-07-13 21:00:02",
                },
                {
                    "intent_id": "close-a",
                    "action_id": "a",
                    "vt_symbol": "JM2609.DCE",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "checked_at": "2026-07-13 21:00:01",
                },
            ]
        )

        selected, deferred, blocker = stage931._bound_ready_intents_for_cycle(
            ready,
            max_orders=1,
            reduce_close_only=True,
        )

        self.assertEqual(blocker, "")
        self.assertEqual(selected["intent_id"].tolist(), ["close-a"])
        self.assertEqual(deferred["intent_id"].tolist(), ["close-b"])

        unbounded, _, blocker = stage931._bound_ready_intents_for_cycle(
            ready.assign(source="stage901_pending_order", offset="open"),
            max_orders=1,
            reduce_close_only=False,
        )
        self.assertEqual(len(unbounded), 2)
        self.assertEqual(blocker, "ready_intent_count_above_limit")

    def test_stale_filled_close_does_not_starve_another_ready_symbol(self) -> None:
        ready = pd.DataFrame(
            [
                {
                    "intent_id": "already-filled",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "order_request_json": "{}",
                },
                {
                    "intent_id": "still-needs-close",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "order_request_json": "{}",
                },
            ]
        )

        def duplicate(**kwargs: object) -> tuple[str, str, dict, dict | None]:
            row = kwargs["row"]
            assert isinstance(row, dict)
            blocker = (
                "ledger_duplicate_close_intent:filled_or_part_filled"
                if row["intent_id"] == "already-filled"
                else ""
            )
            return blocker, "fingerprint", {}, None

        with patch.object(stage931, "duplicate_blocker", side_effect=duplicate):
            eligible, skipped = stage931._drop_terminal_duplicate_close_intents(
                ready,
                ledger_rows=[],
                target_date="2026-07-13",
                close_retry_after_cancel_seconds=30,
                reduce_close_only=True,
            )

        self.assertEqual(eligible["intent_id"].tolist(), ["still-needs-close"])
        self.assertEqual(skipped["intent_id"].tolist(), ["already-filled"])
        self.assertEqual(
            skipped["ledger_preselection_blocker"].tolist(),
            ["ledger_duplicate_close_intent:filled_or_part_filled"],
        )

    def test_nonretryable_close_fingerprint_does_not_starve_next_symbol(self) -> None:
        ready = pd.DataFrame(
            [
                {
                    "intent_id": "blocked-first",
                    "action_id": "a",
                    "checked_at": "2026-07-13 21:00:01",
                    "vt_symbol": "JM2609.DCE",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "order_request_json": "{}",
                },
                {
                    "intent_id": "healthy-second",
                    "action_id": "b",
                    "checked_at": "2026-07-13 21:00:02",
                    "vt_symbol": "RB2610.SHFE",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "order_request_json": "{}",
                },
            ]
        )
        permanent_suffixes = (
            "unknown_order_status_after_send",
            "residual_order_active_after_cancel",
            "residual_order_unknown_after_cancel",
            "fill_reconciliation_pending",
            "known_zero_retry_limit_reached",
        )
        for suffix in permanent_suffixes:
            with self.subTest(blocker=suffix):
                blocker = f"ledger_duplicate_close_intent:{suffix}"

                def duplicate(**kwargs: object) -> tuple[str, str, dict, dict]:
                    row = kwargs["row"]
                    assert isinstance(row, dict)
                    if row["intent_id"] == "blocked-first":
                        return blocker, "fingerprint-a", {}, {"event_type": suffix}
                    return "", "fingerprint-b", {}, {}

                with patch.object(stage931, "duplicate_blocker", side_effect=duplicate):
                    eligible, nonretryable = (
                        stage931._drop_terminal_duplicate_close_intents(
                            ready,
                            ledger_rows=[],
                            target_date="2026-07-13",
                            close_retry_after_cancel_seconds=30,
                            reduce_close_only=True,
                        )
                    )
                selected, deferred, limit_blocker = (
                    stage931._bound_ready_intents_for_cycle(
                        eligible,
                        max_orders=1,
                        reduce_close_only=True,
                    )
                )

                self.assertEqual(limit_blocker, "")
                self.assertEqual(selected["intent_id"].tolist(), ["healthy-second"])
                self.assertTrue(deferred.empty)
                self.assertEqual(
                    nonretryable["intent_id"].tolist(), ["blocked-first"]
                )
                self.assertEqual(
                    nonretryable["ledger_preselection_blocker"].tolist(),
                    [blocker],
                )
                self.assertEqual(
                    nonretryable["ledger_preselection_evidence_event"].tolist(),
                    [suffix],
                )

        # Skipping A at preselection never weakens the later authoritative
        # global O-P-O gate for B.
        request = stage931.OrderRequest(
            symbol="RB2610",
            exchange=stage931.Exchange.SHFE,
            direction=stage931.Direction.LONG,
            type=stage931.OrderType.LIMIT,
            volume=1,
            price=3201.0,
            offset=stage931.Offset.CLOSE,
            reference="test-starvation-global-gate",
        )
        final_blockers = stage931._final_pre_send_blockers(
            {
                "positions": [
                    {
                        "vt_symbol": request.vt_symbol,
                        "direction": "short",
                        "volume": 1,
                        "frozen": 0,
                    }
                ]
            },
            request,
            request.vt_symbol,
            authoritative_active_orders=[{"vt_orderid": "CTP.A"}],
            order_query_confirmed=True,
        )
        self.assertIn("final_order_query_active_order_count=1", final_blockers)

    def test_transient_or_global_close_blocker_is_not_skipped_for_throughput(self) -> None:
        ready = pd.DataFrame(
            [
                {
                    "intent_id": "first",
                    "action_id": "a",
                    "checked_at": "2026-07-13 21:00:01",
                    "vt_symbol": "JM2609.DCE",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "order_request_json": "{}",
                },
                {
                    "intent_id": "second",
                    "action_id": "b",
                    "checked_at": "2026-07-13 21:00:02",
                    "vt_symbol": "RB2610.SHFE",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "order_request_json": "{}",
                },
            ]
        )
        for blocker in (
            "ledger_close_known_zero_retry_throttled:1.0",
            "ledger_close_retry_throttled_after_reserved:1.0",
            "ledger_integrity_error:checksum",
            "ledger_duplicate_close_intent:future_transient_blocker",
            "future_unknown_close_blocker",
        ):
            with self.subTest(blocker=blocker):

                def duplicate(**kwargs: object) -> tuple[str, str, dict, dict]:
                    row = kwargs["row"]
                    assert isinstance(row, dict)
                    current = blocker if row["intent_id"] == "first" else ""
                    return current, "fingerprint", {}, {"event_type": "test"}

                with patch.object(stage931, "duplicate_blocker", side_effect=duplicate):
                    eligible, nonretryable = (
                        stage931._drop_terminal_duplicate_close_intents(
                            ready,
                            ledger_rows=[],
                            target_date="2026-07-13",
                            close_retry_after_cancel_seconds=30,
                            reduce_close_only=True,
                        )
                    )
                selected, _, _ = stage931._bound_ready_intents_for_cycle(
                    eligible,
                    max_orders=1,
                    reduce_close_only=True,
                )

                self.assertTrue(nonretryable.empty)
                self.assertEqual(selected["intent_id"].tolist(), ["first"])

    def test_mixed_close_open_queue_never_partitions_close_to_release_open(self) -> None:
        ready = pd.DataFrame(
            [
                {
                    "intent_id": "close-risk",
                    "checked_at": "2026-07-13 21:00:01",
                    "vt_symbol": "JM2609.DCE",
                    "source": "stage904_c9_intraday_close",
                    "offset": "close",
                    "order_request_json": "{}",
                },
                {
                    "intent_id": "open-new-risk",
                    "checked_at": "2026-07-13 21:00:02",
                    "vt_symbol": "RB2610.SHFE",
                    "source": "stage904_c9_intraday_retry_open",
                    "offset": "open",
                    "order_request_json": "{}",
                },
            ]
        )
        with patch.object(
            stage931,
            "duplicate_blocker",
            side_effect=AssertionError(
                "mixed mode must fail before fingerprint partition"
            ),
        ):
            eligible, nonretryable = (
                stage931._drop_terminal_duplicate_close_intents(
                    ready,
                    ledger_rows=[],
                    target_date="2026-07-13",
                    close_retry_after_cancel_seconds=30,
                    reduce_close_only=False,
                )
            )
        selected, deferred, limit_blocker = (
            stage931._bound_ready_intents_for_cycle(
                eligible,
                max_orders=1,
                reduce_close_only=False,
            )
        )

        self.assertTrue(nonretryable.empty)
        self.assertEqual(selected["intent_id"].tolist(), ready["intent_id"].tolist())
        self.assertTrue(deferred.empty)
        self.assertEqual(limit_blocker, "ready_intent_count_above_limit")

    def test_retry_open_requires_target_symbol_gross_flat_across_both_directions(self) -> None:
        request = stage931.OrderRequest(
            symbol="JM2609",
            exchange=stage931.Exchange.DCE,
            direction=stage931.Direction.SHORT,
            type=stage931.OrderType.LIMIT,
            volume=1,
            price=1246.0,
            offset=stage931.Offset.OPEN,
            reference="test",
        )
        rows = {
            "orders": [],
            "positions": [
                {
                    "vt_symbol": "JM2609.DCE",
                    "direction": "long",
                    "volume": 1.0,
                    "frozen": 0.0,
                }
            ],
        }

        blockers = stage931._final_pre_send_blockers(
            rows,
            request,
            "JM2609.DCE",
            authoritative_active_orders=[],
            order_query_confirmed=True,
        )

        self.assertIn(
            "final_target_symbol_gross_position_exists_for_open:1.0",
            blockers,
        )

    def test_protective_close_requires_exact_fresh_broker_volume(self) -> None:
        def request(volume: float) -> object:
            return stage931.OrderRequest(
                symbol="JM2609",
                exchange=stage931.Exchange.DCE,
                direction=stage931.Direction.LONG,
                type=stage931.OrderType.LIMIT,
                volume=volume,
                price=1252.0,
                offset=stage931.Offset.CLOSE,
                reference="test",
            )

        rows = {
            "orders": [],
            "positions": [
                {
                    "vt_symbol": "JM2609.DCE",
                    "direction": "short",
                    "volume": 2.0,
                    "frozen": 0.0,
                }
            ],
        }
        stale_intent_blockers = stage931._final_pre_send_blockers(
            rows,
            request(1.0),
            "JM2609.DCE",
            authoritative_active_orders=[],
            order_query_confirmed=True,
        )
        refreshed_intent_blockers = stage931._final_pre_send_blockers(
            rows,
            request(2.0),
            "JM2609.DCE",
            authoritative_active_orders=[],
            order_query_confirmed=True,
        )

        self.assertIn(
            "final_broker_position_volume_mismatch_for_exact_reduce_close:broker=2.0;request=1.0",
            stale_intent_blockers,
        )
        self.assertEqual(refreshed_intent_blockers, [])


if __name__ == "__main__":
    unittest.main()
