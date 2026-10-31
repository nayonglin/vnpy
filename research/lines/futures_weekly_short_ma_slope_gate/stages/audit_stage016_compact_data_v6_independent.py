"""Independent compact-state/data/V6 boundaries. Temporary fixtures only."""
import base64,copy,hashlib,json,os,sqlite3,sys,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path[:0]=[str(R/'examples/portfolio_backtesting'),str(R/'tests')]
import qmt_roll_weekly19_runtime as runtime
import qmt_roll_weekly19_data as reader
import qmt_roll_weekly19_data_update as updater
import qmt_roll_weekly19_broker_evidence as provider
import qmt_roll_weekly19_pipeline_state as storemod
import qmt_roll_weekly19_funding as funding
import qmt_roll_official_live_execution_ledger as ledger
import test_weekly19_data as df
import test_weekly19_data_update as uf
import test_weekly19_broker_evidence as pf
import pandas as pd

class CompactIndependent(unittest.TestCase):
 def packed(self,raw):
  return {'@':'zjson','encoding':'zlib-base64-v1','raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'value':base64.b64encode(zlib.compress(raw)).decode()}
 def test_compressed_tagged_json_roundtrips_without_executing_objects(self):
  value={'one':list(range(5000)),'two':{'f':float('nan')}};encoded=runtime._encode(value);packed=runtime._pack_section(encoded)
  self.assertEqual(packed['@'],'zjson');self.assertEqual(runtime._unpack_section(packed),encoded)
  decoded=runtime._decode(packed);self.assertEqual(decoded['one'],list(range(5000)));self.assertTrue(__import__('math').isnan(decoded['two']['f']))
 def test_decompression_output_limit_rejects_bomb_before_full_allocation(self):
  body=self.packed(b'x'*2_000_000);body['raw_bytes']=1;body['raw_sha256']=hashlib.sha256(b'x').hexdigest()
  with self.assertRaises(runtime.RuntimeContractError):runtime._unpack_section(body)
 def test_concatenated_truncated_and_wrong_digest_zlib_are_rejected(self):
  original=self.packed(b'{"ok":1}')
  cases=[dict(original,raw_sha256='0'*64),dict(original,raw_bytes=True),dict(original,raw_bytes=128*1024*1024+1),dict(original,value='not base64') ]
  packed=base64.b64decode(original['value']);cases.extend([dict(original,value=base64.b64encode(packed+zlib.compress(b'{}')).decode()),dict(original,value=base64.b64encode(packed[:-1]).decode())])
  for body in cases:
   with self.subTest(body={k:v for k,v in body.items()if k!='value'}),self.assertRaises(runtime.RuntimeContractError):runtime._unpack_section(body)
 def test_shared_weeks_reference_requires_exact_bound_context(self):
  weeks={'week-1':['2026-10-26','2026-10-30']};shared=dict(weeks=weeks,weeks_sha256=runtime._hash(runtime._encode(weeks)));tag=runtime._encode(weeks,shared=shared)
  self.assertEqual(tag['@'],'sharedref');self.assertIs(runtime._decode(tag,shared=shared),weeks)
  with self.assertRaises(runtime.RuntimeContractError):runtime._decode(tag)
  with self.assertRaises(runtime.RuntimeContractError):runtime._decode(dict(tag,sha256='0'*64),shared=shared)
 def test_unknown_object_class_and_shared_name_are_not_restored(self):
  with self.assertRaises(runtime.RuntimeContractError):runtime._decode({'@':'object','class':'eval','value':{'@':'dict','value':[]}})
  with self.assertRaises(runtime.RuntimeContractError):runtime._decode({'@':'sharedref','name':'arbitrary','sha256':'a'*64},shared={'weeks':{},'weeks_sha256':'a'*64})
 def test_pipeline_cap_is_checked_before_temp_write_or_replace(self):
  self.assertEqual(storemod.MAX_STATE_BYTES,64_000_000)
  with tempfile.TemporaryDirectory(dir='/private/tmp')as t:
   parent=Path(t).resolve();parent.chmod(0o700);path=parent/'bundle.json';s=storemod.PipelineStateStore(path,pf.ACCOUNT,pf.RELEASE)
   state=dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=pf.ACCOUNT,material_release_id=pf.RELEASE,runtime_mode='preview',funding=funding.initial_state(pf.ACCOUNT,pf.RELEASE,'2026-10-30'),runtime=None,decision=None,decision_state=None)
   s.initialize(state);before=path.read_bytes()
   def grow(value):value['diagnostic']='x'*5000;return value
   with patch.object(storemod,'MAX_STATE_BYTES',len(before)+100):
    with self.assertRaisesRegex(storemod.PipelineStateError,'oversized'):s.transact(grow)
   self.assertEqual(path.read_bytes(),before);self.assertFalse(list(parent.glob('*.tmp')))

class ReaderIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=df.DataTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_close_oi_zero_is_observed_and_not_replaced_by_open_oi(self):
  path=self.fx.root/'physical_epoch_daily.csv';frame=pd.read_csv(path);frame['close_oi']=0.;frame['open_oi']=999999.;frame.to_csv(path,index=False)
  with sqlite3.connect(self.fx.root/'daily.sqlite')as db:db.execute('update dbbardata set open_interest=0')
  result=self.fx.load();self.assertTrue(all(b.open_interest==0 for batch in result['bars_by_day'].values()for b in batch.values()));self.assertFalse(result['receipt']['production_qualified'])
 def test_sql_close_oi_disagreement_is_not_source_qualified_by_boolean(self):
  with sqlite3.connect(self.fx.root/'daily.sqlite')as db:db.execute("update dbbardata set open_interest=999999 where symbol='rb2612'")
  self.fx.receipt['production_qualified']=True;self.fx.save_receipt()
  with self.assertRaisesRegex(reader.DataInputError,'value_mismatch'):self.fx.load()
 def test_nonfinite_or_zero_volume_never_creates_dto(self):
  path=self.fx.root/'physical_epoch_daily.csv';original=pd.read_csv(path)
  for value in [0.,float('nan'),float('inf')]:
   frame=original.copy();frame.loc[0,'volume']=value;frame.to_csv(path,index=False)
   with self.subTest(value=value),self.assertRaises(reader.DataInputError):self.fx.load()
 def test_future_physical_and_sql_prices_do_not_enter_completed_day_dtos(self):
  path=self.fx.root/'physical_epoch_daily.csv';frame=pd.read_csv(path);future=frame.iloc[:1].copy();future['date']='2026-11-02';future[['open','high','low','close']]=999999.
  pd.concat([frame,future],ignore_index=True).to_csv(path,index=False);row=future.iloc[0];code,exchange=row.vt_symbol.split('.')
  with sqlite3.connect(self.fx.root/'daily.sqlite')as db:db.execute("insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price)values(?,?,?,?,?,?,?,?,?,?,?)",(code,exchange,'2026-11-02 00:00:00','d',1000,1,2000,999999,999999,999999,999999))
  result=self.fx.load();self.assertEqual(max(result['bars_by_day']),'2026-10-30');self.assertEqual(max(result['physical_epoch_daily'].date),'2026-10-30')

class UpdateIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=uf.UpdateTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_raw_close_oi_is_used_and_original_overlapping_rows_stay_immutable(self):
  old=self.fx.backend.fetch_contracts;before=self.fx.hashes()
  def source(*a,**kw):
   result=old(*a,**kw)
   for payload in result.values():payload['daily']['close_oi']=[765432.,4321.];payload['daily']['open_oi']=999999.
   return result
  self.fx.backend.fetch_contracts=source;out=self.fx.run_update();root=Path(out['asset_root'])
  self.assertEqual(before,self.fx.hashes())
  with sqlite3.connect(root/'daily.sqlite')as db:
   self.assertEqual(db.execute("select open_interest from dbbardata where symbol='rb2612'and substr(datetime,1,10)='2026-11-02'").fetchone()[0],4321.)
   self.assertEqual(db.execute("select open_interest from dbbardata where symbol='rb2612'and substr(datetime,1,10)='2026-10-30'").fetchone()[0],2000.)
  self.assertTrue(json.loads((root/'receipt.json').read_text())['observed_overlap_not_overwritten'])
 def test_zero_held_bar_failure_cannot_advance_existing_latest(self):
  self.fx.run_update();latest=self.fx.generations/'latest.json';before=latest.read_bytes();old=self.fx.backend.fetch_contracts
  def bad(*a,**kw):
   result=old(*a,**kw);result['rb2701.SHFE']['daily'].loc[1,'volume']=0;return result
  self.fx.backend.fetch_contracts=bad
  with self.assertRaises(updater.DataUpdateError):self.fx.run_update()
  self.assertEqual(before,latest.read_bytes())

