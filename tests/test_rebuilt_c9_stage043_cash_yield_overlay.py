import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage043_cash_yield_overlay_feasibility import (  # noqa: E402
    _audit_cash_yield_variants,
    _required_simple_annual_yield,
)


class Stage043CashYieldOverlayTest(unittest.TestCase):
    def test_required_simple_annual_yield_matches_window_deficit(self) -> None:
        required = _required_simple_annual_yield(
            start_equity=150000.0,
            end_equity=120000.0,
            elapsed_days=366,
            yield_base_capital=150000.0,
        )

        self.assertAlmostEqual(required, 30000.0 / (150000.0 * 366.0 / 365.0))

    def test_cash_yield_variant_audit_flips_synthetic_one_year_deficit(self) -> None:
        curves = pd.DataFrame(
            [
                {"requested_start": "2020-01-01", "date": "2020-01-01", "equity": 150000.0},
                {"requested_start": "2020-01-01", "date": "2021-01-01", "equity": 120000.0},
            ]
        )

        audit = _audit_cash_yield_variants(curves, yield_rates=[0.0, 0.20])

        no_yield = audit[audit["cash_yield_rate"].eq(0.0)].iloc[0]
        yield_20 = audit[audit["cash_yield_rate"].eq(0.20)].iloc[0]
        self.assertEqual(int(no_yield["negative_count"]), 1)
        self.assertLess(float(no_yield["min_return_pct"]), 0.0)
        self.assertEqual(int(yield_20["negative_count"]), 0)
        self.assertGreater(float(yield_20["min_return_pct"]), 0.0)


if __name__ == "__main__":
    unittest.main()
