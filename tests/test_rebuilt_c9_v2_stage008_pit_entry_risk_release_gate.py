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


from stage008_pit_entry_risk_release_gate_engine import (  # noqa: E402
    _stage008_apply_pit_entry_risk_release_gate,
    _stage008_sizing_with_signal_fields,
)


class RebuiltC9V2Stage008PitEntryRiskReleaseGateTest(unittest.TestCase):
    def test_gate_reduces_long_mid_rank_rsi_exhaustion_release_to_pilot_size(self) -> None:
        selected, fields = _stage008_apply_pit_entry_risk_release_gate(
            sizing={
                "selected_volume": 8,
                "ai_product_pool_rank": 6,
                "rsi_value": 80,
                "risk_multiplier": 2,
            },
            direction="long",
            entry_context="flat_entry",
            min_position_size=1,
            enabled=True,
        )

        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage008_pit_gate_applied"], 1)
        self.assertEqual(fields["stage008_pit_gate_reason"], "stage008_mid_ai_rank_rsi_exhaustion_pilot")
        self.assertEqual(fields["stage008_pit_gate_ai_rank_hit"], 1)
        self.assertEqual(fields["stage008_pit_gate_rsi_exhaustion_hit"], 1)

    def test_gate_reduces_short_mid_rank_rsi_exhaustion_release_to_pilot_size(self) -> None:
        selected, fields = _stage008_apply_pit_entry_risk_release_gate(
            sizing={
                "selected_volume": 5,
                "ai_product_pool_rank": 5,
                "rsi_value": 20,
                "risk_multiplier": 1,
            },
            direction="short",
            entry_context="flat_entry",
            min_position_size=1,
            enabled=True,
        )

        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage008_pit_gate_applied"], 1)

    def test_gate_preserves_non_mid_rank_non_exhaustion_pilot_or_non_flat(self) -> None:
        cases = [
            (
                {"selected_volume": 8, "ai_product_pool_rank": 4, "rsi_value": 80},
                "long",
                "flat_entry",
                "ai_rank_outside_stage008_band",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 6, "rsi_value": 60},
                "long",
                "flat_entry",
                "rsi_not_in_stage008_exhaustion_zone",
            ),
            (
                {"selected_volume": 1, "ai_product_pool_rank": 6, "rsi_value": 80},
                "long",
                "flat_entry",
                "already_at_or_below_stage008_pilot_size",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 6, "rsi_value": 80},
                "long",
                "regular_add",
                "non_flat_entry_context",
            ),
        ]

        for sizing, direction, context, reason in cases:
            with self.subTest(reason=reason):
                selected, fields = _stage008_apply_pit_entry_risk_release_gate(
                    sizing=sizing,
                    direction=direction,
                    entry_context=context,
                    min_position_size=1,
                    enabled=True,
                )
                self.assertEqual(selected, int(sizing["selected_volume"]))
                self.assertEqual(fields["stage008_pit_gate_applied"], 0)
                self.assertEqual(fields["stage008_pit_gate_reason"], reason)

    def test_gate_reads_rsi_from_signal_data_when_sizing_omits_it(self) -> None:
        plan = {
            "sizing": {
                "selected_volume": 8,
                "ai_product_pool_rank": 6,
                "risk_multiplier": 2,
            },
            "signal_data": {
                "rsi_value": 80,
            },
        }

        sizing = _stage008_sizing_with_signal_fields(plan)
        selected, fields = _stage008_apply_pit_entry_risk_release_gate(
            sizing=sizing,
            direction="long",
            entry_context="flat_entry",
            min_position_size=1,
            enabled=True,
        )

        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage008_pit_gate_applied"], 1)


if __name__ == "__main__":
    unittest.main()
