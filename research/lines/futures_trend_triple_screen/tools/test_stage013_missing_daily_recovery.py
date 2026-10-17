"""Daily completion, identity and fixed openOI contracts without a provider."""
import unittest
import pandas as pd

try:
    import stage013_missing_daily_recovery as module
except ImportError:
    module = None


class MissingDailyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module, "Stage013 recovery is not implemented")
        self.serial = pd.DataFrame([dict(id=identifier,
            datetime=int(pd.Timestamp(day,tz="Asia/Shanghai").value),
            open=10., high=14., low=9., close=13., volume=9., open_oi=100., close_oi=91.)
            for identifier,day in [(10,"2020-08-11"),(11,"2020-08-12"),(12,"2020-08-13")]])
        self.references = pd.DataFrame([dict(trade_date="2020-08-12",open=10.,high=14.,low=9.,
            close=13.,volume=9.,open_interest=100.)])

    def test_daily_date_uses_utc_nanoseconds_then_shanghai_calendar_date(self):
        stamp = pd.Timestamp("2020-08-11 16:00:00",tz="UTC").value
        self.assertEqual(module.daily_trade_date(stamp), "2020-08-12")

    def test_last_valid_daily_bar_is_not_qualified_without_successor(self):
        reference = pd.concat([self.references,self.references.assign(trade_date="2020-08-13")],ignore_index=True)
        accepted, audit = module.qualify_daily_snapshot("rb2010.SHFE",self.serial,reference)
        self.assertEqual(list(accepted.trade_date), ["2020-08-12"])
        self.assertEqual(int(accepted.iloc[0].source_bar_id),11)
        self.assertEqual(int(accepted.iloc[0].successor_id),12)
        self.assertEqual(audit.set_index("trade_date").loc["2020-08-13","reason"],"no_forward_successor")

    def test_completion_requires_both_greater_id_and_later_time(self):
        reversed_id = self.serial.copy()
        reversed_id.loc[2,"id"] = 9
        same_time = self.serial.copy()
        same_time.loc[2,"datetime"] = same_time.loc[1,"datetime"]
        for serial in (reversed_id,same_time):
            with self.subTest(serial=serial):
                accepted,_ = module.qualify_daily_snapshot("rb2010.SHFE",serial,self.references)
                self.assertTrue(accepted.empty)

    def test_fixed_database_openoi_contract_never_chooses_closeoi_to_rescue(self):
        good,_ = module.qualify_daily_snapshot("rb2010.SHFE",self.serial,self.references)
        self.assertEqual(len(good),1)
        changed = self.serial.copy()
        changed.loc[1,"open_oi"] = 91.
        changed.loc[1,"close_oi"] = 100.
        bad,audit = module.qualify_daily_snapshot("rb2010.SHFE",changed,self.references)
        self.assertTrue(bad.empty)
        self.assertEqual(audit.iloc[0].reason,"database_six_field_mismatch")
        self.assertEqual(audit.iloc[0].mismatch_fields,"open_oi")

    def test_padding_or_illegal_later_bar_cannot_supply_completion(self):
        changed = self.serial.copy()
        changed.loc[2,"high"] = 8.
        padding = changed.iloc[:1].copy()
        padding.loc[:,"id"] = -1
        padding.loc[:,"datetime"] = 0
        accepted,audit = module.qualify_daily_snapshot("rb2010.SHFE",pd.concat([padding,changed]),self.references)
        self.assertTrue(accepted.empty)
        self.assertEqual(audit.iloc[0].reason,"no_forward_successor")


if __name__ == "__main__":
    unittest.main()