class V6LedgerIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=pf.BrokerEvidenceTest();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def derive(self,rows):return provider.derive_order_intent_bindings(rows,expected_account_key=pf.ACCOUNT,material_release_id=pf.RELEASE,execution_profile=pf.PROFILE)
 def private(self,rows):
  path=self.fx.root/'independent-ledger.jsonl';path.write_text(''.join(json.dumps(r)+'\n'for r in rows));path.chmod(0o600)
  result=provider.load_execution_order_intent_bindings(path,expected_account_key=pf.ACCOUNT,material_release_id=pf.RELEASE,execution_profile=pf.PROFILE);return path,result
 def test_full_prefix_api_usage_is_part_of_real_quota_identity(self):
  rows=self.fx.batch_ledger();prefix=ledger._with_record_checksum(dict(event_type='api_slot_reserved',target_date=rows[0]['target_date'],api_slot_type='send_order',api_slot_reserved=1,api_slot_reserved_count=1))
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'quota_id_mismatch'):self.derive([prefix,*rows])
 def test_rehashed_caller_named_batch_cannot_replace_real_quota_id(self):
  rows=self.fx.batch_ledger()
  for row in rows:row['api_slot_batch_id']='1'*24;row['record_checksum']=ledger._record_checksum(row)
  with self.assertRaisesRegex(provider.BrokerEvidenceError,'quota_id_mismatch'):self.derive(rows)
 def test_unsent_second_child_has_logical_protection_without_invented_broker_id(self):
  rows=self.fx.batch_ledger(both_native=False);bindings=self.derive(rows)
  self.assertEqual(len(bindings),1);self.assertEqual(len(bindings[0]['expected_children']),2)
  self.assertNotIn('broker_order_id',bindings[0]['expected_children'][1]);self.assertEqual(bindings[0]['broker_order_volume'],1);self.assertEqual(bindings[0]['planned_volume'],2)
 def test_checksum_and_private_source_digest_are_independently_recomputable(self):
  rows=self.fx.batch_ledger();path,bindings=self.private(rows)
  self.assertEqual(bindings._source['raw_sha256'],hashlib.sha256(path.read_bytes()).hexdigest());self.assertEqual(bindings._source['row_count'],3)
  raw=json.loads(path.read_text().splitlines()[0]);expected=hashlib.sha256(json.dumps({k:v for k,v in raw.items()if k!='record_checksum'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
  self.assertEqual(raw['record_checksum'],expected)
 def test_typed_capability_does_not_survive_json_or_nested_mutation(self):
  _,bindings=self.private(self.fx.batch_ledger());provider._require_verified_execution_bindings(bindings,True)
  with self.assertRaises(provider.BrokerEvidenceError):provider._require_verified_execution_bindings(json.loads(json.dumps(bindings)),True)
  bindings[0]['expected_children'][1]['volume']=99
  with self.assertRaises(provider.BrokerEvidenceError):provider._require_verified_execution_bindings(bindings,True)
 def test_private_hardlink_and_foreign_parent_mode_do_not_grant_capability(self):
  path,_=self.private(self.fx.batch_ledger());alias=self.fx.root/'alias';os.link(path,alias)
  with self.assertRaises(provider.BrokerEvidenceError):provider.load_execution_order_intent_bindings(path,expected_account_key=pf.ACCOUNT,material_release_id=pf.RELEASE,execution_profile=pf.PROFILE)
  alias.unlink();self.fx.root.chmod(0o755)
  with self.assertRaises(provider.BrokerEvidenceError):provider.load_execution_order_intent_bindings(path,expected_account_key=pf.ACCOUNT,material_release_id=pf.RELEASE,execution_profile=pf.PROFILE)
 def test_callback_cannot_create_quota_or_native_preinsert_proof(self):
  rows=self.fx.batch_ledger();forged=copy.deepcopy(rows[1]);forged['event_type']='filled_or_part_filled';forged=ledger._with_record_checksum(forged)
  for changed in [[forged],[rows[0],forged],[rows[1],rows[0],rows[2]]]:
   with self.subTest(order=[r['event_type']for r in changed]),self.assertRaises(provider.BrokerEvidenceError):self.derive(changed)
if __name__=='__main__':unittest.main(verbosity=2)
