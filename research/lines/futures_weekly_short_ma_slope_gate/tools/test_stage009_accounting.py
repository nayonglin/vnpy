import copy
import unittest
import pandas as pd
from stage009_accounting import bucket_curve, curve_metrics, compare_pair


def raw_curve():
    return pd.DataFrame(dict(date=['2020-01-02','2020-01-03','2020-01-06','2020-01-07'],
        account_equity=[150000.,140000.,160000.,130000.],net_pnl=[0.,-10000.,20000.,-30000.],
        slippage=[0.,10.,20.,30.],commission=[0.,0.,0.,0.],trade_count=[0,1,1,1]))


def event(day,before,reserve,cumulative,ident):
    amount=min(150000-before,reserve)
    return dict(event_id=str(ident),date=day,vt_symbol='x2401.DCE',direction='long',
        signal='long_case1a',entry_context='flat_entry',candidate_key=day+'x',phase='before_parent_sizing',
        trading_equity_before=before,trading_equity_after=before+amount,
        reserve_before=reserve,reserve_after=reserve-amount,transfer_amount=amount,
        cumulative_transfer=cumulative+amount,raw_account_equity=before-cumulative,
        total_account_equity=before+reserve,weekly_stop_valid=True,
        range_checked=False,range_would_block=False)


class BucketAccounting(unittest.TestCase):
    def test_internal_transfers_do_not_create_profit(self):
        raw=raw_curve();events=[event('2020-01-03',140000,150000,0,1),event('2020-01-07',140000,140000,10000,2)]
        d=bucket_curve(raw,events,'A');idle=bucket_curve(raw,[],'A')
        self.assertEqual(d.trading_account_equity.tolist(),[150000,150000,170000,150000])
        self.assertEqual(d.reserve_balance.tolist(),[150000,140000,140000,130000])
        self.assertEqual(d.total_account_equity.tolist(),[300000,290000,310000,280000])
        self.assertEqual(d.total_account_equity.tolist(),idle.total_account_equity.tolist())
        self.assertEqual(curve_metrics(d)['net_pnl'],-20000)
        self.assertAlmostEqual(curve_metrics(d)['total_return_pct'],-6.6666666667)
        self.assertAlmostEqual(curve_metrics(d)['max_dd_pct'],(280000/310000-1)*100)
        self.assertEqual(raw.account_equity.tolist(),[150000,140000,160000,130000])

    def test_reserve_exhaustion_partial_topup(self):
        raw=pd.DataFrame(dict(date=['2020-01-02','2020-01-03'],account_equity=[150000.,-50000.],net_pnl=[0.,-200000.],slippage=[0.,0.],commission=[0.,0.],trade_count=[0,1]))
        d=bucket_curve(raw,[event('2020-01-03',-50000,150000,0,1)],'A')
        self.assertEqual(d.reserve_balance.iloc[-1],0)
        self.assertEqual(d.trading_account_equity.iloc[-1],100000)
        self.assertEqual(d.total_account_equity.iloc[-1],100000)

    def test_reject_duplicate_candidate_or_external_money(self):
        e=event('2020-01-03',140000,150000,0,1)
        with self.assertRaises(ValueError):bucket_curve(raw_curve(),[e,copy.deepcopy(e)],'A')
        e['reserve_after']+=1
        with self.assertRaises(ValueError):bucket_curve(raw_curve(),[e],'A')

    def test_no_funding_from_probes_rollover_or_blocked_short(self):
        for context in ['env_probe','rollover_reopen','regular_add']:
            e=event('2020-01-03',140000,150000,0,1);e['entry_context']=context
            with self.assertRaises(ValueError):bucket_curve(raw_curve(),[e],'A')
        e=event('2020-01-03',140000,150000,0,1);e.update(direction='short',signal='short_case1a',range_checked=True,range_would_block=True)
        with self.assertRaises(ValueError):bucket_curve(raw_curve(),[e],'C')

    def test_reject_invalid_stop_and_unfunded_equity_bridge(self):
        e=event('2020-01-03',140000,150000,0,1);e['weekly_stop_valid']=False
        with self.assertRaises(ValueError):bucket_curve(raw_curve(),[e],'A')
        d=raw_curve();d.loc[2,'account_equity']+=1000
        with self.assertRaises(ValueError):bucket_curve(d,[],'A')

    def test_event_must_anchor_to_real_same_day_pnl(self):
        forged=event('2020-01-03',145000,150000,0,1)
        with self.assertRaisesRegex(ValueError,'event_raw_day_anchor'):
            bucket_curve(raw_curve(),[forged],'A')

    def test_total_capital_comparison_and_observation_vote(self):
        a=curve_metrics(bucket_curve(raw_curve(),[],'A'));b=dict(a)
        b['end_equity']+=1;b['max_dd_pct']+=1;b['sharpe']+=.1
        p=compare_pair(a,b,'2020-01-01','2026-10-29')
        self.assertTrue(p['three_gate_pass']);self.assertTrue(p['vote_eligible'])
        self.assertFalse(compare_pair(a,b,'2026-01-01','2026-10-29')['vote_eligible'])
        self.assertFalse(compare_pair(a,a,'2020-01-01','2026-10-29')['three_gate_pass'])


if __name__=='__main__':unittest.main()
