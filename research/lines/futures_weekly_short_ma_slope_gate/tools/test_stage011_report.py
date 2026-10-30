"""Non-mirroring accounting and economic comparison counterexamples."""
import unittest
import pandas as pd
from stage011_report import summarize,pair_metrics


def raw(pnl):
    d=pd.DataFrame(dict(date=pd.date_range('2020-01-01',periods=len(pnl)).strftime('%Y-%m-%d'),net_pnl=pnl))
    d['account_equity']=150000+d.net_pnl.cumsum()
    for k in ['slippage','commission','trade_count','total_margin_exact']:d[k]=0
    return d


def funding(amount=10000):
    return [dict(date='2020-01-02',event_id='1',candidate_key='entry1',phase='before_parent_sizing',
        entry_context='flat_entry',signal='long_case1a',direction='long',weekly_stop_valid=True,
        raw_account_equity=140000,trading_equity_before=140000,trading_equity_after=140000+amount,
        reserve_before=150000,reserve_after=150000-amount,total_account_equity=290000,
        transfer_amount=amount,cumulative_transfer=amount)]


def rounds(pnl):
    return dict(count=1,wins=int(pnl>0),losses=int(pnl<0),flat=int(pnl==0),win_rate_pct=100 if pnl>0 else 0,
        average_win=max(0,pnl),average_loss_abs=abs(min(0,pnl)),payoff_ratio=0,profit_factor=0,closed_net_pnl=pnl)


class ReportCounterexamples(unittest.TestCase):
    def test_both_versions_can_use_reserve(self):
        m,d=summarize(raw([0,-10000,1000]),funding(),rounds(-9000),0,'2020-01-01','A','prior_risk')
        self.assertEqual(m['account_end_equity'],151000)
        self.assertEqual(m['real_trading_net_pnl'],-9000)
        self.assertEqual(m['total_transferred'],10000)
        self.assertAlmostEqual(m['account_growth_pct'],2/3)
        self.assertEqual(m['wealth_end_equity'],291000)
        self.assertAlmostEqual(m['wealth_return_pct'],-3)
        self.assertEqual(d.account_nav.iloc[0],1)

    def test_more_deposits_never_win_real_pnl_gate(self):
        old=dict(account_growth_pct=0,balance_max_dd_pct=-20,balance_sharpe=.2,real_trading_net_pnl=-10000,
            account_end_equity=150000,total_transferred=10000,off_account_reserve_end=140000,wealth_return_pct=-10/3,wealth_max_dd_pct=-10,wealth_sharpe=.3)
        new=dict(old,account_growth_pct=10,account_end_equity=165000,total_transferred=25000,off_account_reserve_end=125000)
        p=pair_metrics(old,new,'2020-01-01','A')
        self.assertEqual(p['delta_account_end_equity'],15000)
        self.assertEqual(p['delta_real_trading_net_pnl'],0)
        self.assertEqual(p['delta_deposits'],15000)
        self.assertFalse(p['real_pnl_gate']);self.assertFalse(p['three_gate_pass'])

    def test_complete_trade_pnl_and_open_mtm_must_reconcile(self):
        with self.assertRaisesRegex(ValueError,'closed_open_real_PnL'):
            summarize(raw([0,-10000,1000]),funding(),rounds(9000),0,'2020-01-01','A','uniform_risk')

    def test_negative_curve_is_preserved(self):
        m,d=summarize(raw([0,-160000]),[],rounds(-160000),0,'2020-01-01','A','uniform_risk')
        self.assertEqual(m['account_end_equity'],-10000)
        self.assertLess(m['balance_max_dd_pct'],-100)
        self.assertEqual(m['nonpositive_trading_equity_days'],1)
        self.assertFalse(m['reserve_exhausted'])


if __name__=='__main__':unittest.main()
