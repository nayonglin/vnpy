from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage052_tqsdk_jd_minute_backfill as s052


class Stage052TqSdkJdMinuteBackfillTest(unittest.TestCase):
    def test_backfill_plan_filters_jd_gaps_and_skips_existing_contract_files(self) -> None:
        manifest = pd.DataFrame(
            {
                "contract_vt": ["jd2608.DCE", "jd2005.DCE", "cu2608.SHFE"],
                "product_vt_symbol": ["jd.DCE", "jd.DCE", "cu.SHFE"],
                "request_start_date": ["2026-06-15", "2020-01-02", "2026-06-24"],
                "request_end_date": ["2026-06-30", "2020-04-08", "2026-06-30"],
                "observed_price_rows": [11, 63, 5],
                "priority": ["P0_jd_true_carry_blocker", "P0_jd_true_carry_blocker", "P1_tail_contract_gap"],
            }
        )
        existing = {"jd2005.DCE": Path("/tmp/already/jd2005_minute_backtest.csv")}

        plan = s052.build_backfill_plan(manifest, existing_minute_files=existing, max_symbols=10)

        self.assertEqual(plan["contract_vt"].tolist(), ["jd2608.DCE"])
        row = plan.iloc[0]
        self.assertEqual(row["tq_symbol"], "DCE.jd2608")
        self.assertTrue(str(row["output_path"]).endswith("DCE/jd2608_minute_backtest.csv"))
        self.assertIn("tqsdk_stage052_jd_minute_gap_backfill", str(row["output_path"]))

    def test_normalize_downloaded_bars_writes_stage049_compatible_schema(self) -> None:
        raw = pd.DataFrame(
            {
                "contract_vt": ["jd2608.DCE", "jd2608.DCE"],
                "tq_symbol": ["DCE.jd2608", "DCE.jd2608"],
                "bar_datetime": ["2026-06-15 09:00:00", "2026-06-15 09:01:00"],
                "bar_id": [1, 2],
                "open": [3000.0, 3001.0],
                "high": [3002.0, 3003.0],
                "low": [2999.0, 3000.0],
                "close": [3001.0, 3002.0],
                "volume": [10.0, 11.0],
                "open_oi": [100.0, 101.0],
                "close_oi": [101.0, 102.0],
            }
        )

        normalized = s052.normalize_downloaded_bars(raw)

        self.assertEqual(
            normalized.columns.tolist(),
            ["vt_symbol", "tq_symbol", "bar_datetime", "bar_id", "open", "high", "low", "close", "volume", "open_oi", "close_oi"],
        )
        self.assertEqual(normalized["vt_symbol"].tolist(), ["jd2608.DCE", "jd2608.DCE"])

    def test_decision_keeps_true_replay_blocked_until_margin_history_exists(self) -> None:
        plan = pd.DataFrame([{"contract_vt": "jd2608.DCE"}])
        status = pd.DataFrame([{"contract_vt": "jd2608.DCE", "status": "downloaded", "rows": 2}])

        decision = s052.make_stage052_decision(plan, status)

        self.assertEqual(decision["decision"], "stage052_tqsdk_jd_minute_backfill_partial_success_margin_still_blocked")
        self.assertEqual(decision["download_success_contract_count"], 1)
        self.assertFalse(decision["ready_for_true_ledger_replay"])
        self.assertEqual(decision["remaining_blocker"], "jd_contract_daily_margin_history")


if __name__ == "__main__":
    unittest.main()
