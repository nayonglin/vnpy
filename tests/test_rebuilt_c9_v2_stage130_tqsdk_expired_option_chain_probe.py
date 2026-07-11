from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage130_tqsdk_expired_option_chain_probe as s130


class Stage130TqSdkExpiredOptionChainProbeTest(unittest.TestCase):
    def test_backtest_query_uses_active_contract_state(self) -> None:
        self.assertIs(s130.OPTION_QUERY_EXPIRED_AS_OF_BACKTEST, False)

    def test_credential_audit_never_returns_secret_values(self) -> None:
        audit = s130.audit_tqsdk_credentials(
            settings={
                "datafeed.username": "user-secret",
                "datafeed.password": "password-secret",
            },
            env={"TQSDK_ACCOUNT": "env-user-secret"},
        )

        self.assertTrue(audit["settings_datafeed_username_present"])
        self.assertTrue(audit["settings_datafeed_password_present"])
        self.assertEqual(audit["environment_tqsdk_key_count"], 1)
        serialized = repr(audit)
        self.assertNotIn("user-secret", serialized)
        self.assertNotIn("password-secret", serialized)
        self.assertNotIn("env-user-secret", serialized)

    def test_select_same_expiry_call_put_requires_both_legs(self) -> None:
        metadata = pd.DataFrame(
            {
                "option_symbol": [
                    "DCE.m2209-C-3000",
                    "DCE.m2209-P-3000",
                    "DCE.m2209-C-3100",
                    "DCE.m2209-P-3100",
                    "DCE.m2211-C-3000",
                ],
                "underlying_symbol": ["DCE.m2209"] * 5,
                "option_class": ["CALL", "PUT", "CALL", "PUT", "CALL"],
                "expire_datetime": ["2022-08-08"] * 4 + ["2022-10-10"],
                "strike_price": [3000.0, 3000.0, 3100.0, 3100.0, 3000.0],
            }
        )

        selected = s130.select_same_expiry_call_put(
            metadata,
            underlying_symbol="DCE.m2209",
            reference_price=3040.0,
        )

        self.assertEqual(len(selected), 2)
        self.assertEqual(set(selected["option_class"]), {"CALL", "PUT"})
        self.assertEqual(selected["expire_datetime"].nunique(), 1)
        self.assertEqual(set(selected["strike_price"]), {3000.0})

        missing_put = metadata[metadata["option_class"].eq("CALL")]
        self.assertTrue(
            s130.select_same_expiry_call_put(
                missing_put,
                underlying_symbol="DCE.m2209",
                reference_price=3040.0,
            ).empty
        )

    def test_normalized_option_metadata_remains_selectable(self) -> None:
        raw = pd.DataFrame(
            {
                "option_symbol": ["DCE.m2209-C-3000", "DCE.m2209-P-3000"],
                "underlying_symbol": ["DCE.m2209", "DCE.m2209"],
                "option_class": ["CALL", "PUT"],
                "expire_datetime": ["2022-08-05 15:00:00"] * 2,
                "strike_price": [3000.0, 3000.0],
                "expired": [False, False],
            }
        )
        normalized = s130.normalize_option_metadata(raw)

        selected = s130.select_same_expiry_call_put(
            normalized,
            underlying_symbol="DCE.m2209",
            reference_price=3040.0,
        )

        self.assertEqual(len(selected), 2)
        self.assertTrue(selected["expire_datetime"].notna().all())
        self.assertEqual(set(selected["option_class"]), {"CALL", "PUT"})

    def test_option_bar_audit_rejects_time_quality_and_symbol_failures(self) -> None:
        clean = pd.DataFrame(
            {
                "symbol": ["DCE.m2209", "CALL", "PUT"] * 2,
                "datetime": ["2022-03-09"] * 3 + ["2022-03-10"] * 3,
                "open": [3000.0, 100.0, 80.0, 3020.0, 110.0, 75.0],
                "high": [3050.0, 120.0, 90.0, 3040.0, 130.0, 85.0],
                "low": [2980.0, 90.0, 70.0, 3000.0, 100.0, 65.0],
                "close": [3020.0, 110.0, 75.0, 3030.0, 120.0, 70.0],
                "volume": [100.0, 20.0, 18.0, 120.0, 25.0, 19.0],
            }
        )
        expected = {"DCE.m2209", "CALL", "PUT"}

        audit = s130.audit_option_bars(
            clean,
            expected_symbols=expected,
            start="2022-03-09",
            end="2022-03-11",
        )
        self.assertTrue(audit["bars_audit_pass"])

        dirty = clean.copy()
        dirty.loc[0, "datetime"] = "2022-03-12"
        dirty.loc[1, "high"] = 50.0
        dirty.loc[2, "volume"] = -1.0
        dirty = pd.concat([dirty, dirty.iloc[[3]]], ignore_index=True)
        dirty_audit = s130.audit_option_bars(
            dirty,
            expected_symbols=expected,
            start="2022-03-09",
            end="2022-03-11",
        )
        self.assertFalse(dirty_audit["bars_audit_pass"])
        self.assertEqual(dirty_audit["outside_window_count"], 1)
        self.assertGreater(dirty_audit["duplicate_key_count"], 0)
        self.assertEqual(dirty_audit["ohlc_relation_error_count"], 1)
        self.assertEqual(dirty_audit["negative_volume_count"], 1)

    def test_readiness_requires_all_data_and_hash_gates(self) -> None:
        ready = s130.classify_probe_readiness(
            module_audit={
                "module_importable": True,
                "has_tqapi": True,
                "has_tqauth": True,
                "has_tqsim": True,
                "has_tqbacktest": True,
            },
            credential_audit={
                "settings_datafeed_username_present": True,
                "settings_datafeed_password_present": True,
            },
            metadata_audit={"metadata_audit_pass": True},
            bars_audit={"bars_audit_pass": True},
            network_enabled=True,
            raw_hash_count=2,
        )
        self.assertEqual(
            ready["decision"],
            "stage130_tqsdk_expired_option_chain_ready_for_acquisition_manifest",
        )

        blocked = s130.classify_probe_readiness(
            module_audit={
                "module_importable": True,
                "has_tqapi": True,
                "has_tqauth": True,
                "has_tqsim": True,
                "has_tqbacktest": True,
            },
            credential_audit={
                "settings_datafeed_username_present": True,
                "settings_datafeed_password_present": True,
            },
            metadata_audit={"metadata_audit_pass": True},
            bars_audit={"bars_audit_pass": True},
            network_enabled=True,
            raw_hash_count=0,
        )
        self.assertEqual(
            blocked["decision"],
            "stage130_tqsdk_expired_option_chain_not_ready_close",
        )

    def test_filter_probe_bars_discloses_raw_outside_and_duplicate_rows(self) -> None:
        raw = pd.DataFrame(
            {
                "symbol": ["CALL", "CALL", "CALL", "PUT"],
                "datetime": [
                    "2022-03-08",
                    "2022-03-09",
                    "2022-03-09",
                    "2022-03-10",
                ],
                "open": [1.0, 2.0, 2.0, 3.0],
                "high": [2.0, 3.0, 3.0, 4.0],
                "low": [0.5, 1.0, 1.0, 2.0],
                "close": [1.5, 2.5, 2.5, 3.5],
                "volume": [1.0, 2.0, 2.0, 3.0],
            }
        )

        filtered, audit = s130.filter_probe_bars(
            raw,
            start="2022-03-09",
            end="2022-03-11",
        )

        self.assertEqual(audit["raw_bar_rows"], 4)
        self.assertEqual(audit["raw_outside_window_count"], 1)
        self.assertEqual(audit["raw_duplicate_key_count"], 2)
        self.assertEqual(audit["filtered_bar_rows"], 2)
        self.assertFalse(filtered.duplicated(["symbol", "datetime"]).any())
        self.assertTrue(
            pd.to_datetime(filtered["datetime"])
            .dt.normalize()
            .between(pd.Timestamp("2022-03-09"), pd.Timestamp("2022-03-11"))
            .all()
        )

    def test_verified_raw_hash_count_requires_nonempty_rows_and_real_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nonempty = root / "nonempty.csv"
            empty = root / "empty.csv"
            nonempty.write_text("a\n1\n", encoding="utf-8")
            empty.write_text("a\n", encoding="utf-8")

            count, records = s130.verified_raw_hashes(
                {
                    "nonempty": (nonempty, 1),
                    "empty": (empty, 0),
                    "missing": (root / "missing.csv", 2),
                }
            )

        self.assertEqual(count, 1)
        self.assertEqual(records["nonempty"]["verified"], True)
        self.assertEqual(len(records["nonempty"]["sha256"]), 64)
        self.assertEqual(records["empty"]["verified"], False)
        self.assertEqual(records["missing"]["verified"], False)


if __name__ == "__main__":
    unittest.main()
