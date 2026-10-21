import unittest
import numpy as np
import pandas as pd
from stage040_daily_source_panel import select_representatives, history_status, daily_fields
from stage008_monthly_raw_matrix import frozen_signal_host, signal_fields

class PanelTests(unittest.TestCase):
    def test_representative_ties_and_no_future_switch(self):
        f=pd.DataFrame([
            dict(contract_epoch_id='B',trade_date='2020-01-01',volume=10.,close_oi=5.),
            dict(contract_epoch_id='A',trade_date='2020-01-01',volume=10.,close_oi=5.),
            dict(contract_epoch_id='C',trade_date='2020-01-01',volume=9.,close_oi=100.),
            dict(contract_epoch_id='C',trade_date='2020-01-02',volume=100.,close_oi=100.),
        ])
        r=select_representatives(f)
        self.assertEqual(r['2020-01-01']['contract_epoch_id'],'A')
        self.assertEqual(r['2020-01-02']['contract_epoch_id'],'C')

    def test_invalid_volume_not_selected_unknown_oi_not_filled(self):
        f=pd.DataFrame([dict(contract_epoch_id='A',trade_date='x',volume=0.,close_oi=100.),dict(contract_epoch_id='B',trade_date='x',volume=10.,close_oi=np.nan)])
        self.assertEqual(select_representatives(f)['x']['contract_epoch_id'],'B')

    def test_exact_epoch41_no_splice_and_invalid_geometry(self):
        values=np.tile([100.,101.,99.,100.,100.,100.],(41,1))
        self.assertEqual(history_status(np.arange(41),values,40),'frozen_AM41_input_ready')
        self.assertEqual(history_status(np.arange(41),values,39),'insufficient_calendar_history')
        g=np.arange(41);g[20]=19
        self.assertEqual(history_status(g,values,40),'missing_exact_epoch_calendar_bar')
        values[10,2]=102
        self.assertEqual(history_status(np.arange(41),values,40),'invalid_OHLC_geometry')

    def test_missing_metadata_preserved(self):
        a=np.tile([100.,101.,99.,100.,100.,100.],(41,1));a[0,5]=np.nan
        self.assertEqual(history_status(np.arange(41),a,40),'unknown_or_invalid_volume_oi')

    def test_skipping_unneeded_hardblocks_does_not_change_fresh(self):
        host,_=frozen_signal_host()
        history=pd.DataFrame(dict(open=np.full(41,100.),high=np.full(41,101.),low=np.full(41,99.),close=np.full(41,100.),volume=np.full(41,100.),close_oi=np.full(41,100.)))
        expected=signal_fields(host,history)
        actual=daily_fields(host,history,None)
        self.assertEqual(actual['raw_signal'],expected['raw_signal'])
        self.assertEqual(actual['fresh_after_hardblocks'],expected['fresh_after_hardblocks'])
        self.assertIsNone(actual['hardblock'])
        self.assertEqual(actual['hardblock_status'],'not_evaluated_no_fresh_direction')
        self.assertEqual(actual['ma_long_prev_value'],100.)

if __name__=='__main__':unittest.main()
