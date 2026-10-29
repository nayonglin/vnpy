import importlib.util,json,math,sqlite3,tempfile,unittest
from pathlib import Path
import pandas as pd
MODULE=Path(__file__).with_name('stage003_blocked_recap.py')
def subject():
 s=importlib.util.spec_from_file_location('recap',MODULE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class BlockedRecapTests(unittest.TestCase):
 def gate(self,**kw):
  d=dict(vt_symbol='ru2009.SHFE',signal_date='2020-07-10',signal='long_case2',applied_block=True,selected_volume_before=1,selected_volume_after=0,ma5_current=9.,ma5_previous=10.,ma5_delta=-1.,ma10_current=10.,ma10_previous=10.,ma10_delta=0.,source_week_ends=['2020-07-03','2020-07-10'],week_end='2020-07-10',previous_week_end='2020-07-03');d.update(kw);return d
 def test_select_actual_positive_blocks_excludes_zero_and_unapplied(self):
  m=subject();a=m.select_blocked([self.gate(signal='short_case1a')],[self.gate(),self.gate(applied_block=False,selected_volume_before=0)])
  self.assertEqual(len(a),2);self.assertEqual({r['direction'] for r in a},{'long','short'})
  with self.assertRaises(ValueError):m.select_blocked([],[self.gate(selected_volume_before=0)])
 def test_frozen_source_has_35_positive_blocks_20long15short(self):
  m=subject();short=json.loads((m.RUN/'short_ma_slope_decisions.json').read_text());long=json.loads((m.RUN/'long_ma_slope_decisions.json').read_text());a=m.select_blocked(short,long)
  self.assertEqual(len(a),35);self.assertEqual(sum(x['direction']=='long' for x in a),20);self.assertEqual(sum(x['direction']=='short' for x in a),15);self.assertTrue(all(x['selected_volume_before']>0 and x['selected_volume_after']==0 for x in a))
 def test_metadata_has_no_fake_fill_or_pnl(self):
  m=subject();g=self.gate();g['direction']='long';g['event_id']='B001'
  raw=dict(meta=dict(entry_date='2020-07-10',exit_date='2020-07-10',entry_price=100.,exit_price=100.,entry_x=5.,exit_x=5.,entry_marker_price=100.,exit_marker_price=100.,open_trade_id='x',close_trade_id='x',volume=1,realized_pnl=0,r_multiple=0,lot_count=1,holding_calendar_days=0,price_change_pct=0))
  x=m.event_metadata(raw,g,{'status':'no_candidate'},100.)
  self.assertEqual(x['meta']['signal_close'],100.);self.assertEqual(x['meta']['status'],'被拦候选，未成交')
  for k in ['entry_date','exit_date','entry_price','exit_price','open_trade_id','close_trade_id','holding_calendar_days']:self.assertNotIn(k,x['meta'])
  for k in ['volume','realized_pnl','r_multiple','lot_count','price_change_pct']:self.assertIsNone(x['meta'][k])
 def test_baseline_requires_four_key_and_actual_anchor_fill(self):
  m=subject();g=self.gate();g['direction']='long'
  c=pd.DataFrame([dict(date='2020-07-10',contract_vt_symbol='ru2009.SHFE',direction='long',signal='long_case2',entry_context='flat_entry',candidate_status='opened',selected_volume=2)])
  a=pd.DataFrame([dict(signal_date='2020-07-10',vt_symbol='ru2009.SHFE',offset='开',order_id='O1',trading_date='2020-07-13')]);t=pd.DataFrame([dict(vt_symbol='ru2009.SHFE',direction='多',offset='开',order_id='O1',trade_id='T1',trading_date='2020-07-13',volume=2,price=101.)])
  x=m.baseline_match(g,c,a,t,'prior');self.assertEqual(x['status'],'actual_open_matched');self.assertEqual(x['actual_open_volume'],2.)
  g['signal']='long_case1a';self.assertEqual(m.baseline_match(g,c,a,t,'prior')['status'],'no_candidate')
 def test_baseline_planned_open_without_fill_is_not_actual(self):
  m=subject();g=self.gate();g['direction']='long';c=pd.DataFrame([dict(date='2020-07-10',contract_vt_symbol='ru2009.SHFE',direction='long',signal='long_case2',entry_context='flat_entry',candidate_status='opened',selected_volume=2)])
  a=pd.DataFrame(columns=['signal_date','vt_symbol','offset','order_id']);t=pd.DataFrame(columns=['vt_symbol','direction','offset','order_id'])
  self.assertEqual(m.baseline_match(g,c,a,t,'prior')['status'],'candidate_opened_no_actual_fill')
 def test_page_never_suggests_nonexistent_minute_cache(self):
  m=subject();renderer=m.frozen.load_canonical_renderer(m.RENDERER)
  records=json.loads((m.OUTPUT/'records.json').read_text());summary=json.loads((m.OUTPUT/'summary.json').read_text())
  page=m.canonical_html(renderer,records,summary)
  self.assertFalse('切到已补数交易时恢复' in page,'misleading minute cache recovery prompt still present')
  self.assertTrue('本页15分钟无缓存、未下载' in page,'missing explicit frozen page cache disclosure')
 def test_output_cannot_overlap_any_other_version(self):
  m=subject()
  with self.assertRaises(ValueError):m.require_output(m.LINE/'outputs/stage002_C_attempt001')
 def test_exact_epoch_rejects_unknown_signal_day(self):
  m=subject();p=pd.DataFrame([dict(vt_symbol='AP005.CZCE',date='2020-01-01',contract_epoch_id='CZCE.AP.202005')])
  with self.assertRaises(ValueError):m.frozen.exact_epoch_bars(Path('/none'),p,'AP005.CZCE','2010-01-01','2010-01-01')
 def test_hash_mismatch_is_fatal(self):
  m=subject()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a';p.write_text('x')
   with self.assertRaises(ValueError):m.verify_hashes({str(p):'bad'})
if __name__=='__main__':unittest.main()
