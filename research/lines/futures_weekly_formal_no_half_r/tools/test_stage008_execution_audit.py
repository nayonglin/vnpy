import importlib
import unittest
import pandas as pd

class UsedMinuteVolumeTests(unittest.TestCase):
    def setUp(self):
        try:
            self.audit = importlib.import_module("stage008_execution_audit").audit_actual_minute_volumes
        except ImportError:
            self.fail("缺少逐实际成交分钟正量接受门；旧执行器仅有OHLC校验")

    def frame(self, volume=100., price=9127.):
        return pd.DataFrame([dict(bar_datetime="2021-05-06 09:00:00", open=price, volume=volume)])

    def trade(self, volume=7., price=9127., trade_id="BACKTESTING.44"):
        return dict(trade_id=trade_id, vt_symbol="eb2105.DCE", execution_datetime="2021-05-06 09:00:00+08:00", price=price, volume=volume)

    def test_zero_volume_eb_exit_rejects_even_with_positive_ohlc(self):
        result=self.audit([self.trade()], {"eb2105.DCE": self.frame(0.)})
        self.assertFalse(result["accepted"])
        self.assertEqual(result["verdict"], "REJECT_EXECUTION_ZERO_VOLUME")
        self.assertEqual(result["zero_or_invalid_volume_count"], 1)

    def test_real_positive_minute_matches_timezone_and_retains_ratio(self):
        result=self.audit([self.trade(2.)], {"eb2105.DCE": self.frame(6.)})
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["max_participation_ratio"], 1/3)

    def test_nan_minute_volume_cannot_pass(self):
        result=self.audit([self.trade()], {"eb2105.DCE": self.frame(float("nan"))})
        self.assertFalse(result["accepted"])

    def test_missing_or_duplicate_minute_is_not_first_row_fallback(self):
        for frame in [self.frame().iloc[:0], pd.concat([self.frame(),self.frame()],ignore_index=True)]:
            with self.subTest(rows=len(frame)):
                result=self.audit([self.trade()], {"eb2105.DCE": frame})
                self.assertFalse(result["accepted"])
                self.assertEqual(result["anchor_mismatch_count"], 1)

    def test_price_mismatch_rejects_without_repricing(self):
        result=self.audit([self.trade(price=9070.)], {"eb2105.DCE": self.frame()})
        self.assertFalse(result["accepted"])
        self.assertEqual(result["anchor_mismatch_count"], 1)

    def test_same_minute_orders_are_aggregated_for_capacity_diagnostic(self):
        result=self.audit([self.trade(2.,trade_id="1"),self.trade(2.,trade_id="2")], {"eb2105.DCE":self.frame(6.)})
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["max_aggregate_participation_ratio"], 2/3)
        self.assertEqual(result["minute_groups"], 1)

    def test_positive_next_minute_cannot_replace_canonical_first_minute(self):
        trade=self.trade(2.)
        trade.update(execution_datetime="2021-05-06 09:01:00+08:00",trading_date="2021-05-06")
        frame=self.frame(100.)
        frame.loc[0,"bar_datetime"]="2021-05-06 09:01:00"
        result=self.audit([trade], {"eb2105.DCE":frame},calendar=["2021-04-30","2021-05-06"])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["anchor_mismatch_count"],1)

    def test_exact_canonical_first_minute_passes(self):
        trade=self.trade(2.);trade["trading_date"]="2021-05-06"
        result=self.audit([trade], {"eb2105.DCE":self.frame(100.)},calendar=["2021-04-30","2021-05-06"])
        self.assertTrue(result["accepted"])

    def test_empty_ledger_has_no_fabricated_volume(self):
        result=self.audit([], {})
        self.assertTrue(result["accepted"])
        self.assertIsNone(result["minimum_positive_minute_volume"])

if __name__ == "__main__":unittest.main()
