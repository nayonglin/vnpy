import math
import unittest
import pandas as pd
import stage009_derive as derive


def frame(values):
    return pd.DataFrame(dict(date=pd.date_range('2020-01-02',periods=len(values)),account_equity=values,
        net_pnl=pd.Series(values).diff().fillna(values[0]-150000),slippage=0.,commission=0.,trade_count=0))


class RawAuxiliaryStats(unittest.TestCase):
    def test_legal_negative_raw_bucket_is_not_total_wealth_bankruptcy(self):
        provider=getattr(derive,'raw_engine_curve_metrics',None)
        self.assertIsNotNone(provider,'source-compatible raw statistic provider missing')
        m=provider(frame([150000.,-50000.,80000.]))
        returns=[0.,-4/3,-13/5];mean=sum(returns)/3;std=math.sqrt(sum((x-mean)**2 for x in returns)/2)
        self.assertAlmostEqual(m['sharpe'],mean/std*math.sqrt(252))
        self.assertEqual(m['nonpositive_equity_days'],1)
        self.assertEqual(m['net_pnl'],-70000)
        self.assertFalse(m['raw_curve_is_investable_wealth'])

    def test_flat_raw_source_sharpe_zero_and_positive_math_unchanged(self):
        provider=getattr(derive,'raw_engine_curve_metrics',None)
        self.assertIsNotNone(provider,'source-compatible raw statistic provider missing')
        self.assertEqual(provider(frame([150000.,150000.]))['sharpe'],0)
        d=frame([150000.,140000.,160000.]);old=derive.previous.legacy.curve_metrics(d);new=provider(d)
        for key in ['end_equity','net_pnl','total_return_pct','max_dd_pct','sharpe','total_slippage']:
            self.assertEqual(old[key],new[key])


if __name__=='__main__':unittest.main()
