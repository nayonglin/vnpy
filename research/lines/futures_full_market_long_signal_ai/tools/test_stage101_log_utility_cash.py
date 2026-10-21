"""New L/G cash wiring/domain/gate fixtures only; zero actual inputs or SQL."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage101_log_utility_cash.py')


def module():
    if not PATH.exists():
        return None
    spec=importlib.util.spec_from_file_location('test101_target',PATH)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class NewLogCashBehavior(unittest.TestCase):
    def setUp(self):
        self.m=module();self.assertIsNotNone(self.m,'Stage101 implementation is missing')

    def points(self):
        return [dict(window=w,cost=c,return_percentage_point_difference=(1. if (w,c)==('primary_2020','stress') else 0.),
            drawdown_percentage_point_difference=0.,ci95_low=.001,active_total_return_pct=1.,
            reference_total_return_pct=1.,identification='observed_cash_comparison')
            for w in ('primary_2020','cold_2023') for c in ('base','stress')]

    def test_main_scope_unknown_labels_do_not_gate_without_external_slots(self):
        labels=pd.DataFrame([dict(event_id='e',product_id='P.X',family_id='P.X',u_date='2020-01-02',u_index=1,
            reference_epoch='P.X2001',label_history_ready20=1,N_u=1.,low20_u=90.,u_close=100.,history_run=20,
            lifecycle_index=99,label_state='open_right_censored')])
        p=labels[['event_id','product_id','family_id','u_date','u_index','reference_epoch']].copy()
        p=p.assign(scope='main',policy='NARROW',arm='G',cutoff='2020-01-01',score=1.,history_ready20=1,selected=1)
        signals=self.m.make_signals(labels,p,'G')
        self.assertEqual(signals.potential.tolist(),[1]);self.assertNotIn('sequence_missing',signals)
        p['scope']='holdout_0'
        with self.assertRaisesRegex(ValueError,'main'):
            self.m.make_signals(labels,p,'G')

    def test_primary_strict_other_nonnegative_and_no_fake_held_requirement(self):
        points=self.points()
        gate=self.m.continuation_gate(points,False,wealth_positive=True)
        self.assertEqual(gate['status'],'supported_research_model_only')
        self.assertFalse(gate['family_holdout_performed'])
        points[1]['return_percentage_point_difference']=0.
        self.assertEqual(self.m.continuation_gate(points,False,wealth_positive=True)['status'],'unsupported')

    def test_g_four_positive_and_all_actual_wealth_positive(self):
        for value in (-1.,0.,float('nan')):
            pts=self.points();pts[0]['active_total_return_pct']=value
            gate=self.m.continuation_gate(pts,False,wealth_positive=True)
            self.assertFalse(gate['G_own_returns_positive_in_all_four']);self.assertFalse(gate['nominal_pass'])
        gate=self.m.continuation_gate(self.points(),False,wealth_positive=False)
        self.assertFalse(gate['actual_wealth_positive']);self.assertEqual(gate['status'],'unsupported')

    def test_unknown_finance_and_unfilled_signal_labels_remain_separate(self):
        pts=self.points()
        self.assertEqual(self.m.continuation_gate(pts,False,wealth_positive=True,signal_unknown_main=True)['status'],
                         'supported_research_model_only')
        self.assertEqual(self.m.continuation_gate(pts,True,wealth_positive=True)['status'],'unknown_historical_stale')
        pts[-1]['drawdown_percentage_point_difference']=-1.
        self.assertEqual(self.m.continuation_gate(pts,True,wealth_positive=True)['status'],'unsupported')

    def test_empty_reference_drawdown_remains_unidentified(self):
        pts=self.points()
        for p in pts:p['drawdown_percentage_point_difference']=None
        self.assertEqual(self.m.continuation_gate(pts,False,wealth_positive=True)['status'],'unknown_empty_reference_DD')

    def test_domain_failure_rejected_before_native_read(self):
        with self.assertRaisesRegex(ValueError,'domain'):
            self.m.validate_domain_report(dict(schema='stage100_log_utility_domain_v1',status='domain_failure',domain_pass=False,cash_eligible=False,oos_checked=True))
        self.assertEqual(self.m.ref.NATIVE_QUERIES,0)


if __name__=='__main__':unittest.main()
