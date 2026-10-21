import unittest
import pandas as pd
from stage014_minute_witness import audit_source, execution

class MinuteWitnessTests(unittest.TestCase):
    def setUp(self):
        self.grid = pd.date_range('2020-01-02 09:00', periods=2, freq='min')
        self.frame = pd.DataFrame([
            dict(bar_datetime=self.grid[0],open=100,high=111,low=99,close=105),
            dict(bar_datetime=self.grid[1],open=105,high=105,low=89,close=100)])
        self.event = dict(direction='long',entry_reference_price=100,stop=90,confirm=110,tick=1,
                          daily_open=100,daily_high=111,daily_low=89,daily_close=100)
    def test_complete_same_source_gives_reference_policy_outcome(self):
        x=audit_source(self.frame,self.grid,self.event)
        self.assertEqual(x['status'],'reference_policy_resolved')
        self.assertEqual(x['outcome'],'confirmation_disarms_c2')
        self.assertFalse(x['real_tick_order_proven'])
    def test_missing_minute_never_resolved(self):
        x=audit_source(self.frame.iloc[:1],self.grid,self.event)
        self.assertEqual(x['status'],'incomplete_grid')
        self.assertEqual(x['missing_minutes'],1)
        self.assertNotIn('outcome',x)
    def test_duplicate_rows_not_silently_deduplicated(self):
        x=audit_source(pd.concat([self.frame,self.frame.iloc[:1]]),self.grid,self.event)
        self.assertEqual(x['status'],'duplicate_minute')
    def test_daily_conflict_rejected(self):
        event={**self.event,'daily_high':112}
        self.assertEqual(audit_source(self.frame,self.grid,event)['status'],'daily_ohlc_mismatch')
    def test_open_anchor_conflict_rejected(self):
        event={**self.event,'entry_reference_price':101}
        self.assertEqual(audit_source(self.frame,self.grid,event)['status'],'entry_open_mismatch')
    def test_stop_kernel_uses_gap_and_adverse_tick(self):
        f=self.frame.copy();f.loc[0,['high','low','close']]=[101,99,100];f.loc[1,['open','high','low','close']]=[89,111,89,100]
        x=audit_source(f,self.grid,self.event)
        self.assertEqual(x['status'],'reference_policy_resolved')
        self.assertEqual(x['outcome'],'c2_stop')
        self.assertEqual(x['reference_fill_price'],89)
        self.assertEqual(x['fill_note'],'gap_open')
    def test_incorrect_stop_side_does_not_use_abs(self):
        event={**self.event,'stop':101}
        self.assertEqual(audit_source(self.frame,self.grid,event)['status'],'invalid_signed_risk')
    def test_invalid_ohlc_rejected(self):
        f=self.frame.copy();f.loc[0,'high']=99
        self.assertEqual(audit_source(f,self.grid,self.event)['status'],'invalid_ohlc')
    def test_m_not_added_to_session_scope(self):
        with self.assertRaisesRegex(ValueError,'unsupported_session'):
            execution.session_minutes('m2209.DCE','2022-06-01',['2022-05-31','2022-06-01'])

if __name__=='__main__':unittest.main()

class InventoryKeyTests(unittest.TestCase):
    def test_stage011_uses_epoch_and_eval_date(self):
        from stage014_minute_witness import inventory_event_row
        table=pd.DataFrame([dict(epoch='CZCE.CF.202005',eval_date='2019-12-31',event_id='CZCE.CF.202005@2019-12-31',any_target_date_evidence='True')])
        row=inventory_event_row(table,'CZCE.CF.202005','2019-12-31')
        self.assertEqual(row['event_id'],'CZCE.CF.202005@2019-12-31')
