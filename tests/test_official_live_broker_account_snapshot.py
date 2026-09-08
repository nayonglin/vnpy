from __future__ import annotations

import copy
import hashlib
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(PORTFOLIO_DIR))
import run_ctp_stage174_readonly_probe as stage174


class BrokerAccountSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.summary_path = self.root / "summary.json"
        self.manifest_path = self.root / "manifest.json"
        self.now = datetime.fromisoformat("2026-09-08T10:00:00+08:00")
        self.generation = "11111111-2222-4333-8444-555555555555"
        self.fingerprint = hashlib.sha256(b"9999\x0000001234").hexdigest()
        self.account = {
            "BrokerID": "9999", "AccountID": "00001234", "CurrencyID": "CNY",
            "Balance": 200000.0, "Available": 170000.0, "CurrMargin": 12345.0,
            "FrozenMargin": 100.0, "FrozenCash": 20.0, "FrozenCommission": 3.0,
        }
        self.positions = [{
            "BrokerID": "9999", "InvestorID": "00001234", "TradingDay": "20260908",
            "InstrumentID": "SH609", "ExchangeID": "CZCE", "PosiDirection": "2",
            "Position": 1, "TodayPosition": 1, "YdPosition": 0,
            "PositionProfit": 0, "LongFrozen": 0, "ShortFrozen": 0, "UseMargin": 1200.0,
        }, {
            "BrokerID": "9999", "InvestorID": "00001234", "TradingDay": "20260908",
            "InstrumentID": "SH611", "ExchangeID": "CZCE", "PosiDirection": "3",
            "Position": 2, "TodayPosition": 0, "YdPosition": 2,
            "PositionProfit": 0, "LongFrozen": 0, "ShortFrozen": 0, "UseMargin": 2300.0,
        }]

    def publish(self, *, accounts=None, positions=None, orders=None, trades=None, mutate=None):
        raw_positions = copy.deepcopy(self.positions if positions is None else positions)
        raw_accounts = copy.deepcopy([self.account] if accounts is None else accounts)
        module = SimpleNamespace(EXCHANGE_CTP2VT={"CZCE": "CZCE"},
                                 DIRECTION_CTP2VT={"2": "long", "3": "short"})
        normalized, position_status = stage174._normalize_queried_positions(
            raw_positions, generation_uuid=self.generation,
            broker_trading_day="20260908", ctp_gateway_module=module,
        )
        query_rows = {"orders": orders or [], "trades": trades or [], "positions": normalized}
        counts = {"orders": len(query_rows["orders"]), "trades": len(query_rows["trades"]),
                  "positions": len(raw_positions), "account": len(raw_accounts), "contracts": 1}
        queries = {}
        for index, name in enumerate(counts):
            queries[name] = {
                "reqid": 101 + index, "request_sent": True, "request_return_code": 0,
                "request_sent_at": (self.now - timedelta(seconds=20 - 2 * index)).isoformat(),
                "completed_at": (self.now - timedelta(seconds=19 - 2 * index)).isoformat(),
                "callback_count": max(1, counts[name]), "data_callback_count": counts[name],
                "last_seen": True, "error_rows": 0, "complete": True,
                "connection_generation": "connection-2",
            }
        queries["positions"].update(position_status)
        generations = {name: "connection-2" for name in stage174.FULL_READINESS_SNAPSHOT_COMPONENTS}
        summary = {
            "generated_at": (self.now - timedelta(seconds=2)).isoformat(),
            "query_generation_uuid": self.generation, "broker_trading_day": "20260908",
            "status": "readonly_snapshots_received",
            "connection_lifecycle": {
                "current_connection_generation": "connection-2", "readiness_generation": "connection-2",
                "snapshot_connection_generations": generations,
                "query_connection_generations": {name: "connection-2" for name in queries},
            },
            "broker_query_bundle": {
                "schema_version": 2, "generation_uuid": self.generation,
                "generated_at": (self.now - timedelta(seconds=2)).isoformat(),
                "broker_trading_day": "20260908", "queries": queries,
                "account": {"account_fingerprint": self.fingerprint, "login_account_match": True,
                            "response_account_match": True, "trading_account_response_match": True},
                "snapshot_connection_generation": "connection-2",
                "snapshot_connection_generations": generations,
                "full_snapshot_current_generation": True, "complete": True,
                "trade_order_join_complete": True, "trade_identity_complete": True,
            },
            "rows": {**query_rows, "accounts": [{"balance": 999999999}],
                     "contracts": [], "logs": [], "position_query_callbacks": [],
                     "order_query_callbacks": [], "trade_query_callbacks": [],
                     "raw_queried_accounts": raw_accounts, "raw_queried_positions": raw_positions},
        }
        if mutate:
            mutate(summary)
        paths = {"SUMMARY_PATH": self.summary_path, "QUERY_BUNDLE_MANIFEST_PATH": self.manifest_path}
        for name in ("ACCOUNT", "POSITION", "ORDER", "TRADE", "CONTRACT", "LOG",
                     "POSITION_QUERY_CALLBACK", "ORDER_QUERY_CALLBACK", "TRADE_QUERY_CALLBACK"):
            paths[name + "_PATH"] = self.root / (name.lower() + ".csv")
        with ExitStack() as stack:
            for name, path in paths.items():
                stack.enter_context(mock.patch.object(stage174, name, path))
            stack.enter_context(mock.patch.object(stage174, "_run_probe", return_value=summary))
            stack.enter_context(mock.patch.object(stage174, "_source_commit", return_value="test-source"))
            stack.enter_context(mock.patch.object(sys, "argv", ["stage174"]))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stage174.main()
        return json.loads(self.summary_path.read_text()), json.loads(self.manifest_path.read_text())

    def load(self, **kwargs):
        spec = importlib.util.find_spec("qmt_roll_official_live_broker_account_snapshot")
        self.assertIsNotNone(spec, "read-only broker account snapshot loader must exist")
        module = importlib.import_module("qmt_roll_official_live_broker_account_snapshot")
        return module.load_broker_account_snapshot(
            self.summary_path, self.manifest_path, now=kwargs.pop("now", self.now), **kwargs,
        )

    def write_pair(self, summary, manifest):
        self.summary_path.write_text(json.dumps(summary), encoding="utf-8")
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_stage174_publishes_sanitized_snapshot_and_money_hash(self):
        summary, manifest = self.publish()
        self.assertIn("broker_sizing", summary)
        sizing = summary["broker_sizing"]
        self.assertTrue(sizing["complete"])
        self.assertEqual(200000.0, sizing["equity"])
        self.assertEqual(12345.0, sizing["margin"])
        self.assertEqual(123.0, sizing["frozen"])
        self.assertEqual({"SH.CZCE": 3500.0}, sizing["product_margin"])
        self.assertEqual(sizing, manifest["broker_sizing"])
        self.assertNotIn("00001234", json.dumps(sizing))
        self.assertEqual(64, len(manifest["broker_sizing_sha256"]))

    def test_loader_uses_raw_cny_account_not_legacy_accounts_csv(self):
        self.publish()
        snapshot = self.load()
        self.assertEqual((200000.0, 170000.0, 12345.0, 123.0),
                         tuple(snapshot[key] for key in ("equity", "available", "margin", "frozen")))
        self.assertEqual({"SH.CZCE": 3500.0}, snapshot["product_margin"])
        self.assertEqual(self.generation, snapshot["generation_uuid"])
        self.assertEqual(self.fingerprint, snapshot["account_fingerprint"])
        self.assertEqual({"orders", "trades", "positions"}, set(snapshot["artifacts"]))

    def test_loader_returns_the_validated_position_and_order_rows(self):
        self.publish()
        snapshot = self.load()
        self.assertEqual(2, len(snapshot["positions"]))
        self.assertEqual({self.generation}, {row["query_generation_uuid"] for row in snapshot["positions"]})
        self.assertEqual([], snapshot["orders"])
        self.assertEqual([], snapshot["trades"])

    def test_flat_account_is_valid_with_empty_product_margin(self):
        self.publish(positions=[])
        self.assertEqual({}, self.load()["product_margin"])

    def test_invalid_raw_money_is_fail_closed_without_breaking_query_bundle(self):
        for field in ("Balance", "Available", "CurrMargin", "FrozenMargin", "FrozenCash", "FrozenCommission"):
            for value in (None, True, "bad", -1, float("nan"), float("inf"), float("-inf")):
                with self.subTest(field=field, value=value):
                    account = {**self.account, field: value}
                    summary, manifest = self.publish(accounts=[account])
                    self.assertTrue(manifest["complete"])
                    with self.assertRaises(ValueError):
                        self.load()

    def test_rejects_missing_zero_equity_foreign_or_multiple_accounts(self):
        for accounts in ([], [{**self.account, "Balance": 0}],
                         [{key: value for key, value in self.account.items() if key != "CurrMargin"}],
                         [{**self.account, "CurrencyID": "USD"}],
                         [{**self.account, "CurrencyID": ""}],
                         [self.account, self.account],
                         [self.account, {**self.account, "CurrencyID": "USD"}],
                         [{**self.account, "AccountID": "1234"}],
                         [{**self.account, "BrokerID": "other"}]):
            with self.subTest(accounts=accounts):
                self.publish(accounts=accounts)
                with self.assertRaises(ValueError):
                    self.load()

    def test_rejects_invalid_product_margin_and_identity(self):
        for override in ({"UseMargin": float("inf")}, {"UseMargin": -1}, {"UseMargin": None},
                         {"UseMargin": True}, {"InstrumentID": "SH609C1000"},
                         {"ExchangeID": ""}, {"InvestorID": "1234"}):
            with self.subTest(override=override):
                self.publish(positions=[{**self.positions[0], **override}])
                with self.assertRaises(ValueError):
                    self.load()

    def test_rejects_money_and_product_sum_overflow(self):
        for accounts, positions in (([{**self.account, "FrozenCash": 1e308, "FrozenMargin": 1e308}], []),
                                     ([self.account], [{**position, "UseMargin": 1e308} for position in self.positions])):
            self.publish(accounts=accounts, positions=positions)
            with self.assertRaises(ValueError):
                self.load()

    def test_reqid_error_count_and_connection_binding_are_required(self):
        for name, key, value in (("account", "complete", False), ("account", "error_rows", 1),
                                 ("account", "reqid", 103), ("account", "reqid", 0),
                                 ("account", "data_callback_count", 2),
                                 ("account", "connection_generation", "old"),
                                 ("positions", "connection_generation", "old"),
                                 ("positions", "data_callback_count", 1)):
            with self.subTest(name=name, key=key):
                self.publish(mutate=lambda summary: summary["broker_query_bundle"]["queries"][name].update({key: value}))
                with self.assertRaises(ValueError):
                    self.load()

    def test_rejects_stale_future_and_invalid_max_age(self):
        self.publish()
        for now in (self.now + timedelta(seconds=301), self.now - timedelta(seconds=3)):
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.load(now=now)
        for limit in (-1, float("nan"), float("inf"), True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.load(max_age_seconds=limit)
        self.assertEqual(200000.0, self.load(max_age_seconds=20)["equity"])

    def test_refreshing_summary_does_not_refresh_old_account_query(self):
        def stale(summary):
            query = summary["broker_query_bundle"]["queries"]["account"]
            query["request_sent_at"] = (self.now - timedelta(seconds=500)).isoformat()
            query["completed_at"] = (self.now - timedelta(seconds=400)).isoformat()
        self.publish(mutate=stale)
        with self.assertRaises(ValueError):
            self.load()

    def test_rejects_sizing_mismatch_and_sizing_hash_tampering(self):
        for target in ("summary", "manifest", "both"):
            with self.subTest(target=target):
                summary, manifest = self.publish()
                self.assertIn("broker_sizing", summary)
                if target in ("summary", "both"):
                    summary["broker_sizing"]["equity"] += 1
                if target in ("manifest", "both"):
                    manifest["broker_sizing"]["equity"] += 1
                self.write_pair(summary, manifest)
                with self.assertRaises(ValueError):
                    self.load()

    def test_rejects_incomplete_wrong_generation_and_wrong_connection(self):
        for key, value in (("complete", False), ("generation_uuid", "other"),
                           ("snapshot_connection_generation", "old"),
                           ("full_snapshot_current_generation", False), ("schema_version", 1)):
            with self.subTest(key=key):
                summary, manifest = self.publish()
                summary["broker_query_bundle"][key] = value
                self.write_pair(summary, manifest)
                with self.assertRaises(ValueError):
                    self.load()

    def test_rejects_each_artifact_hash_change_or_missing_file(self):
        for name in ("orders", "trades", "positions"):
            for missing in (False, True):
                with self.subTest(name=name, missing=missing):
                    _, manifest = self.publish()
                    path = Path(manifest["artifacts"][name]["path"])
                    if missing:
                        path.unlink()
                    else:
                        path.write_bytes(path.read_bytes() + b"tampered\n")
                    with self.assertRaises(ValueError):
                        self.load()

    def test_rejects_active_or_unknown_orders_allows_terminal_orders(self):
        for status, allowed in (("未成交", False), ("part_traded", False), ("unknown", False),
                                 ("全部成交", True), ("all_traded", True), ("已撤销", True), ("拒单", True)):
            with self.subTest(status=status):
                self.publish(orders=[{"query_generation_uuid": self.generation, "broker_id": "9999",
                                     "account_id": "00001234", "status": status, "vt_orderid": "CTP.1_2_3"}])
                if allowed:
                    self.assertEqual(200000.0, self.load()["equity"])
                else:
                    with self.assertRaises(ValueError):
                        self.load()

    def test_malformed_or_missing_json_raises_value_error(self):
        for value in ("[]", "null", "not json"):
            self.publish()
            self.summary_path.write_text(value)
            with self.assertRaises(ValueError):
                self.load()
        self.summary_path.unlink()
        with self.assertRaises(ValueError):
            self.load()

    def test_manifest_connection_metadata_must_match_summary(self):
        summary, manifest = self.publish()
        manifest["queries"]["account"]["connection_generation"] = "prior-connection"
        self.write_pair(summary, manifest)
        with self.assertRaises(ValueError):
            self.load()

    def test_valid_trade_evidence_is_loaded_and_unmapped_trade_rejected(self):
        order = {"query_generation_uuid": self.generation, "broker_id": "9999",
                 "account_id": "00001234", "status": "全部成交", "vt_orderid": "CTP.1_2_3"}
        trade = {**order, "order_mapping_complete": 1, "stable_trade_identity_complete": 1,
                 "broker_trade_identity": "ctp-test-trade"}
        self.publish(orders=[order], trades=[trade])
        self.assertEqual(1, self.load()["bundle_evidence"]["artifacts"]["trades"]["row_count"])
        for override in ({"order_mapping_complete": 0}, {"stable_trade_identity_complete": 0},
                         {"vt_orderid": ""}, {"broker_trade_identity": ""}):
            self.publish(orders=[order], trades=[{**trade, **override}])
            with self.assertRaises(ValueError):
                self.load()

    def test_rehashed_artifacts_still_require_every_row_account_and_generation(self):
        for field, value in (("query_generation_uuid", "other"), ("query_generation_uuid", ""),
                             ("account_id", "1234"), ("account_id", "")):
            with self.subTest(field=field, value=value):
                summary, manifest = self.publish()
                ref = manifest["artifacts"]["positions"]
                path = Path(ref["path"])
                frame = stage174.pd.read_csv(path, dtype=str, keep_default_na=False)
                frame.loc[0, field] = value
                frame.to_csv(path, index=False, encoding="utf-8-sig")
                ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                summary["broker_query_bundle"]["artifacts"]["positions"] = ref
                self.write_pair(summary, manifest)
                with self.assertRaises(ValueError):
                    self.load()

    def test_rehashed_sizing_still_requires_valid_money_and_identity(self):
        for key, value in (("equity", 0), ("available", -1), ("margin", True),
                           ("frozen", 999), ("currency", "USD"),
                           ("account_query_reqid", 999), ("account_fingerprint", "a" * 64),
                           ("connection_generation", "old"), ("product_margin", {"SH.CZCE": 999}),
                           ("position_raw_row_count", 0)):
            with self.subTest(key=key):
                summary, manifest = self.publish()
                self.assertIn("broker_sizing", summary)
                sizing = summary["broker_sizing"]
                sizing[key] = value
                manifest["broker_sizing"] = sizing
                digest = hashlib.sha256(json.dumps(sizing, sort_keys=True, ensure_ascii=False,
                                                  separators=(",", ":")).encode()).hexdigest()
                manifest["broker_sizing_sha256"] = digest
                summary["broker_query_bundle"]["broker_sizing_sha256"] = digest
                self.write_pair(summary, manifest)
                with self.assertRaises(ValueError):
                    self.load()

    def test_same_contract_raw_position_slices_are_summed_without_dedup(self):
        self.publish(positions=[self.positions[0], self.positions[0]])
        snapshot = self.load()
        self.assertEqual({"SH.CZCE": 2400.0}, snapshot["product_margin"])
        self.assertEqual(1, snapshot["artifacts"]["positions"]["row_count"])

    def test_product_symbol_preserves_exchange_conventions(self):
        self.publish(positions=[{**self.positions[0], "InstrumentID": "rb2610", "ExchangeID": "SHFE"}])
        self.assertEqual({"rb.SHFE": 1200.0}, self.load()["product_margin"])

    def test_zero_available_margin_and_frozen_are_not_missing(self):
        account = {**self.account, "Available": 0, "CurrMargin": 0,
                   "FrozenMargin": 0, "FrozenCash": 0, "FrozenCommission": 0}
        self.publish(accounts=[account], positions=[])
        snapshot = self.load(now=self.now.replace(tzinfo=None))
        self.assertEqual((0, 0, 0), tuple(snapshot[key] for key in ("available", "margin", "frozen")))

    def test_future_query_and_timestamp_without_timezone_are_rejected(self):
        for value in ((self.now + timedelta(seconds=1)).isoformat(), "2026-09-08T09:59:50"):
            self.publish(mutate=lambda summary: summary["broker_query_bundle"]["queries"]["account"].update(
                request_sent_at=value, completed_at=value))
            with self.assertRaises(ValueError):
                self.load()

    def test_rejects_summary_or_artifact_path_substitution(self):
        for target in ("summary", "manifest", "positions"):
            summary, manifest = self.publish()
            if target == "summary":
                manifest["summary_binding"]["path"] = str(self.root / "elsewhere.json")
            elif target == "manifest":
                summary["broker_query_bundle"]["manifest_path"] = str(self.root / "elsewhere.json")
            else:
                manifest["artifacts"]["positions"]["path"] = str(self.root / "elsewhere.csv")
            self.write_pair(summary, manifest)
            with self.assertRaises(ValueError):
                self.load()


if __name__ == "__main__":
    unittest.main()
