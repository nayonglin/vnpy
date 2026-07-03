from __future__ import annotations

from pathlib import Path
import sys
import unittest


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage062_oi_confirmed_reverse_budget_engine import (  # noqa: E402
    _stage062_apply_oi_confirmed_reverse_budget_cap,
    _stage062_decision_from_metrics,
    _stage062_extract_oi_confirmed_state,
)


class RebuiltC9Stage062OiConfirmedReverseBudgetEngineTest(unittest.TestCase):
    def test_oi_confirmed_flat_entry_caps_release_to_one_contract(self) -> None:
        selected, fields = _stage062_apply_oi_confirmed_reverse_budget_cap(
            sizing={"selected_volume": 5, "oi_price_confirm_passed": 1},
            plan={},
            entry_context="flat_entry",
            min_position_size=1,
            enabled=True,
            max_oi_confirmed_volume=1,
        )

        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage062_oi_reverse_budget_applied"], 1)
        self.assertEqual(fields["stage062_oi_reverse_budget_reason"], "stage062_oi_confirmed_cap_to_one")
        self.assertEqual(fields["stage062_oi_reverse_budget_selected_volume_before"], 5)
        self.assertEqual(fields["stage062_oi_reverse_budget_selected_volume_after"], 1)
        self.assertEqual(fields["stage062_oi_reverse_budget_reduced_volume"], 4)
        self.assertEqual(fields["stage062_oi_confirmed"], 1)

    def test_oi_confirmed_aliases_are_read_from_sizing_or_plan(self) -> None:
        self.assertTrue(_stage062_extract_oi_confirmed_state({"oi_price_confirm_passed": 1}, {}))
        self.assertTrue(_stage062_extract_oi_confirmed_state({"oi_confirmed": "true"}, {}))
        self.assertTrue(_stage062_extract_oi_confirmed_state({}, {"entry_candidate_oi_confirmed": "1"}))
        self.assertTrue(
            _stage062_extract_oi_confirmed_state({}, {"candidate": {"oi_price_confirm_passed": True}})
        )
        self.assertFalse(_stage062_extract_oi_confirmed_state({"oi_price_confirm_passed": 0}, {}))

    def test_non_oi_non_flat_and_disabled_paths_do_not_change_volume(self) -> None:
        selected, fields = _stage062_apply_oi_confirmed_reverse_budget_cap(
            sizing={"selected_volume": 5, "oi_price_confirm_passed": 0},
            plan={},
            entry_context="flat_entry",
            min_position_size=1,
            enabled=True,
            max_oi_confirmed_volume=1,
        )
        self.assertEqual(selected, 5)
        self.assertEqual(fields["stage062_oi_reverse_budget_reason"], "oi_not_confirmed")

        selected, fields = _stage062_apply_oi_confirmed_reverse_budget_cap(
            sizing={"selected_volume": 5, "oi_price_confirm_passed": 1},
            plan={},
            entry_context="regular_add",
            min_position_size=1,
            enabled=True,
            max_oi_confirmed_volume=1,
        )
        self.assertEqual(selected, 5)
        self.assertEqual(fields["stage062_oi_reverse_budget_reason"], "non_flat_entry_context")

        selected, fields = _stage062_apply_oi_confirmed_reverse_budget_cap(
            sizing={"selected_volume": 5, "oi_price_confirm_passed": 1},
            plan={},
            entry_context="flat_entry",
            min_position_size=1,
            enabled=False,
            max_oi_confirmed_volume=1,
        )
        self.assertEqual(selected, 5)
        self.assertEqual(fields["stage062_oi_reverse_budget_reason"], "disabled")

    def test_decision_requires_left_tail_improvement_and_retention(self) -> None:
        decision = _stage062_decision_from_metrics(
            {
                "stage013_strict_negative_window_count": 12,
                "stage062_strict_negative_window_count": 7,
                "stage013_strict_min_return_pct": -35.0,
                "stage062_strict_min_return_pct": -18.0,
                "retention_rows": 4,
                "retention_pass_count": 4,
            }
        )
        self.assertEqual(decision["decision"], "stage062_pressure_improves_left_tail_expand_validation")

        retention_fail = _stage062_decision_from_metrics(
            {
                "stage013_strict_negative_window_count": 12,
                "stage062_strict_negative_window_count": 7,
                "stage013_strict_min_return_pct": -35.0,
                "stage062_strict_min_return_pct": -18.0,
                "retention_rows": 4,
                "retention_pass_count": 3,
            }
        )
        self.assertEqual(retention_fail["decision"], "stage062_pressure_not_enough_stop_no_param_rescue")


if __name__ == "__main__":
    unittest.main()
