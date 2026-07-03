from __future__ import annotations

from pathlib import Path
import sys
import tempfile
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


from stage018_regime_pilot_gate_engine import (  # noqa: E402
    STAGE018_TARGET_REGIME,
    _stage018_apply_regime_pilot_gate,
    _stage018_build_causal_regime_table,
)


class RebuiltC9Stage018RegimeGateTest(unittest.TestCase):
    def test_regime_gate_reduces_only_target_flat_entry(self) -> None:
        regime_info = {
            "stage018_joint_regime": STAGE018_TARGET_REGIME,
            "stage018_regime_source_date": "2022-07-14",
            "stage018_vol60_bucket": "high",
            "stage018_eff60_bucket": "low",
        }
        selected, fields = _stage018_apply_regime_pilot_gate(
            sizing={"selected_volume": 7},
            entry_context="flat_entry",
            regime_info=regime_info,
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 1)
        self.assertEqual(fields["stage018_regime_gate_applied"], 1)
        self.assertEqual(fields["stage018_regime_gate_reason"], "stage018_high_vol_low_eff_flat_entry_pilot")
        self.assertEqual(fields["stage018_regime_gate_selected_volume_before"], 7)
        self.assertEqual(fields["stage018_regime_gate_selected_volume_after"], 1)

        selected, fields = _stage018_apply_regime_pilot_gate(
            sizing={"selected_volume": 7},
            entry_context="regular_add",
            regime_info=regime_info,
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 7)
        self.assertEqual(fields["stage018_regime_gate_applied"], 0)
        self.assertEqual(fields["stage018_regime_gate_reason"], "non_flat_entry_context")

        selected, fields = _stage018_apply_regime_pilot_gate(
            sizing={"selected_volume": 7},
            entry_context="flat_entry",
            regime_info={"stage018_joint_regime": "trend_clean"},
            min_position_size=1,
            enabled=True,
        )
        self.assertEqual(selected, 7)
        self.assertEqual(fields["stage018_regime_gate_applied"], 0)
        self.assertEqual(fields["stage018_regime_gate_reason"], "regime_not_target")

    def test_causal_regime_table_shifts_prior_day_state_to_next_date(self) -> None:
        rows = []
        dates = pd.date_range("2022-01-03", periods=6, freq="B")
        values = [
            (0.10, 0.20, 0.02),
            (0.11, 0.19, 0.02),
            (0.12, 0.18, 0.02),
            (0.30, 0.05, -0.02),
            (0.31, 0.04, -0.02),
            (0.32, 0.03, -0.02),
        ]
        for date, (vol, eff, ma) in zip(dates, values, strict=True):
            for product in ("a.DCE", "b.DCE", "c.DCE"):
                rows.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "product_vt_symbol": product,
                        "market_realized_vol_60d": vol,
                        "market_trend_efficiency_60d": eff,
                        "market_ma20_over_ma60_60d": ma,
                    }
                )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "market_daily.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            table = _stage018_build_causal_regime_table(path, min_history_days=2)

        matched = table[table["date"].eq(pd.Timestamp("2022-01-07"))]
        self.assertEqual(len(matched), 1)
        row = matched.iloc[0]
        self.assertEqual(pd.Timestamp(row["stage018_regime_source_date"]), pd.Timestamp("2022-01-06"))
        self.assertEqual(row["stage018_joint_regime"], STAGE018_TARGET_REGIME)


if __name__ == "__main__":
    unittest.main()
