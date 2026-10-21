import unittest
from copy import deepcopy
import pandas as pd
from stage034_episode_driver import run_episode


def record(day,close=100,opening=100,rsi=50,ma=80):
    bar=dict(open=opening,high=max(opening,close)+1,low=min(opening,close)-1,close=close,volume=100)
    hist=[dict(open=100,high=101,low=99,close=100,volume=100) for _ in range(40)]+[bar]
    dates=[str(x.date()) for x in pd.bdate_range(end=day,periods=41)]
    return dict(bar=bar,history=hist,history_dates=dates,rsi_value=rsi,ma_long_prev_value=ma,
                anchor=dict(price=opening,execution_datetime=day+'T09:00:00',evidence_id='synthetic-anchor'),
                economics=dict(multiplier=10,tick=1,open_per_lot=0,open_rate=0,close_per_lot=0,close_rate=0,
                               close_today_per_lot=0,close_today_rate=0,historical_validated=False),
                extra_slippage_price=0,daily_bar_complete=True,minute_paths=None,c2_guard_tick=1)


def case(horizon=2,mode='mtm',qty=2):
    calendar=[str(x.date()) for x in pd.bdate_range('2019-10-01',periods=110)]
    i=45;days=calendar[i+1:i+horizon+2]
    return dict(calendar=calendar,signal_day=calendar[i],observed_through=days[-1],horizon=horizon,
                terminal_mode=mode,initial=dict(direction='long',contract='A',qty=qty,stop_price=90,
                                                signal_high=101,signal_low=99),
                sessions={day:dict(target_contract='A',contracts={'A':record(day)}) for day in days})


