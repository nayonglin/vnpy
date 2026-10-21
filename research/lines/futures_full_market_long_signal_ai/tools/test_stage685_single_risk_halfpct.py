"""Small half-percent effectiveness fixtures; no real payload or actual run."""
import importlib.util
from pathlib import Path
import types
import unittest
import pandas as pd

P=Path(__file__).with_name('stage685_single_risk_halfpct.py')

class HalfPercentRisk(unittest.TestCase):
    def setUp(self):
        self.assertTrue(P.exists(),'Stage685 half-percent implementation missing')
        spec=importlib.util.spec_from_file_location('fixture685',P)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.old=self.m.cash.kernel;self.new=self.m.private_kernel

    def economics(self):
        return {e:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
            round_lot=1,tick_size=.1,vendor_margin_rate=.1) for e in ('P.X.203001','Q.X.203001','R.X.203001','S.X.203001','T.X.203001')}

    def test_effective_half_percent_raw_budget_is_twice_baseline_without_mutation(self):
        before=self.m.snapshot_old_globals()
        c=[dict(event_id='a',reference_epoch='P.X.203001',u_close=100.,N_u=4.,entry_capacity_qty=100000)]
        a=self.old.original.reserve_batch(c,1000000.,0.,0.,self.economics(),'base','NARROW')[0]
        b=self.new.reserve_batch(c,1000000.,0.,0.,self.economics(),'base','NARROW')[0]
        self.assertEqual(b['target_qty_unscaled'],2*a['target_qty_unscaled'])
        self.assertEqual(b['allocated_risk'],5000.)
        self.assertEqual(b['unit_risk_u'],a['unit_risk_u'])
        self.assertEqual(self.m.parameter_receipt(before)['effective']['SINGLE_RISK'],.005)
        self.assertEqual(before,self.m.snapshot_old_globals())
        self.assertEqual(self.old.original.SINGLE_RISK,.0025)

    def test_joint_two_percent_cap_and_capacity_order_remain_fixed(self):
        c=[dict(event_id=e,reference_epoch=e,u_close=100.,N_u=40.,entry_capacity_qty=1 if i==0 else 100000)
            for i,e in enumerate(self.economics())]
        rows=self.new.reserve_capped(c,1000000.,0.,0.,self.economics(),'base')
        self.assertAlmostEqual(sum(r['allocated_risk'] for r in rows),20000.)
        self.assertTrue(all(abs(r['joint_scale']-.8)<1e-12 for r in rows))
        self.assertEqual(rows[0]['qty_cap'],1)
        self.assertEqual(rows[0]['allocated_risk'],rows[1]['allocated_risk'])
        self.assertIs(self.new.run_cash_account.__code__,self.old.run_cash_account.__code__)
        self.assertIs(self.new.run_cash_account.__globals__['execution_quantity'],self.old.execution_quantity)
        self.assertIs(self.new.run_cash_account.__globals__['reduction_targets'],self.old.reduction_targets)

    def test_real_cash_call_reaches_half_percent_budget(self):
        dates=[f'2020-01-{i:02d}' for i in range(1,31)]
        bars=[dict(contract_epoch_id='P.X.203001',trade_date=d,open=100.,high=102.,low=99.5,close=100.,volume=10000000.,quality_status='accepted') for d in dates]
        market=self.old.ref.Market.from_records(bars,dates)
        signal=pd.DataFrame([dict(event_id='a',mother_event_id='p',product_id='P.X',family_id='P.X',reference_epoch='P.X.203001',anchor_epoch='P.X.203001',u_index=20,u_date=dates[20],D_index=21,N_u=4.,low20_u=98.,u_close=100.,history_run=21,lifecycle_index=99,entry_capacity_qty=100000,potential=1)])
        prepared=({20:signal.to_dict('records')},{k:{'P.X':'P.X.203001'} for k in range(30)})
        before=self.m.snapshot_old_globals()
        a=self.old.run_cash_account(signal,market,dates,self.economics(),'base','same',21,21,prepared=prepared)
        b=self.new.run_cash_account(signal,market,dates,self.economics(),'base','same',21,21,prepared=prepared)
        self.assertEqual(b['budgets'][0]['target_qty_unscaled'],2*a['budgets'][0]['target_qty_unscaled'])
        self.assertGreater(b['fills'][0]['qty'],a['fills'][0]['qty'])
        self.assertEqual(b['open_episodes'][0]['R0'],.25*4.)
        self.assertEqual(b['open_episodes'][0]['risk_per_lot'],a['open_episodes'][0]['risk_per_lot'])
        self.assertEqual(before,self.m.snapshot_old_globals())

    def test_halfpct_output_guard_precedes_protocol_read(self):
        with self.assertRaisesRegex(ValueError,'unique fresh685'):
            self.m.authorize(types.SimpleNamespace(output='/private/tmp/not685'))

if __name__=='__main__':unittest.main()
