"""Private context CAS and readonly update orchestration; no external services."""
from copy import deepcopy
from datetime import datetime
import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
from qmt_roll_weekly19_context_update import advance_market_context,refresh_market_data,resolve_completed_target,ContextUpdateError
from qmt_roll_weekly19_local_backend import private_json
from test_weekly19_runtime import broker as fixture_broker,envelope
import qmt_roll_weekly19_data as data
import qmt_roll_weekly19_data_update as updater
import qmt_roll_weekly19_broker_evidence as evidence
NOW=datetime(2026,11,2,15,30,tzinfo=ZoneInfo('Asia/Shanghai'))
class ContextUpdateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700);self.path=self.root/'context.json'
  self.cfg=dict(schema='weekly19.live-context.v1',execution_profile='weekly19-15w-r150k',account_key='fixture',material_release_id='m-fixture',cold_start_date='2026-10-31',state_path=str(self.root/'state'),target_date='2026-10-30',
   market_data=dict(asset_root=str(self.root/'base'),expected_hashes={},forward_calendar=[]),broker=dict(summary_path='summary',manifest_path='manifest'),market_generation_root=str(self.root/'generations'),cash_sources={})
  self.write(self.cfg)
 def tearDown(self):self.tmp.cleanup()
 def write(self,value):self.path.write_text(json.dumps(value));self.path.chmod(0o600)
 def advance(self,**kw):
  args=dict(expected=self.cfg,new_market=dict(asset_root='new',expected_hashes={'receipt.json':'a'*64},forward_calendar='next'),target_date='2026-11-02');args.update(kw)
  return advance_market_context(self.path,**args)
 def test_advances_market_only_and_preserves_concurrent_cash_config(self):
  changed=deepcopy(self.cfg);changed['cash_sources']={'deposits':[{'native':'fixture'}]};self.write(changed)
  result=self.advance();self.assertEqual(result['cash_sources'],changed['cash_sources']);self.assertEqual(private_json(self.path),result);self.assertEqual(self.path.stat().st_mode&0o777,0o600)
 def test_concurrent_market_or_identity_change_rejected_without_overwrite(self):
  for key in ['market_data','material_release_id']:
   changed=deepcopy(self.cfg);changed[key]='changed';self.write(changed);raw=self.path.read_bytes()
   with self.assertRaises(ContextUpdateError):self.advance()
   self.assertEqual(self.path.read_bytes(),raw)
 def test_symlink_context_lock_and_insecure_parent_rejected(self):
  link=self.root/'link';link.symlink_to(self.path)
  with self.assertRaises(OSError):advance_market_context(link,expected=self.cfg,new_market={},target_date='2026-11-02')
  lock=self.root/'.context.json.lock';lock.symlink_to(self.path)
  with self.assertRaises(OSError):self.advance()
  lock.unlink();self.root.chmod(0o755)
  with self.assertRaisesRegex(ContextUpdateError,'private_parent'):self.advance()
  self.root.chmod(0o700)
 def test_replace_failure_preserves_old_context(self):
  raw=self.path.read_bytes()
  with patch('qmt_roll_weekly19_context_update.os.replace',side_effect=OSError('fixture_disk_failure')):
   with self.assertRaises(OSError):self.advance()
  self.assertEqual(self.path.read_bytes(),raw);self.assertFalse(list(self.root.glob('*.pending')))
 def test_parent_directory_rename_during_replace_never_reports_success(self):
  original_replace=os.replace;old_root=self.root;archived=old_root.with_name(old_root.name+'-moved')
  self.addCleanup(lambda:__import__('shutil').rmtree(archived,ignore_errors=True))
  def moved(*a,**kw):
   old_root.rename(archived);old_root.mkdir(mode=0o700);self.write(self.cfg)
   return original_replace(*a,**kw)
  with patch('qmt_roll_weekly19_context_update.os.replace',side_effect=moved):
   with self.assertRaisesRegex(ContextUpdateError,'parent_identity_changed'):self.advance()
  self.assertEqual(private_json(self.path),self.cfg)
 def test_rollback_rejected(self):
  with self.assertRaisesRegex(ContextUpdateError,'rollback'):self.advance(target_date='2026-10-29')
 def backend(self):
  base=Path(self.cfg['market_data']['asset_root']);base.mkdir();(base/'receipt.json').write_text(json.dumps(dict(date_end='2026-10-30')))
  class Backend:
   preview=False;external_action_started=False
   def require_production(self):pass
   def _broker_policy(self,now):return {'now':now}
  b=Backend();b.config=deepcopy(self.cfg);b.context_file=self.path;return b
 def test_update_derives_real_held_set_and_atomically_advances_context(self):
  b=self.backend();snapshot=fixture_broker(now=NOW);raw=json.loads(snapshot['positions']['raw_payload']);raw['positions']=[dict(vt_symbol='rb2701.SHFE',direction='long',volume=2)];snapshot['positions']=envelope(raw)
  result=dict(target_date='2026-11-02',asset_root=str(self.root/'new-generation'),source_hashes={'receipt.json':'b'*64},source_manifest_sha256='c'*64,market_order_calls=0)
  with patch.object(data,'_hashes',return_value={}),patch.object(evidence,'load_broker_snapshot',return_value=snapshot),patch.object(updater,'update_weekly19_assets',return_value=result)as update:
   out=refresh_market_data(b,'2026-11-02',NOW)
  self.assertEqual(update.call_args.kwargs['held_contracts'],['rb2701.SHFE']);self.assertEqual(out['status'],'generation_advanced');self.assertEqual(private_json(self.path),b.config);self.assertTrue(b.external_action_started);self.assertIsNone(b._market_cache)
 def test_retry_covered_date_does_not_query_broker_or_network(self):
  b=self.backend()
  with patch.object(data,'_hashes',return_value={}),patch.object(evidence,'load_broker_snapshot',side_effect=AssertionError('no broker query')),patch.object(updater,'update_weekly19_assets',side_effect=AssertionError('no market feed')):
   out=refresh_market_data(b,'2026-10-30',NOW)
  self.assertEqual(out['status'],'already_covered');self.assertFalse(b.external_action_started)
 def test_unverified_base_never_contacts_broker_or_market(self):
  b=self.backend()
  with patch.object(data,'_hashes',side_effect=ValueError('bad_base')),patch.object(evidence,'load_broker_snapshot',side_effect=AssertionError('no broker')),patch.object(updater,'update_weekly19_assets',side_effect=AssertionError('no network')):
   with self.assertRaisesRegex(ValueError,'bad_base'):refresh_market_data(b,'2026-11-02',NOW)
 def test_resolver_uses_completed_calendar_including_holiday_friday(self):
  b=self.backend();b.config['market_data']['forward_calendar']=['2026-10-29','2026-11-02','2026-11-03']
  with patch.object(data,'_hashes',return_value={}):
   self.assertEqual(resolve_completed_target(b,NOW),'2026-11-02')
   self.assertEqual(resolve_completed_target(b,NOW.replace(hour=14)),'2026-10-29')
   self.assertEqual(resolve_completed_target(b,NOW.replace(month=10,day=30)),'2026-10-29')
 def test_resolver_requires_future_coverage_and_calendar_file_sha(self):
  b=self.backend();b.config['market_data']['forward_calendar']=['2026-10-30']
  with patch.object(data,'_hashes',return_value={}):
   with self.assertRaisesRegex(ContextUpdateError,'coverage_expired'):resolve_completed_target(b,NOW)
  p=self.root/'forward.csv';p.write_text('date\n2026-10-30\n2026-11-03\n');b.config['market_data']['forward_calendar']=str(p)
  with patch.object(data,'_hashes',return_value={}):
   with self.assertRaisesRegex(ContextUpdateError,'sha_mismatch'):resolve_completed_target(b,NOW)
  b.config['market_data']['expected_hashes']['forward.csv']=hashlib.sha256(p.read_bytes()).hexdigest()
  with patch.object(data,'_hashes',return_value={}):self.assertEqual(resolve_completed_target(b,NOW),'2026-10-30')
if __name__=='__main__':unittest.main()
