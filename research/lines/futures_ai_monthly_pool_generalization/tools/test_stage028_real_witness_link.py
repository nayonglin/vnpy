import unittest
import pandas as pd
from stage028_real_witness_link import select_reference_window


class WindowTests(unittest.TestCase):
    def test_history_ends_at_execution_day_without_future(self):
        calendar=pd.date_range('2020-01-01',periods=50,freq='B')
        days=[str(d.date()) for d in calendar]
        lookup={d:{'trade_date':d,'open':100,'high':101,'low':99,'close':100} for d in days}
        x=select_reference_window(days,days[45],days[44],lookup)
        self.assertEqual(len(x['history']),41)
        self.assertEqual(x['history'][-1]['trade_date'],days[45])
        self.assertEqual(x['next_open_proxy']['trade_date'],days[46])
        self.assertFalse(x['next_open_proxy']['canonical_anchor_verified'])

    def test_missing_calendar_day_is_not_replaced_by_older_or_future(self):
        days=[str(d.date()) for d in pd.date_range('2020-01-01',periods=50,freq='B')]
        lookup={d:{'trade_date':d,'open':100,'high':101,'low':99,'close':100} for d in days}
        del lookup[days[10]]
        with self.assertRaisesRegex(ValueError,'history_missing'):select_reference_window(days,days[45],days[44],lookup)

    def test_signal_must_be_immediately_previous_source_day(self):
        days=[str(d.date()) for d in pd.date_range('2020-01-01',periods=50,freq='B')]
        with self.assertRaisesRegex(ValueError,'signal_execution_clock'):select_reference_window(days,days[45],days[43],{})


if __name__=='__main__':unittest.main()
