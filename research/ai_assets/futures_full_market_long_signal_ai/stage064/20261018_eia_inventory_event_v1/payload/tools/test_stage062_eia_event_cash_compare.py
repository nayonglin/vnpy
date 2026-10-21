"""New EIA cash behavior only; no actual estimator, SQL, or account replay."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage062_eia_event_cash_compare.py')


def load_subject():
    if not PATH.exists():
        return None
    spec=importlib.util.spec_from_file_location('stage062_tested',PATH)
    subject=importlib.util.module_from_spec(spec);spec.loader.exec_module(subject)
    return subject


def labels():
    return pd.DataFrame([dict(event_id=event,product_id=product,family_id=product,u_date=day,u_index=i,
        reference_epoch=epoch,label_history_ready20=ready,N_u=1.,low20_u=90.,u_close=100.,history_run=20,lifecycle_index=500,
        label_state=state,filled=0,net_R_stress=np.nan)
        for i,(event,product,day,epoch,ready,state) in enumerate([
            ('prior','DCE.I','2019-12-31','old',1,'closed_complete_bar_model'),
            ('iron','DCE.I','2020-01-02','old',1,'entry_execution_unknown'),
            ('oil','INE.SC','2020-01-02','oil',1,'open_right_censored'),
            ('non_event','DCE.I','2020-01-03','new',1,'known_nonparticipation'),
            ('not_ready','SHFE.CU','2020-01-02','cu',0,'not_history_ready')])])


def predictions(frame):
    selected=frame.loc[frame.u_date.ge('2020-01-01')]
    return selected[['event_id','product_id','family_id','u_date','u_index']].assign(arm='INVENTORY',cutoff='2020-01-01',
        score=1.,history_ready20=selected.label_history_ready20.to_numpy(),is_report_event=[1,1,0,1],
        report_id=['r1','r1','','r1'],external_missing=[0,0,1,0],selected=[1,1,0,0])


class EIACashBehavior(unittest.TestCase):
    def setUp(self):
        self.m=load_subject()
        self.assertIsNotNone(self.m,'new062 module must exist')

    def test_all_families_event_eligible_non_event_reference_retained_future_labels_ignored(self):
        source=labels();pred=predictions(source)
        got=self.m.make_signals(source,pred,'INVENTORY')
        self.assertEqual(got.event_id.tolist(),source.event_id.tolist())
        self.assertEqual(got.potential.tolist(),[0,1,1,0,0])
        self.assertEqual(got.loc[got.event_id.eq('non_event'),'reference_epoch'].iloc[0],'new')
        changed=source.assign(label_state='closed_complete_bar_model',filled=1,net_R_stress=-999.)
        pd.testing.assert_frame_equal(got,self.m.make_signals(changed,pred,'INVENTORY'))
        pred.loc[pred.event_id.eq('iron'),'selected']=0
        with self.assertRaises(ValueError):
            self.m.make_signals(source,pred,'INVENTORY')

    def test_twelve_independent_cells_use_actual_arm_names_and_shared_complete_signals(self):
        frame=labels();signal_map={a:frame.assign(potential=0) for a in self.m.ARMS}
        calls=[]
        def stub(signals,market,dates,economics,scenario,account_id,start,end,initial,prepared):
            calls.append((account_id,len(signals),scenario,start,end,initial,prepared))
            return {'stub':True}
        dates=['2019-12-31','2020-01-02','2022-12-30','2023-01-03','2026-10-16']
        result=list(self.m.run_accounts(signal_map,None,dates,{},runner=stub,execution_kind='synthetic_fixture'))
        self.assertEqual(len(result),12)
        self.assertEqual(len({r[0] for r in calls}),12)
        self.assertTrue(all(r[1]==len(frame) for r in calls))
        self.assertEqual({r[2] for r in calls},{'base','stress'})
        self.assertEqual({r[3] for r in calls},{1,3})
        self.assertTrue(all(r[4]==4 and r[5]==1000000. for r in calls))
        self.assertEqual({cell['arm'] for cell,book in result},set(self.m.ARMS))

    def test_inventory_two_CIs_use_one_index_array_initial_day_log_and_no_bankruptcy_repair(self):
        dates=['2020-01-02','2020-01-03','2020-01-06']
        good=pd.DataFrame(dict(date=dates,equity=[110.,121.,133.1],ever_insolvent=[False]*3))
        flat=good.assign(equity=100.)
        indices=self.m.circular_indices(3,repetitions=4,block_length=2,seed=7)
        report,distribution=self.m.paired_log_statistics(dict(INVENTORY=good,COMMON_EVENT=flat,PAST_SHAM=flat),100.,indices)
        np.testing.assert_allclose(distribution.INVENTORY_minus_COMMON_EVENT,distribution.INVENTORY_minus_PAST_SHAM)
        self.assertAlmostEqual(report['INVENTORY_minus_COMMON_EVENT']['mean_daily_log_difference'],np.log(1.1))
        report,distribution=self.m.paired_log_statistics(dict(INVENTORY=good.assign(equity=[110.,-1.,133.1]),COMMON_EVENT=flat,PAST_SHAM=flat),100.,indices)
        self.assertIsNone(report['INVENTORY_minus_COMMON_EVENT']['ci95_low'])
        self.assertTrue(distribution.INVENTORY_minus_PAST_SHAM.isna().all())

    def test_unknown_differential_exposure_cannot_be_given_invented_finite_R_bound(self):
        open_a=pd.DataFrame([dict(event_id='e',epoch='X.A.203001',qty=2,entry_fill=100.,last_mark=110.,stale=True,notional=220.)])
        open_b=open_a.assign(qty=1,notional=110.)
        result=self.m.compare_unresolved_exposure(dict(open_episodes=open_a,position_days=pd.DataFrame(),closed_episodes=pd.DataFrame()),
            dict(open_episodes=open_b,position_days=pd.DataFrame(),closed_episodes=pd.DataFrame()))
        self.assertTrue(result['differential_unresolved_exposure'])
        self.assertIsNone(result['finite_R_bound'])
        self.assertEqual(result['judgment'],'unknown')
        identical=self.m.compare_unresolved_exposure(dict(open_episodes=open_a,position_days=pd.DataFrame(),closed_episodes=pd.DataFrame()),
            dict(open_episodes=open_a,position_days=pd.DataFrame(),closed_episodes=pd.DataFrame()))
        self.assertFalse(identical['differential_unresolved_exposure'])
        stress=dict(ever_insolvent=False,total_return_pct=1.,unresolved_records=0)
        points=[dict(scenario=scenario,window_id=window,unresolved=result,survival_failure=False,
            return_percentage_point_difference=1.,drawdown_percentage_point_difference=1.,cumulative_log_growth_difference=.1)
            for scenario,window in [('base','primary_2020'),('base','cold_2023'),('stress','cold_2023')] for _ in range(2)]
        report=self.m.continuation_conditions({('INVENTORY','stress','primary_2020'):stress},points,
            {'one':dict(ci95_low=.01),'two':dict(ci95_low=.01)})
        self.assertEqual(report['decision'],'unknown')
        self.assertFalse(report['increased_bet_qualified'])
        stress['ever_insolvent']=True
        report=self.m.continuation_conditions({('INVENTORY','stress','primary_2020'):stress},points,
            {'one':dict(ci95_low=.01),'two':dict(ci95_low=.01)})
        self.assertEqual(report['decision'],'unsupported')

    def test_all_family_year_attribution_retains_inactive_cells_zero_and_oil_only_groups(self):
        self.assertTrue(callable(getattr(self.m,'complete_family_year',None)),'all-family yearly cash attribution needs explicit zero-activity cells')
        partial=pd.DataFrame([dict(family_id='DCE.I',year='2020',net_equity_contribution=100.,fee=2.),
            dict(family_id='INE.SC',year='2021',net_equity_contribution=50.,fee=3.)])
        complete=self.m.complete_family_year(partial,{'DCE.I','INE.SC','SHFE.CU'},['2020','2021'])
        self.assertEqual(len(complete),6)
        self.assertEqual(complete.net_equity_contribution.sum(),150.)
        report,groups,totals=self.m.oil_group_diagnostics(complete,{'DCE.I','INE.SC','SHFE.CU'})
        self.assertEqual(len(groups),4)
        self.assertEqual(len(totals),3)
        self.assertTrue(report['all_families_trade_eligible'])
        self.assertEqual(totals.loc[totals.family_id.eq('SHFE.CU'),'net_equity_contribution'].iloc[0],0.)


if __name__=='__main__':
    unittest.main()
