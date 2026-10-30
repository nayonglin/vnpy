import unittest
import pandas as pd
import stage014_data_prepare as m

class DataBoundaryTests(unittest.TestCase):
 def test_forming_next_trading_day_never_admitted(self):
  self.assertTrue(hasattr(m,'split_serial'),'completed day splitter missing')
  stamp=lambda d:pd.Timestamp(d+' 09:00',tz='Asia/Shanghai').value
  d=pd.DataFrame({'datetime':[stamp(x)for x in ['2026-10-29','2026-10-30','2026-11-02']], 'id':[1,2,3],'duration':[86400]*3})
  target,overlap,excluded=m.split_serial(d,'2026-10-30','2026-10-29')
  self.assertEqual(target.date.tolist(),['2026-10-30']);self.assertEqual(overlap.date.tolist(),['2026-10-29']);self.assertEqual(excluded,1)
 def test_duplicate_real_daily_date_is_rejected(self):
  self.assertTrue(hasattr(m,'split_serial'),'completed day splitter missing')
  stamp=pd.Timestamp('2026-10-30 09:00',tz='Asia/Shanghai').value
  with self.assertRaisesRegex(ValueError,'duplicate'):
   m.split_serial(pd.DataFrame({'datetime':[stamp,stamp],'id':[1,2],'duration':[86400]*2}),'2026-10-30','2026-10-29')
 def test_lifecycle_candidate_includes_unheld_existing_active_epoch(self):
  self.assertTrue(hasattr(m,'select_epoch_candidates'),'epoch selector missing')
  def row(symbol,month,listed='',delisted=''):
   return dict(vt_symbol=symbol,product_vt_symbol='rb.SHFE',contract_epoch_id='SHFE.RB.'+month,contract_yyyymm=month,listed_date=listed,delisted_date=delisted,maturity_date=delisted,lifecycle_status='test')
  rows=[row('rb2701.SHFE','202701','2026-01-01','2027-01-15'),row('rb2703.SHFE','202703'),row('rb2610.SHFE','202610','2025-10-01','2026-10-15'),row('rb2711.SHFE','202711','2026-11-01')]
  selected,coverage=m.select_epoch_candidates(rows,['rb.SHFE'],'2026-10-30')
  self.assertEqual(set(selected),{'rb2701.SHFE','rb2703.SHFE'});self.assertEqual(len(coverage),4)
 def test_unknown_past_month_does_not_invent_exact_expiry(self):
  self.assertTrue(hasattr(m,'select_epoch_candidates'),'epoch selector missing')
  row=dict(vt_symbol='rb2501.SHFE',product_vt_symbol='rb.SHFE',contract_epoch_id='SHFE.RB.202501',contract_yyyymm='202501',listed_date='',delisted_date='',maturity_date='',lifecycle_status='unknown')
  selected,coverage=m.select_epoch_candidates([row],['rb.SHFE'],'2026-10-30')
  self.assertEqual(selected,[]);self.assertEqual(coverage[0]['delisted_date'],'');self.assertIn('no_exact_expiry_inferred',coverage[0]['reason'])
if __name__=='__main__':unittest.main()