class DriverTests(unittest.TestCase):
    def test_request_not_fill_then_next_open_commits_close(self):
        c=case();days=sorted(c['sessions']);a=c['sessions'][days[0]]['contracts']['A']
        a['rsi_value']=96;c['sessions'][days[1]]['contracts']['A']=record(days[1],100,110)
        before=deepcopy(c);r=run_episode(c)['paths'][0]
        self.assertEqual(c,before)
        self.assertEqual(r['trace'][0]['snapshot']['remaining_qty'],2)
        self.assertEqual(r['trace'][0]['pending']['reduce_qty'],1)
        self.assertEqual(r['trace'][1]['snapshot']['remaining_qty'],1)
        self.assertEqual(r['tape'][1]['price'],110)
        self.assertEqual(r['trace'][1]['c2_event'],None)

    def test_mtm_and_exit_next_open_have_different_horizon(self):
        c=case(horizon=1);r=run_episode(c)['paths'][0]
        self.assertEqual(len(r['tape']),1)
        self.assertEqual(r['snapshot']['remaining_qty'],2)
        c['terminal_mode']='exit_next_open';r=run_episode(c)['paths'][0]
        self.assertEqual(len(r['tape']),2)
        self.assertEqual(r['snapshot']['remaining_qty'],0)

    def test_missing_anchor_preserves_pending_and_unknown(self):
        c=case();d=sorted(c['sessions']);c['sessions'][d[0]]['contracts']['A']['rsi_value']=96
        c['sessions'][d[1]]['contracts']['A']['anchor']=None
        r=run_episode(c)['paths'][0]
        self.assertEqual(r['status'],'trajectory_unknown')
        self.assertEqual(len(r['tape']),1)
        self.assertIsNone(r['reference_net_r'])
        self.assertIsNotNone(r['pending'])

    def test_c2_branches_and_flat_survives_missing_later_bar(self):
        c=case();d=sorted(c['sessions']);a=c['sessions'][d[0]]['contracts']['A']
        a['bar']=dict(open=100,high=111,low=89,close=100,volume=100);a['history'][-1]=a['bar']
        a['minute_paths']=[[dict(open=100,high=101,low=89,close=95),dict(open=95,high=111,low=94,close=100)],
                           [dict(open=100,high=111,low=99,close=105),dict(open=105,high=106,low=89,close=100)]]
        a['minute_evidence_id']='synthetic-two-paths'
        del c['sessions'][d[1]]
        r=run_episode(c)['paths']
        self.assertEqual(len(r),2)
        self.assertEqual(r[0]['status'],'known')
        self.assertEqual(r[0]['snapshot']['gross_r'],-1)
        self.assertEqual(r[1]['status'],'trajectory_unknown')

    def test_unknown_minute_both_not_default_stop(self):
        c=case();a=c['sessions'][sorted(c['sessions'])[0]]['contracts']['A']
        a['bar']=dict(open=100,high=111,low=89,close=100,volume=100);a['history'][-1]=a['bar']
        r=run_episode(c)['paths'][0]
        self.assertEqual(r['status'],'trajectory_unknown')
        self.assertEqual(len(r['tape']),1)

    def test_c2_guard_tick_is_separate_from_effective_fill_tick(self):
        c=case(horizon=1);c['initial']['stop_price']=99.5
        a=c['sessions'][sorted(c['sessions'])[0]]['contracts']['A']
        a['economics']['tick']=.5;a['c2_guard_tick']=1
        a['bar']=dict(open=100,high=100.1,low=99.4,close=99.5,volume=100);a['history'][-1]=a['bar']
        r=run_episode(c)['paths'][0]
        self.assertEqual(r['status'],'known')
        self.assertEqual(r['trace'][0]['c2_event'],'guard_inactive')

    def test_unknown_execution_does_not_expose_known_total_value(self):
        c=case(horizon=1);a=c['sessions'][sorted(c['sessions'])[0]]['contracts']['A']
        a['bar']=dict(open=100,high=111,low=89,close=100,volume=100);a['history'][-1]=a['bar']
        r=run_episode(c)['paths'][0]
        self.assertEqual(r['status'],'trajectory_unknown')
        self.assertIsNone(r['snapshot']['net_r'])
        self.assertIsNone(r['trace'][0]['actual_qty'])

    def test_missing_cost_keeps_gross_but_net_unknown(self):
        c=case();a=c['sessions'][sorted(c['sessions'])[0]]['contracts']['A']
        a['economics']['open_per_lot']=None;r=run_episode(c)['paths'][0]
        self.assertEqual(r['status'],'known')
        self.assertIsNone(r['snapshot']['net_r'])
        self.assertEqual(r['snapshot']['gross_r'],0)

    def test_d60_clock_does_not_move_when_flat(self):
        c=case(horizon=60);d=sorted(c['sessions']);a=c['sessions'][d[0]]['contracts']['A']
        a['bar']=dict(open=100,high=101,low=89,close=95,volume=100);a['history'][-1]=a['bar']
        a['minute_paths']=[[dict(open=100,high=101,low=89,close=95)]];a['minute_evidence_id']='synthetic-stop'
        c['observed_through']=d[0];c['sessions']={d[0]:c['sessions'][d[0]]}
        r=run_episode(c);self.assertFalse(r['maturity_clock_reached'])
        self.assertEqual(r['paths'][0]['snapshot']['remaining_qty'],0)
        self.assertFalse(r['training_eligible'])

    def test_invalid_future_history_and_skipped_session_not_repaired(self):
        c=case();d=sorted(c['sessions']);a=c['sessions'][d[0]]['contracts']['A']
        a['history_dates'][-1]=d[1]
        with self.assertRaisesRegex(ValueError,'history_calendar'):run_episode(c)
        c=case();del c['sessions'][sorted(c['sessions'])[0]]
        self.assertEqual(run_episode(c)['paths'][0]['status'],'trajectory_unknown')

    def test_rejects_nat_anchor_and_boolean_numeric_evidence(self):
        for key,value in [('execution_datetime','NaT'),('execution_datetime',None),('price',True)]:
            c=case();a=c['sessions'][sorted(c['sessions'])[0]]['contracts']['A']
            a['anchor'][key]=value
            with self.assertRaises(ValueError):run_episode(c)
        c=case();c['sessions'][sorted(c['sessions'])[0]]['contracts']['A']['c2_guard_tick']=True
        with self.assertRaises(ValueError):run_episode(c)


if __name__=='__main__':unittest.main()
