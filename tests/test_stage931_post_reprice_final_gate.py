from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = (
    Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
)
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931


class Stage931PostRepriceFinalGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows: dict[str, object] = {
            "orders": [],
            "trades": [],
            "positions": [],
            "position_events_unscoped": [],
            "ticks": [],
        }
        self.readiness = stage931.CtpReadinessState(account_required=False)
        self.td_api = SimpleNamespace()
        self.engine = SimpleNamespace(subscribe=lambda *_args, **_kwargs: None)

    @staticmethod
    def _position(
        *,
        direction: str,
        volume: float,
    ) -> dict[str, object]:
        return {
            "vt_symbol": "jm2609.DCE",
            "direction": direction,
            "volume": volume,
            "today_volume": volume,
            "yesterday_volume": 0.0,
            "frozen": 0.0,
        }

    @staticmethod
    def _request(
        *,
        direction: stage931.Direction,
        offset: stage931.Offset,
        volume: float = 1.0,
    ) -> stage931.OrderRequest:
        return stage931.OrderRequest(
            symbol="jm2609",
            exchange=stage931.Exchange.DCE,
            direction=direction,
            type=stage931.OrderType.LIMIT,
            volume=volume,
            price=100.0,
            offset=offset,
            reference="stage931-post-reprice-final-gate-test",
        )

    def _snapshot(
        self,
        *,
        positions: list[dict[str, object]] | None = None,
        active_orders: list[dict[str, object]] | None = None,
        confirmed: bool = True,
        stable: bool = True,
        blockers: list[str] | None = None,
        q2_completed_monotonic: float = 100.0,
        watermark: dict[str, int] | None = None,
    ) -> dict[str, object]:
        position_rows = list(positions or [])
        active_order_rows = list(active_orders or [])
        event_watermark = dict(
            watermark
            or {
                "event_order_count": 0,
                "event_trade_count": 0,
                "event_position_count": 0,
            }
        )
        return {
            "success": confirmed and stable and not blockers,
            "confirmed": confirmed,
            "stable": stable,
            "blockers": list(blockers or []),
            "positions": position_rows,
            "canonical_positions": stage931._canonical_position_snapshot(
                position_rows
            ),
            "active_orders": active_order_rows,
            "orders": active_order_rows,
            "canonical_q1": [],
            "canonical_q2": [],
            "order_q1": {"reqid": 31},
            "position": {"reqid": 32},
            "order_q2": {"reqid": 33},
            "q2_completed_monotonic": q2_completed_monotonic,
            "event_watermark_before_q2": event_watermark,
            "event_watermark_after_q2": event_watermark,
        }

    def _run_gate(
        self,
        *,
        initial_snapshot: dict[str, object],
        second_snapshot: dict[str, object],
        intent: dict[str, object],
        request: stage931.OrderRequest,
        reprice_side_effect: object | None = None,
        initial_reprice_result: dict[str, object] | None = None,
    ) -> dict[str, object]:
        def snapshot_side_effect(*_args: object, **_kwargs: object) -> dict[str, object]:
            self.rows["positions"] = list(second_snapshot.get("positions", []))
            watermark = stage931._execution_event_watermark(self.rows)
            second_snapshot["event_watermark_before_q2"] = dict(watermark)
            second_snapshot["event_watermark_after_q2"] = dict(watermark)
            return second_snapshot

        patches = [
            patch.object(
                stage931,
                "_final_pre_send_snapshot_epoch",
                side_effect=snapshot_side_effect,
            ),
            patch.object(
                stage931,
                "_final_ctp_transport_blockers",
                return_value=[],
            ),
        ]
        if reprice_side_effect is not None:
            patches.append(
                patch.object(
                    stage931,
                    "_post_snapshot_final_reprice",
                    side_effect=reprice_side_effect,
                )
            )
        with patches[0], patches[1]:
            if len(patches) == 3:
                with patches[2]:
                    return stage931._post_reprice_final_state_gate(
                        self.engine,
                        self.td_api,
                        self.rows,
                        intent,
                        request,
                        initial_snapshot=initial_snapshot,
                        initial_reprice_result=(
                            initial_reprice_result
                            or {"final_reprice_status": "applied"}
                        ),
                        max_tick_age_seconds=30,
                        max_wait_seconds=8.0,
                        readiness_state=self.readiness,
                    )
            return stage931._post_reprice_final_state_gate(
                self.engine,
                self.td_api,
                self.rows,
                intent,
                request,
                initial_snapshot=initial_snapshot,
                initial_reprice_result=(
                    initial_reprice_result
                    or {"final_reprice_status": "applied"}
                ),
                max_tick_age_seconds=30,
                max_wait_seconds=8.0,
                readiness_state=self.readiness,
            )

    @staticmethod
    def _stage372_intent(*, pricetick: float = 0.5) -> dict[str, object]:
        return {
            "vt_symbol": "jm2609.DCE",
            "source": "stage260_stage372_daily",
            "pricetick": pricetick,
        }

    @staticmethod
    def _c9_intent(
        source: str,
        *,
        pricetick: float = 0.5,
    ) -> dict[str, object]:
        intent: dict[str, object] = {
            "vt_symbol": "jm2609.DCE",
            "source": source,
            "pricetick": pricetick,
        }
        if source == "stage904_c9_intraday_retry_open":
            intent["retry_trigger_price"] = 100.0
        return intent

    @staticmethod
    def _stage372_engine(*, pricetick: float = 0.5) -> SimpleNamespace:
        contract = SimpleNamespace(
            vt_symbol="jm2609.DCE",
            pricetick=pricetick,
            gateway_name="CTP",
        )
        return SimpleNamespace(
            subscribe=lambda *_args, **_kwargs: None,
            get_contract=lambda vt_symbol: (
                contract if vt_symbol == contract.vt_symbol else None
            ),
        )

    def _stage372_tick(self, **overrides: object) -> dict[str, object]:
        tick: dict[str, object] = {
            "vt_symbol": "jm2609.DCE",
            "datetime": datetime.now().isoformat(),
            "received_monotonic": 121.0,
            "gateway_name": "CTP",
            "last_price": 100.0,
            "bid_price_1": 99.5,
            "ask_price_1": 100.0,
            "limit_down": 90.0,
            "limit_up": 110.0,
        }
        tick.update(overrides)
        return tick

    def test_no_change_regular_open_passes_one_second_snapshot(self) -> None:
        initial = self._snapshot()
        second = self._snapshot(q2_completed_monotonic=120.0)
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent={"vt_symbol": request.vt_symbol, "source": "stage905"},
            request=request,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(
            result["final_reprice_result"]["final_reprice_status"],
            "skipped_not_stage904_intraday_close",
        )

    def test_stage372_long_uses_post_q2_ask_and_live_ctp_pricetick(self) -> None:
        request = self._request(
            direction=stage931.Direction.LONG,
            offset=stage931.Offset.CLOSE,
        )
        rows = {"ticks": [self._stage372_tick()]}

        with patch.object(
            stage931,
            "_latest_fresh_tick_from_file",
            side_effect=AssertionError("Stage372 must not use tick-file fallback"),
        ):
            result = stage931._post_snapshot_final_reprice(
                self._stage372_engine(),
                rows,
                self._stage372_intent(),
                request,
                max_tick_age_seconds=30,
                q2_completed_monotonic=120.0,
                tick_wait_seconds=0,
            )

        self.assertEqual(result["final_reprice_status"], "applied")
        self.assertEqual(result["final_reprice_source"], "ctp_event_tick")
        self.assertEqual(result["final_reprice_tick_file_fallback_allowed"], 0)
        self.assertGreaterEqual(request.price, 100.0)
        self.assertTrue(stage931._price_on_tick(request.price, 0.5))
        self.assertLessEqual(request.price, 110.0)
        self.assertEqual(result["final_reprice_live_contract_pricetick"], 0.5)

    def test_stage372_open_passes_complete_post_reprice_state_gate(self) -> None:
        self.engine = self._stage372_engine()
        initial = self._snapshot(q2_completed_monotonic=100.0)
        second = self._snapshot(q2_completed_monotonic=120.0)
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )
        self.rows["ticks"].append(self._stage372_tick())

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent=self._stage372_intent(),
            request=request,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(
            result["final_reprice_result"]["final_reprice_status"],
            "applied",
        )
        self.assertLessEqual(request.price, 99.5)
        self.assertTrue(stage931._price_on_tick(request.price, 0.5))

    def test_all_c9_sources_use_the_same_strict_post_q2_price_gate(self) -> None:
        cases = (
            ("stage901_pending_order", stage931.Offset.OPEN),
            ("stage904_c9_intraday_close", stage931.Offset.CLOSE),
            ("stage904_c9_intraday_retry_open", stage931.Offset.OPEN),
        )

        for source, offset in cases:
            with self.subTest(source=source):
                request = self._request(
                    direction=stage931.Direction.SHORT,
                    offset=offset,
                )
                with patch.object(
                    stage931,
                    "_latest_fresh_tick_from_file",
                    side_effect=AssertionError("C9 must not use tick-file fallback"),
                ):
                    result = stage931._post_snapshot_final_reprice(
                        self._stage372_engine(),
                        {"ticks": [self._stage372_tick()]},
                        self._c9_intent(source),
                        request,
                        max_tick_age_seconds=30,
                        q2_completed_monotonic=120.0,
                        tick_wait_seconds=0,
                    )

                self.assertEqual("applied", result["final_reprice_status"])
                self.assertEqual("ctp_event_tick", result["final_reprice_source"])
                self.assertEqual(0, result["final_reprice_tick_file_fallback_allowed"])
                self.assertEqual(0.5, result["final_reprice_live_contract_pricetick"])
                self.assertLessEqual(request.price, 99.5)
                self.assertGreaterEqual(request.price, 90.0)
                self.assertTrue(stage931._price_on_tick(request.price, 0.5))

    def test_all_c9_sources_reject_tick_between_first_and_second_q2(self) -> None:
        self.engine = self._stage372_engine(pricetick=0.5)
        cases = (
            ("stage901_pending_order", stage931.Offset.OPEN),
            ("stage904_c9_intraday_close", stage931.Offset.CLOSE),
            ("stage904_c9_intraday_retry_open", stage931.Offset.OPEN),
        )

        for source, offset in cases:
            with self.subTest(source=source):
                self.rows["ticks"] = [
                    self._stage372_tick(received_monotonic=110.0)
                ]
                positions = (
                    [self._position(direction="long", volume=1.0)]
                    if offset == stage931.Offset.CLOSE
                    else []
                )
                initial = self._snapshot(
                    positions=positions,
                    q2_completed_monotonic=100.0,
                )
                second = self._snapshot(
                    positions=positions,
                    q2_completed_monotonic=120.0,
                )
                request = self._request(
                    direction=stage931.Direction.SHORT,
                    offset=offset,
                )
                request.price = 98.0

                result = self._run_gate(
                    initial_snapshot=initial,
                    second_snapshot=second,
                    intent=self._c9_intent(source),
                    request=request,
                    initial_reprice_result={
                        "final_reprice_status": "applied",
                        "final_reprice_price_before": 100.0,
                        "final_reprice_price_after": 98.0,
                    },
                )

                self.assertFalse(result["success"])
                self.assertIn(
                    "final_close_reprice_not_applied:"
                    "blocked_c9_no_fresh_post_q2_ctp_tick",
                    result["blockers"],
                )
                self.assertEqual(100.0, request.price)
                self.assertEqual(1, result["request_price_restored_after_block"])

    def test_retry_open_rejects_explicit_invalid_trigger_values(self) -> None:
        invalid_values = (
            float("nan"),
            float("inf"),
            float("-inf"),
            sys.float_info.max,
            True,
        )

        for invalid in invalid_values:
            with self.subTest(trigger=repr(invalid)):
                request = self._request(
                    direction=stage931.Direction.SHORT,
                    offset=stage931.Offset.OPEN,
                )
                intent = self._c9_intent(
                    "stage904_c9_intraday_retry_open",
                    pricetick=0.5,
                )
                intent.update(
                    {
                        "retry_trigger_price": invalid,
                        # An explicit invalid primary trigger must not silently
                        # fall through to a later valid-looking field.
                        "strategy_entry_price": 100.0,
                    }
                )

                result = stage931._post_snapshot_final_reprice(
                    self._stage372_engine(pricetick=0.5),
                    {"ticks": [self._stage372_tick()]},
                    intent,
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=120.0,
                    tick_wait_seconds=0,
                )

                self.assertEqual(
                    "blocked_retry_reclaim_trigger_invalid",
                    result["final_reprice_status"],
                )
                self.assertEqual(100.0, request.price)

    def test_all_c9_sources_require_a_contract_from_the_same_ctp_session(self) -> None:
        engine = SimpleNamespace(
            subscribe=lambda *_args, **_kwargs: None,
            get_contract=lambda _vt_symbol: None,
        )
        cases = (
            ("stage901_pending_order", stage931.Offset.OPEN),
            ("stage904_c9_intraday_close", stage931.Offset.CLOSE),
            ("stage904_c9_intraday_retry_open", stage931.Offset.OPEN),
        )

        for source, offset in cases:
            with self.subTest(source=source):
                request = self._request(
                    direction=stage931.Direction.SHORT,
                    offset=offset,
                )
                result = stage931._post_snapshot_final_reprice(
                    engine,
                    {"ticks": [self._stage372_tick()]},
                    self._c9_intent(source),
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=120.0,
                    tick_wait_seconds=0,
                )

                self.assertEqual(
                    "blocked_c9_live_contract_missing",
                    result["final_reprice_status"],
                )
                self.assertTrue(stage931._final_reprice_blockers(result))
                self.assertEqual(100.0, request.price)

    def test_c9_source_names_cannot_disguise_the_wrong_offset(self) -> None:
        cases = (
            ("stage901_pending_order", stage931.Offset.CLOSE),
            ("stage904_c9_intraday_close", stage931.Offset.OPEN),
            ("stage904_c9_intraday_retry_open", stage931.Offset.CLOSE),
        )

        for source, offset in cases:
            with self.subTest(source=source):
                request = self._request(
                    direction=stage931.Direction.SHORT,
                    offset=offset,
                )
                result = stage931._post_snapshot_final_reprice(
                    self._stage372_engine(),
                    {"ticks": [self._stage372_tick()]},
                    self._c9_intent(source),
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=120.0,
                    tick_wait_seconds=0,
                )

                self.assertEqual(
                    "blocked_c9_source_offset_mismatch",
                    result["final_reprice_status"],
                )
                self.assertTrue(stage931._final_reprice_blockers(result))
                self.assertEqual(100.0, request.price)

    def test_all_c9_sources_require_a_positive_post_q2_cutoff(self) -> None:
        cases = (
            ("stage901_pending_order", stage931.Offset.OPEN),
            ("stage904_c9_intraday_close", stage931.Offset.CLOSE),
            ("stage904_c9_intraday_retry_open", stage931.Offset.OPEN),
        )

        for source, offset in cases:
            with self.subTest(source=source):
                request = self._request(
                    direction=stage931.Direction.SHORT,
                    offset=offset,
                )
                result = stage931._post_snapshot_final_reprice(
                    self._stage372_engine(),
                    {"ticks": [self._stage372_tick()]},
                    self._c9_intent(source),
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=0.0,
                    tick_wait_seconds=0,
                )

                self.assertEqual(
                    "blocked_post_snapshot_tick_cutoff_missing",
                    result["final_reprice_status"],
                )
                self.assertTrue(stage931._final_reprice_blockers(result))
                self.assertEqual(100.0, request.price)

    def test_stage372_short_clamps_to_tick_aligned_lower_limit(self) -> None:
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )
        rows = {
            "ticks": [
                self._stage372_tick(
                    bid_price_1=91.0,
                    ask_price_1=91.5,
                    limit_down=90.2,
                    limit_up=110.3,
                )
            ]
        }

        result = stage931._post_snapshot_final_reprice(
            self._stage372_engine(),
            rows,
            self._stage372_intent(),
            request,
            max_tick_age_seconds=30,
            q2_completed_monotonic=120.0,
            tick_wait_seconds=0,
        )

        self.assertEqual(result["final_reprice_status"], "applied")
        self.assertEqual(request.price, 90.5)
        self.assertLessEqual(request.price, 91.0)
        self.assertGreaterEqual(request.price, 90.2)
        self.assertTrue(stage931._price_on_tick(request.price, 0.5))
        self.assertEqual(result["final_reprice_aligned_limit_down"], 90.5)
        self.assertEqual(result["final_reprice_aligned_limit_up"], 110.0)

    def test_stage372_missing_post_q2_tick_fails_closed(self) -> None:
        request = self._request(
            direction=stage931.Direction.LONG,
            offset=stage931.Offset.OPEN,
        )

        result = stage931._post_snapshot_final_reprice(
            self._stage372_engine(),
            {"ticks": []},
            self._stage372_intent(),
            request,
            max_tick_age_seconds=30,
            q2_completed_monotonic=120.0,
            tick_wait_seconds=0,
        )

        self.assertEqual(
            result["final_reprice_status"],
            "blocked_stage372_no_fresh_post_q2_ctp_tick",
        )
        self.assertTrue(stage931._final_reprice_blockers(result))
        self.assertEqual(request.price, 100.0)

    def test_stage372_tick_must_have_strict_post_q2_ingress_stamp(self) -> None:
        for label, received_monotonic in {
            "missing": None,
            "before": 119.9,
            "equal": 120.0,
        }.items():
            with self.subTest(label=label):
                request = self._request(
                    direction=stage931.Direction.LONG,
                    offset=stage931.Offset.OPEN,
                )
                tick = self._stage372_tick(
                    received_monotonic=received_monotonic
                )
                result = stage931._post_snapshot_final_reprice(
                    self._stage372_engine(),
                    {"ticks": [tick]},
                    self._stage372_intent(),
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=120.0,
                    tick_wait_seconds=0,
                )

                self.assertEqual(
                    result["final_reprice_status"],
                    "blocked_stage372_no_fresh_post_q2_ctp_tick",
                )
                self.assertTrue(stage931._final_reprice_blockers(result))
                self.assertEqual(request.price, 100.0)

    def test_stage372_requires_contract_from_same_ctp_session(self) -> None:
        cases = {
            "missing": (
                SimpleNamespace(
                    subscribe=lambda *_args, **_kwargs: None,
                    get_contract=lambda _vt_symbol: None,
                ),
                "blocked_stage372_live_contract_missing",
            ),
            "other_gateway": (
                SimpleNamespace(
                    subscribe=lambda *_args, **_kwargs: None,
                    get_contract=lambda _vt_symbol: SimpleNamespace(
                        pricetick=0.5,
                        gateway_name="SIM",
                    ),
                ),
                "blocked_stage372_live_contract_not_ctp",
            ),
            "other_contract": (
                SimpleNamespace(
                    subscribe=lambda *_args, **_kwargs: None,
                    get_contract=lambda _vt_symbol: SimpleNamespace(
                        vt_symbol="i2609.DCE",
                        pricetick=0.5,
                        gateway_name="CTP",
                    ),
                ),
                "blocked_stage372_live_contract_vt_symbol_mismatch",
            ),
        }

        for label, (engine, expected_status) in cases.items():
            with self.subTest(label=label):
                request = self._request(
                    direction=stage931.Direction.LONG,
                    offset=stage931.Offset.OPEN,
                )
                result = stage931._post_snapshot_final_reprice(
                    engine,
                    {"ticks": [self._stage372_tick()]},
                    self._stage372_intent(),
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=120.0,
                    tick_wait_seconds=0,
                )

                self.assertEqual(result["final_reprice_status"], expected_status)
                self.assertTrue(stage931._final_reprice_blockers(result))
                self.assertEqual(request.price, 100.0)

    def test_stage372_quote_tick_and_limits_are_mandatory(self) -> None:
        cases = {
            "quote_missing": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(ask_price_1=0.0),
                "blocked_stage372_executable_quote_missing",
            ),
            "crossed_quote": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(bid_price_1=101.0, ask_price_1=100.0),
                "blocked_stage372_crossed_quote",
            ),
            "intent_pricetick_missing": (
                self._stage372_engine(),
                self._stage372_intent(pricetick=0.0),
                self._stage372_tick(),
                "blocked_stage372_intent_pricetick_missing",
            ),
            "live_pricetick_missing": (
                self._stage372_engine(pricetick=0.0),
                self._stage372_intent(),
                self._stage372_tick(),
                "blocked_stage372_live_contract_pricetick_missing",
            ),
            "pricetick_mismatch": (
                self._stage372_engine(pricetick=1.0),
                self._stage372_intent(pricetick=0.5),
                self._stage372_tick(),
                "blocked_stage372_pricetick_mismatch",
            ),
            "sub_tolerance_pricetick_mismatch": (
                self._stage372_engine(pricetick=0.5000000000005),
                self._stage372_intent(pricetick=0.5),
                self._stage372_tick(),
                "blocked_stage372_pricetick_mismatch",
            ),
            "unrepresentable_pricetick": (
                self._stage372_engine(pricetick=5e-324),
                self._stage372_intent(pricetick=5e-324),
                self._stage372_tick(),
                "blocked_stage372_pricetick_not_representable",
            ),
            "limit_missing": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(limit_up=0.0),
                "blocked_stage372_price_limits_missing",
            ),
            "limit_invalid": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(limit_down=111.0, limit_up=110.0),
                "blocked_stage372_invalid_price_limits",
            ),
            "quote_outside_limit": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(ask_price_1=110.5),
                "blocked_stage372_quote_outside_price_limits",
            ),
            "quote_not_on_tick": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(bid_price_1=99.4),
                "blocked_stage372_quote_not_on_tick",
            ),
            "ctp_max_float_quote": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(ask_price_1=sys.float_info.max),
                "blocked_stage372_executable_quote_missing",
            ),
            "ctp_max_float_limit": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(limit_up=sys.float_info.max),
                "blocked_stage372_price_limits_missing",
            ),
            "non_ctp_tick_gateway": (
                self._stage372_engine(),
                self._stage372_intent(),
                self._stage372_tick(gateway_name="SIM"),
                "blocked_stage372_tick_not_ctp",
            ),
        }

        for label, (engine, intent, tick, expected_status) in cases.items():
            with self.subTest(label=label):
                request = self._request(
                    direction=stage931.Direction.LONG,
                    offset=stage931.Offset.OPEN,
                )
                result = stage931._post_snapshot_final_reprice(
                    engine,
                    {"ticks": [tick]},
                    intent,
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=120.0,
                    tick_wait_seconds=0,
                )
                self.assertEqual(result["final_reprice_status"], expected_status)
                self.assertTrue(stage931._final_reprice_blockers(result))
                self.assertEqual(request.price, 100.0)

    def test_stage372_monotonic_cutoff_must_be_positive(self) -> None:
        request = self._request(
            direction=stage931.Direction.LONG,
            offset=stage931.Offset.OPEN,
        )
        result = stage931._post_snapshot_final_reprice(
            self._stage372_engine(),
            {"ticks": [self._stage372_tick(received_monotonic=1.0)]},
            self._stage372_intent(),
            request,
            max_tick_age_seconds=30,
            q2_completed_monotonic=0.0,
            tick_wait_seconds=0,
        )

        self.assertEqual(
            result["final_reprice_status"],
            "blocked_post_snapshot_tick_cutoff_missing",
        )
        self.assertTrue(stage931._final_reprice_blockers(result))
        self.assertEqual(request.price, 100.0)

    def test_stage372_tick_tolerance_cannot_authorize_non_marketable_price(self) -> None:
        cases = (
            (
                stage931.Direction.LONG,
                self._stage372_tick(
                    bid_price_1=99.5,
                    ask_price_1=100.000000001,
                    limit_up=100.000000004,
                ),
            ),
            (
                stage931.Direction.SHORT,
                self._stage372_tick(
                    bid_price_1=99.999999999,
                    ask_price_1=100.5,
                    limit_down=99.999999996,
                ),
            ),
        )

        for direction, tick in cases:
            with self.subTest(direction=direction.value):
                request = self._request(
                    direction=direction,
                    offset=stage931.Offset.OPEN,
                )
                result = stage931._post_snapshot_final_reprice(
                    self._stage372_engine(),
                    {"ticks": [tick]},
                    self._stage372_intent(),
                    request,
                    max_tick_age_seconds=30,
                    q2_completed_monotonic=120.0,
                    tick_wait_seconds=0,
                )

                self.assertEqual(
                    result["final_reprice_status"],
                    "blocked_stage372_no_executable_price_within_limits",
                )
                self.assertTrue(stage931._final_reprice_blockers(result))
                self.assertEqual(request.price, 100.0)

    def test_stage372_pre_snapshot_price_is_not_repriced_or_subscribed(self) -> None:
        subscribe_calls: list[object] = []
        engine = self._stage372_engine()
        engine.subscribe = lambda *args, **_kwargs: subscribe_calls.append(args)
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )

        result = stage931._final_close_reprice(
            engine,
            {"ticks": []},
            self._stage372_intent(),
            request,
            max_tick_age_seconds=30,
            tick_wait_seconds=2,
        )

        self.assertEqual(
            result["final_reprice_status"],
            "skipped_not_stage904_intraday_close",
        )
        self.assertEqual(subscribe_calls, [])
        self.assertEqual(request.price, 100.0)

    def test_manual_active_order_during_tick_wait_blocks_open(self) -> None:
        initial = self._snapshot()
        self.rows["orders"].append({"vt_orderid": "CTP.manual-1"})
        active = {"order_identity": "sys:manual-1", "active": True}
        second = self._snapshot(
            active_orders=[active],
            q2_completed_monotonic=120.0,
        )
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent={"vt_symbol": request.vt_symbol, "source": "stage905"},
            request=request,
        )

        self.assertFalse(result["success"])
        self.assertIn("final_order_query_active_order_count=1", result["blockers"])
        self.assertTrue(
            any(
                blocker.startswith("post_q2_event_order_watermark_changed:")
                for blocker in result["blockers"]
            )
        )

    def test_manual_fill_and_position_change_blocks_protective_close(self) -> None:
        original_position = self._position(direction="short", volume=2.0)
        changed_position = self._position(direction="short", volume=1.0)
        initial = self._snapshot(positions=[original_position])
        self.rows["trades"].append(
            {"vt_tradeid": "CTP.manual-fill", "volume": 1.0}
        )
        self.rows["position_events_unscoped"].append(changed_position)
        second = self._snapshot(
            positions=[changed_position],
            q2_completed_monotonic=120.0,
        )
        request = self._request(
            direction=stage931.Direction.LONG,
            offset=stage931.Offset.CLOSE,
            volume=2.0,
        )

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent={
                "vt_symbol": request.vt_symbol,
                "source": "stage904_c9_intraday_close",
            },
            request=request,
        )

        self.assertFalse(result["success"])
        self.assertIn(
            "post_reprice_authoritative_position_changed", result["blockers"]
        )
        self.assertIn(
            "final_broker_position_volume_mismatch_for_exact_reduce_close:broker=1.0;request=2.0",
            result["blockers"],
        )
        self.assertTrue(
            any(
                blocker.startswith("post_q2_event_trade_watermark_changed:")
                for blocker in result["blockers"]
            )
        )
        self.assertEqual(result["position_event_watermark_changed"], 1)

    def test_incomplete_second_snapshot_fails_closed_without_tick_loop(self) -> None:
        initial = self._snapshot()
        second = self._snapshot(
            confirmed=False,
            stable=False,
            blockers=["final_snapshot_q2:timeout"],
            q2_completed_monotonic=120.0,
        )
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent={"vt_symbol": request.vt_symbol, "source": "stage905"},
            request=request,
        )

        self.assertFalse(result["success"])
        self.assertIn(
            "post_reprice_snapshot:final_snapshot_q2:timeout",
            result["blockers"],
        )
        self.assertIn(
            "final_order_query_missing_or_incomplete", result["blockers"]
        )

    def test_async_event_order_after_second_snapshot_blocks_before_send(self) -> None:
        initial = self._snapshot()
        second = self._snapshot(q2_completed_monotonic=120.0)
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )

        def reprice(*_args: object, **_kwargs: object) -> dict[str, object]:
            self.rows["orders"].append({"vt_orderid": "CTP.async-manual"})
            return {"final_reprice_status": "skipped_not_stage904_intraday_close"}

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent={"vt_symbol": request.vt_symbol, "source": "stage905"},
            request=request,
            reprice_side_effect=reprice,
        )

        self.assertFalse(result["success"])
        self.assertTrue(
            any(
                blocker.startswith(
                    "post_final_snapshot_event_order_watermark_changed:"
                )
                for blocker in result["blockers"]
            )
        )

    def test_ingress_backlog_after_gate_is_caught_before_api_slot(self) -> None:
        gate_watermark = stage931._execution_event_watermark(self.rows)
        self.rows["_execution_event_ingress_counts"] = {
            "order": 1,
            "trade": 0,
            "position": 0,
        }

        blockers = stage931._post_final_gate_pre_api_slot_blockers(
            self.rows,
            gate_watermark,
        )

        self.assertEqual(self.rows["orders"], [])
        self.assertEqual(len(blockers), 1)
        self.assertTrue(
            blockers[0].startswith(
                "post_final_gate_pre_api_slot_event_order_watermark_changed:"
            )
        )

    def test_query_echo_rows_do_not_override_authoritative_ingress_counter(self) -> None:
        # reqQryOrder may publish historical EVENT_ORDER rows synchronously.
        # The gateway ingress hook excludes those query echoes; only its
        # counter, not the append-only diagnostic list, is authoritative.
        self.rows["orders"] = [
            {"vt_orderid": "CTP.query-echo-1"},
            {"vt_orderid": "CTP.query-echo-2"},
        ]
        self.rows["_execution_event_ingress_counts"] = {
            "order": 0,
            "trade": 0,
            "position": 0,
        }

        watermark = stage931._execution_event_watermark(self.rows)

        self.assertEqual(watermark["event_order_count"], 0)

    def test_order_ingress_between_q2_callback_and_watermark_is_not_lost(self) -> None:
        before = {
            "event_order_count": 0,
            "event_trade_count": 0,
            "event_position_count": 0,
        }
        after = {**before, "event_order_count": 1}
        initial = self._snapshot(watermark=before)
        # Model an external order entering after the authoritative Q2 callback
        # completed but before Stage931 sampled its after-Q2 watermark.
        initial["event_watermark_after_q2"] = after
        self.rows["_execution_event_ingress_counts"] = {
            "order": 1,
            "trade": 0,
            "position": 0,
        }
        second = self._snapshot(q2_completed_monotonic=120.0)
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent={"vt_symbol": request.vt_symbol, "source": "stage905"},
            request=request,
        )

        self.assertFalse(result["success"])
        self.assertIn(
            "final_q2_event_order_watermark_changed:before=0;after=1",
            result["blockers"],
        )

    def test_protective_close_rechecks_real_event_tick_without_file_fallback(self) -> None:
        self.engine = self._stage372_engine(pricetick=1.0)
        position = self._position(direction="short", volume=2.0)
        initial = self._snapshot(positions=[position])
        second = self._snapshot(
            positions=[position],
            q2_completed_monotonic=120.0,
        )
        request = self._request(
            direction=stage931.Direction.LONG,
            offset=stage931.Offset.CLOSE,
            volume=2.0,
        )
        self.rows["ticks"].append(
            {
                "vt_symbol": request.vt_symbol,
                "datetime": datetime.now().isoformat(),
                "received_monotonic": 121.0,
                "gateway_name": "CTP",
                "last_price": 100.0,
                "bid_price_1": 99.0,
                "ask_price_1": 100.0,
                "limit_down": 90.0,
                "limit_up": 110.0,
            }
        )
        # vn.py's own reqQryInvestorPosition echo is intentionally unscoped;
        # the second authoritative position epoch, not this append-only count,
        # must decide whether exposure changed.
        self.rows["position_events_unscoped"].append(dict(position))

        with patch.object(
            stage931,
            "_latest_fresh_tick_from_file",
            side_effect=AssertionError("Stage608 fallback must remain disabled"),
        ):
            result = self._run_gate(
                initial_snapshot=initial,
                second_snapshot=second,
                intent={
                    "vt_symbol": request.vt_symbol,
                    "source": "stage904_c9_intraday_close",
                    "pricetick": 1.0,
                },
                request=request,
            )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["final_reprice_result"]["final_reprice_status"], "applied"
        )
        self.assertEqual(
            result["final_reprice_result"][
                "final_reprice_tick_file_fallback_allowed"
            ],
            0,
        )
        self.assertEqual(
            result["final_reprice_result"]["final_reprice_source"],
            "ctp_event_tick",
        )
        self.assertEqual(result["position_event_watermark_changed"], 1)

    def test_retry_open_latest_tick_no_longer_favourable_fails_closed(self) -> None:
        self.engine = self._stage372_engine(pricetick=1.0)
        initial = self._snapshot()
        second = self._snapshot(q2_completed_monotonic=120.0)
        request = self._request(
            direction=stage931.Direction.SHORT,
            offset=stage931.Offset.OPEN,
        )
        self.rows["ticks"].append(
            {
                "vt_symbol": request.vt_symbol,
                "datetime": datetime.now().isoformat(),
                "received_monotonic": 121.0,
                "gateway_name": "CTP",
                "last_price": 101.0,
                "bid_price_1": 101.0,
                "ask_price_1": 102.0,
                "limit_down": 90.0,
                "limit_up": 110.0,
            }
        )

        result = self._run_gate(
            initial_snapshot=initial,
            second_snapshot=second,
            intent={
                "vt_symbol": request.vt_symbol,
                "source": "stage904_c9_intraday_retry_open",
                "retry_trigger_price": 100.0,
                "pricetick": 1.0,
            },
            request=request,
        )

        self.assertFalse(result["success"])
        self.assertIn(
            "final_close_reprice_not_applied:blocked_retry_reclaim_no_longer_favorable",
            result["blockers"],
        )


if __name__ == "__main__":
    unittest.main()
