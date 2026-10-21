import copy
import unittest
import stage039_continuous_source as continuous
from test_stage034_episode_driver import case,record


def source_case(days=5):
    c=case(horizon=days)
    c['start_day']=c.pop('signal_day');c.pop('initial');c.pop('horizon');c.pop('terminal_mode')
    all_days=[c['start_day']]+sorted(c['sessions'])[:days]
    c['observed_through']=all_days[-1]
    c['sessions']={d:c['sessions'].get(d,dict(target_contract='A',contracts={'A':record(d)})) for d in all_days}
    for d in all_days:c['sessions'][d]['fresh_signal']=None
    c['monthly_eval_days']=[all_days[0],all_days[-1],c['calendar'][c['calendar'].index(all_days[-1])+1]]
    return c,all_days


def fresh(direction='long',stop=90,qty=2):
    return dict(direction=direction,contract='A',qty=qty,stop_price=stop,signal_high=101,signal_low=99)


def replace_record(c,day,**kw):
    c['sessions'][day]['contracts']['A']=record(day,**kw)


class ContinuousTests(unittest.TestCase):
    def setUp(self):self.assertTrue(callable(getattr(continuous,'run_continuous_source',None)),'missing continuous source API')

    def test_mtm_changes_do_not_add_cumulative_value_twice(self):
        c,ds=source_case(3);c['sessions'][ds[0]]['fresh_signal']=fresh()
        for d in ds[1:]:replace_record(c,d,close=105,ma=80)
        r=continuous.run_continuous_source(c)['paths'][0]
        self.assertEqual([x['cumulative_gross_r'] for x in r['trace']],[0,.5,.5,.5])
        self.assertEqual([x['delta_gross_r'] for x in r['trace']],[0,.5,0,0])
        self.assertEqual(len(r['episodes']),1)

    def test_pending_full_exit_cannot_start_fresh_until_next_open(self):
        c,ds=source_case(4);c['sessions'][ds[0]]['fresh_signal']=fresh()
        replace_record(c,ds[1],close=100,ma=110)
        c['sessions'][ds[1]]['fresh_signal']=fresh('short',110)
        c['sessions'][ds[2]]['fresh_signal']=fresh('short',110)
        r=continuous.run_continuous_source(c)['paths'][0]
        self.assertEqual(r['trace'][1]['pending']['kind'],'reduce')
        self.assertEqual(r['trace'][1]['episode_count'],1)
        self.assertEqual(r['trace'][2]['pending']['kind'],'open')
        self.assertEqual(r['trace'][2]['pending']['signal_day'],ds[2])
        self.assertEqual(r['trace'][3]['state']['direction'],'short')
        self.assertEqual(len(r['episodes']),2)
        self.assertEqual(r['episodes'][0]['snapshot']['risk_currency'],200)
        self.assertEqual(r['episodes'][1]['snapshot']['risk_currency'],200)

    def test_fresh_new_initial_R_differs_from_previous(self):
        c,ds=source_case(4);c['sessions'][ds[0]]['fresh_signal']=fresh()
        replace_record(c,ds[1],ma=110);replace_record(c,ds[2],opening=105,close=105)
        c['sessions'][ds[2]]['fresh_signal']={**fresh('long',95),'signal_high':106,'signal_low':104}
        replace_record(c,ds[3],opening=110,close=110)
        replace_record(c,ds[4],opening=110,close=110)
        r=continuous.run_continuous_source(c)['paths'][0]
        self.assertEqual(r['episodes'][0]['snapshot']['risk_currency'],200)
        self.assertEqual(r['episodes'][1]['snapshot']['risk_currency'],300)
        self.assertEqual(r['trace'][2]['cumulative_gross_r'],.5)
        self.assertEqual(r['trace'][3]['cumulative_gross_r'],.5)

    def test_unknown_trajectory_never_recovers_on_new_fresh(self):
        c,ds=source_case(4);c['sessions'][ds[0]]['fresh_signal']=fresh()
        a=c['sessions'][ds[1]]['contracts']['A'];a['bar'].update(high=111,low=89);a['history'][-1]=a['bar']
        for d in ds[2:]:c['sessions'][d]['fresh_signal']=fresh()
        r=continuous.run_continuous_source(c)['paths'][0]
        self.assertEqual(r['status'],'trajectory_unknown')
        self.assertTrue(all(x['cumulative_net_r'] is None for x in r['trace'][1:]))
        self.assertEqual(len(r['episodes']),1)
        self.assertEqual(len(r['episodes'][0]['tape']),1)

    def test_missing_cost_in_completed_episode_keeps_future_net_unknown(self):
        c,ds=source_case(4);c['sessions'][ds[0]]['fresh_signal']=fresh()
        a=c['sessions'][ds[1]]['contracts']['A'];a['economics']['open_per_lot']=None;a['ma_long_prev_value']=110
        c['sessions'][ds[2]]['fresh_signal']=fresh()
        r=continuous.run_continuous_source(c)['paths'][0]
        self.assertEqual(len(r['episodes']),2)
        self.assertIsNone(r['cumulative_net_r']);self.assertEqual(r['cumulative_gross_r'],0)

    def test_flat_source_missing_signal_or_session_is_unknown(self):
        for missing in ('signal','session'):
            c,ds=source_case(3)
            if missing=='signal':del c['sessions'][ds[1]]['fresh_signal']
            else:del c['sessions'][ds[1]]
            c['sessions'][ds[2]]['fresh_signal']=fresh()
            r=continuous.run_continuous_source(c)['paths'][0]
            self.assertEqual(r['status'],'trajectory_unknown');self.assertEqual(r['episodes'],[])
            self.assertIsNone(r['cumulative_net_r'])

    def test_branch_c2_stop_can_reenter_only_flat_branch(self):
        c,ds=source_case(3);c['sessions'][ds[0]]['fresh_signal']=fresh();c['sessions'][ds[1]]['fresh_signal']=fresh('short',120)
        a=c['sessions'][ds[1]]['contracts']['A'];a['bar'].update(high=111,low=89);a['history'][-1]=a['bar']
        a['minute_paths']=[[dict(open=100,high=101,low=89,close=95),dict(open=95,high=111,low=94,close=100)],
                           [dict(open=100,high=111,low=99,close=105),dict(open=105,high=106,low=89,close=100)]]
        a['minute_evidence_id']='synthetic-finite-paths'
        c['sessions'][ds[1]]['fresh_signal'].update(signal_high=111,signal_low=89)
        paths=continuous.run_continuous_source(c)['paths']
        self.assertEqual(len(paths),2)
        self.assertEqual([len(r['episodes']) for r in paths],[2,1])
        self.assertEqual(paths[0]['episodes'][0]['snapshot']['gross_r'],-1)

    def test_monthly_clocks_preserve_future_rows_and_case_immutable(self):
        c,ds=source_case(2);before=copy.deepcopy(c);r=continuous.run_continuous_source(c)
        self.assertEqual(c,before);m=r['paths'][0]['monthly_evaluations']
        self.assertEqual(len(m),3);self.assertEqual([x['observed'] for x in m],[True,True,False])
        self.assertIsNone(m[-1]['cumulative_net_r']);self.assertFalse(r['training_eligible'])
        self.assertFalse(r['complete_formal_source'])

    def test_invalid_fresh_structural_input_rejected(self):
        for field,value in [('qty',True),('direction','sideways'),('stop_price',-1),('contract','B')]:
            c,ds=source_case(2);c['sessions'][ds[0]]['fresh_signal']=fresh();c['sessions'][ds[0]]['fresh_signal'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):continuous.run_continuous_source(c)

    def test_partial_flag_commits_but_new_fresh_resets_it(self):
        c,ds=source_case(5);c['sessions'][ds[0]]['fresh_signal']=fresh(qty=3)
        replace_record(c,ds[1],rsi=96)
        replace_record(c,ds[2],ma=110)
        c['sessions'][ds[3]]['fresh_signal']=fresh('short',110,qty=3)
        r=continuous.run_continuous_source(c)['paths'][0]
        self.assertTrue(r['trace'][2]['state']['rsi_partial_exit_done'])
        self.assertFalse(r['trace'][4]['state']['rsi_partial_exit_done'])
        self.assertEqual(r['trace'][4]['state']['qty'],3)
        self.assertEqual(r['episodes'][0]['snapshot']['remaining_qty'],0)
        self.assertEqual(len(r['episodes']),2)

    def test_roll_keeps_same_episode_and_initial_currency_R(self):
        from stage034_run_episode_probe import fixtures
        original=next(row['case'] for row in fixtures() if row['case_id']=='roll_new_c2_and_original_denominator')
        initial=original.pop('initial');start=original.pop('signal_day')
        original.update(start_day=start,monthly_eval_days=[])
        original['sessions'][start]=dict(target_contract='A',contracts={'A':record(start)},fresh_signal=initial)
        for d,session in original['sessions'].items():session.setdefault('fresh_signal',None)
        r=continuous.run_continuous_source(original)['paths'][0]
        self.assertEqual(len(r['episodes']),1)
        self.assertEqual(r['episodes'][0]['snapshot']['risk_currency'],200)
        opens=[x for x in r['episodes'][0]['tape'] if x['kind']=='open']
        self.assertEqual([x['contract'] for x in opens],['A','B'])
        self.assertEqual([x['rollover'] for x in opens],[False,True])

    def test_future_input_outside_observed_rejected(self):
        c,ds=source_case(2);c['observed_through']=ds[-2]
        with self.assertRaises(ValueError):continuous.run_continuous_source(c)

    def test_roll_episode_signal_provenance_preserves_fresh_clock_and_layer_age(self):
        from stage034_run_episode_probe import fixtures
        c=next(row['case'] for row in fixtures() if row['case_id']=='roll_new_c2_and_original_denominator')
        initial=c.pop('initial');start=c.pop('signal_day');c.update(start_day=start,monthly_eval_days=[])
        c['sessions'][start]=dict(target_contract='A',contracts={'A':record(start)},fresh_signal=initial)
        for session in c['sessions'].values():session.setdefault('fresh_signal',None)
        r=continuous.run_continuous_source(c)['paths'][0]
        episode=r['episodes'][0]
        newopen=next(fill for fill in episode['tape'] if fill['kind']=='open' and fill['contract']=='B')
        layer_signal=c['calendar'][c['calendar'].index(newopen['trading_day'])-1]
        self.assertNotEqual(start,layer_signal)
        self.assertEqual(episode['signal_day'],start)
        self.assertEqual(episode['snapshot']['risk_currency'],200)
        held=[t for t in r['trace'] if t['state'] is not None and t['state']['contract']=='B']
        self.assertTrue(held)
        for trace in held:
            self.assertEqual(trace['state']['bars_since_entry'],c['calendar'].index(trace['day'])-c['calendar'].index(layer_signal))

if __name__=='__main__':unittest.main()
