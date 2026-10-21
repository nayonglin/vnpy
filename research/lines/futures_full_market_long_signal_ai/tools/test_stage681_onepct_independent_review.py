"""Small arithmetic/mutation fixtures only; no historical payload or cash run."""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
import stage681_onepct_independent_review as review
import stage102_cash_adapter as cash


def candidate(name,cap=100):
    return dict(event_id=name,reference_epoch=name,anchor_epoch=name,product_id=name,
        family_id=name,u_date='2020-01-01',u_index=0,N_u=1000.,u_close=1000.,
        entry_capacity_qty=cap,lifecycle_index=10)


def economics(names):
    return {name:dict(contract_multiplier=10.,round_lot=1,tick_size=None,
        vendor_margin_rate=.2,economics_status='exact_epoch_metadata_snapshot') for name in names}


class ArithmeticTests(unittest.TestCase):
    def test_one_percent_raw_demand_without_scaling(self):
        sig=candidate('a');rows=review.independent_reservations([sig],1e6,0.,0.,economics(['a']),'base',cash)
        row=rows[0]
        # At 1000 price: .25*1000*10 + 2*fee(2) + 2*slip(1) = 2506.
        self.assertAlmostEqual(row['unit_risk_u'],2506.)
        self.assertAlmostEqual(row['target_qty_unscaled'],10000./2506.)
        self.assertEqual(row['joint_scale'],1.)
        self.assertEqual(row['qty_cap'],3)

    def test_three_candidates_joint_total_two_percent(self):
        sig=[candidate(n) for n in ('a','b','c')]
        rows=review.independent_reservations(sig,1e6,0.,0.,economics(['a','b','c']),'base',cash)
        self.assertTrue(all(np.isclose(r['joint_scale'],2/3) for r in rows))
        self.assertAlmostEqual(sum(r['allocated_risk'] for r in rows),20000.)
        self.assertTrue(all(r['qty_cap']==2 for r in rows))

    def test_capacity_clip_does_not_redistribute(self):
        sig=[candidate('a',1),candidate('b'),candidate('c')]
        rows=review.independent_reservations(sig,1e6,0.,0.,economics(['a','b','c']),'base',cash)
        self.assertEqual([r['qty_cap'] for r in rows],[1,2,2])
        self.assertAlmostEqual(rows[0]['allocated_risk'],rows[1]['allocated_risk'])
        self.assertAlmostEqual(rows[0]['target_qty_prefloor'],rows[1]['target_qty_prefloor'])

    def test_existing_risk_stays_reserved(self):
        sig=[candidate('a'),candidate('b')]
        rows=review.independent_reservations(sig,1e6,15000.,0.,economics(['a','b']),'base',cash)
        self.assertTrue(all(np.isclose(r['joint_scale'],.25) for r in rows))
        self.assertAlmostEqual(sum(r['allocated_risk'] for r in rows),5000.)

    def test_margin_joint_limit_and_buffer(self):
        sig=candidate('a');sig['N_u']=10.
        row=review.independent_reservations([sig],1e6,0.,0.,economics(['a']),'base',cash)[0]
        self.assertEqual(row['unit_margin_u'],2200.)
        self.assertAlmostEqual(row['allocated_buffered_margin'],250000.)
        self.assertLess(row['joint_scale'],1.)

    def test_zero_equity_cannot_reserve(self):
        row=review.independent_reservations([candidate('a')],0.,0.,0.,economics(['a']),'base',cash)[0]
        self.assertEqual(row['qty_cap'],0)
        self.assertEqual(row['allocated_risk'],0)
        self.assertEqual(row['joint_scale'],0)

    def fixture(self):
        sig=candidate('a');e=economics(['a'])
        row=review.independent_reservations([sig],1e6,0.,0.,e,'base',cash)[0]
        row.update(budget_id='b',budget_kind='new_entry',u_date='2020-01-01',
            execution_date='2020-01-02',u_equity=1e6,existing_risk=0.,existing_buffered_margin=0.,
            D_qty=0,D_state='own_open_allocation_insufficient',reference_epoch='a',anchor_epoch='a')
        daily=pd.DataFrame([dict(date='2020-01-01',equity=1e6,initial_risk=0.,buffered_margin=0.,ever_insolvent='False'),
                            dict(date='2020-01-02',equity=1e6,initial_risk=0.,buffered_margin=0.,ever_insolvent='False')])
        return row,daily,pd.DataFrame([sig]).set_index('event_id',drop=False),e

    def audit(self,row,daily,signals,e):
        return review.review_budgets(pd.DataFrame([row]),daily,signals,e,'base',
            ['2020-01-01','2020-01-02'],0,.25,positions=pd.DataFrame(columns=['date','family_id','root_id']),
            cash=cash,compare=cash.compare)

    def test_saved_one_percent_fixture_accepted(self):
        row,daily,signals,e=self.fixture()
        result=self.audit(row,daily,signals,e)
        self.assertEqual(result['new_allocations'],1)
        self.assertAlmostEqual(result['max_unscaled_single_risk_fraction'],.01)

    def test_legacy_quarter_percent_mutation_rejected(self):
        row,daily,signals,e=self.fixture();row['target_qty_unscaled']/=4
        with self.assertRaises(AssertionError):self.audit(row,daily,signals,e)

    def test_next_day_increase_mutation_rejected(self):
        row,daily,signals,e=self.fixture();row['D_qty']=row['qty_cap']+1
        with self.assertRaises(AssertionError):self.audit(row,daily,signals,e)

    def test_wrong_prepare_equity_rejected(self):
        row,daily,signals,e=self.fixture();row['u_equity']+=1
        with self.assertRaises(AssertionError):self.audit(row,daily,signals,e)

    def test_annual_float_representation_is_exactly_equivalent(self):
        old=pd.DataFrame([dict(account='a',year='2020',source_days='243',partial='False',
            start='2020-01-02',end='2020-12-31',ending_equity='1049052.6414999999')])
        new=old.copy();new.loc[0,'ending_equity']='1049052.6415'
        result=review.annual_equivalence(new,old)
        self.assertEqual(result['serialization_only_cells'],1)
        self.assertEqual(result['max_numeric_difference'],0.)

    def test_annual_source_days_change_is_rejected(self):
        old=pd.DataFrame([dict(account='a',year='2020',source_days='243',ending_equity='100')])
        new=old.copy();new.loc[0,'source_days']='244'
        with self.assertRaises(AssertionError):review.annual_equivalence(new,old)

    def test_annual_nonzero_float_difference_is_rejected(self):
        old=pd.DataFrame([dict(account='a',year='2020',source_days='243',ending_equity='100')])
        new=old.copy();new.loc[0,'ending_equity']='100.00000001'
        with self.assertRaises(AssertionError):review.annual_equivalence(new,old)


if __name__=='__main__':unittest.main()
