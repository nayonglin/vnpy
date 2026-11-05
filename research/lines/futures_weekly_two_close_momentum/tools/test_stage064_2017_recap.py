from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from stage064_2017_recap import RUN, DESTINATION, load_frozen, marked_value, write


class Annual2017RecapTest(unittest.TestCase):
    def test_annual_overlap_uses_the_2015_continuous_account(self):
        bundle = load_frozen(RUN)
        self.assertEqual(bundle.inputs["start"], "2015-01-01")
        self.assertEqual(bundle.inputs["initial"], 200000)
        self.assertEqual((len(bundle.closed), len(bundle.residual)), (141, 0))
        self.assertEqual((bundle.closed.entry_day.lt("2017-01-01").sum(),
                          bundle.closed.exit_day.gt("2017-12-31").sum()), (2, 5))
        self.assertEqual((bundle.closed.net_pnl.gt(0).sum(), bundle.closed.net_pnl.lt(0).sum()), (40, 101))
        self.assertEqual(bundle.closed.net_pnl.sum(), -100360)
        self.assertEqual(bundle.calendar_year_pnl, -102655)
        self.assertEqual((bundle.year_open_equity, bundle.year_end_equity), (316340, 213685))
        self.assertEqual(bundle.metrics["equity"], 1249535)
        self.assertEqual(len(bundle.rejected), 0)

    def test_incoming_position_contribution_starts_at_prior_year_mark(self):
        legs = pd.DataFrame([
            dict(date="2016-12-20", side=1, volume=1, price=100, size=10,
                 slippage=2, commission=0, epoch="E", reason="entry"),
            dict(date="2017-02-01", side=-1, volume=1, price=120, size=10,
                 slippage=2, commission=0, epoch="E", reason="touch_intraday"),
        ])
        exact = pd.DataFrame([dict(contract_epoch_id="E", date=pd.Timestamp("2016-12-30"), close=110)]
                             ).set_index(["contract_epoch_id", "date"])
        self.assertEqual(marked_value(legs, "2016-12-30", exact), 98)
        self.assertEqual(marked_value(legs, "2017-12-29", exact), 196)
        self.assertEqual(marked_value(legs, "2017-12-29", exact)
                         - marked_value(legs, "2016-12-30", exact), 98)
        self.assertEqual(marked_value(legs, "2016-12-01", exact), 0)

    def test_wrong_source_and_unregistered_outputs_are_rejected(self):
        with TemporaryDirectory() as temp:
            with self.assertRaises((ValueError, FileNotFoundError)):
                load_frozen(Path(temp) / "2017-01-01")
            with self.assertRaises(ValueError):
                write(RUN, Path(temp) / "wrong-output")
        with self.assertRaises(FileExistsError):
            write(RUN, DESTINATION.parent)


if __name__ == "__main__":
    unittest.main()
