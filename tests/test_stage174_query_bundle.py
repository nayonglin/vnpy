from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import tempfile
import unittest


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_ctp_stage174_readonly_probe as stage174


class Stage174ReadonlyQueryBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.generation = "11111111-2222-4333-8444-555555555555"
        self.module = SimpleNamespace(
            EXCHANGE_CTP2VT={"DCE": "DCE"},
            DIRECTION_CTP2VT={"1": "short", "0": "long"},
            OFFSET_CTP2VT={"0": "open", "1": "close"},
            STATUS_CTP2VT={"0": "all_traded"},
        )

    def raw_order(self, **overrides: object) -> dict:
        row = {
            "BrokerID": "9999",
            "InvestorID": "00001234",
            "TradingDay": "20260713",
            "InstrumentID": "JM609",
            "ExchangeID": "DCE",
            "Direction": "1",
            "CombOffsetFlag": "0",
            "LimitPrice": 1246.0,
            "VolumeTotalOriginal": 1,
            "VolumeTraded": 1,
            "OrderStatus": "0",
            "FrontID": 11,
            "SessionID": 22,
            "OrderRef": "33",
            "OrderSysID": "  SYS-1  ",
            "InsertDate": "20260713",
            "InsertTime": "09:00:00",
        }
        row.update(overrides)
        return row

    def raw_trade(self, **overrides: object) -> dict:
        row = {
            "BrokerID": "9999",
            "InvestorID": "00001234",
            "TradingDay": "20260713",
            "TradeDate": "20260713",
            "TradeTime": "09:00:01",
            "InstrumentID": "JM609",
            "ExchangeID": "DCE",
            "Direction": "1",
            "OffsetFlag": "0",
            "Price": 1246.0,
            "Volume": 1,
            "TradeID": "T-1",
            "OrderSysID": "SYS-1",
        }
        row.update(overrides)
        return row

    def raw_position(self, **overrides: object) -> dict:
        row = {
            "BrokerID": "9999",
            "InvestorID": "00001234",
            "TradingDay": "20260713",
            "InstrumentID": "JM609",
            "ExchangeID": "DCE",
            "PosiDirection": "1",
            "Position": 1,
            "TodayPosition": 1,
            "YdPosition": 0,
            "PositionProfit": 12.5,
            "LongFrozen": 0,
            "ShortFrozen": 0,
        }
        row.update(overrides)
        return row

    def test_reqid_bound_last_and_zero_error_are_required(self) -> None:
        callbacks = [
            {"reqid": 99, "has_data": True, "last": True, "error_id": 0, "received_at": "2026-07-13T09:00:00+08:00"},
            {"reqid": 101, "has_data": True, "last": False, "error_id": 0, "received_at": "2026-07-13T09:00:02+08:00"},
            {"reqid": 101, "has_data": False, "last": True, "error_id": 0, "received_at": "2026-07-13T09:00:03+08:00"},
        ]

        state = stage174._query_callback_state(
            callbacks,
            expected_reqid=101,
            request_return_code=0,
            request_sent_at="2026-07-13T09:00:01+08:00",
        )

        self.assertTrue(state["complete"])
        self.assertEqual(2, state["callback_count"])
        self.assertEqual(1, state["data_callback_count"])

        callbacks[-1]["error_id"] = 7
        failed = stage174._query_callback_state(
            callbacks,
            expected_reqid=101,
            request_return_code=0,
            request_sent_at="2026-07-13T09:00:01+08:00",
        )
        self.assertFalse(failed["complete"])
        self.assertEqual(1, failed["error_rows"])

    def test_trade_joins_queried_order_sysid_to_stable_vt_orderid(self) -> None:
        orders, trades, status = stage174._normalize_query_bundle_rows(
            [self.raw_order()],
            [self.raw_trade()],
            generation_uuid=self.generation,
            ctp_gateway_module=self.module,
        )

        self.assertEqual("CTP.11_22_33", orders[0]["vt_orderid"])
        self.assertEqual("CTP.11_22_33", trades[0]["vt_orderid"])
        self.assertEqual("joined_unique_order_sys_id", trades[0]["order_mapping_status"])
        self.assertTrue(trades[0]["broker_trade_identity"].endswith(":T-1"))
        self.assertTrue(status["trade_order_join_complete"])
        self.assertTrue(status["trade_identity_complete"])

    def test_missing_order_sysid_mapping_fails_bundle_join(self) -> None:
        _, trades, status = stage174._normalize_query_bundle_rows(
            [self.raw_order()],
            [self.raw_trade(OrderSysID="missing")],
            generation_uuid=self.generation,
            ctp_gateway_module=self.module,
        )

        self.assertEqual("", trades[0]["vt_orderid"])
        self.assertEqual(0, trades[0]["order_mapping_complete"])
        self.assertFalse(status["trade_order_join_complete"])

    def test_ambiguous_order_sysid_mapping_fails_closed(self) -> None:
        duplicate = self.raw_order(FrontID=44, SessionID=55, OrderRef="66")
        _, trades, status = stage174._normalize_query_bundle_rows(
            [self.raw_order(), duplicate],
            [self.raw_trade()],
            generation_uuid=self.generation,
            ctp_gateway_module=self.module,
        )

        self.assertEqual("", trades[0]["vt_orderid"])
        self.assertFalse(status["trade_order_join_complete"])

    def test_atomic_csv_hash_binds_exact_published_bytes(self) -> None:
        rows = [{"query_generation_uuid": self.generation, "value": 1}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            frame = stage174._atomic_write_df(path, rows)
            first = stage174._sha256_path(path)
            stage174._atomic_write_df(path, rows + [{"query_generation_uuid": self.generation, "value": 2}])
            second = stage174._sha256_path(path)

        self.assertEqual(1, len(frame))
        self.assertEqual(64, len(first))
        self.assertNotEqual(first, second)

    def test_account_fingerprint_preserves_leading_zero_identity(self) -> None:
        first = stage174._account_fingerprint("9999", "00001234")
        second = stage174._account_fingerprint("9999", "1234")

        self.assertEqual(64, len(first))
        self.assertNotEqual(first, second)

    def test_positions_are_aggregated_from_only_the_bound_generation(self) -> None:
        positions, status = stage174._normalize_queried_positions(
            [self.raw_position(), self.raw_position(Position=2, TodayPosition=0, YdPosition=2)],
            generation_uuid=self.generation,
            broker_trading_day="20260713",
            ctp_gateway_module=self.module,
        )

        self.assertEqual(1, len(positions))
        self.assertEqual(3.0, positions[0]["volume"])
        self.assertEqual(2, positions[0]["source_row_count"])
        self.assertEqual(self.generation, positions[0]["query_generation_uuid"])
        self.assertEqual("00001234", positions[0]["account_id"])
        self.assertTrue(status["position_normalization_complete"])
        self.assertEqual(2, status["position_raw_row_count"])
        self.assertEqual(1, status["position_normalized_row_count"])

    def test_position_without_stable_exchange_identity_fails_closed(self) -> None:
        positions, status = stage174._normalize_queried_positions(
            [self.raw_position(ExchangeID="")],
            generation_uuid=self.generation,
            broker_trading_day="20260713",
            ctp_gateway_module=self.module,
        )

        self.assertEqual([], positions)
        self.assertFalse(status["position_normalization_complete"])
        self.assertEqual(1, status["position_invalid_row_count"])

    def test_readonly_order_firewall_blocks_gateway_and_td_api_calls(self) -> None:
        calls: list[str] = []

        class FakeGateway:
            def send_order(self, *args: object, **kwargs: object) -> str:
                calls.append("gateway_send")
                return "sent"

            def cancel_order(self, *args: object, **kwargs: object) -> str:
                calls.append("gateway_cancel")
                return "cancelled"

        class FakeTdApi:
            def send_order(self, *args: object, **kwargs: object) -> str:
                calls.append("td_send")
                return "sent"

            def cancel_order(self, *args: object, **kwargs: object) -> str:
                calls.append("td_cancel")
                return "cancelled"

        counters = stage174._new_order_api_counters()
        originals = stage174._install_readonly_order_api_firewall(
            FakeGateway,
            FakeTdApi,
            counters,
        )
        try:
            for instance, method_name in (
                (FakeGateway(), "send_order"),
                (FakeGateway(), "cancel_order"),
                (FakeTdApi(), "send_order"),
                (FakeTdApi(), "cancel_order"),
            ):
                with self.assertRaisesRegex(RuntimeError, "readonly_order_api_blocked"):
                    getattr(instance, method_name)(object())
        finally:
            stage174._restore_readonly_order_api_firewall(
                FakeGateway,
                FakeTdApi,
                originals,
            )

        self.assertEqual([], calls)
        self.assertEqual(2, counters["send_order_api_attempted_count"])
        self.assertEqual(2, counters["cancel_order_api_attempted_count"])
        self.assertEqual(0, counters["send_order_api_called_count"])
        self.assertEqual(0, counters["cancel_order_api_called_count"])
        self.assertEqual("sent", FakeGateway().send_order(object()))
        self.assertEqual("cancelled", FakeTdApi().cancel_order(object()))

    def test_dry_run_publishes_exact_zero_order_api_counters(self) -> None:
        result = stage174._run_probe(connect=False, wait_seconds=1)

        for field in (
            "send_order_api_attempted_count",
            "cancel_order_api_attempted_count",
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "order_api_called_count",
        ):
            self.assertIs(type(result[field]), int)
            self.assertEqual(0, result[field])

    def test_reconnect_proof_requires_fresh_queries_on_new_generation(self) -> None:
        lifecycle = {
            "disconnect_observed": 1,
            "reconnect_observed": 1,
            "old_connection_generation": "old",
            "new_connection_generation": "new",
            "readiness_revoked_epoch_ns": 10,
        }
        queries = {
            name: {"connection_generation": "new"}
            for name in ("orders", "trades", "positions")
        }

        proof = stage174._finalize_connection_lifecycle(
            lifecycle,
            query_requests=queries,
            query_bundle_complete=True,
            order_api_counters=stage174._new_order_api_counters(),
            restored_epoch_ns=20,
        )
        stale = stage174._finalize_connection_lifecycle(
            lifecycle,
            query_requests={**queries, "positions": {"connection_generation": "old"}},
            query_bundle_complete=True,
            order_api_counters=stage174._new_order_api_counters(),
            restored_epoch_ns=20,
        )

        self.assertEqual(1, proof["proof_complete"])
        self.assertEqual(20, proof["readiness_restored_epoch_ns"])
        self.assertEqual(0, stale["proof_complete"])
        self.assertIsNone(stale["readiness_restored_epoch_ns"])


if __name__ == "__main__":
    unittest.main()
