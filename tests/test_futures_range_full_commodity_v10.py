from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))


def load_module():
    try:
        return importlib.import_module("run_qmt_range_reversion_full_commodity_v10_backtest")
    except ModuleNotFoundError as exc:
        raise AssertionError("full-commodity v10 backtest module is missing") from exc


class FullCommodityUniverseTests(unittest.TestCase):
    def test_filters_to_eligible_non_financial_products_and_enables_both_directions(self) -> None:
        module = load_module()
        source = pd.DataFrame(
            [
                {"product_vt_symbol": "IF.CFFEX", "exchange": "CFFEX", "eligible": 1},
                {"product_vt_symbol": "IM.CFFEX", "exchange": "SHFE", "eligible": 1},
                {"product_vt_symbol": "rb.SHFE", "exchange": "SHFE", "eligible": 1},
                {"product_vt_symbol": "PF.CZCE", "exchange": "CZCE", "eligible": 1},
                {"product_vt_symbol": "fb.DCE", "exchange": "DCE", "eligible": 0},
            ]
        )

        result = module.build_full_commodity_universe(source)

        self.assertEqual(result["product_vt_symbol"].tolist(), ["PF.CZCE", "rb.SHFE"])
        self.assertEqual(result["direction_hint"].tolist(), ["both", "both"])
        self.assertEqual(result["eligible"].tolist(), [1, 1])
        self.assertNotIn("CFFEX", set(result["exchange"]))

    def test_rejects_universe_without_required_columns(self) -> None:
        module = load_module()

        with self.assertRaisesRegex(ValueError, "missing required columns"):
            module.build_full_commodity_universe(pd.DataFrame({"vt_symbol": ["rb.SHFE"]}))

    def test_v10_setting_changes_universe_not_v8_signal_or_risk_contract(self) -> None:
        module = load_module()
        universe_path = Path("/tmp/full_commodity.csv")

        setting = module.build_full_commodity_v10_setting(
            {"rb.SHFE": 0.10},
            product_universe_path=universe_path,
        )

        self.assertEqual(setting["product_universe_csv_path"], str(universe_path))
        self.assertEqual(setting["range_direction_hints_path"], "")
        self.assertFalse(setting["range_direction_hints_required"])
        self.assertTrue(setting["long_entry_enabled"])
        self.assertTrue(setting["short_entry_enabled"])
        self.assertEqual(setting["risk_ratio_of_total_assets"], 0.008)
        self.assertEqual(setting["range_entry_mode"], "score")
        self.assertEqual(setting["range_score_threshold"], 4.0)
        self.assertEqual(setting["range_soft_adx_max"], 32.0)
        self.assertEqual(setting["range_efficiency_max"], 0.40)
        self.assertTrue(setting["range_two_stage_stop_enabled"])
        self.assertEqual(setting["range_hard_stop_r_multiple"], 2.0)
        self.assertFalse(setting["range_previous_day_stop_long_enabled"])
        self.assertTrue(setting["range_previous_day_stop_short_enabled"])
        self.assertEqual(setting["max_concurrent_positions"], 4)

    def test_product_count_uses_backtest_metadata_product_symbols(self) -> None:
        module = load_module()

        count = module.product_count_from_metadata(
            {"product_symbols": ["PF.CZCE", "rb.SHFE", "y.DCE"]}
        )

        self.assertEqual(count, 3)

    def test_run_identity_hashes_frozen_inputs_and_setting_deterministically(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            universe_path = Path(tmp_dir) / "universe.csv"
            universe_path.write_text("product_vt_symbol\nrb.SHFE\n", encoding="utf-8")
            missing_source = Path(tmp_dir) / "missing-source.csv"

            first = module.build_run_identity(
                {"risk": 0.008, "nested": {"b": 2, "a": 1}},
                product_universe_path=universe_path,
                source_universe_path=missing_source,
            )
            second = module.build_run_identity(
                {"nested": {"a": 1, "b": 2}, "risk": 0.008},
                product_universe_path=universe_path,
                source_universe_path=missing_source,
            )

        self.assertEqual(first["setting_sha256"], second["setting_sha256"])
        self.assertEqual(len(first["product_universe_sha256"]), 64)
        self.assertEqual(first["source_universe_sha256"], "")
        self.assertEqual(first["execution_model"], "same_day_close_on_bar")
        self.assertEqual(len(first["strategy_source_sha256"]), 64)

    def test_loads_frozen_universe_when_ignored_source_artifact_is_unavailable(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            frozen_path = Path(tmp_dir) / "frozen.csv"
            pd.DataFrame(
                [
                    {
                        "product_vt_symbol": "IM.CFFEX",
                        "exchange": "CFFEX",
                        "eligible": 1,
                        "direction_hint": "both",
                    },
                    {
                        "product_vt_symbol": "rb.SHFE",
                        "exchange": "SHFE",
                        "eligible": 1,
                        "direction_hint": "both",
                    }
                ]
            ).to_csv(frozen_path, index=False)

            result = module.load_or_materialize_full_commodity_universe(
                source_path=Path(tmp_dir) / "missing-source.csv",
                output_path=frozen_path,
            )
            persisted = pd.read_csv(frozen_path)

        self.assertEqual(result["product_vt_symbol"].tolist(), ["rb.SHFE"])
        self.assertEqual(result["direction_hint"].tolist(), ["both"])
        self.assertEqual(persisted["product_vt_symbol"].tolist(), ["rb.SHFE"])


if __name__ == "__main__":
    unittest.main()
