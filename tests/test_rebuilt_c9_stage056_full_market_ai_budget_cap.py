from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage056_full_market_ai_budget_cap_engine import (  # noqa: E402
    _build_stage056_full_market_lookup,
    _stage056_apply_full_market_ai_budget_cap,
    _stage056_lookup_full_market_ai_state,
)


class RebuiltC9Stage056FullMarketAiBudgetCapTest(unittest.TestCase):
    def test_non_full_market_ai_top8_flat_entry_caps_release_to_one(self) -> None:
        selected, fields = _stage056_apply_full_market_ai_budget_cap(
            sizing={"selected_volume": 6},
            entry_context="flat_entry",
            full_market_state={
                "full_market_ai_top8": False,
                "full_market_eval_date": "2022-04-30",
                "full_market_ai_rank_desc": 15,
            },
            min_position_size=1,
            enabled=True,
            max_non_top8_volume=1,
        )

        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage056_budget_cap_applied"], 1)
        self.assertEqual(fields["stage056_budget_cap_reason"], "stage056_non_full_market_ai_top8_cap")
        self.assertEqual(fields["stage056_budget_cap_selected_volume_before"], 6)
        self.assertEqual(fields["stage056_budget_cap_selected_volume_after"], 1)
        self.assertEqual(fields["stage056_budget_cap_reduced_volume"], 5)

    def test_full_market_ai_top8_preserves_release_budget(self) -> None:
        selected, fields = _stage056_apply_full_market_ai_budget_cap(
            sizing={"selected_volume": 6},
            entry_context="flat_entry",
            full_market_state={
                "full_market_ai_top8": True,
                "full_market_eval_date": "2022-04-30",
                "full_market_ai_rank_desc": 3,
            },
            min_position_size=1,
            enabled=True,
            max_non_top8_volume=1,
        )

        self.assertEqual(selected, 6)
        self.assertEqual(fields["stage056_budget_cap_applied"], 0)
        self.assertEqual(fields["stage056_budget_cap_reason"], "full_market_ai_top8_release_allowed")

    def test_non_flat_entry_and_disabled_gate_are_preserved(self) -> None:
        selected, fields = _stage056_apply_full_market_ai_budget_cap(
            sizing={"selected_volume": 6},
            entry_context="regular_add",
            full_market_state={"full_market_ai_top8": False},
            min_position_size=1,
            enabled=True,
            max_non_top8_volume=1,
        )
        self.assertEqual(selected, 6)
        self.assertEqual(fields["stage056_budget_cap_reason"], "non_flat_entry_context")

        selected, fields = _stage056_apply_full_market_ai_budget_cap(
            sizing={"selected_volume": 6},
            entry_context="flat_entry",
            full_market_state={"full_market_ai_top8": False},
            min_position_size=1,
            enabled=False,
            max_non_top8_volume=1,
        )
        self.assertEqual(selected, 6)
        self.assertEqual(fields["stage056_budget_cap_reason"], "disabled")

    def test_full_market_lookup_uses_latest_eval_date_not_after_entry_date(self) -> None:
        lookup = _build_stage056_full_market_lookup(
            pd.DataFrame(
                [
                    {
                        "eval_date": "2022-03-31",
                        "product_vt_symbol": "rb.SHFE",
                        "stage021_ai_top8": False,
                        "ai_rank_desc": 12,
                    },
                    {
                        "eval_date": "2022-04-30",
                        "product_vt_symbol": "rb.SHFE",
                        "stage021_ai_top8": True,
                        "ai_rank_desc": 4,
                    },
                ]
            )
        )

        before_april_update = _stage056_lookup_full_market_ai_state(lookup, "rb.SHFE", pd.Timestamp("2022-04-15"))
        after_april_update = _stage056_lookup_full_market_ai_state(lookup, "rb.SHFE", pd.Timestamp("2022-05-02"))

        self.assertFalse(before_april_update["full_market_ai_top8"])
        self.assertEqual(before_april_update["full_market_eval_date"], "2022-03-31")
        self.assertTrue(after_april_update["full_market_ai_top8"])
        self.assertEqual(after_april_update["full_market_eval_date"], "2022-04-30")


if __name__ == "__main__":
    unittest.main()
