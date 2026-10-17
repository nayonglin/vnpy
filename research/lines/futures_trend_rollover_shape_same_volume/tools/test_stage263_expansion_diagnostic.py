import unittest

import pandas as pd

from stage263_run_expansion_diagnostic import remove_undefined_rank_months


class UndefinedRankMonthTests(unittest.TestCase):
    def test_constant_future_cross_section_has_no_rank_information(self):
        frame = pd.DataFrame({"eval_date": pd.to_datetime(["2018-01-31"]*3 + ["2020-01-31"]*3),
                              "future_net_pnl_60d": [0., 0., 0., -1., 0., 2.],
                              "feature": [0., 0., 0., 1., 2., 3.]})
        clean, audit = remove_undefined_rank_months(frame)
        self.assertEqual(clean.index.tolist(), [3, 4, 5])
        self.assertEqual(clean.feature.tolist(), [1., 2., 3.])
        self.assertEqual(audit["removed_months"], 1)
        self.assertEqual(audit["removed_rows"], 3)


if __name__ == "__main__":
    unittest.main()
