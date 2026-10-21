"""Small runner-only synthetic fixtures; no historic inputs, fit or cash."""
import importlib.util
from pathlib import Path
import unittest
import pandas as pd

spec=importlib.util.spec_from_file_location('runner597',Path(__file__).with_name('stage597_winner_addition_cash.py'))
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class RunnerContracts(unittest.TestCase):
    def test_add_root_not_mislabeled_as_common_fresh(self):
        old=pd.DataFrame([dict(event_id='e1',epoch='x',date='d1',qty=2),dict(event_id='e2',epoch='x',date='d2',qty=1)])
        fills=[dict(root_id=r,event_id=e,epoch='x',date=d,side='BUY',qty=q) for r,e,d,q in [('r1','e1','d1',3),('add','e2','d2',2),('r3','e3','d3',1)]]
        result=runner.fresh_overlap(old,dict(fills=fills,add_root_ids=['add']))
        self.assertIsNotNone(result)
        by=result.set_index('event_id')
        self.assertEqual(by.loc['e1','participation'],'common')
        self.assertEqual(by.loc['e2','participation'],'A_only')
        self.assertTrue(by.loc['e2','C_add_same_event'])
        self.assertEqual(by.loc['e3','participation'],'C_only')
        self.assertEqual(by.loc['e1','quantity_difference_C_minus_A'],1)

    def test_material_add_unknown_and_actual_root_counts(self):
        b=dict(add_audit=[dict(unknown=True,reason='unknown_u')],add_root_ids=['one'],fills=[dict(root_id='one',side='BUY',qty=2,fee=4.,slippage=10.),dict(root_id='one',side='SELL',qty=1,fee=2.,slippage=5.)])
        s=runner.addition_summary(b)
        self.assertTrue(s['material_add_unknown'])
        self.assertEqual(s['actual_add_roots'],1)
        self.assertEqual(s['add_buy_qty'],2)
        self.assertEqual(s['add_fees'],6.)

    def test_per_u_cutoff_check_without_truncating_primary(self):
        s=pd.DataFrame([dict(event_id=e,policy='NARROW',arm='VOLUNTARY_RESELECT',u_close=100.,N_u=2.,low20_u=90.,u_index=i,D_index=i+1,u_date=d,cutoff=c) for e,i,d,c in [('old',1,'2022-12-30','2020-01-01'),('new',2,'2023-01-03','2023-01-01')]])
        runner.metadata_frame(s)
        self.assertEqual(len(s),2)
        s.loc[1,'cutoff']='2020-01-01'
        with self.assertRaises(ValueError):runner.metadata_frame(s)


if __name__=='__main__':unittest.main()
