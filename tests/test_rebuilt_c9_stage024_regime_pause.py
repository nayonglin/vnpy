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


from stage024_causal_high_vol_pause_engine import _stage024_apply_regime_pause_gate  # noqa: E402


class RebuiltC9Stage024RegimePauseTest(unittest.TestCase):
    def test_pause_gate_skips_only_target_flat_entry(self) -> None:
        selected, fields = _stage024_apply_regime_pause_gate(
            sizing={"selected_volume": 5},
            entry_context="flat_entry",
            regime_info={
                "stage018_joint_regime": "high_vol_high_eff",
                "stage018_regime_source_date": "2022-07-14",
            },
            enabled=True,
            target_regimes=("high_vol_high_eff",),
        )
        self.assertEqual(selected, 0)
        self.assertEqual(fields["stage024_pause_gate_applied"], 1)
        self.assertEqual(fields["stage024_pause_gate_reason"], "stage024_causal_high_vol_pause_flat_entry")
        self.assertEqual(fields["stage024_pause_gate_reduced_volume"], 5)

        selected, fields = _stage024_apply_regime_pause_gate(
            sizing={"selected_volume": 5},
            entry_context="regular_add",
            regime_info={"stage018_joint_regime": "high_vol_high_eff"},
            enabled=True,
            target_regimes=("high_vol_high_eff",),
        )
        self.assertEqual(selected, 5)
        self.assertEqual(fields["stage024_pause_gate_applied"], 0)
        self.assertEqual(fields["stage024_pause_gate_reason"], "non_flat_entry_context")

        selected, fields = _stage024_apply_regime_pause_gate(
            sizing={"selected_volume": 5},
            entry_context="flat_entry",
            regime_info={"stage018_joint_regime": "trend_clean"},
            enabled=True,
            target_regimes=("high_vol_high_eff",),
        )
        self.assertEqual(selected, 5)
        self.assertEqual(fields["stage024_pause_gate_applied"], 0)
        self.assertEqual(fields["stage024_pause_gate_reason"], "regime_not_target")


if __name__ == "__main__":
    unittest.main()
