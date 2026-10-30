import unittest
from copy import deepcopy
from pathlib import Path
import json
from run_stage006 import validate_window,range_enabled_for_arm,normalize_settings,ROOT,FROZEN

class Window2015Tests(unittest.TestCase):
 def receipt(self):return dict(date_start='2014-01-01',financial_start='2020-01-01',date_end='2026-10-29',data_ready=True,data_ready_for_bounded_replay=True,main_missing_2015_onward=0)
 def test_2015_requested_with_prior2020_receipt_scope_is_explicit(self):self.assertEqual(validate_window('2015-01-01','2026-10-29',self.receipt()),('2015-01-01','2026-10-29'))
 def test_incomplete_source_or_changed_window_fails(self):
  for kind in ['late_start','gaps','not_ready','bad_end','wrong_requested']:
   r=self.receipt();start='2015-01-01';end='2026-10-29'
   if kind=='late_start':r['date_start']='2015-01-05'
   if kind=='gaps':r['main_missing_2015_onward']=1
   if kind=='not_ready':r['data_ready_for_bounded_replay']=False
   if kind=='bad_end':end='2026-10-30'
   if kind=='wrong_requested':start='2020-01-01'
   with self.assertRaises(ValueError):validate_window(start,end,r)
 def test_only_C_enables_the_unchanged_range_gate(self):
  self.assertFalse(range_enabled_for_arm('A'));self.assertTrue(range_enabled_for_arm('C'))
  with self.assertRaises(ValueError):range_enabled_for_arm('other')
 def test_actual_trade_start_must_really_be_2015(self):
  r=json.loads((FROZEN/'R_attempt003/actual_strategy_settings.json').read_text())[0]['actual'];c=deepcopy(r);mapping=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/outputs/test_mapping.csv';c['mapping_csv_path']=str(mapping)
  for k,v in list(c.items()):
   if isinstance(v,str):c[k]=v.replace('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/',str(ROOT)+'/')
  self.assertEqual(normalize_settings(c,r,mapping,{}),r)
  c['trade_start_date']='2020-01-01'
  with self.assertRaises(ValueError):normalize_settings(c,r,mapping,{})
if __name__=='__main__':unittest.main()
