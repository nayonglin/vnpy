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


from stage013_account_state_pilot_gate_engine import (  # noqa: E402
    PILOT_ACTIVE_POSITIONS_MAX,
    PILOT_DRAWDOWN_TRIGGER_PCT,
    _stage013_apply_account_state_pilot_gate,
)


class RebuiltC9Stage013PilotGateTest(unittest.TestCase):
    def test_reduces_deep_drawdown_low_active_flat_entry_to_one_contract(self) -> None:
        sizing = {
            "selected_volume": 9,
            "portfolio_drawdown_pct": PILOT_DRAWDOWN_TRIGGER_PCT + 0.01,
        }

        selected, fields = _stage013_apply_account_state_pilot_gate(
            sizing=sizing,
            entry_context="flat_entry",
            active_positions_before=PILOT_ACTIVE_POSITIONS_MAX,
            min_position_size=1,
            enabled=True,
        )

        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage013_pilot_gate_enabled"], 1)
        self.assertEqual(fields["stage013_pilot_gate_applied"], 1)
        self.assertEqual(fields["stage013_pilot_gate_reason"], "stage013_deep_drawdown_low_active_flat_entry_pilot")
        self.assertEqual(fields["stage013_pilot_gate_selected_volume_before"], 9)
        self.assertEqual(fields["stage013_pilot_gate_selected_volume_after"], 1)

    def test_does_not_touch_non_deep_drawdown_or_non_flat_entry(self) -> None:
        shallow = {"selected_volume": 9, "portfolio_drawdown_pct": PILOT_DRAWDOWN_TRIGGER_PCT - 0.01}
        selected, fields = _stage013_apply_account_state_pilot_gate(
            sizing=shallow,
            entry_context="flat_entry",
            active_positions_before=0,
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 9)
        self.assertEqual(fields["stage013_pilot_gate_applied"], 0)
        self.assertEqual(fields["stage013_pilot_gate_reason"], "drawdown_below_stage013_trigger")

        add = {"selected_volume": 9, "portfolio_drawdown_pct": PILOT_DRAWDOWN_TRIGGER_PCT + 0.01}
        selected, fields = _stage013_apply_account_state_pilot_gate(
            sizing=add,
            entry_context="regular_add",
            active_positions_before=0,
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 9)
        self.assertEqual(fields["stage013_pilot_gate_applied"], 0)
        self.assertEqual(fields["stage013_pilot_gate_reason"], "non_flat_entry_context")


if __name__ == "__main__":
    unittest.main()
