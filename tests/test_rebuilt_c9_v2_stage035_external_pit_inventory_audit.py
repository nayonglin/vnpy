from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage035_external_pit_inventory_audit as s035


class Stage035ExternalPitInventoryAuditTest(unittest.TestCase):
    def test_classifies_orderflow_file_outside_research_as_schema_candidate_only(self) -> None:
        row = s035.classify_path(Path("external_data/orderflow_depth_mbo/rb2301_depth_snapshot_20200102.parquet"), 1024)

        self.assertEqual(row["route_id"], "authorized_orderflow_depth_mbo")
        self.assertEqual(row["asset_kind"], "potential_pit_data")
        self.assertTrue(row["schema_validation_required"])
        self.assertFalse(row["rule_candidate_allowed"])
        self.assertFalse(row["true_engine_allowed"])

    def test_research_replay_and_live_logs_do_not_count_as_same_source_replay(self) -> None:
        rows = pd.DataFrame(
            [
                s035.classify_path(Path("research/lines/a/outputs/stage028/trade_events.csv.gz"), 2048),
                s035.classify_path(Path(".vntrader/log/ctp_live_20260702.log"), 4096),
            ]
        )

        summary = s035.summarize_routes(rows)
        replay = summary[summary["route_id"] == "broker_or_production_execution_replay"].iloc[0]

        self.assertEqual(int(replay["accepted_same_source_replay_file_count"]), 0)
        self.assertEqual(int(replay["protected_live_log_count"]), 1)
        self.assertEqual(int(replay["research_artifact_count"]), 1)
        self.assertFalse(bool(replay["rule_candidate_allowed"]))

    def test_optionmaster_doc_is_capability_not_option_chain_history(self) -> None:
        row = s035.classify_path(Path("docs/community/app/option_master.md"), 512)

        self.assertEqual(row["route_id"], "options_iv_skew")
        self.assertEqual(row["asset_kind"], "code_capability_doc")
        self.assertFalse(row["schema_validation_required"])
        self.assertFalse(row["rule_candidate_allowed"])

    def test_decision_blocks_rule_when_only_docs_backtests_and_research_artifacts_exist(self) -> None:
        rows = pd.DataFrame(
            [
                s035.classify_path(Path("docs/community/app/option_master.md"), 512),
                s035.classify_path(Path("examples/portfolio_backtesting/downloaded_futures/tqsdk/a_minute_backtest.csv"), 1024),
                s035.classify_path(Path("research/lines/a/outputs/stage028/trade_events.csv.gz"), 2048),
            ]
        )
        summary = s035.summarize_routes(rows)
        decision = s035.make_inventory_decision(summary)

        self.assertEqual(decision["decision"], "stage035_external_pit_inventory_no_local_rule_candidate")
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])

    def test_short_tokens_do_not_false_match_symbols_live_or_config_files(self) -> None:
        rows = [
            s035.classify_path(Path("examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/_symbols.csv"), 1024),
            s035.classify_path(Path("examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage907_official_live_summary.json"), 1024),
            s035.classify_path(Path("vntrader/connect_ctp.json"), 1024),
        ]

        self.assertEqual(rows[0]["route_id"], "minute_ohlcv_backtest_cache")
        self.assertEqual(rows[0]["asset_kind"], "minute_ohlcv_backtest_cache")
        self.assertEqual(rows[1]["asset_kind"], "research_artifact")
        self.assertEqual(rows[2]["asset_kind"], "configuration_file")
        self.assertFalse(rows[2]["schema_validation_required"])


if __name__ == "__main__":
    unittest.main()
