import unittest
from copy import deepcopy
from pathlib import Path
import json,tempfile
from stage008_contract import STARTS,validate_start,first_trading_day,validate_freeze,metric_close,checkpoint_key,sha,make_checkpoint,read_checkpoint,validate_run
from run_stage008 import normalize_settings,FROZEN,ROOT
class MultiStartTests(unittest.TestCase):
 def fake_run(self,root):
  import pandas as pd
  start='2015-01-01';mapping=root/'mapping.csv';pd.DataFrame({'date':['2015-01-05','2026-10-29']}).to_csv(mapping,index=False)
  source=root/'source.txt';source.write_text('immutable data')
  freeze=dict(source_head='a'*40,cutoff='2026-10-29',data_identity={'data':'b'*64})
  run=root/'run';run.mkdir()
  def write(name,x):(run/name).write_text(json.dumps(x))
  write('preflight.json',dict(freeze_sha256='f'*64,frozen_source_head='a'*40,arm='A',start=start,end=freeze['cutoff'],data_identity=freeze['data_identity'],short_ma_slope_gate_enabled=False,long_ma_slope_gate_enabled=False,long_price_range_gate_enabled=False,short_price_range_gate_enabled=False))
  write('terminal.json',dict(status='completed_pending_independent_review',error=None));write('postflight.json',dict(inputs_unchanged=True))
  write('short_ma_slope_acceptance.json',dict(accepted=True,enabled=False,applied_block_count=0));write('long_price_range_acceptance.json',dict(accepted=True,enabled=False,applied_block_count=0))
  write('actual_strategy_settings.json',[dict(actual=dict(trade_start_date=start,capital_base=150000,enable_add_position=False,mapping_csv_path=str(mapping)))])
  write('input_manifest.json',{str(source):sha(source)})
  pd.DataFrame(dict(date=['2015-01-05','2026-10-29'],account_equity=[150000,140000],trade_count=[0,2],slippage=[0,100])).to_csv(run/'daily.csv',index=False)
  write('metrics.json',dict(end_equity=140000,total_return_pct=(140000/150000-1)*100,total_slippage=100,total_trade_count=2,max_dd_pct=-60,sharpe=-.5,dd40_pass=0,deployable_pass=0))
  return run,freeze
 def test_checkpoint_preserves_negative_economic_result_and_rejects_tampering(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);run,freeze=self.fake_run(root);cp=root/'checkpoint.json';make_checkpoint(run,cp,freeze,'f'*64,'A','2015-01-01')
   self.assertEqual(read_checkpoint(cp,freeze,'f'*64,'A','2015-01-01')['metrics']['end_equity'],140000)
   r=json.loads(cp.read_text());r['metrics']['end_equity']+=1e-8;cp.write_text(json.dumps(r));self.assertEqual(read_checkpoint(cp,freeze,'f'*64,'A','2015-01-01')['arm'],'A')
   r['metrics']['end_equity']+=1;cp.write_text(json.dumps(r))
   with self.assertRaises(ValueError):read_checkpoint(cp,freeze,'f'*64,'A','2015-01-01')
   make_checkpoint(run,cp,freeze,'f'*64,'A','2015-01-01');(run/'daily.csv').write_text((run/'daily.csv').read_text()+'\n')
   with self.assertRaises(ValueError):read_checkpoint(cp,freeze,'f'*64,'A','2015-01-01')
 def test_new_run_freeze_identity_and_exact_reuse_path(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);run,freeze=self.fake_run(root);cp=root/'cp.json';pre=json.loads((run/'preflight.json').read_text())
   for field,value in [('freeze_sha256','e'*64),('frozen_source_head','b'*40)]:
    bad=deepcopy(pre);bad[field]=value;(run/'preflight.json').write_text(json.dumps(bad))
    with self.assertRaises(ValueError):make_checkpoint(run,cp,freeze,'f'*64,'A','2015-01-01')
   (run/'preflight.json').write_text(json.dumps(pre));make_checkpoint(run,cp,freeze,'f'*64,'A','2015-01-01')
   with self.assertRaises(ValueError):make_checkpoint(run,cp,freeze,'f'*64,'A','2015-01-01',reused=True)
   del pre['freeze_sha256'];del pre['frozen_source_head'];(run/'preflight.json').write_text(json.dumps(pre));freeze['reuse_runs']={'2015-01-01|A':str(run)};make_checkpoint(run,cp,freeze,'f'*64,'A','2015-01-01',reused=True)
   self.assertTrue(read_checkpoint(cp,freeze,'f'*64,'A','2015-01-01')['reused'])
 def test_wrong_window_or_long_filter_is_not_accepted(self):
  with tempfile.TemporaryDirectory() as d:
   run,freeze=self.fake_run(Path(d));pre=json.loads((run/'preflight.json').read_text());pre['start']='2015-06-01';(run/'preflight.json').write_text(json.dumps(pre))
   with self.assertRaises(ValueError):validate_run(run,freeze,'A','2015-01-01')
   pre['start']='2015-01-01';pre['long_price_range_gate_enabled']=True;(run/'preflight.json').write_text(json.dumps(pre))
   with self.assertRaises(ValueError):validate_run(run,freeze,'A','2015-01-01')

 def test_exact23_January_and_June(self):
  self.assertEqual(len(STARTS),23);self.assertEqual(STARTS[0],'2015-01-01');self.assertEqual(STARTS[-1],'2026-01-01');self.assertEqual(STARTS[1],'2015-06-01');self.assertNotIn('2026-06-01',STARTS)
  self.assertEqual(len(set(STARTS)),23)
 def test_only_frozen_starts_allowed(self):
  for x in ['2015-07-01','2026-06-01','2014-01-01','2017-02-01']:
   with self.assertRaises(ValueError):validate_start(x)
 def test_calendar_moves_forward_only(self):
  self.assertEqual(first_trading_day('2015-01-01',['2014-12-31','2015-01-05','2015-01-06']),'2015-01-05')
  with self.assertRaises(ValueError):first_trading_day('2026-01-01',['2015-01-05'])
 def test_actual_start_is_required_not_hidden_as2015(self):
  r=json.loads((FROZEN/'R_attempt003/actual_strategy_settings.json').read_text())[0]['actual'];c=deepcopy(r);m=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/outputs/test_mapping.csv';c['mapping_csv_path']=str(m);c['trade_start_date']='2018-06-01'
  for k,v in list(c.items()):
   if isinstance(v,str):c[k]=v.replace('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/',str(ROOT)+'/')
  self.assertEqual(normalize_settings(c,r,m,{},'2018-06-01'),r)
  with self.assertRaises(ValueError):normalize_settings(c,r,m,{},'2015-01-01')
 def test_float_roundtrip_tolerance_not_material_drift(self):
  self.assertTrue(metric_close(1234567.89,1234567.8900000001));self.assertFalse(metric_close(1234567.89,1234567.99))
 def test_freeze_has_exact_windows_and_strict_source_hash(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'core.py';source.write_text('fixed core')
   f=dict(source_head='a'*40,cutoff='2026-10-29',starts=list(STARTS),data_identity={k:'f'*64 for k in ['daily_sqlite_sha256','mapping_sha256','physical_epoch_daily_sha256','receipt_sha256']},source_files_sha256={str(source):sha(source)})
   p=root/'freeze.json';p.write_text(json.dumps(f));self.assertEqual(validate_freeze(p)[0],f)
   source.write_text('fixed core ')
   with self.assertRaises(ValueError):validate_freeze(p)
   source.write_text('fixed core');f['starts']=list(STARTS)+[STARTS[-1]];p.write_text(json.dumps(f))
   with self.assertRaises(ValueError):validate_freeze(p)
 def test_checkpoint_key_binds_all_axes(self):
  f=dict(source_head='a'*40,cutoff='2026-10-29');base=checkpoint_key(f,'f'*64,'A','2015-01-01')
  for x in [checkpoint_key(f,'e'*64,'A','2015-01-01'),checkpoint_key(f,'f'*64,'C','2015-01-01'),checkpoint_key(f,'f'*64,'A','2015-06-01')]:self.assertNotEqual(base,x)
if __name__=='__main__':unittest.main()
