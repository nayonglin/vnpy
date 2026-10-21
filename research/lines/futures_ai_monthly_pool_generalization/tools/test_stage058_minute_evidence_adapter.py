import copy,hashlib,json,pickle,tempfile,unittest
from pathlib import Path
import pandas as pd
from stage058_minute_evidence_adapter import MinuteEvidenceIndex,validate_review_gate

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

class AdapterTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def fixture(self,variant=False,source='a'):
  epoch='SHFE.AU.202112';day='2021-08-03'
  data=[dict(bar_datetime='2021-08-02T21:00:00',open=100.,high=101.,low=89.,close=95.),dict(bar_datetime='2021-08-02T21:01:00',open=95.,high=111.,low=94.,close=100.)]
  if variant:data=[dict(bar_datetime='2021-08-02T21:00:00',open=100.,high=111.,low=99.,close=105.),dict(bar_datetime='2021-08-02T21:01:00',open=105.,high=106.,low=89.,close=100.)]
  digest=hashlib.sha256(canonical(data)).hexdigest();path=self.folder/(source+digest+'.csv');pd.DataFrame(data).to_csv(path,index=False)
  binding=dict(contract_epoch_id=epoch,source_trade_date=day,source_id=source,component='component-'+source,identity_basis='synthetic-reference-only',source_path='synthetic-parent-'+source,
               source_payload_sha256='parent-digest',expected_grid_sha256=hashlib.sha256('\n'.join(r['bar_datetime'] for r in data).encode()).hexdigest(),kernel055_sha256='synthetic-kernel',expected_minutes=2,
               source_daily_OHLC=dict(open=100.,high=111.,low=89.,close=100.),entry_open=100.,physical_session_verified=False,broker_symbol_qualified=False)
  item=dict(requirement_id=hashlib.sha256((epoch+'|'+day).encode()).hexdigest()[:20],state_id='state',data_path=str(path),data_csv_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),canonical_input_sha256=digest,rows=2,source_ids=[source],bindings=[binding],physical_session_verified=False,reference_policy_grid_only=True,usable_for_trading=False)
  bar=dict(open=100.,high=111.,low=89.,close=100.,volume=100.)
  base=dict(bar=bar,history=[dict(bar) for _ in range(41)],history_dates=['declared-history']*41,rsi_value=42.,ma_long_prev_value=99.,
            economics=dict(multiplier=1000.,tick=.02,historical_validated=False),c2_guard_tick=.02,extra_slippage_price=0.,
            anchor=dict(price=100.,execution_datetime=day+'T00:00:00',evidence_id='daily-open-assumption',logical_bar_label_not_physical=True),minute_paths=None,minute_evidence_id=None)
  return item,base,epoch,day
 def index(self,items):
  path=self.folder/'manifest.json';path.write_text(json.dumps(items));return MinuteEvidenceIndex(path)
 def test_clone_only_minute_fields_and_receipt_preserves_logical_anchor(self):
  item,base,epoch,day=self.fixture();before=pickle.dumps(base,protocol=5);r=self.index([item]).attach(base,epoch,day)
  self.assertEqual(before,pickle.dumps(base,protocol=5))
  self.assertEqual(r['anchor'],base['anchor']);self.assertEqual(r['anchor']['execution_datetime'],day+'T00:00:00')
  allowed={'minute_paths','minute_evidence_id','minute_input_receipt'}
  self.assertEqual({k:v for k,v in r.items() if k not in allowed},{k:v for k,v in base.items() if k not in allowed})
  self.assertEqual(len(r['minute_paths']),1);self.assertFalse(r['minute_input_receipt']['physical_session_verified'])
 def test_distinct_paths_all_retained_identical_hash_dedup_keeps_sources(self):
  a,base,epoch,day=self.fixture(source='a');b,_,_,_=self.fixture(source='b');c,_,_,_=self.fixture(True,source='c')
  r=self.index([a,b,c]).attach(base,epoch,day)
  self.assertEqual(len(r['minute_paths']),2)
  self.assertEqual(set(r['minute_input_receipt']['source_ids']),{'a','b','c'})
 def test_exact_epoch_day_only_no_representative_fallback(self):
  item,base,epoch,day=self.fixture();index=self.index([item])
  self.assertIs(index.attach(base,'SHFE.AU.202212',day),base)
  self.assertIs(index.attach(base,epoch,'2021-08-04'),base)
 def test_bad_daily_match_or_parent_receipt_rejected(self):
  item,base,epoch,day=self.fixture();index=self.index([item]);changed=copy.deepcopy(base);changed['bar']['high']=112
  with self.assertRaises(ValueError):index.attach(changed,epoch,day)
  item['physical_session_verified']=True
  with self.assertRaises(ValueError):self.index([item])
 def test_tampered_snapshot_fails_before_any_attachment(self):
  item,base,epoch,day=self.fixture();Path(item['data_path']).write_text('changed')
  with self.assertRaises(ValueError):self.index([item])
 def test_review_gate_required_exact_manifest_and_zero_blockers(self):
  item,base,epoch,day=self.fixture();index=self.index([item]);receipt=self.folder/'review.json'
  data=dict(accepts_stage056_inputs=True,qualified_inputs_manifest_sha256=index.manifest_sha256,unresolved_P0=0,unresolved_P1=0,unresolved_P2=0)
  receipt.write_text(json.dumps(data));validate_review_gate(receipt,index.manifest_sha256)
  data['unresolved_P1']=1;receipt.write_text(json.dumps(data))
  with self.assertRaises(ValueError):validate_review_gate(receipt,index.manifest_sha256)

if __name__=='__main__':unittest.main()
