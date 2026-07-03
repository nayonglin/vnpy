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


from stage036_overheat_recovery_pilot_engine import (  # noqa: E402
    _stage036_apply_overheat_recovery_gate,
)


class RebuiltC9Stage036OverheatRecoveryGateTest(unittest.TestCase):
    def test_overheat_high_vol_narrow_consensus_caps_flat_entry_to_one(self) -> None:
        selected, fields = _stage036_apply_overheat_recovery_gate(
            sizing={"selected_volume": 7},
            entry_context="flat_entry",
            regime_info={
                "stage018_joint_regime": "high_vol_high_eff",
                "stage018_regime_source_date": "2022-08-30",
            },
            account_state={"portfolio_return_63d_pct": 25.0, "portfolio_drawdown_pct": 0.12},
            ai_state={"consensus_top8_count": 2},
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage036_overheat_gate_applied"], 1)
        self.assertEqual(fields["stage036_overheat_gate_reason"], "stage036_overheat_high_vol_narrow_consensus_pilot")
        self.assertEqual(fields["stage036_overheat_gate_reduced_volume"], 6)

    def test_recovery_drawdown_or_63d_loss_is_protected(self) -> None:
        selected, fields = _stage036_apply_overheat_recovery_gate(
            sizing={"selected_volume": 7},
            entry_context="flat_entry",
            regime_info={"stage018_joint_regime": "high_vol_high_eff"},
            account_state={"portfolio_return_63d_pct": 25.0, "portfolio_drawdown_pct": 0.31},
            ai_state={"consensus_top8_count": 2},
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 7)
        self.assertEqual(fields["stage036_overheat_gate_applied"], 0)
        self.assertEqual(fields["stage036_overheat_gate_reason"], "recovery_drawdown_protected")

        selected, fields = _stage036_apply_overheat_recovery_gate(
            sizing={"selected_volume": 7},
            entry_context="flat_entry",
            regime_info={"stage018_joint_regime": "high_vol_high_eff"},
            account_state={"portfolio_return_63d_pct": -21.0, "portfolio_drawdown_pct": 0.05},
            ai_state={"consensus_top8_count": 2},
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 7)
        self.assertEqual(fields["stage036_overheat_gate_applied"], 0)
        self.assertEqual(fields["stage036_overheat_gate_reason"], "recovery_63d_loss_protected")

    def test_gate_preserves_non_target_regime_wide_consensus_and_non_flat_entry(self) -> None:
        selected, fields = _stage036_apply_overheat_recovery_gate(
            sizing={"selected_volume": 7},
            entry_context="flat_entry",
            regime_info={"stage018_joint_regime": "trend_clean"},
            account_state={"portfolio_return_63d_pct": 25.0, "portfolio_drawdown_pct": 0.12},
            ai_state={"consensus_top8_count": 2},
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 7)
        self.assertEqual(fields["stage036_overheat_gate_reason"], "regime_not_target")

        selected, fields = _stage036_apply_overheat_recovery_gate(
            sizing={"selected_volume": 7},
            entry_context="flat_entry",
            regime_info={"stage018_joint_regime": "high_vol_high_eff"},
            account_state={"portfolio_return_63d_pct": 25.0, "portfolio_drawdown_pct": 0.12},
            ai_state={"consensus_top8_count": 4},
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 7)
        self.assertEqual(fields["stage036_overheat_gate_reason"], "consensus_not_narrow")

        selected, fields = _stage036_apply_overheat_recovery_gate(
            sizing={"selected_volume": 7},
            entry_context="regular_add",
            regime_info={"stage018_joint_regime": "high_vol_high_eff"},
            account_state={"portfolio_return_63d_pct": 25.0, "portfolio_drawdown_pct": 0.12},
            ai_state={"consensus_top8_count": 2},
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 7)
        self.assertEqual(fields["stage036_overheat_gate_reason"], "non_flat_entry_context")


if __name__ == "__main__":
    unittest.main()
