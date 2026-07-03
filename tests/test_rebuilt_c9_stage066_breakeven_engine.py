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


from stage066_breakeven_after_1r_true_engine import (  # noqa: E402
    _stage066_evaluate_breakeven_update,
)


class RebuiltC9Stage066BreakevenEngineTest(unittest.TestCase):
    def test_long_arms_and_applies_breakeven_when_1r_hit_without_same_bar_retrace(self) -> None:
        result = _stage066_evaluate_breakeven_update(
            direction="long",
            entry_price=100.0,
            original_stop_price=90.0,
            current_stop_price=90.0,
            high_price=111.0,
            low_price=101.0,
            trigger_r=1.0,
            already_armed=False,
            pending_apply=False,
        )

        self.assertTrue(result["armed"])
        self.assertTrue(result["apply_now"])
        self.assertFalse(result["pending_apply"])
        self.assertEqual(result["new_stop_price"], 100.0)
        self.assertEqual(result["reason"], "stage066_breakeven_armed_and_applied")

    def test_same_bar_activation_and_retrace_is_deferred_until_next_bar(self) -> None:
        result = _stage066_evaluate_breakeven_update(
            direction="long",
            entry_price=100.0,
            original_stop_price=90.0,
            current_stop_price=90.0,
            high_price=111.0,
            low_price=99.0,
            trigger_r=1.0,
            already_armed=False,
            pending_apply=False,
        )

        self.assertTrue(result["armed"])
        self.assertFalse(result["apply_now"])
        self.assertTrue(result["pending_apply"])
        self.assertEqual(result["new_stop_price"], 90.0)
        self.assertEqual(result["reason"], "stage066_same_bar_activation_retrace_deferred")

    def test_pending_activation_applies_breakeven_on_next_bar(self) -> None:
        result = _stage066_evaluate_breakeven_update(
            direction="long",
            entry_price=100.0,
            original_stop_price=90.0,
            current_stop_price=90.0,
            high_price=103.0,
            low_price=97.0,
            trigger_r=1.0,
            already_armed=True,
            pending_apply=True,
        )

        self.assertTrue(result["armed"])
        self.assertTrue(result["apply_now"])
        self.assertFalse(result["pending_apply"])
        self.assertEqual(result["new_stop_price"], 100.0)
        self.assertEqual(result["reason"], "stage066_pending_breakeven_applied")

    def test_short_arms_and_applies_breakeven_symmetrically(self) -> None:
        result = _stage066_evaluate_breakeven_update(
            direction="short",
            entry_price=100.0,
            original_stop_price=110.0,
            current_stop_price=110.0,
            high_price=99.0,
            low_price=89.0,
            trigger_r=1.0,
            already_armed=False,
            pending_apply=False,
        )

        self.assertTrue(result["armed"])
        self.assertTrue(result["apply_now"])
        self.assertFalse(result["pending_apply"])
        self.assertEqual(result["new_stop_price"], 100.0)
        self.assertEqual(result["reason"], "stage066_breakeven_armed_and_applied")

    def test_no_update_when_existing_stop_is_already_better_than_breakeven(self) -> None:
        result = _stage066_evaluate_breakeven_update(
            direction="long",
            entry_price=100.0,
            original_stop_price=90.0,
            current_stop_price=102.0,
            high_price=113.0,
            low_price=101.0,
            trigger_r=1.0,
            already_armed=False,
            pending_apply=False,
        )

        self.assertFalse(result["armed"])
        self.assertFalse(result["apply_now"])
        self.assertEqual(result["new_stop_price"], 102.0)
        self.assertEqual(result["reason"], "stop_already_at_or_beyond_breakeven")


if __name__ == "__main__":
    unittest.main()
