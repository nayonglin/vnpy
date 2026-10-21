"""Synthetic financial failure checks; no actual files/cache/fit/cash kernel."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixture500',TOOLS/'stage500_member_identity_cash_review.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Review500Checks(unittest.TestCase):
    def points(self):
        return [dict(window=w,cost=c,active_total_return_pct=1.,return_percentage_point_difference=.1,
            drawdown_percentage_point_difference=.1,ci95_low=.0001) for w in m.WINDOWS for c in m.COSTS]
    def held(self):
        return dict(groups={s:dict(known_u_equal_mean_increment_R=.01,unknown_differential_selected_events=0)
            for s in ['holdout_0','holdout_1']})
    def test_strict_primary_dd_and_unknowns_cannot_pass(self):
        p,h=self.points(),self.held();self.assertTrue(m.gate(p,h,wealth=True,stale=False,execution_unknown=False)['nominal_pass'])
        p[1]['drawdown_percentage_point_difference']=0.
        self.assertFalse(m.gate(p,h,wealth=True,stale=False,execution_unknown=False)['nominal_pass'])
        p=self.points();h['groups']['holdout_1']['unknown_differential_selected_events']=1
        self.assertFalse(m.gate(p,h,wealth=True,stale=False,execution_unknown=False)['nominal_pass'])
        h=self.held();self.assertFalse(m.gate(p,h,wealth=True,stale=True,execution_unknown=False)['nominal_pass'])
        self.assertFalse(m.gate(p,h,wealth=True,stale=False,execution_unknown=True)['nominal_pass'])
    def test_paired_original_indices_exact_and_insolvency_not_repaired(self):
        a=pd.DataFrame(dict(date=['2020-01-02','2020-01-03'],equity=[1100000.,990000.],ever_insolvent=[False,False]))
        b=pd.DataFrame(dict(date=a.date,equity=[1000000.,1000000.],ever_insolvent=[False,False]))
        index=np.tile(np.array([1,0]),(2000,1));stats,draw=m.paired(a,b,index)
        self.assertTrue(np.allclose(draw,np.log(.99)/2))
        self.assertAlmostEqual(stats['cumulative_log_difference'],np.log(.99))
        bad=a.copy();bad.loc[1,'equity']=0.;bad.loc[1,'ever_insolvent']=True
        stats,draw=m.paired(bad,b,index);self.assertIsNone(stats);self.assertTrue(np.isnan(draw).all())
    def test_raw_checkpoint_changed_fee_is_detected_and_ids_strict(self):
        original=[dict(root_id='r',fee=2.,qty=1,date='2020-01-02',unknown=None)]
        saved=pd.DataFrame([dict(root_id='r',fee='2.0000000000000004',qty='1',date='2020-01-02',unknown='')])
        m.semantic_raw_table(saved,original,'synthetic')
        changed=saved.copy();changed.loc[0,'fee']='4'
        with self.assertRaises(AssertionError):m.semantic_raw_table(changed,original,'double fee')
        changed=saved.copy();changed.loc[0,'root_id']='other'
        with self.assertRaises(AssertionError):m.semantic_raw_table(changed,original,'identity')
    def test_saved_fill_slippage_never_double_deducted(self):
        core=m.load('stage102_cash_core.py')
        fills=pd.DataFrame([dict(date='2020-01-02',side='BUY',root='r',qty=1,fill=101.,multiplier=10.,fee=2.,slippage=10.),
            dict(date='2020-01-03',side='SELL',root='r',qty=1,fill=109.,multiplier=10.,fee=2.,slippage=10.)])
        daily,roots,opened=core.replay_fill_cash(fills)
        self.assertEqual(daily.cash.iloc[-1],1000076.)
        self.assertEqual(roots['r']['net'],76.);self.assertEqual(opened,{})
        self.assertNotEqual(daily.cash.iloc[-1],1000056.)
    def test_diagnostics_infers_numeric_daily_counts_from_cached_bytes(self):
        raw=b'date,year,family_id,stale_positions,stale_notional,equity,ever_insolvent\n2020-01-02,2020,SHFE.cu,0,0.0,1000000.0,False\n'
        frame=m.diagnostic_frame(raw,compression=None)
        self.assertEqual(frame.date.tolist(),['2020-01-02'])
        self.assertEqual(frame.year.tolist(),['2020'])
        self.assertEqual(int((frame.stale_positions>0).sum()),0)
        self.assertEqual(float(frame.equity.iloc[0]),1000000.)
    def test_recovery_exact_type_budget_and_prior_failure_required(self):
        b=dict(path='/synthetic/terminal.json',bytes=1,sha256='synthetic')
        expected=dict(schema='stage500_dtype_adapter_recovery_v1',prior_terminal_binding=b,
            current_native_cache_reads_max=1,cumulative_native_cache_reads_max=2,
            prior_complete_cash_review_accounts=0,prior_partial_first_account_recertified=False,
            source_model_held_argmax_reruns=0,fit=0,strategy_cash_replays=0,native_SQL=0)
        auth=dict(recovery=expected)
        prior=dict(status='failed',error=dict(type='TypeError',message="'>' not supported between instances of 'str' and 'int'"),
            reads_by_path={'/cache.npz':1},predictive_fits=0,strategy_cash_replays=0,native_SQL=0)
        result=m.recovery_contract(auth,prior,b,'/cache.npz')
        self.assertFalse(result['prior_partial_first_account_scope_inherited_as_complete'])
        bad=dict(recovery=dict(expected,cumulative_native_cache_reads_max=3))
        with self.assertRaises(AssertionError):m.recovery_contract(bad,prior,b,'/cache.npz')
        bad_prior=dict(prior,status='completed')
        with self.assertRaises(AssertionError):m.recovery_contract(auth,bad_prior,b,'/cache.npz')


if __name__=='__main__':unittest.main()
