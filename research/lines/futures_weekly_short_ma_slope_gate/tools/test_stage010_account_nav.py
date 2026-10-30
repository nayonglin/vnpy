"""Accounting counterexamples for the user's deposit-inclusive account NAV."""
import unittest
import numpy as np
import pandas as pd
from stage010_account_nav import project_curve, metrics


def ledger(pnl, deposits):
    p=np.asarray(pnl,float);t=np.cumsum(deposits);raw=150000+np.cumsum(p)
    return pd.DataFrame(dict(date=pd.date_range('2020-01-01',periods=len(p)).strftime('%Y-%m-%d'),
        raw_account_equity=raw,net_pnl=p,trading_account_equity=raw+t,
        reserve_balance=150000-t,cumulative_transfer=t,transfer_amount=deposits,
        total_account_equity=raw+150000,slippage=np.zeros(len(p)),commission=np.zeros(len(p)),trade_count=np.zeros(len(p))))


class AccountNavTests(unittest.TestCase):
    def test_untransferred_reserve_never_in_nav(self):
        d=project_curve(ledger([0,-30000,60000],[0,0,0]),'A_idle')
        np.testing.assert_allclose(d.account_nav,[1,.8,1.2])
        self.assertEqual(metrics(d)['account_end_equity'],180000)
        self.assertAlmostEqual(metrics(d)['balance_max_dd_pct'],-20)

    def test_deposit_lifts_balance_but_never_pnl(self):
        d=project_curve(ledger([0,-30000,0],[0,0,30000]),'C_R');m=metrics(d)
        np.testing.assert_allclose(d.account_nav,[1,.8,1])
        self.assertEqual(m['real_trading_net_pnl'],-30000)
        self.assertEqual(m['total_transferred'],30000)
        self.assertEqual(m['account_growth_pct'],0)
        self.assertAlmostEqual(m['balance_max_dd_pct'],-20)

    def test_positive_balance_growth_can_coexist_with_trading_loss(self):
        d=project_curve(ledger([0,-8560,0],[0,0,31660]),'C_R');m=metrics(d)
        self.assertAlmostEqual(m['account_growth_pct'],15.4)
        self.assertEqual(m['real_trading_net_pnl'],-8560)
        self.assertEqual(m['account_end_equity'],173100)

    def test_source_corruption_rejected(self):
        d=ledger([0,-100,200],[0,100,0]);d.loc[2,'trading_account_equity']+=10
        with self.assertRaisesRegex(ValueError,'trading_bridge'):project_curve(d,'A_R')

    def test_idle_cannot_receive_funding(self):
        with self.assertRaisesRegex(ValueError,'original_cannot_receive'):
            project_curve(ledger([0,-100],[0,100]),'A_idle')

    def test_first_balance_must_be_150000(self):
        with self.assertRaisesRegex(ValueError,'fresh_150k_start'):
            project_curve(ledger([-100,100],[0,0]),'A_R')

    def test_negative_equity_not_clipped(self):
        d=project_curve(ledger([0,-160000],[0,0]),'A_R')
        self.assertAlmostEqual(d.account_nav.iloc[-1],-1/15)
        self.assertLess(metrics(d)['balance_max_dd_pct'],-100)

    def test_zero_denominator_returns_are_explicitly_undefined(self):
        d=project_curve(ledger([0,-150000,100],[0,0,0]),'A_R')
        m=metrics(d);self.assertFalse(m['balance_returns_defined']);self.assertEqual(m['balance_sharpe'],0)

    def test_deposit_sequence_is_monotone_and_capped(self):
        with self.assertRaisesRegex(ValueError,'isolated_reserve'):
            project_curve(ledger([0,-100,0],[0,100,-1]),'A_R')
        with self.assertRaisesRegex(ValueError,'isolated_reserve'):
            project_curve(ledger([0,-200000],[0,150001]),'A_R')


if __name__=='__main__':unittest.main()
