import importlib.util,unittest
import pandas as pd

class Reserve100ContractTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage013_contract'),'Stage013 contract missing')
  import stage013_contract as m
  return m
 def test_scope_is_4_fresh19_proven23_C_and_250k_total(self):
  m=self.subject();self.assertEqual((len(m.STARTS),len(m.FRESH_STARTS),len(m.REUSE_STARTS)),(23,4,19));self.assertEqual(set(m.FRESH_STARTS)|set(m.REUSE_STARTS),set(m.STARTS));self.assertEqual(m.RESERVE_CAPITAL,100000.);self.assertEqual(m.TOTAL_CAPITAL,250000.);self.assertEqual(m.CANARY,'2017-01-01')
 def test_100k_bridge_transfers_cancel_and_overdraw_is_rejected(self):
  m=self.subject();raw=pd.DataFrame(dict(date=['2015-01-05','2015-01-06'],account_equity=[150000.,130000.],net_pnl=[0.,-20000.],slippage=[0.,1.],commission=[0.,0.],trade_count=[0,1]))
  event=dict(date='2015-01-06',event_id=1,transfer_amount=20000.,cumulative_transfer=20000.,reserve_before=100000.,reserve_after=80000.,trading_equity_before=130000.,trading_equity_after=150000.,raw_account_equity=130000.,total_account_equity=230000.,entry_context='flat_entry',phase='before_parent_sizing',signal='long_case1a',direction='long',weekly_stop_valid=True,range_would_block=False)
  d=m.reserve_daily_bridge(raw,[event],'2015-01-01');self.assertEqual(d.total_account_equity.tolist(),[250000.,230000.]);self.assertEqual(d.trading_account_equity.tolist(),[150000.,150000.])
  with self.assertRaises(ValueError):m.reserve_daily_bridge(raw,[dict(event,reserve_before=150000.,reserve_after=130000.,total_account_equity=280000.)],'2015-01-01')
 def test_settings_equivalence_requires_original_risk_and_C_gate(self):
  m=self.subject();old=dict(setting={'risk_ratio_of_total_assets':.018,**m.ORIGINAL_RISK},actual={'risk_ratio_of_total_assets':.018,**m.ORIGINAL_RISK});self.assertTrue(m.settings_equivalent([old],[old],{}, {})['accepted'])
  import copy
  bad=copy.deepcopy(old);bad['actual']['risk_ratio_open_interest_surge']=.018
  with self.assertRaises(ValueError):m.settings_equivalent([bad],[old],{}, {})
 def fixture(self,root):
  m=self.subject();old=m.load(m.LINE/'stages/stage009_freeze.json')
  f=dict(schema='stage013_frozen_reserve100k_23starts_v1',starts=list(m.STARTS),arms=['C'],cutoff=m.CUTOFF,engine_initial_capital=150000.,reserve_initial_capital=100000.,total_initial_capital=250000.,candidate_windows=23,baseline_arm_windows=23,planned_arm_windows=23,planned_financial_replays=4,planned_new_replays=4,planned_proven_reuse=19,fresh_starts=list(m.FRESH_STARTS),reuse_starts=list(m.REUSE_STARTS),canary_start=m.CANARY,max_workers=2,source_head='a'*40,data_identity=old['data_identity'],data_directory=old['data_directory'],source_files_sha256={str(p):m.sha(p) for p in m.required_financial_sources()},baseline_freeze=str(m.LINE/'stages/stage009_freeze.json'),baseline_registry=str(m.LINE/'outputs/stage009_multistart/registry.json'),baseline_delivery_manifest=str(m.LINE/'stages/stage009_delivery_manifest.json'),baseline_reporting_manifest=str(m.LINE/'stages/stage010_delivery_manifest.json'))
  f['source_files_sha256'].update(old['source_files_sha256'])
  for name in m.BASELINE_IDENTITIES:f[name+'_sha256']=m.sha(f[name])
  p=root/'freeze.json';m.atomic_json(p,f);return m,p,f
 def test_freeze_rejects_wrong_cap_source_data_or_4_19_scope(self):
  import tempfile,copy
  from pathlib import Path
  with tempfile.TemporaryDirectory() as td:
   m,p,f=self.fixture(Path(td));self.assertEqual(m.validate_freeze(p)[0],f)
   for key,value in [('reserve_initial_capital',150000),('total_initial_capital',300000),('planned_financial_replays',23),('arms',['A','C']),('source_files_sha256',{}),('fresh_starts',list(m.STARTS)),('source_head','pending')]:
    bad=copy.deepcopy(f);bad[key]=value;m.atomic_json(p,bad)
    with self.subTest(key=key),self.assertRaises(ValueError):m.validate_freeze(p)
   bad=copy.deepcopy(f);bad['data_identity']['receipt_sha256']='b'*64;m.atomic_json(p,bad)
   with self.assertRaises(ValueError):m.validate_freeze(p)
 def test_checkpoint_key_refuses_A(self):
  m=self.subject()
  with self.assertRaises(ValueError):m.checkpoint_key(dict(source_head='a'*40,cutoff=m.CUTOFF),'b'*64,'A','2015-01-01')
 def test_original_risk_tier_must_match_mode_in_actual_sizing_ledger(self):
  m=self.subject();self.assertTrue(hasattr(m,'validate_entry_tiers'),'Stage013 mode/risk audit missing')
  entries=pd.DataFrame(dict(risk_mode=['regular','open_interest_surge','open_interest_decline'],risk_ratio=[.018,.06,.025]))
  self.assertEqual(m.validate_entry_tiers(entries),3)
  entries.loc[1,'risk_ratio']=.018
  with self.assertRaises(ValueError):m.validate_entry_tiers(entries)
 def test_fresh_checkpoint_rejects_each_forged_metadata_field(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import patch
  m=self.subject()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run=root/'run';run.mkdir();f=dict(source_head='a'*40,cutoff=m.CUTOFF);freeze_sha='b'*64;cp=root/'cp.json'
   m.atomic_json(run/'preflight.json',dict(head=f['source_head'],frozen_source_head=f['source_head'],freeze_sha256=freeze_sha))
   metrics=dict(end_equity=150000.);info=dict(metrics=metrics,raw_metrics=metrics)
   row=dict(schema='stage013_checked_reserve_run_v1',method='fresh_engine',reused=False,path=str(run),checkpoint_key=m.checkpoint_key(f,freeze_sha,'C',m.CANARY),files_sha256=m.snapshot_dir(run),freeze_sha256=freeze_sha,source_head=f['source_head'],arm='C',start=m.CANARY,end=m.CUTOFF,**info)
   with patch.object(m,'validate_run',return_value=info):
    m.atomic_json(cp,row);self.assertEqual(m.read_checkpoint(cp,f,freeze_sha,'C',m.CANARY)['method'],'fresh_engine')
    for key,value in [('schema','stage009'),('method','proven_nonbinding_reuse'),('source_head','c'*40),('freeze_sha256','d'*64),('arm','A'),('start','2015-01-01'),('end','2026-10-30')]:
     m.atomic_json(cp,dict(row,**{key:value}))
     with self.subTest(key=key),self.assertRaisesRegex(ValueError,'checkpoint_identity'):m.read_checkpoint(cp,f,freeze_sha,'C',m.CANARY)
if __name__=='__main__':unittest.main()
