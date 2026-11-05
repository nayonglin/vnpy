import unittest
from decimal import Decimal

from run_weekly_portfolio import entry_risk_lots, affordable_lots


class CashRiskSizingTest(unittest.TestCase):
    def test_long_short_exact_boundary(self):
        for side, price, stop in [(1, 100.3, 100), (-1, 100, 100.3)]:
            with self.subTest(side=side):
                budget, risk, lots = entry_risk_lots(30_000, side, price, stop, 1_000)
                self.assertEqual((budget, risk, lots), (600, 300, 2))

    def test_crossed_or_touched_stop_and_below_one_lot(self):
        for args in [(30_000, 1, 100, 100, 10), (30_000, -1, 101, 100, 10),
                     (1_000, 1, 101, 100, 50), (-1_000, 1, 101, 100, 10)]:
            with self.subTest(args=args):
                self.assertEqual(entry_risk_lots(*args)[2], 0)

    def test_affordability_includes_cost(self):
        self.assertEqual(affordable_lots(2_009, Decimal("1000"), Decimal("5")), 1)
        self.assertEqual(affordable_lots(2_010, Decimal("1000"), Decimal("5")), 2)
        self.assertEqual(affordable_lots(-1, Decimal("1000"), Decimal("5")), 0)
