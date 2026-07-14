from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "stage002_execution_preflight.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage002_execution_preflight", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Stage002ExecutionPreflightTest(unittest.TestCase):
    def test_atm_tie_uses_lower_strike_then_symbol(self) -> None:
        module = load_module()
        metadata = pd.DataFrame(
            [
                ["INE.sc2205P500", "INE.sc2205", "PUT", "2022-04-12 15:00:00", 500, False, 1000, 0.05],
                ["INE.sc2205P490B", "INE.sc2205", "PUT", "2022-04-12 15:00:00", 490, False, 1000, 0.05],
                ["INE.sc2205P490A", "INE.sc2205", "PUT", "2022-04-12 15:00:00", 490, False, 1000, 0.05],
                ["INE.sc2205C490", "INE.sc2205", "CALL", "2022-04-12 15:00:00", 490, False, 1000, 0.05],
            ],
            columns=["option_symbol", "underlying_symbol", "option_class", "expire_datetime", "strike_price", "expired", "volume_multiple", "price_tick"],
        )
        ranked = module.rank_atm_candidates(
            metadata,
            event_id="event",
            entry_date=pd.Timestamp("2022-03-25"),
            requested_underlying="INE.sc2205",
            option_class="PUT",
            sc_t1_close=495,
        )
        self.assertEqual(ranked.iloc[0]["strike_price"], 490)
        self.assertEqual(ranked.iloc[0]["option_symbol"], "INE.sc2205P490A")
        self.assertEqual(ranked.iloc[0]["selected"], 1)

    def test_selection_rejects_wrong_class_underlying_and_expired(self) -> None:
        module = load_module()
        metadata = pd.DataFrame(
            [
                ["wrong", "INE.sc2206", "PUT", "2022-04-12", 500, False, 1000, 0.05],
                ["call", "INE.sc2205", "CALL", "2022-04-12", 500, False, 1000, 0.05],
                ["expired", "INE.sc2205", "PUT", "2022-03-20", 500, True, 1000, 0.05],
            ],
            columns=["option_symbol", "underlying_symbol", "option_class", "expire_datetime", "strike_price", "expired", "volume_multiple", "price_tick"],
        )
        ranked = module.rank_atm_candidates(
            metadata,
            event_id="event",
            entry_date=pd.Timestamp("2022-03-25"),
            requested_underlying="INE.sc2205",
            option_class="PUT",
            sc_t1_close=500,
        )
        self.assertTrue(ranked.empty)

    def test_ideal_lots_formula_and_two_lot_boundary(self) -> None:
        module = load_module()
        exact_two = module.ideal_option_lots(
            fu_volume=25,
            fu_multiplier=10,
            fu_weighted_entry_price=4000,
            beta=0.8,
            sc_multiplier=1000,
            sc_t1_close=800,
            atm_delta_proxy=0.5,
        )
        self.assertAlmostEqual(exact_two, 2.0)
        below = module.ideal_option_lots(
            fu_volume=24,
            fu_multiplier=10,
            fu_weighted_entry_price=4000,
            beta=0.8,
            sc_multiplier=1000,
            sc_t1_close=800,
            atm_delta_proxy=0.5,
        )
        self.assertLess(below, module.MIN_IDEAL_OPTION_LOTS)

    def test_current_snapshot_semantically_revalidates_before_selection(self) -> None:
        module = load_module()
        result = module.evaluate()
        self.assertEqual(len(result["semantic"]), 32)
        self.assertEqual(int(result["semantic"]["semantic_pass"].sum()), 32)
        self.assertEqual(int(result["semantic"]["normalized_value_mismatch_count"].sum()), 0)
        self.assertEqual(int(result["selection"]["selection_pass"].sum()), 29)
        self.assertEqual(result["decision"]["decision"], "CLOSE_LINE_SELECTION_INELIGIBLE")
        failed = result["selection"][result["selection"]["selection_pass"].eq(0)]
        self.assertEqual(len(failed), 3)
        self.assertTrue(failed["selected_expiry"].isna().all())
        self.assertTrue(failed["granularity_pass"].eq(0).all())
        self.assertEqual(int(result["selection"]["granularity_pass"].sum()), 29)
        self.assertEqual(result["decision"]["granularity_pass_count"], 29)
        self.assertAlmostEqual(result["decision"]["granularity_pass_rate"], 29 / 32)
        self.assertFalse(result["decision"]["network_called"])


if __name__ == "__main__":
    unittest.main()
