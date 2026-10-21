import copy,math,unittest
import numpy as np
import stage044_asof_features as feature


def hist(kind='linear'):
    rows=[]
    for i in range(41):
        close=100+i if kind=='linear' else 100.
        rows.append(dict(open=close,high=close+2,low=close-2,close=close,volume=100.,close_oi=0.))
    return rows


class FeaturesTests(unittest.TestCase):
    def setUp(self):self.assertTrue(callable(getattr(feature,'compute_features',None)),'missing asof feature API')

    def test_exactly_twelve_features_and_literal_MA_ATR_RSI(self):
        out=feature.compute_features(hist())
        self.assertEqual(len(out),12)
        self.assertAlmostEqual(out['ma5_ma20_atr14'],1.875)
        self.assertAlmostEqual(out['ma20_ma40_atr14'],2.5)
        self.assertAlmostEqual(out['atr14_close'],4/140)
        self.assertEqual(out['rsi6_abs_centered'],1.)
        self.assertEqual(out['volume5_volume20'],1.)
        self.assertEqual(out['oi_symmetric_change20'],0.)

    def test_returns_use_exact_20_and_40_intervals(self):
        rows=hist()
        for i,row in enumerate(rows):
            c=100*math.exp(i*.01);row.update(open=c,close=c,high=c+2,low=c-2)
        out=feature.compute_features(rows)
        self.assertAlmostEqual(out['trend_energy20'],math.sqrt(20))
        self.assertAlmostEqual(out['trend_energy40'],math.sqrt(40))
        self.assertAlmostEqual(out['efficiency20'],1.)
        self.assertAlmostEqual(out['efficiency40'],1.)
        self.assertAlmostEqual(out['return_std20'],0.,places=12)

    def test_flat_zero_denominators_and_explicit_flat_RSI(self):
        rows=hist('flat')
        for row in rows:row.update(high=100.,low=100.,volume=0.)
        out=feature.compute_features(rows)
        for k,v in out.items():
            self.assertEqual(v,1. if k=='rsi6_abs_centered' else 0.,k)

    def test_OI_lag20_is_index20_and_not_window_first(self):
        rows=hist();rows[20]['close_oi']=20;rows[21]['close_oi']=200;rows[-1]['close_oi']=60
        self.assertEqual(feature.compute_features(rows)['oi_symmetric_change20'],.5)

    def test_volume_uses_last5_and20(self):
        rows=hist()
        for row in rows[-5:]:row['volume']=200
        self.assertEqual(feature.compute_features(rows)['volume5_volume20'],1.6)

    def test_missing_nan_boolean_or_negative_never_zero_filled(self):
        for field,value in [('close',float('nan')),('close',True),('volume',-1),('close_oi',None),('high',float('inf'))]:
            rows=hist();rows[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):feature.compute_features(rows)
        rows=hist();del rows[0]['close_oi']
        with self.assertRaises(ValueError):feature.compute_features(rows)

    def test_invalid_length_or_geometry_rejected(self):
        rows=hist()
        for bad in (rows[:-1],rows+[rows[-1]]):
            with self.assertRaises(ValueError):feature.compute_features(bad)
        rows[0]['low']=500
        with self.assertRaises(ValueError):feature.compute_features(rows)

    def test_input_immutable(self):
        rows=hist();before=copy.deepcopy(rows);feature.compute_features(rows);self.assertEqual(before,rows)

if __name__=='__main__':unittest.main()
