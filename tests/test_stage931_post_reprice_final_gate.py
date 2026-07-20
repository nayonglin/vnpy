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
                        initial_reprice_result={
                            "final_reprice_status": "applied"
                        },
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
                initial_reprice_result={"final_reprice_status": "applied"},
                max_tick_age_seconds=30,
                max_wait_seconds=8.0,
                readiness_state=self.readiness,
            )

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
                "last_price": 100.0,
                "bid_price_1": 99.0,
                "ask_price_1": 100.0,
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
                "last_price": 101.0,
                "bid_price_1": 101.0,
                "ask_price_1": 102.0,
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
