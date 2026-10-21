"""One new .005 arithmetic fixture; accepted prior contracts are not retested."""
from pathlib import Path
import sys
import unittest

TOOLS=Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
import stage686_halfpct_independent_review as review
import stage102_cash_adapter as cash


class HalfPercent(unittest.TestCase):
    def test_raw_target_is_half_percent_and_cost_unit_unchanged(self):
        sig=dict(event_id='synthetic',reference_epoch='e',u_close=1000.,N_u=1000.,entry_capacity_qty=100)
        econ={'e':dict(contract_multiplier=10.,round_lot=1,tick_size=None,vendor_margin_rate=.2,
            economics_status='exact_epoch_metadata_snapshot')}
        row=review.independent_reservations([sig],1_000_000.,0.,0.,econ,'base',cash)[0]
        self.assertAlmostEqual(row['unit_risk_u'],2506.)
        self.assertAlmostEqual(row['target_qty_unscaled'],5000./2506.)
        self.assertEqual(row['joint_scale'],1.)
        self.assertEqual(row['allocated_risk'],5000.)
        self.assertEqual(row['qty_cap'],1)
        self.assertEqual(review.TOTAL,.02)
        self.assertEqual(review.MARGIN,.25)
        self.assertEqual(review.BUFFER,1.1)


if __name__=='__main__':unittest.main()
