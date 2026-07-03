from __future__ import annotations

from pathlib import Path
import sys
import unittest


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage026_cool_quality_add_risk_engine import (  # noqa: E402
    _stage026_apply_cool_quality_add_risk,
    _stage026_is_rsi_exhaustion,
    _stage026_sizing_with_signal_fields,
)


class RebuiltC9V2Stage026CoolQualityAddRiskEngineTest(unittest.TestCase):
    def test_cool_quality_adds_floor_25pct_integer_risk_for_top_ai_non_exhausted_entry(self) -> None:
        selected, fields = _stage026_apply_cool_quality_add_risk(
            sizing={
                "selected_volume": 8,
                "ai_product_pool_rank": 3,
                "risk_multiplier": 1,
                "rsi_value": 62,
            },
            direction="long",
            entry_context="flat_entry",
            enabled=True,
        )

        self.assertEqual(selected, 10)
        self.assertEqual(fields["stage026_cool_quality_add_risk_applied"], 1)
        self.assertEqual(fields["stage026_cool_quality_add_risk_added_volume"], 2)
        self.assertEqual(fields["stage026_cool_quality_add_risk_reason"], "stage026_cool_quality_floor25_add_risk")
        self.assertEqual(fields["stage026_cool_quality_ai_rank_hit"], 1)
        self.assertEqual(fields["stage026_cool_quality_rsi_exhaustion_hit"], 0)

    def test_cool_quality_preserves_non_top_ai_hot_rsi_risk_ge2_small_integer_or_non_flat(self) -> None:
        cases = [
            (
                {"selected_volume": 8, "ai_product_pool_rank": 5, "risk_multiplier": 1, "rsi_value": 62},
                "long",
                "flat_entry",
                "ai_rank_outside_stage026_top_band",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 3, "risk_multiplier": 1, "rsi_value": 80},
                "long",
                "flat_entry",
                "rsi_in_stage026_exhaustion_zone",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 3, "risk_multiplier": 2, "rsi_value": 62},
                "long",
                "flat_entry",
                "risk_multiplier_not_below_stage026_floor",
            ),
            (
                {"selected_volume": 3, "ai_product_pool_rank": 3, "risk_multiplier": 1, "rsi_value": 62},
                "long",
                "flat_entry",
                "floor25_no_integer_increment",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 3, "risk_multiplier": 1, "rsi_value": 62},
                "long",
                "regular_add",
                "non_flat_entry_context",
            ),
        ]

        for sizing, direction, context, reason in cases:
            with self.subTest(reason=reason):
                selected, fields = _stage026_apply_cool_quality_add_risk(
                    sizing=sizing,
                    direction=direction,
                    entry_context=context,
                    enabled=True,
                )

                self.assertEqual(selected, int(sizing["selected_volume"]))
                self.assertEqual(fields["stage026_cool_quality_add_risk_applied"], 0)
                self.assertEqual(fields["stage026_cool_quality_add_risk_reason"], reason)

    def test_short_rsi_exhaustion_uses_lower_tail(self) -> None:
        self.assertTrue(_stage026_is_rsi_exhaustion("short", 20))
        self.assertFalse(_stage026_is_rsi_exhaustion("short", 40))
        self.assertTrue(_stage026_is_rsi_exhaustion("long", 80))
        self.assertFalse(_stage026_is_rsi_exhaustion("long", 60))

    def test_sizing_reads_rsi_from_signal_data_when_sizing_omits_it(self) -> None:
        plan = {
            "sizing": {
                "selected_volume": 8,
                "ai_product_pool_rank": 3,
                "risk_multiplier": 1,
            },
            "signal_data": {
                "rsi_value": 62,
            },
        }

        sizing = _stage026_sizing_with_signal_fields(plan)
        selected, fields = _stage026_apply_cool_quality_add_risk(
            sizing=sizing,
            direction="long",
            entry_context="flat_entry",
            enabled=True,
        )

        self.assertEqual(selected, 10)
        self.assertEqual(fields["stage026_cool_quality_add_risk_applied"], 1)


if __name__ == "__main__":
    unittest.main()
