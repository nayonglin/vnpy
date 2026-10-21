"""Five policy behaviors, using synthetic paths only."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('s029',Path(__file__).with_name('stage029_uncapped_day_experiment.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixtures():
    rows=[];audit=[]
    # Stop, profit followed by giveback, dual touch, close, history-unready, no observation.
    for i,(state,ready,known,al,au,H,L,C,status) in enumerate([
        ('stop_only',1,1,-1,-1,103,98,100,'observed_long_research_opportunity'),
        ('profit_only',1,1,4,4,107,99.5,106,'observed_long_research_opportunity'),
        ('double_touch_interval',1,1,-1,4,107,98,106,'observed_long_research_opportunity'),
        ('day_close',1,1,.5,.5,103,99.5,100.5,'observed_long_research_opportunity'),
        ('history_unready',0,0,None,None,None,None,None,'observed_long_research_opportunity'),
        ('no_reference_observation',0,0,None,None,None,None,None,'no_accepted_observation')]):
        r=dict(event_id=f'e{i}',product_id=f'X.P{i}',product=f'P{i}',exchange='X',family_id=f'X.P{i}',u_date='2020-01-02',
            reference_epoch=f'X.P{i}.202001' if status=='observed_long_research_opportunity' else '',planned_execution_date='2020-01-03',status=status,direction='long',
            feature_ready=ready,label_identified=known,label_state=state,history_state='ready' if ready else state,
            label_known_date='2020-01-03' if known else '',path_ambiguous=int(state=='double_touch_interval'),
            gross_lower=al,gross_upper=au,proxy_lower=al-.2 if known else None,proxy_upper=au-.2 if known else None,atr20=4 if ready else None)
        rows.append(r)
        if status=='observed_long_research_opportunity':audit.append(dict(event_id=r['event_id'],u_date=r['u_date'],reference_epoch=r['reference_epoch'],planned_execution_date=r['planned_execution_date'],history_state=r['history_state'],label_state=state,
            atr20=4 if ready else '',ideal_entry_F=100 if ready else '',risk_distance=1 if ready else '',ideal_stop=99 if ready else '',ideal_profit=104 if ready else '',D_high=H if ready else '',D_low=L if ready else '',D_close=C if ready else ''))
    return pd.DataFrame(rows),pd.DataFrame(audit)

class UncappedPolicyBehavior(unittest.TestCase):
    def test_four_inherited_states_keep_same_path_difference(self):
        expected=[('stop_only',-1,-1,2,-1,0,0),('profit_only',4,4,6,6,2,2),
            ('double_touch_interval',-1,4,6,-1,-5,0),('day_close',.3,.3,.30000000000000004,.3,0,0)]
        for state,al,au,c,b,pl,pu in expected:
            row=m.policy_payoff(state,al,au,c)
            self.assertEqual((row['B_gross_lower'],row['B_gross_upper'],row['paired_lower'],row['paired_upper']),(b,b,pl,pu))

    def test_equal_fill_base_and_stress_costs_cancel_exactly(self):
        for state,al,au,c in [('profit_only',4,4,3.1),('double_touch_interval',-1,4,2)]:
            r=m.policy_payoff(state,al,au,c)
            self.assertEqual(r['paired_lower'],r['stress_paired_lower']);self.assertEqual(r['paired_upper'],r['stress_paired_upper'])
            self.assertAlmostEqual(r['B_lower']-r['stress_B_lower'],.8)
            self.assertAlmostEqual(r['A_lower']-r['stress_A_lower'],.8)

    def test_observed_audit_includes_unready_but_outer_and_unknown_survive(self):
        frame,audit=fixtures();events,diag=m.build_events(frame,audit,['2020-01-02'])
        self.assertEqual(events.event_id.tolist(),list('e'+str(i) for i in range(6)))
        self.assertTrue(events.loc[events.label_identified.eq(0),['A_lower','B_lower','paired_lower']].isna().all().all())
        self.assertEqual(diag['audit_rows'],5);self.assertEqual(diag['identified_rows'],4)
        with self.assertRaises(ValueError):m.build_events(frame,audit.iloc[:-1],['2020-01-02'])

    def test_state_remains_authoritative_at_tiny_price_boundary_difference(self):
        frame,audit=fixtures()
        # Synthetic CSV roundoff contradicts an inclusive raw predicate by 1e-13.
        audit.loc[audit.event_id.eq('e0'),'D_low']=99.0000000000001
        events,diag=m.build_events(frame,audit,['2020-01-02'])
        self.assertEqual(events.loc[events.event_id.eq('e0'),'B_gross_lower'].iloc[0],-1)
        self.assertEqual(diag['raw_stop_predicate_disagreements'],1)
        self.assertEqual(events.loc[events.event_id.eq('e3'),'paired_lower'].iloc[0],0)

    def test_tail_is_realized_close_and_decomposition_survives_daily_grid(self):
        frame,audit=fixtures();audit.loc[audit.event_id.eq('e1'),'D_close']=102
        events,_=m.build_events(frame,audit,['2020-01-02','2020-01-03'])
        r=events.loc[events.event_id.eq('e1')].iloc[0]
        self.assertEqual(r['new_realized_tail'],0);self.assertEqual(r['giveback'],-2)
        d=m.daily_metrics(events,['2020-01-02','2020-01-03'])
        self.assertAlmostEqual(d.loc['2020-01-02','paired_lower'],-1.75)
        self.assertAlmostEqual(d.loc['2020-01-02','tail_gain']+d.loc['2020-01-02','giveback']+d.loc['2020-01-02','double_penalty_lower'],-1.75)
        self.assertTrue(d.loc['2020-01-03'].isna().all())

if __name__=='__main__':unittest.main()
