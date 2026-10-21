"""One finite date-reader regression; no account or market data is loaded."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, '/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
import pandas as pd
import stage106_independent_off_account_review as reader


class DateReaderTests(unittest.TestCase):
    def test_raw_usage_day_reader_preserves_both_joins_and_rejects_unsafe_days(self):
        # Real first105 signal type/value. The second row is a tiny roll-close
        # identity fixture, not an additional market-data or financial claim.
        usage=pd.DataFrame(dict(trade_id=['BACKTESTING.1','fixture.roll.close'],
            vt_symbol=['rb2005.SHFE','rb1910.SHFE'],
            signal_date=pd.Series([pd.Timestamp('2020-01-08'), '2020-01-08'],dtype=object),
            execution_datetime=['2020-01-08T21:00:00','2020-01-08T21:00:00'],
            price=[3617.,3500.],volume=[10.,10.]))
        before=usage.copy(deep=True)
        candidates=pd.DataFrame(dict(date=['2020-01-08'],contract_vt_symbol=['rb2005.SHFE'],direction=['long']))
        self.assertEqual(int(candidates.date.eq(usage.signal_date.iloc[0]).sum()),0)
        trades=pd.DataFrame(dict(trade_id=['BACKTESTING.1']));clock=pd.DataFrame(dict(trade_id=['BACKTESTING.1']))
        hashes={'example.csv':'fixture'};identity={'actual_rows':1}
        result=reader.adapt_exports((trades,usage,clock,hashes,identity),pd)
        normalized=result[1]
        self.assertEqual(int(candidates.date.eq(normalized.signal_date.iloc[0]).sum()),1)
        self.assertEqual(len(normalized.loc[normalized.vt_symbol.eq('rb1910.SHFE') & normalized.signal_date.eq('2020-01-08')]),1)
        self.assertIsNot(normalized,usage)
        pd.testing.assert_frame_equal(usage,before)
        pd.testing.assert_frame_equal(normalized.drop(columns='signal_date'),usage.drop(columns='signal_date'))
        for i in (0,2,3,4):self.assertIs(result[i],(trades,usage,clock,hashes,identity)[i])
        for bad in (pd.Timestamp('2020-01-08T00:00:01'),pd.Timestamp('2020-01-08',tz='Asia/Shanghai'),
                    '2020-1-08','2020-01-08T00:00:00','2020-02-30',None,pd.NaT):
            invalid=usage.copy();invalid['signal_date']=pd.Series([bad,bad],dtype=object)
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):reader.adapt_exports((trades,invalid,clock,hashes,identity),pd)


if __name__=='__main__':unittest.main()
