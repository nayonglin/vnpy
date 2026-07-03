from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage049_stage208_true_carry_replay_gate as s049


class Stage049Stage208TrueCarryReplayGateTest(unittest.TestCase):
    def test_required_sources_are_current_rebuild_not_legacy_stage506_outputs(self) -> None:
        sources = s049.required_replay_sources()
        source_ids = {item["source_id"] for item in sources}

        self.assertIn("current_c9_stage167_daily_pnl_margin", source_ids)
        self.assertIn("stage020_xsmom_signal_daily", source_ids)
        self.assertIn("stage020_price_frame_daily", source_ids)
        self.assertIn("current_minute_fill_bars", source_ids)
        self.assertNotIn("legacy_stage506_daily", source_ids)
        self.assertTrue(all(item["current_rebuild_required"] for item in sources))

    def test_product_specs_block_exact_replay_when_jd_margin_ratio_is_missing(self) -> None:
        product_returns = pd.DataFrame(
            {
                "product_vt_symbol": ["jd.DCE", "rb.SHFE"],
                "main_close": [4300.0, 3600.0],
            }
        )
        metadata = pd.DataFrame(
            {
                "vt_symbol": ["jd.DCE"],
                "price_tick": [1.0],
                "volume_multiple": [10.0],
                "margin_ratio": [float("nan")],
            }
        )

        audit = s049.audit_contract_specs(product_returns, metadata)

        jd = audit[audit["product_vt_symbol"].eq("jd.DCE")].iloc[0]
        rb = audit[audit["product_vt_symbol"].eq("rb.SHFE")].iloc[0]
        self.assertFalse(bool(jd["exact_spec_ready"]))
        self.assertIn("missing_margin_ratio", jd["blocking_reason"])
        self.assertTrue(bool(rb["exact_spec_ready"]))

    def test_replay_gate_blocks_when_contract_specs_or_minute_coverage_are_incomplete(self) -> None:
        source_table = pd.DataFrame(
            [
                {"source_id": "current_c9_stage167_daily_pnl_margin", "ready": True, "blocking_reason": ""},
                {"source_id": "stage020_xsmom_signal_daily", "ready": True, "blocking_reason": ""},
                {"source_id": "stage020_price_frame_daily", "ready": True, "blocking_reason": ""},
                {"source_id": "contract_specs_exact", "ready": False, "blocking_reason": "missing_margin_ratio:jd.DCE"},
                {"source_id": "current_minute_fill_bars", "ready": False, "blocking_reason": "missing_minute_contracts:3"},
            ]
        )

        decision = s049.make_stage049_decision(source_table)

        self.assertEqual(decision["decision"], "stage049_stage208_true_carry_replay_blocked_keep_readonly")
        self.assertFalse(decision["ready_for_true_ledger_replay"])
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])
        self.assertIn("contract_specs_exact", decision["blocking_source_ids"])
        self.assertIn("current_minute_fill_bars", decision["blocking_source_ids"])

    def test_minute_coverage_uses_contract_files_not_product_names(self) -> None:
        contracts = pd.Series(["rb2405.SHFE", "jd2608.DCE"])
        files = {
            "rb2405.SHFE": Path("/tmp/rb2405_minute_backtest.csv"),
        }

        coverage = s049.audit_minute_contract_coverage(contracts, files)

        self.assertEqual(set(coverage["contract_vt"]), {"rb2405.SHFE", "jd2608.DCE"})
        self.assertTrue(bool(coverage[coverage["contract_vt"].eq("rb2405.SHFE")]["minute_file_ready"].iloc[0]))
        self.assertFalse(bool(coverage[coverage["contract_vt"].eq("jd2608.DCE")]["minute_file_ready"].iloc[0]))


if __name__ == "__main__":
    unittest.main()
