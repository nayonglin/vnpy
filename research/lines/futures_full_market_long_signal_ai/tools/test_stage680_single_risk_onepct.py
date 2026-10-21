"""Finite synthetic Stage680 tests; no cache, model, SQL or actual accounts."""
import importlib.util
from pathlib import Path
import types
import unittest
import pandas as pd

P = Path(__file__).with_name('stage680_single_risk_onepct.py')


class OnePercentRisk(unittest.TestCase):
    def setUp(self):
        self.assertTrue(P.exists(), 'Stage680 single-risk implementation missing')
        spec = importlib.util.spec_from_file_location('fixture680', P)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.old = self.m.cash.kernel
        self.new = self.m.private_kernel

    def economics(self, margin=.1):
        return {e: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10.,
            round_lot=1, tick_size=.1, vendor_margin_rate=margin) for e in ('P.X.203001', 'Q.X.203001', 'R.X.203001')}

    def candidates(self, number=1, cap=100000):
        return [dict(event_id=str(i), reference_epoch=e, u_close=100., N_u=4., entry_capacity_qty=cap)
            for i,e in enumerate(list(self.economics())[:number])]

    def test_single_uncapped_proposal_has_fourfold_risk_budget(self):
        args=(self.candidates(), 1000000., 0., 0., self.economics(), 'base', 'NARROW')
        a=self.old.original.reserve_batch(*args)[0];c=self.new.reserve_batch(*args)[0]
        self.assertEqual(c['joint_scale'], 1.)
        self.assertEqual(c['target_qty_unscaled'], 4*a['target_qty_unscaled'])
        self.assertEqual(c['allocated_risk'], 10000.)
        for field in ('unit_risk_u','unit_margin_u','unit_fee_reserve_u'):
            self.assertEqual(c[field], a[field])

    def test_joint_risk_cap_is_two_percent_and_capacity_follows_scale(self):
        cand=self.candidates(3);cand[0]['entry_capacity_qty']=1
        for candidate in cand:candidate['N_u']=40.
        rows=self.new.reserve_capped(cand,1000000.,0.,0.,self.economics(),'base')
        self.assertAlmostEqual(sum(r['allocated_risk'] for r in rows),20000.)
        self.assertTrue(all(abs(r['joint_scale']-2/3)<1e-12 for r in rows))
        self.assertEqual(rows[0]['qty_cap'],1)
        self.assertEqual(rows[1]['allocated_risk'], rows[0]['allocated_risk'])
        self.assertEqual(rows[1]['qty_cap'], rows[1]['original_qty_cap'])

    def test_existing_entry_risk_and_margin_are_subtracted_before_scale(self):
        rows=self.new.reserve_batch(self.candidates(2),1000000.,15000.,0.,self.economics(),'base','NARROW')
        self.assertAlmostEqual(sum(r['allocated_risk'] for r in rows),5000.)
        margins=self.new.reserve_batch(self.candidates(2),1000000.,0.,249000.,self.economics(),'base','NARROW')
        self.assertAlmostEqual(sum(r['allocated_buffered_margin'] for r in margins),1000.)
        self.assertTrue(all(r['joint_scale']<1 for r in margins))

    def test_D_only_reduces_own_allocation_and_same_original_function(self):
        row=self.new.reserve_capped(self.candidates(),1000000.,0.,0.,self.economics(),'base')[0]
        e=self.economics()['P.X.203001']
        q,unit=self.old.execution_quantity(row,250.,e,'base','NARROW')
        self.assertLessEqual(q,row['qty_cap'])
        self.assertLessEqual(q*unit['risk_per_lot'],row['allocated_risk']+1e-8)
        self.assertLessEqual(q*unit['actual_margin_plus_entry_fee_per_lot'],row['allocated_buffered_margin']+row['allocated_fee']+1e-8)
        self.assertIs(self.new.run_cash_account.__globals__['execution_quantity'],self.old.execution_quantity)

    def test_private_three_layer_call_graph_preserves_old_globals_and_code(self):
        before=self.m.snapshot_old_globals()
        private=self.m.build_private_kernel()
        self.assertIs(private.reserve_batch.__code__,self.old.original.reserve_batch.__code__)
        self.assertIs(private.reserve_capped.__code__,self.old.reserve_capped.__code__)
        self.assertIs(private.run_cash_account.__code__,self.old.run_cash_account.__code__)
        self.assertIs(private.run_cash_account.__defaults__,self.old.run_cash_account.__defaults__)
        self.assertEqual(private.reserve_batch.__globals__['SINGLE_RISK'],.01)
        self.assertIs(private.reserve_capped.__globals__['original'].reserve_batch,private.reserve_batch)
        self.assertIs(private.run_cash_account.__globals__['reserve_capped'],private.reserve_capped)
        self.assertEqual(self.old.SINGLE_RISK,.0025)
        self.assertEqual(self.old.original.SINGLE_RISK,.0025)
        self.assertEqual(before,self.m.snapshot_old_globals())

    def synthetic(self):
        dates=[f'2020-01-{k:02d}' for k in range(1,31)]
        bars=[dict(contract_epoch_id='P.X.203001',trade_date=d,open=100.,high=102.,low=99.5,close=100.,volume=10000000.,quality_status='accepted') for d in dates]
        market=self.old.ref.Market.from_records(bars,dates)
        sig=pd.DataFrame([dict(event_id='a',mother_event_id='p',product_id='P.X',family_id='P.X',reference_epoch='P.X.203001',anchor_epoch='P.X.203001',u_index=20,u_date=dates[20],D_index=21,N_u=4.,low20_u=98.,u_close=100.,history_run=21,lifecycle_index=99,entry_capacity_qty=100000,potential=1)])
        refs={k:{'P.X':'P.X.203001'} for k in range(len(dates))}
        return market,dates,sig,refs

    def test_real_cash_cycle_uses_private_one_percent_reservation(self):
        market,dates,sig,refs=self.synthetic();prepared=({20:sig.to_dict('records')},refs)
        before=self.m.snapshot_old_globals()
        a=self.old.run_cash_account(sig,market,dates,self.economics(),'base','same',21,21,prepared=prepared)
        c=self.new.run_cash_account(sig,market,dates,self.economics(),'base','same',21,21,prepared=prepared)
        self.assertEqual(c['budgets'][0]['target_qty_unscaled'],4*a['budgets'][0]['target_qty_unscaled'])
        self.assertGreater(c['fills'][0]['qty'],a['fills'][0]['qty'])
        self.assertEqual(c['open_episodes'][0]['risk_per_lot'],a['open_episodes'][0]['risk_per_lot'])
        self.assertEqual(c['open_episodes'][0]['R0'],1.)
        self.assertEqual(before,self.m.snapshot_old_globals())

    def test_seeded_existing_position_next_day_reduction_unchanged(self):
        market,dates,sig,refs=self.synthetic();old=self.old
        class Seeded(old.CapacityLedger):
            def __init__(self,*args):
                super().__init__(*args)
                root=dict(root_id='seed',event_id='seed',family_id='P.X',product_id='P.X',epoch='P.X.203001',entry_date=dates[20],entry_index=20,anchor_epoch='P.X.203001',multiplier=10.,margin_rate=.1,risk_per_lot=10000.,round_lot=1,R0=1.,SL0=1.,boundary=1.,expiry=99,force_reason=None)
                self.enter(root,4,100.,100.,0.,0.);self.mark('seed',100.,False)
        books=[]
        for run in (old.run_cash_account,self.new.run_cash_account):
            ns=dict(run.__globals__,CapacityLedger=Seeded)
            local=types.FunctionType(run.__code__,ns,run.__name__,run.__defaults__,run.__closure__)
            local.__kwdefaults__=run.__kwdefaults__
            books.append(local(sig.iloc[:0],market,dates,self.economics(),'base','same',21,21,prepared=({},refs)))
        self.assertEqual(books[0],books[1])
        reduction=books[1]['budgets'][0]
        self.assertEqual(reduction['budget_kind'],'existing_position_reduction')
        self.assertEqual(reduction['D_state'],'executed_reduction')
        self.assertEqual(reduction['target_existing_qty'],2)
        self.assertEqual(books[1]['open_episodes'][0]['risk_per_lot'],10000.)

    def test_paired_descriptive_outputs_require_same_dates_no_bootstrap(self):
        a=pd.DataFrame(dict(date=['d1','d2'],equity=[100.,110.]))
        b=pd.DataFrame(dict(date=['d1','d2'],equity=[100.,105.]))
        row=self.m.describe_daily_pair(a,b,100.)
        self.assertEqual(row['source_days'],2)
        self.assertEqual(row['final_equity_difference'],5.)
        self.assertFalse(row['bootstrap_performed'])
        with self.assertRaisesRegex(ValueError,'calendar'):
            self.m.describe_daily_pair(a,b.iloc[:1],100.)

    def test_missing_sharpe_cannot_pass_descriptive_dominance(self):
        good=dict(total_return_pct=10.,max_drawdown_pct=-1.,sharpe=1.,ever_insolvent=False)
        missing=dict(good,sharpe=None)
        self.assertTrue(self.m.point_dominance([dict(active_summary=good,baseline_summary=good)]))
        self.assertFalse(self.m.point_dominance([dict(active_summary=missing,baseline_summary=good)]))

    def test_unique_output_is_rejected_before_any_protocol_read(self):
        args=types.SimpleNamespace(output='/private/tmp/not_the680_authorized_output')
        with self.assertRaisesRegex(ValueError,'unique fresh680'):
            self.m.authorize(args)


if __name__=='__main__':unittest.main()
