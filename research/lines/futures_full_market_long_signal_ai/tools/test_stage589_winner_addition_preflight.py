"""Finite synthetic contracts only: no accepted data, fit, or cash execution."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import pandas as pd

spec=importlib.util.spec_from_file_location('stage589_fixture',Path(__file__).with_name('stage589_winner_addition_preflight.py'))
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=Path(__file__).parent
        names=['stage042_cross_session_experiment.py','stage070_policy_kernel.py','stage156_voluntary_choices.py']
        cls.original=probe.helpers_from_raw({n:(folder/n).read_bytes() for n in names})

    def test_buffered_margin_only_upper_not_margin_plus_fee(self):
        h=SimpleNamespace(unit_estimate=lambda *a:dict(risk_per_lot=24.25,buffered_margin_per_lot=220.,fee_roundtrip_per_lot=4.),floor_lot=lambda q,L:int(q//L)*L)
        v=probe.calculate_upper(10000.,0.,0.,2279.,dict(u_close=100.,N_u=.1,entry_capacity_qty=10),dict(round_lot=1),'base',h)
        self.assertEqual(v['qty_upper'],1)
        self.assertGreater(v['raw_upper'],1.)

    def test_remaining_quantity_entry_fee_and_no_double_slip(self):
        h=SimpleNamespace(adverse_quote=lambda *a:dict(fill_price=109.),fee_at=lambda *a:2.)
        p=dict(qty=2.,multiplier=10.,mark=110.,entry_fill=100.)
        self.assertEqual(probe.liquidation_profit([p],{},'base',h),172.)

    def test_original_winner_before_same_epoch_intersection(self):
        def organize(frame):
            return {0:frame.to_dict('records')},{}
        def select(rows,occupied,economics,cash):
            return [sorted(rows,key=lambda r:(r['product_id'].endswith('_F'),r['product_id'],r['reference_epoch']))[0]],{}
        h=SimpleNamespace(organize=organize,select_family_candidates=select)
        s=pd.DataFrame([dict(u_index=0,product_id='p_F',family_id='F',reference_epoch='held'),dict(u_index=0,product_id='p',family_id='F',reference_epoch='new')])
        winners=probe.select_original_winners(s,{},h)
        self.assertEqual(winners[0][0]['reference_epoch'],'new')

    def test_full_primary_window_keeps_both_original_model_cutoffs(self):
        s=pd.DataFrame([dict(u_date='2022-12-30',cutoff='2020-01-01'),dict(u_date='2023-01-03',cutoff='2023-01-01'),dict(u_date='2023-01-04',cutoff='2023-01-01')])
        scoped=probe.scope_signals(s,['2022-12-30','2023-01-03','2023-01-04'],self.original)
        self.assertEqual(scoped.cutoff.tolist(),['2020-01-01','2023-01-01'])
        cold=probe.scope_signals(s,['2023-01-03','2023-01-04'],self.original)
        self.assertEqual(cold.cutoff.tolist(),['2023-01-01'])

    def test_known_zero_positive_and_unknown_are_distinct(self):
        e=dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,round_lot=1,tick_size=1.,vendor_margin_rate=.2)
        c=dict(event_id='event',u_index=100,D_index=101,u_date='2023-01-03',cutoff='2023-01-01',product_id='p',family_id='F',reference_epoch='held',potential=1,N_u=.1,u_close=110.,entry_capacity_qty=10,lifecycle_index=200,effective_lifecycle_index=200)
        p=dict(account_id='own',scenario='base',date='2023-01-03',root_id='root',event_id='entry',family_id='F',product_id='p',epoch='held',qty=2.,entry_fill=100.,multiplier=10.,margin_rate=.2,risk_per_lot=1.,mark=110.,mark_state='native_close',stale_days=0.,force_next='',reduce_to_next='')
        daily=pd.DataFrame([dict(account_id='own',scenario='base',date=day,equity=20000.,initial_risk=2.,buffered_margin=484.,open_positions=1,stale_positions=0,ever_insolvent='False') for day in ['2023-01-03','2023-01-04']])
        old=dict(execution_unknown=True,any_historical_stale=False,entry_execution_unknown=0,capacity_unknown_roots=1)
        spec=dict(account_id='own',scenario='base',window='cold_2023')
        rows,info=probe.evaluate_account(spec,pd.DataFrame([c]),daily,pd.DataFrame([p]),{'held':e},self.original,old)
        self.assertEqual(rows[0]['state'],'positive_upper');self.assertFalse(info['no_first_modeled_divergence'])
        self.assertEqual(rows[0]['net_profit'],172.)
        c['entry_capacity_qty']=0
        rows,info=probe.evaluate_account(spec,pd.DataFrame([c]),daily,pd.DataFrame([p]),{'held':e},self.original,old)
        self.assertEqual(rows[0]['state'],'zero_upper');self.assertTrue(info['no_first_modeled_divergence'])
        p['force_next']='nan'
        rows,info=probe.evaluate_account(spec,pd.DataFrame([c]),daily,pd.DataFrame([p]),{'held':e},self.original,old)
        self.assertEqual(rows[0]['state'],'unknown');self.assertIsNone(rows[0]['qty_upper']);self.assertFalse(info['no_first_modeled_divergence'])


if __name__=='__main__':unittest.main()
