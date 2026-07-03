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


from stage029_account_injury_flat_entry_pause_engine import (  # noqa: E402
    _stage029_apply_account_injury_pause_gate,
)


class RebuiltC9Stage029AccountInjuryPauseTest(unittest.TestCase):
    def test_pause_gate_skips_flat_entry_on_deep_drawdown(self) -> None:
        selected, fields = _stage029_apply_account_injury_pause_gate(
            sizing={"selected_volume": 9, "portfolio_drawdown_pct": 0.21},
            entry_context="flat_entry",
            loss_streak=0,
            enabled=True,
        )
        self.assertEqual(selected, 0)
        self.assertEqual(fields["stage029_injury_pause_gate_applied"], 1)
        self.assertEqual(fields["stage029_injury_pause_gate_reason"], "stage029_account_injury_flat_entry_pause")
        self.assertEqual(fields["stage029_injury_pause_drawdown_hit"], 1)
        self.assertEqual(fields["stage029_injury_pause_loss_streak_hit"], 0)

    def test_pause_gate_skips_flat_entry_on_loss_streak(self) -> None:
        selected, fields = _stage029_apply_account_injury_pause_gate(
            sizing={"selected_volume": 5, "portfolio_drawdown_pct": 0.05},
            entry_context="flat_entry",
            loss_streak=3,
            enabled=True,
        )
        self.assertEqual(selected, 0)
        self.assertEqual(fields["stage029_injury_pause_gate_applied"], 1)
        self.assertEqual(fields["stage029_injury_pause_drawdown_hit"], 0)
        self.assertEqual(fields["stage029_injury_pause_loss_streak_hit"], 1)

    def test_pause_gate_preserves_non_injured_or_non_flat_entry(self) -> None:
        selected, fields = _stage029_apply_account_injury_pause_gate(
            sizing={"selected_volume": 5, "portfolio_drawdown_pct": 0.19},
            entry_context="flat_entry",
            loss_streak=2,
            enabled=True,
        )
        self.assertEqual(selected, 5)
        self.assertEqual(fields["stage029_injury_pause_gate_applied"], 0)
        self.assertEqual(fields["stage029_injury_pause_gate_reason"], "account_state_not_injured")

        selected, fields = _stage029_apply_account_injury_pause_gate(
            sizing={"selected_volume": 5, "portfolio_drawdown_pct": 0.40},
            entry_context="regular_add",
            loss_streak=5,
            enabled=True,
        )
        self.assertEqual(selected, 5)
        self.assertEqual(fields["stage029_injury_pause_gate_applied"], 0)
        self.assertEqual(fields["stage029_injury_pause_gate_reason"], "non_flat_entry_context")


if __name__ == "__main__":
    unittest.main()
