"""Four fixed behavioral tests for the Stage015 execution attribution contract."""
import math
import unittest
import pandas as pd
import stage018_entry_confirmation_experiment as subject


class EntryConfirmationTests(unittest.TestCase):
    def test_gap_is_same_path_even_when_both_barriers_touch(self):
        # Breaking shared-path cancellation must fail, including the 1R stress budget.
        for fee, bounds in [(.2, (-1.2, 3.8)), (1., (-2., 3.))]:
            got = subject.policy_intervals(-.5, 5., -2., 0., fee)
            self.assertIsNotNone(got)
            self.assertEqual(got['trigger_state'], 'gap_open')
            self.assertEqual(got['confirm_fill'], 1)
            self.assertEqual((got['open_lower'], got['open_upper']), bounds)
            self.assertEqual((got['confirm_lower'], got['confirm_upper']), bounds)
            self.assertEqual((got['paired_lower'], got['paired_upper']), (0., 0.))

    def test_known_no_fill_is_zero_but_missing_and_unready_stay_unknown(self):
        # Turning missing D into a free no-fill or dropping an outer row must fail.
        days = ['2020-01-02', '2020-01-03', '2020-01-06']
        opportunities = pd.DataFrame([
            dict(event_id='a', product_id='DCE.A', exchange='DCE', product='A', u_date=days[0], direction='long',
                 status='observed_long_research_opportunity', reference_epoch='DCE.A.202005', planned_execution_date=days[1], high='105'),
            dict(event_id='b', product_id='DCE.B', exchange='DCE', product='B', u_date=days[0], direction='long',
                 status='observed_long_research_opportunity', reference_epoch='DCE.B.202005', planned_execution_date=days[1], high='105'),
            dict(event_id='c', product_id='DCE.C', exchange='DCE', product='C', u_date=days[2], direction='long',
                 status='observed_long_research_opportunity', reference_epoch='DCE.C.202005', planned_execution_date='', high='105'),
            dict(event_id='d', product_id='DCE.D', exchange='DCE', product='D', u_date=days[0], direction='long',
                 status='no_accepted_observation', reference_epoch='', planned_execution_date=days[1], high='')])
        features = opportunities.drop(columns='high').copy()
        features['family_id'] = features.product_id
        features['feature_ready'] = ['1','1','1','0']
        features['label_identified'] = ['1','0','0','0']
        features['history_state'] = ['ready','ready','ready','no_reference_observation']
        features['label_state'] = ['identified','missing_D','right_censored','no_reference_observation']
        features['label_known_date'] = [days[1],'','','']
        features['atr20'] = ['8','8','8','']
        features['gross_lower'] = ['1','','','']
        features['gross_upper'] = ['1','','','']
        features['proxy_lower'] = ['.8','','','']
        features['proxy_upper'] = ['.8','','','']
        audit = pd.DataFrame([dict(event_id='a', u_date=days[0], reference_epoch='DCE.A.202005',
            planned_execution_date=days[1], ideal_entry_F='100', risk_distance='2', D_high='104', D_low='99', D_close='102')])
        got = subject.build_events(opportunities, features, audit, days)
        self.assertIsNotNone(got)
        self.assertEqual(list(got.event_id), ['a','b','c','d'])
        self.assertEqual(got.loc[0,'trigger_state'], 'not_filled')
        self.assertEqual(got.loc[0,'confirm_lower'], 0.)
        self.assertEqual(got.loc[0,'confirm_upper'], 0.)
        self.assertAlmostEqual(got.loc[0,'paired_lower'], -.8)
        self.assertTrue(got.loc[1:,'confirm_lower'].isna().all())
        self.assertEqual(list(got.evaluation_state), ['identified','missing_D','right_censored','not_feature_ready'])
        self.assertFalse({'high','open','D_high','ideal_entry_F','atr20','risk_distance'} & set(got.columns))
        # The report ends before the source calendar: preserve the real future D as censored.
        future_opportunities=opportunities.copy();future_features=features.copy()
        future_opportunities.loc[2,'planned_execution_date']='2020-01-07'
        future_features.loc[2,'planned_execution_date']='2020-01-07'
        try:
            future=subject.build_events(future_opportunities,future_features,audit,days,
                successor_calendar=days+['2020-01-07'])
        except (ValueError,TypeError) as exc:
            self.fail('valid out-of-scope source-calendar successor was rejected: '+str(exc))
        self.assertEqual(future.loc[2,'planned_execution_date'],'2020-01-07')
        self.assertEqual(future.loc[2,'evaluation_state'],'right_censored')
        self.assertTrue(math.isnan(future.loc[2,'confirm_lower']))
        poisoned = opportunities.copy(); poisoned.loc[0,'reference_epoch']='DCE.A.203005'
        with self.assertRaises(ValueError): subject.build_events(poisoned, features, audit, days)

    def test_pre_entry_low_does_not_force_stop_and_close_can_force_it(self):
        # Forcing the day's low to occur after confirmation must fail this counterexample.
        got = subject.policy_intervals(2.5, 5., -.5, 4., .2)
        self.assertIsNotNone(got)
        self.assertEqual((got['confirm_lower'], got['confirm_upper']), (-1.2, 1.3))
        self.assertEqual((got['paired_lower'], got['paired_upper']), (-5., -2.5))
        self.assertEqual(subject.policy_intervals(2.5,5.,-.5,1.,.2)['confirm_upper'], -1.2)
        self.assertEqual(subject.policy_intervals(2.5,7.,-.5,4.,.2)['confirm_upper'], 3.8)
        no_stop = subject.policy_intervals(.5, 2., 0., 1., .2)
        self.assertAlmostEqual(no_stop['confirm_lower'], .3)
        self.assertEqual(subject.policy_intervals(2.5,2.5,-.5,2.,.2)['confirm_fill'], 1)
        # IEEE division can put an exact raw-price touch inside the normalized barrier.
        # Preserve the accepted OPEN interval and test all CONFIRM decisions before division.
        self.assertGreater((996.7-1000.)/3.3,-1.)
        if not hasattr(subject,'price_intervals'):
            self.fail('missing original-price comparison adapter')
        boundary=subject.price_intervals(1000.,1003.3,996.7,1002.31,999.,3.3,.2,(-1.,-1.))
        self.assertEqual((boundary['open_lower'],boundary['open_upper']),(-1.2,-1.2))
        self.assertEqual((boundary['confirm_lower'],boundary['confirm_upper']),(-1.2,-1.2))
        self.assertEqual((boundary['paired_lower'],boundary['paired_upper']),(0.,0.))
        self.assertEqual(boundary['raw_open_stop_touch'],1)
        intraday=subject.price_intervals(1000.,1001.4,999.95,1001.3,1001.,.1,.2,(4.,4.))
        self.assertLess((1001.4-1000.)/.1,14.)
        self.assertEqual((intraday['confirm_lower'],intraday['confirm_upper']),(-1.2,3.8))
        self.assertEqual(intraday['raw_high_ge_confirm_profit'],1)

    def test_daily_participation_shared_gap_cost_cancellation_and_calendar_nan(self):
        # Independent endpoint subtraction on a shared gap, wrong p, fees, or NaN-to-zero must fail.
        a = subject.policy_intervals(-.5,5.,-2.,0.,.2)
        self.assertIsNotNone(a)
        b = subject.policy_intervals(2.5,2.,-.5,1.,.2)
        sa = subject.policy_intervals(-.5,5.,-2.,0.,1.)
        sb = subject.policy_intervals(2.5,2.,-.5,1.,1.)
        rows=[]
        for event, values, stress in [('a',a,sa),('b',b,sb)]:
            row=dict(event_id=event,u_date='2020-01-02',family_id='DCE.'+event,label_identified=1,feature_ready=1,**values)
            row.update({'stress_'+k:v for k,v in stress.items() if k.endswith(('_lower','_upper'))})
            rows.append(row)
        rows.append(dict(event_id='unknown',u_date='2020-01-06',family_id='DCE.C',label_identified=0,feature_ready=1))
        daily=subject.daily_metrics(pd.DataFrame(rows),['2020-01-02','2020-01-03','2020-01-06'])
        self.assertAlmostEqual(daily.loc['2020-01-02','fill_rate'],.5)
        self.assertAlmostEqual(daily.loc['2020-01-02','paired_lower'],-.4)
        self.assertAlmostEqual(daily.loc['2020-01-02','paired_upper'],-.4)
        self.assertAlmostEqual(daily.loc['2020-01-02','participation_lower'],-.5)
        self.assertAlmostEqual(daily.loc['2020-01-02','participation_upper'],.75)
        self.assertAlmostEqual(daily.loc['2020-01-02','stress_participation_lower'],-.5)
        self.assertAlmostEqual(daily.loc['2020-01-02','stress_participation_upper'],.75)
        self.assertLess(abs(daily.loc['2020-01-02','participation_cost_residual']),1e-12)
        self.assertTrue(daily.loc['2020-01-03':,'paired_lower'].isna().all())
        ci=subject.bootstrap_intervals(daily,['paired_lower','participation_lower'])
        self.assertEqual(ci['source_grid_days'],3)
        self.assertEqual(ci['repetitions'],2000)
        self.assertEqual(ci['metrics']['paired_lower']['finite_source_days'],1)
        self.assertAlmostEqual(ci['metrics']['paired_lower']['ci95_lower'],-.4)


if __name__=='__main__': unittest.main(verbosity=2)
