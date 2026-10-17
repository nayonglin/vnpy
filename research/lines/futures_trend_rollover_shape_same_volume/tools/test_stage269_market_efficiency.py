"""Boundary contracts for the frozen Stage268 market definition."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

MODULE = Path(__file__).with_name('stage269_market_efficiency.py')


def load_module():
    if not MODULE.exists():
        return None
    spec = importlib.util.spec_from_file_location('stage269_market_efficiency', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load_module()


def bars(rows):
    return pd.DataFrame(rows, columns=['trade_date', 'exchange', 'product', 'contract_epoch_id',
                                       'close', 'volume', 'close_oi'])


class MarketDefinitionTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'market implementation is absent')

    def test_prior_day_winner_and_same_contract_return(self):
        # A same-day winner or switched-contract close produces a large false return.
        c = pd.date_range('2020-01-01', periods=3)
        b = bars([
            (c[0], 'SHFE', 'CU', 'SHFE.CU.202002', 100, 20, 100),
            (c[0], 'SHFE', 'CU', 'SHFE.CU.202003', 1000, 50, 50),
            (c[1], 'SHFE', 'CU', 'SHFE.CU.202002', 110, 20, 5),
            (c[1], 'SHFE', 'CU', 'SHFE.CU.202003', 2000, 50, 500),
            (c[2], 'SHFE', 'CU', 'SHFE.CU.202002', 120, 20, 5),
            (c[2], 'SHFE', 'CU', 'SHFE.CU.202003', 2200, 50, 500),
        ])
        f = m.build_product_features(b, c, start_date=c[0], end_date=c[-1])
        self.assertEqual(f.reference_epoch.tolist(), ['', 'SHFE.CU.202002', 'SHFE.CU.202003'])
        np.testing.assert_allclose(f.r.iloc[1:], [np.log(1.1), np.log(1.1)])

    def test_ties_use_volume_then_lexical_epoch_and_do_not_rescue_gap(self):
        c = pd.date_range('2020-01-01', periods=2)
        b = bars([
            (c[0], 'DCE', 'A', 'DCE.A.202003', 100, 8, 10),
            (c[0], 'DCE', 'A', 'DCE.A.202002', 100, 9, 10),
            (c[0], 'DCE', 'A', 'DCE.A.202001', 100, 9, 10),
            (c[1], 'DCE', 'A', 'DCE.A.202002', 110, 50, 100),
        ])
        f = m.build_product_features(b, c, start_date=c[0], end_date=c[-1])
        self.assertEqual(f.reference_epoch.iloc[1], 'DCE.A.202001')
        self.assertTrue(np.isnan(f.r.iloc[1]))
        self.assertEqual(f.return_status.iloc[1], 'missing_current_bar')

    def test_all_zero_oi_and_nonadjacent_calendar_are_missing(self):
        c = pd.date_range('2020-01-01', periods=3)
        b = bars([
            (c[0], 'DCE', 'A', 'DCE.A.202003', 100, 8, 0),
            (c[2], 'DCE', 'A', 'DCE.A.202003', 120, 8, 50),
        ])
        f = m.build_product_features(b, c, start_date=c[0], end_date=c[-1])
        self.assertTrue(f.r.isna().all())
        self.assertEqual(f.return_status.iloc[1], 'all_oi_zero')
        self.assertEqual(f.return_status.iloc[2], 'missing_previous_reference')

    def test_complete_windows_zero_paths_and_missing_bar(self):
        c = pd.date_range('2020-01-01', periods=125)
        b = bars([(d, 'DCE', 'A', 'DCE.A.202112', 100, 8, 50) for d in c])
        f = m.build_product_features(b, c, start_date=c[0], end_date=c[-1])
        self.assertTrue(np.isnan(f.er60.iloc[59]))
        self.assertEqual(f.er60.iloc[60], 0)
        self.assertTrue(f.zero_path60.iloc[60])
        # At least 61 elapsed source days: day index 60 is still immature.
        self.assertFalse(f.active.iloc[60])
        self.assertTrue(f.active.iloc[61])
        g = m.build_product_features(b.loc[b.trade_date.ne(c[70])], c, start_date=c[0], end_date=c[-1])
        self.assertTrue(g.er20.iloc[70:91].isna().all())
        self.assertEqual(g.er20.iloc[91], 0)

    def test_no_future_rows_or_families_and_inactive_after_twenty_days(self):
        c = pd.date_range('2020-01-01', periods=100)
        b = bars([(d, 'DCE', 'A', 'DCE.A.202112', 100, 8, 50) for d in c[:65]] +
                 [(d, 'DCE', 'L_F', 'DCE.L_F.202112', 100, 8, 50) for d in c])
        f = m.build_product_features(b, c, start_date=c[0], end_date=c[85])
        self.assertEqual(f.product_id.unique().tolist(), ['DCE.A'])
        self.assertEqual(f.date.max(), c[85])
        self.assertTrue(f.active.iloc[83])
        self.assertFalse(f.active.iloc[84])

    def test_gate_fails_for_one_undercovered_existing_sector(self):
        # Overall 19/20=95% cannot compensate for a 1/2 covered sector.
        rows=[]
        sectors={}
        names=['black','metal','precious','chemical','agri']
        for i in range(20):
            pid=f'X.P{i:02}'
            sectors[pid]=names[0] if i < 2 else names[1+(i-2)%4]
            rows.append(dict(date=pd.Timestamp('2020-01-01'), product_id=pid, active=True,
                             er20=0.2, er60=np.nan if i==0 else 0.2, er120=0.2,
                             r=0.01, vol60=0.1,sum60=0.5,zero_path60=False))
        daily, details=m.aggregate_market(pd.DataFrame(rows),sectors)
        self.assertAlmostEqual(daily.raw_market_er60.iloc[0],0.2)
        self.assertTrue(np.isnan(daily.market_er60.iloc[0]))
        self.assertFalse(daily.gate_pass.iloc[0])
        self.assertIn('sector_coverage_below_80pct', daily.gate_reasons.iloc[0])
        self.assertAlmostEqual(daily.coverage_ratio.iloc[0],0.95)

    def test_expanding_rank_uses_prior_only_and_average_ties(self):
        s=pd.Series([0.2]*252+[0.2,0.5,0.1,0.2])
        pct,regime=m.expanding_percentile(s)
        self.assertTrue(pct.iloc[:252].isna().all())
        self.assertEqual(pct.iloc[252],0.5)
        self.assertEqual(regime.iloc[252],'mid')
        self.assertEqual(pct.iloc[253],1)
        self.assertEqual(regime.iloc[253],'high')
        self.assertEqual(pct.iloc[254],0)
        self.assertEqual(regime.iloc[254],'low')


if __name__ == '__main__':
    unittest.main()
